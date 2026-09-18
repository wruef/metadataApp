"""The run report: one versioned JSON document per verification run.

Replaces the five loosely-shaped CSV and TXT files the notebooks wrote, which
could not reliably be read back -- the calibration report embedded a python list
literal containing commas in its last column, and the season lists wrote multi-
valued serial numbers unquoted.

Two things the dashboard should not have to work out for itself are settled
here. Every row carries a **severity**, so a queue can be ranked by consequence
rather than by row order; a row a reviewer has signed off takes the severity
'cleared', which is a category of its own and never work waiting on somebody.
And it keeps **finding**, the severity its checks actually produced, because a
sign-off is a judgement about a finding rather than the absence of one -- three
signed-off calibrations turned out to carry real transcription errors, so a
category that hid what was found would be a lie.
"""

import datetime
import json
import math
import os
import platform
import subprocess

import numpy as np
import pandas as pd

SCHEMA_VERSION = 2

## Worst first. A row takes the worst severity of any of its verdicts, unless a
## reviewer has signed it off -- a sign-off is a category of its own.
SEVERITIES = ['problem', 'review', 'unchecked', 'cleared', 'ok', 'excluded']

## The severities that put a row in front of a person. 'cleared' is deliberately
## not among them: a sign-off is a person having already been.
OPEN = ('problem', 'review')

## What a reviewer's sign-off looks like in the 2i-HITL sheets.
CLEARED = 'Clear'

## The category a signed-off row takes, whatever its checks found. The finding
## is not discarded -- it stays on the row as 'finding', and the dashboard shows
## it beside the badge, because three cleared calibrations turned out to carry
## real transcription errors and a category that hid them would be a lie.
CLEARED_SEVERITY = 'cleared'

## Outside what this check can judge: no calibration exists for the instrument
## in asset-management, so there is nothing to compare and nothing was missed.
## It is a category of its own rather than a pass or an omission, and it is
## counted in neither -- 'unchecked' would claim a look that was never owed.
EXCLUDED = 'excluded'

## Something worth noticing that nobody has to act on. Like EXCLUDED it does not
## rank the row -- a deployment confirmed by its raw serial is confirmed whether
## or not its calibration is getting old -- but unlike EXCLUDED it is not
## nothing, so it colours its cell amber and is said in the row's reason.
WARNING = 'warning'

## Verdict severities that describe a row without ranking it. Neither is ever a
## row's own status: they qualify one.
NEUTRAL = (EXCLUDED, WARNING)

## verdict -> severity, per field. A verdict absent here is 'review', so a new
## one surfaces in the queue rather than disappearing into a pass.
SEVERITY = {
    'sensorBulk': {'verdict': {
        ## The same number written two ways -- a prefix one record carries and
        ## the other does not. The instrument is the instrument, so the records
        ## agree about which one it is, which is what this check asks.
        'MATCH': 'ok', 'FORMAT_MATCH': 'ok', 'MISMATCH': 'problem',
        'MISSING_FROM_RCA_LIST': 'review', 'MISSING_FROM_SENSOR_BULK': 'problem',
        'NO_BULK_SERIAL': 'unchecked'}},
    'calibrations': {
        'vendorMatch': {
            ## COMPARED_XML is no longer produced -- DOFSTA is compared against
            ## its .cal only -- but reports published before that rule can still
            ## be opened, and an unmapped verdict would read as 'review'.
            'COMPARED': 'ok', 'COMPARED_XML': 'ok', 'MISMATCH': 'problem',
            'MISSING_COEFFICIENT': 'problem', 'NO_VENDOR_FILE': 'problem',
            'CONSTANT_MISMATCH': 'review', 'PDF_NOTCOMPARED': 'unchecked',
            ## The vendor has a calibration for this asset within days of the
            ## one named here. Matching is on the whole file name, so a date one
            ## digit out matches nothing -- the fix is a file name rather than a
            ## hunt for a calibration nobody ever published.
            'VENDOR_DATE_NEAR_MISS': 'problem',
            ## The near file was read and holds exactly these coefficients, so
            ## the two are one calibration under two dates. Nothing about the
            ## numbers is in doubt; a file name is wrong. That needs a person,
            ## not an alarm.
            'VENDOR_DATE_MISNAMED': 'review',
            ## No vendor measures these -- an ADCP's scale factors, a
            ## hydrophone's gain -- so the record is held to the fixed values
            ## instead, and agreeing with them is a pass like any other.
            'COMPARED_CONSTANTS': 'ok', 'NO_CONSTANTS': 'review',
            ## The file holds only how the instrument was set up for this
            ## deployment -- a transformation matrix, a bin size -- and none of
            ## that is a calibration anyone can check.
            'CONFIGURATION_ONLY': 'unchecked',
            ## A vendor file is on record in a format this instrument is not
            ## compared against -- a CTD with only a .cal. Unchecked rather than
            ## a problem: nothing disagrees, nothing was read.
            'FORMAT_NOTCOMPARED': 'unchecked',
            'NOTCOMPARED': 'unchecked', 'NAN': 'unchecked'},
        ## NOT_EXPECTED: no vendor publishes a file for this instrument, so its
        ## absence says nothing about the record and is counted as nothing.
        'calRepo_check': {'MATCH': 'ok', 'NOMATCH': 'review', 'NOT_EXPECTED': 'excluded'},
        'fileParse': {'SUCCESS_TYPE1': 'ok', 'SUCCESS_TYPE2': 'ok', 'FAIL': 'problem'},
        'serialNumber': {
            'MATCH_SENSORBULK': 'ok', 'MISMATCH_SENSORBULK': 'problem', 'MULTIPLE': 'problem',
            'PARSING_ERROR': 'problem', 'NOTFOUND_FILE': 'unchecked',
            'NOTFOUND_SENSORBULK': 'unchecked'},
        ## Repeated coefficient names only matter when the values disagree.
        'duplicateCoeff': {'NONE': 'ok', 'DUPLICATES_IDENTICAL': 'ok',
                           'DUPLICATES_NOTIDENTICAL': 'problem'}},
    'deploymentSheets': {'verdict': {
        'SENSOR_NOT_IN_BULK': 'problem', 'MOORING_NOT_IN_PLATFORM_BULK': 'problem',
        'NODE_NOT_IN_NODE_BULK': 'problem', 'ELECTRICAL_NOT_IN_ENG_BULK': 'problem',
        ## In a bulk record, just not the one this column calls for.
        'ASSET_IN_WRONG_BULK_RECORD': 'problem',
        'CRUISE_NOT_IN_CRUISE_LIST': 'problem', 'DUPLICATE_ASSET_IN_DEPLOYMENT': 'problem'}},
    'deployments': {
        'verificationStatus': {'VERIFIED': 'ok', 'RAW_SN_POSSIBLE': 'review',
                               'NOT_VERIFIED': 'review'},
        ## NAN on either of these means there was nothing to check, not that a
        ## check was skipped: the instrument class writes no serial into its raw
        ## data, or nobody photographed it. Neither is a gap, and counting them
        ## as 'unchecked' held 459 confirmed deployments back from reading as
        ## confirmed. NO_SN is different -- a raw file exists and the serial has
        ## not been pulled out of it, which extraction would settle.
        ## AMBIGUOUS_SN: the serial was read and is too short to tell this
        ## instrument from another of the same model. Nothing disagrees, so it
        ## is not a mismatch; nothing was established either, so it is not a
        ## match. Unchecked, like a serial nobody has extracted yet.
        'rawFile_verify': {'MATCH': 'ok', 'MISMATCH': 'problem', 'NO_FILE': 'review',
                           'AMBIGUOUS_SN': 'unchecked',
                           'NO_SN': 'unchecked', 'NAN': 'excluded'},
        ## A photograph does not confirm a deployment, so it does not condemn
        ## one either: it shows an instrument, not which instrument went in the
        ## water. A disagreement is worth noticing and worth reconciling, and it
        ## is said on the row, but it does not rank it.
        ## NO_IMAGE_ASSET: a photograph is on record and no asset could be read
        ## from it, so there is nothing to compare -- excluded, like no photograph.
        'image_verify': {'MATCH': 'ok', 'MISMATCH': 'warning', 'NAN': 'excluded',
                         'NO_IMAGE_ASSET': 'excluded'},
        'calFile_verify': {'VALID_FILE': 'ok', 'NO_VALID_FILE': 'problem',
                           ## Worth noticing, not worth holding a row for: a
                           ## deployment the raw archive or a reviewer has
                           ## confirmed is confirmed whether or not the
                           ## calibration on file was getting old.
                           'VALID_FILE_CAL_OLDER_THAN_15MONTHS': 'warning',
                           ## No calibration directory exists for the instrument,
                           ## so nothing could be compared and nothing is owed.
                           'EXCLUDED': 'excluded',
                           ## By the time this is read, 'none' can only mean a
                           ## calibration was required and asset-management
                           ## holds none at all. That is worse than one dated
                           ## after the deployment, which is already a problem,
                           ## so reading it as merely 'unchecked' undersold it.
                           'none': 'problem', 'NAN': 'unchecked'}},
    'positions': {'verdict': {
        'MATCH': 'ok', 'MISMATCH': 'problem', 'NEEDS_HITL': 'review',
        'NO_POSITION': 'review', 'NO_POSITION_NAME': 'review',
        'BAD_POSITION_RECORD': 'review', 'HITL_PIN_NOT_FOUND': 'review'}},
}


def severityOf(check, row):
    """The worst severity among a row's verdicts.

    A verdict with no mapping counts as 'review' rather than 'ok', so adding a
    verdict without adding it here puts rows in front of a person instead of
    quietly passing them.

    An excluded or warning verdict is skipped rather than ranked. Excluded says
    this check has nothing to judge on that field; warning says there is
    something worth noticing that nobody has to act on. Neither passes the row
    nor holds it back. A row whose every verdict is excluded is excluded itself.
    """
    worst = None
    excluded = False
    for field, mapping in SEVERITY.get(check, {}).items():
        if field not in row:
            continue
        ## A verdict can carry detail after a colon -- 'MISMATCH: raw: 1130: AT...'
        verdict = str(row[field]).split(':')[0].strip()
        severity = mapping.get(verdict, 'review')
        if severity in NEUTRAL:
            ## Describes the row without ranking it.
            excluded = excluded or severity == EXCLUDED
            continue
        if worst is None or SEVERITIES.index(severity) < SEVERITIES.index(worst):
            worst = severity
    if worst is not None:
        return worst
    ## No field said anything. Excluded when one declined to, 'ok' when the
    ## check has no verdicts of its own -- which is what it has always meant.
    return EXCLUDED if excluded else 'ok'


def _verdict(row, field):
    """A verdict without the detail some of them carry after a colon."""
    return str(row.get(field, '')).split(':')[0].strip()


def _calibrationReason(row):
    if row.get('fileParse') == 'FAIL':
        return 'The calibration file could not be read'
    vendor = _verdict(row, 'vendorMatch')
    if vendor == 'MISMATCH':
        return ('Coefficients differ from the vendor file, reviewed and cleared'
                if row['cleared'] else
                'Coefficients differ from the vendor file and nobody has reviewed it')
    if vendor == 'MISSING_COEFFICIENT':
        return 'The vendor file does not carry a coefficient this file claims'
    if _verdict(row, 'duplicateCoeff') == 'DUPLICATES_NOTIDENTICAL':
        return 'The same coefficient is named twice with conflicting values'
    serial = _verdict(row, 'serialNumber')
    if serial in ('MISMATCH_SENSORBULK', 'MULTIPLE', 'PARSING_ERROR'):
        return 'The serial number in the file disagrees with the sensor bulk record'
    if vendor == 'CONSTANT_MISMATCH':
        return 'The only differences are with the fixed values in coefficientConstants.csv'
    if vendor == 'NO_VENDOR_FILE':
        return 'No vendor calibration is on record to compare against'
    if vendor == 'VENDOR_DATE_MISNAMED':
        near = str(row.get('vendorMatch', '')).partition(':')[2].strip()
        return (f'The vendor file dated {near}, so the two are one calibration under two '
                'dates and the date in one of the file names is wrong')
    if vendor == 'VENDOR_DATE_NEAR_MISS':
        near = str(row.get('vendorMatch', '')).partition(':')[2].strip()
        return (f'No vendor file under this name. The nearest for this asset is dated {near}, '
                'so it is a different calibration and this one has no original on record')
    if vendor == 'FORMAT_NOTCOMPARED':
        return 'A vendor file is on record, but not in the format this instrument is compared against'
    if vendor == 'PDF_NOTCOMPARED':
        return 'The vendor calibration is a scan, so it has to be read by a person'
    if vendor == 'NO_CONSTANTS':
        return 'No fixed values are written for this instrument to be checked against'
    if vendor == 'CONFIGURATION_ONLY':
        return 'The file holds only deployment configuration, so there is nothing to compare'
    if vendor in ('NOTCOMPARED', 'NAN'):
        return 'No comparison is written for this instrument yet'
    if _verdict(row, 'calRepo_check') == 'NOMATCH':
        return 'No vendor file in calibrationFiles for this calibration'
    if serial in ('NOTFOUND_FILE', 'NOTFOUND_SENSORBULK'):
        return 'No serial number could be found to check against the sensor bulk record'
    ## Last, with the other settled sentence: a comparison that agreed says so
    ## only once everything that could make the row open has had its say.
    if vendor == 'COMPARED_CONSTANTS':
        return 'Every coefficient matches the fixed values for this instrument'
    return 'Every coefficient matches the vendor calibration'


def _deploymentReason(row):
    ## Ahead of everything: a row with nothing to judge is not a row with a
    ## problem, and the sentence has to say which it is.
    if row.get('finding') == EXCLUDED:
        return 'No calibration exists for this instrument, so there is nothing to compare'
    if _verdict(row, 'rawFile_verify') == 'MISMATCH':
        return 'The serial number in the raw archive is not the asset on the deployment sheet'
    calibration = _verdict(row, 'calFile_verify')
    if calibration == 'NO_VALID_FILE':
        return 'No calibration on file dated before this deployment'
    if calibration == 'none':
        return 'This instrument needs a calibration and asset-management holds none for it'
    ## Ahead of the two below, which both describe a settled row: a deployment
    ## can be confirmed by its serial number and still carry a stale
    ## calibration, and the severity takes the worse of the two. A sentence
    ## saying the row is fine above a badge saying it is not helps nobody.
    if _verdict(row, 'rawFile_verify') == 'NO_FILE':
        return 'No raw file was found to check the serial number against'
    if _verdict(row, 'rawFile_verify') == 'AMBIGUOUS_SN':
        return ('The serial in the raw archive is too short to tell this instrument from '
                'another of the same model')
    ## What is worth noticing without unsettling the row. Neither an ageing
    ## calibration nor a photograph of a different instrument changes what the
    ## raw archive or a reviewer established, so both ride along with whatever
    ## settled it rather than replacing the sentence. Not on the two sign-off
    ## reasons: those describe what a person did rather than what a check found,
    ## and they have to stay exactly what they are.
    notes = []
    if calibration == 'VALID_FILE_CAL_OLDER_THAN_15MONTHS':
        notes.append('its calibration is more than fifteen months older than the deployment')
    if _verdict(row, 'image_verify') == 'MISMATCH':
        notes.append('the pre-deploy photograph shows a different asset')
    stale = (' — ' + '; '.join(notes)) if notes else ''
    if row['cleared']:
        return 'Cleared in 2i-HITL review'
    if str(row.get('HITLstatus', '')).strip() == 'NotClear':
        return 'Flagged in 2i-HITL review'
    status = _verdict(row, 'verificationStatus')
    if status == 'VERIFIED':
        ## A sign-off returned above, so the raw archive is the only thing left
        ## that could have confirmed this.
        evidence = 'The serial number in the raw archive'
        ## Confirmed by one thing while another was never looked at. Read off
        ## the finding rather than from the fields, because the finding is the
        ## worst of every verdict on the row and this sentence has to explain
        ## it -- naming two of the four fields by hand left 442 deployments
        ## claiming to be confirmed under a badge reading 'not checked'. The
        ## finding rather than the severity, which a sign-off overwrites.
        if row.get('finding') == 'unchecked':
            return f'{evidence} confirms the asset; not every check on this row could run' + stale
        return f'{evidence} confirms the asset that was deployed' + stale
    if status == 'RAW_SN_POSSIBLE':
        return ('The serial number is recoverable from the raw archive but has not been '
                'extracted' + stale)
    ## The photograph agrees and the row is still not confirmed, which is worth
    ## saying outright -- otherwise the sentence below claims nothing was found
    ## when something was, and a reader goes looking for it.
    if _verdict(row, 'image_verify') == 'MATCH':
        return ('A pre-deploy photograph agrees, but a photograph alone does not confirm a '
                'deployment' + stale)
    return 'Nothing independent of the deployment sheet can confirm this instrument' + stale


def _positionReason(row):
    return {
        'MISMATCH': 'The position on the deployment sheet differs from the RCA spreadsheet',
        'NEEDS_HITL': 'More than one spreadsheet row could be this deployment',
        'NO_POSITION': 'The spreadsheet holds no position for this deployment',
        'HITL_PIN_NOT_FOUND': 'A reviewer pinned this deployment to a spreadsheet row that is no longer there',
        'NO_POSITION_NAME': 'No position name maps to this reference designator',
        'BAD_POSITION_RECORD': 'The spreadsheet row could not be read as a position',
    }.get(_verdict(row, 'verdict'), 'Latitude, longitude and depth match the spreadsheet')


def _sensorBulkReason(row):
    return {
        'MISMATCH': 'The RCA list and the sensor bulk record hold different serial numbers',
        'MISSING_FROM_SENSOR_BULK': 'The asset is in the RCA list but not in the sensor bulk record',
        'MISSING_FROM_RCA_LIST': 'The asset is in the sensor bulk record but not in the RCA list',
        'FORMAT_MATCH': 'The same serial number, written two different ways',
        'NO_BULK_SERIAL': 'The sensor bulk record carries no serial number for this asset',
    }.get(_verdict(row, 'verdict'), 'The serial numbers agree')


def _sheetReason(row):
    verdict = _verdict(row, 'verdict')
    where = str(row.get('verdict', '')).partition(':')[2].strip()
    if verdict == 'ASSET_IN_WRONG_BULK_RECORD':
        return f'The asset is in the bulk records, but under {where} rather than its own'
    if verdict == 'DUPLICATE_ASSET_IN_DEPLOYMENT':
        ## Runs published before the verdict named the other place carry no detail.
        return (f'The same asset was in the water somewhere else at the same time, {where}'
                if where else 'The same asset appears twice in one deployment')
    return {
        'SENSOR_NOT_IN_BULK': 'The sheet names an asset the sensor bulk record does not have',
        'MOORING_NOT_IN_PLATFORM_BULK': 'The sheet names a mooring the platform record does not have',
        'NODE_NOT_IN_NODE_BULK': 'The sheet names a node the node record does not have',
        'ELECTRICAL_NOT_IN_ENG_BULK': 'The sheet names an electrical asset the eng record does not have',
        'CRUISE_NOT_IN_CRUISE_LIST': 'The sheet names a cruise the cruise list does not have',
    }.get(verdict, 'Every entry names something another record knows')


## What a reviewer did, rather than what a check found. These sit beside a
## severity instead of explaining it: a sign-off does not erase the failing
## check, so 'Cleared in 2i-HITL review' belongs on a failing row as readily as
## on a settled one.
REVIEWER_REASONS = ('Cleared in 2i-HITL review', 'Flagged in 2i-HITL review')


## Why a row reads the way it does, in the words someone would use out loud.
## Carried in the report for the same reason the severity is: a queue is worked
## by people, and "MISMATCH: raw: 379: ATAPL-68020-00002" is not a reason.
REASONS = {
    'calibrations': _calibrationReason,
    'deployments': _deploymentReason,
    'positions': _positionReason,
    'sensorBulk': _sensorBulkReason,
    'deploymentSheets': _sheetReason,
}


def reasonOf(check, row):
    """One sentence saying why this row reads the way it does."""
    return REASONS[check](row) if check in REASONS else ''


## A recorded calibration difference, in the order compareCalCoefficients
## appends them.
## 'note' is last, so a difference recorded before it existed still reads --
## zip stops at the shorter of the two and the note simply comes back absent.
DIFFERENCE_FIELDS = ['file', 'coefficient', 'github', 'expected', 'difference', 'source', 'note']


def asDifference(recorded):
    """One calibration difference, named rather than positional."""
    ## Not strict: a difference recorded before the note field existed has six
    ## values, and it still has to read.
    return dict(zip(DIFFERENCE_FIELDS, recorded))  # noqa: B905


def scoreRows(check, rows):
    """Each row with what its checks found, and the category it belongs in.

    The two differ only for a signed-off row: it belongs in 'cleared', and it
    keeps its finding so the disagreement stays on screen beside the sign-off.
    """
    scored = []
    for row in rows:
        finding = severityOf(check, row)
        cleared = str(row.get('HITLstatus', '')).strip() == CLEARED
        scored.append({**row, 'finding': finding, 'cleared': cleared,
                       'severity': CLEARED_SEVERITY if cleared else finding})
        ## After cleared, because a sign-off changes what the row means.
        scored[-1]['reason'] = reasonOf(check, scored[-1])
        if 'differences' in row and check == 'calibrations':
            scored[-1]['differences'] = [asDifference(d) for d in row['differences']]
    return scored


def summarise(rows):
    counts = {severity: 0 for severity in SEVERITIES}
    for row in rows:
        counts[row['severity']] += 1
    ## The same set as the 'cleared' severity -- a signed-off row is in that
    ## category and no other -- named separately because 'cleared' reads as a
    ## count of sign-offs wherever the severities are not in view.
    counts['cleared'] = sum(1 for row in rows if row['cleared'])
    ## What is still waiting on somebody. Counted here rather than in the
    ## dashboard so the rail, the segmented control and the overview queue
    ## cannot drift into disagreeing about how much is left.
    counts['attention'] = sum(counts[severity] for severity in OPEN)
    ## Settled: agreed with the record on its own, or settled by a reviewer.
    counts['verified'] = counts['ok'] + counts['cleared']
    ## Rows this check could judge at all. An excluded row is in no other
    ## number, so a proportion measured against the total would shrink every
    ## time an instrument with no calibration was deployed.
    counts['considered'] = len(rows) - counts[EXCLUDED]
    counts['total'] = len(rows)
    return counts


def commitOf(path):
    """The commit a checkout is at, or None if it cannot be determined."""
    result = subprocess.run(['git', '-C', path, 'rev-parse', 'HEAD'],
                            capture_output=True, text=True)
    return result.stdout.strip() or None


def gitProvenance(path='.'):
    """The commit this repository is at, and whether it has uncommitted changes.

    The parameter files are owned by this repository, so this is the provenance
    record for every number in the report. In a workflow the checkout's sha is
    authoritative and is used directly; asking git is the fallback.

    A commit that cannot be determined says so, rather than coming back empty --
    a report nobody can trace back to its inputs should look wrong, not fine.
    """
    commit = os.environ.get('GITHUB_SHA') or commitOf(path)
    dirty = subprocess.run(['git', '-C', path, 'status', '--porcelain'],
                           capture_output=True, text=True).stdout.strip()
    ## Comparison is exact to the last digit a file publishes, so which pandas
    ## parsed the csv is part of what produced these numbers.
    return {'commit': commit or 'UNKNOWN', 'dirty': bool(dirty),
            'python': platform.python_version(), 'pandas': pd.__version__}


def describeSource(source):
    """What a run read, and the exact state it read it in.

    The ref is what was asked for; the commit is what that resolved to. Only the
    commit makes two runs comparable -- ``master`` today and ``master`` next
    season are different states of the repository.
    """
    if source is None:
        return None
    ## 'UNKNOWN' rather than None, for the same reason gitProvenance does it: a
    ## run nobody can trace back to a state of the repository should look wrong.
    ## A directory copied rather than cloned has no .git to ask, and that read as
    ## a plain absent value -- so two runs were compared while neither recorded
    ## which asset-management they had read.
    ## The clone's path is left out deliberately. It describes the machine the
    ## run happened on rather than the data it read, it means nothing to whoever
    ## opens the published report, and two runs of the same commit from
    ## different directories compared as different sources because of it.
    commit = commitOf(source.local) if source.local else None
    return {'repo': source.repo, 'ref': source.ref, 'commit': commit or 'UNKNOWN'}


def _excludedInstruments(deployments):
    """The instruments whose deployments carry no calibration to compare.

    Read off the rows rather than declared, so the list is what the run actually
    saw. An instrument leaves it by acquiring a calibration directory, not by
    anyone remembering to edit a file.
    """
    if not deployments:
        return []
    return sorted({str(row['refDes']).split('-')[-1] for row in deployments['rows']
                   if not row.get('calibrationRequired') and row.get('refDes')})


def buildReport(result, paramsPath='.'):
    """Turn a run's results into the document the dashboard reads."""
    checks = {}
    for name in ('sensorBulk', 'deploymentSheets', 'deployments', 'positions'):
        if result.get(name) is None:
            continue
        checks[name] = {'rows': scoreRows(name, result[name])}
        checks[name]['summary'] = summarise(checks[name]['rows'])

    calibrations = result.get('calibrations')
    if calibrations:
        rows = scoreRows('calibrations', calibrations['files'])
        checks['calibrations'] = {
            'rows': rows, 'summary': summarise(rows),
            ## Vendor originals on file for which asset-management holds nothing.
            'missingFromGithub': calibrations['missingFromGithub']}

    return {
        'schemaVersion': SCHEMA_VERSION,
        'runAt': result['runAt'],
        'sources': result['sources'],
        'parameters': gitProvenance(paramsPath),
        ## What the run covered, as opposed to what it found.
        'referenceDesignators': result.get('referenceDesignators', []),
        ## The instruments asset-management holds no calibration for at all.
        ## Listed rather than left implicit: a check that quietly covers less
        ## than you think is worse than one that says what it skipped.
        'excludedInstruments': _excludedInstruments(checks.get('deployments')),
        ## The reasons a sign-off picks from -- every note already in the
        ## 2i-HITL sheets, so a reviewer reuses the team's wording.
        'hitlNotes': result.get('hitlNotes', {}),
        'checks': checks,
    }


def _encode(value):
    if isinstance(value, (datetime.datetime, datetime.date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if value is pd.NaT or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)


def _finite(value):
    """Replace values JSON cannot express with null.

    Python writes a non-finite float as the bare token ``NaN``, which is valid
    Python and invalid JSON. Python reads it back without complaint, so a report
    can look fine from this side while every browser refuses to parse it and
    hands the reader 2MB of text instead of a report.

    numpy floats subclass float, so this catches those too -- json serializes
    them directly and never consults ``default``.
    """
    if isinstance(value, dict):
        return {key: _finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def writeReport(report, path):
    """Write the report as strict JSON.

    ``allow_nan=False`` is the guard: if anything non-finite survives, this
    raises rather than writing a file no browser can read.
    """
    with open(path, 'w') as handle:
        json.dump(_finite(report), handle, default=_encode, indent=1, allow_nan=False)
    return path
