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
SEVERITIES = ['problem', 'review', 'unchecked', 'cleared', 'ok']

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

## verdict -> severity, per field. A verdict absent here is 'review', so a new
## one surfaces in the queue rather than disappearing into a pass.
SEVERITY = {
    'sensorBulk': {'verdict': {
        'MATCH': 'ok', 'FORMAT_MATCH': 'review', 'MISMATCH': 'problem',
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
            ## A vendor file is on record in a format this instrument is not
            ## compared against -- a CTD with only a .cal. Unchecked rather than
            ## a problem: nothing disagrees, nothing was read.
            'FORMAT_NOTCOMPARED': 'unchecked',
            'NOTCOMPARED': 'unchecked', 'NAN': 'unchecked'},
        'calRepo_check': {'MATCH': 'ok', 'NOMATCH': 'review'},
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
        'CRUISE_NOT_IN_CRUISE_LIST': 'problem', 'DUPLICATE_ASSET_IN_DEPLOYMENT': 'problem'}},
    'deployments': {
        'verificationStatus': {'VERIFIED': 'ok', 'RAW_SN_POSSIBLE': 'review',
                               'NOT_VERIFIED': 'review'},
        'rawFile_verify': {'MATCH': 'ok', 'MISMATCH': 'problem', 'NO_FILE': 'review',
                           'NO_SN': 'unchecked', 'NAN': 'unchecked'},
        'image_verify': {'MATCH': 'ok', 'MISMATCH': 'problem', 'NAN': 'unchecked'},
        'calFile_verify': {'VALID_FILE': 'ok', 'NO_VALID_FILE': 'problem',
                           'VALID_FILE_CAL_OLDER_THAN_15MONTHS': 'review',
                           'none': 'unchecked', 'NAN': 'unchecked'}},
    'positions': {'verdict': {
        'MATCH': 'ok', 'MISMATCH': 'problem', 'NEEDS_HITL': 'review',
        'NO_POSITION': 'review', 'NO_POSITION_NAME': 'review',
        'BAD_POSITION_RECORD': 'review'}},
}


def severityOf(check, row):
    """The worst severity among a row's verdicts.

    A verdict with no mapping counts as 'review' rather than 'ok', so adding a
    verdict without adding it here puts rows in front of a person instead of
    quietly passing them.
    """
    worst = 'ok'
    for field, mapping in SEVERITY.get(check, {}).items():
        if field not in row:
            continue
        ## A verdict can carry detail after a colon -- 'MISMATCH: raw: 1130: AT...'
        verdict = str(row[field]).split(':')[0].strip()
        severity = mapping.get(verdict, 'review')
        if SEVERITIES.index(severity) < SEVERITIES.index(worst):
            worst = severity
    return worst


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
    if vendor == 'FORMAT_NOTCOMPARED':
        return 'A vendor file is on record, but not in the format this instrument is compared against'
    if vendor == 'PDF_NOTCOMPARED':
        return 'The vendor calibration is a scan, so it has to be read by a person'
    if vendor in ('NOTCOMPARED', 'NAN'):
        return 'No comparison is written for this instrument yet'
    if _verdict(row, 'calRepo_check') == 'NOMATCH':
        return 'No vendor file in calibrationFiles for this calibration'
    if serial in ('NOTFOUND_FILE', 'NOTFOUND_SENSORBULK'):
        return 'No serial number could be found to check against the sensor bulk record'
    return 'Every coefficient matches the vendor calibration'


def _deploymentReason(row):
    if _verdict(row, 'rawFile_verify') == 'MISMATCH':
        return 'The serial number in the raw archive is not the asset on the deployment sheet'
    if _verdict(row, 'image_verify') == 'MISMATCH':
        return 'The asset in the pre-deploy photograph is not the one on the deployment sheet'
    calibration = _verdict(row, 'calFile_verify')
    if calibration == 'NO_VALID_FILE':
        return 'No calibration on file dated before this deployment'
    ## Ahead of the two below, which both describe a settled row: a deployment
    ## can be confirmed by its serial number and still carry a stale
    ## calibration, and the severity takes the worse of the two. A sentence
    ## saying the row is fine above a badge saying it is not helps nobody.
    if calibration == 'VALID_FILE_CAL_OLDER_THAN_15MONTHS':
        return 'The calibration on file is more than fifteen months older than the deployment'
    if _verdict(row, 'rawFile_verify') == 'NO_FILE':
        return 'No raw file was found to check the serial number against'
    if row['cleared']:
        return 'Cleared in 2i-HITL review'
    if str(row.get('HITLstatus', '')).strip() == 'NotClear':
        return 'Flagged in 2i-HITL review'
    status = _verdict(row, 'verificationStatus')
    if status == 'VERIFIED':
        evidence = ('The serial number in the raw archive'
                    if _verdict(row, 'rawFile_verify') == 'MATCH'
                    else 'The pre-deploy photograph')
        ## Confirmed by one thing while another was never looked at. Read off
        ## the finding rather than from the fields, because the finding is the
        ## worst of every verdict on the row and this sentence has to explain
        ## it -- naming two of the four fields by hand left 442 deployments
        ## claiming to be confirmed under a badge reading 'not checked'. The
        ## finding rather than the severity, which a sign-off overwrites.
        if row.get('finding') == 'unchecked':
            return f'{evidence} confirms the asset; not every check on this row could run'
        return f'{evidence} confirms the asset that was deployed'
    if status == 'RAW_SN_POSSIBLE':
        return 'The serial number is recoverable from the raw archive but has not been extracted'
    return 'Nothing independent of the deployment sheet can confirm this instrument'


def _positionReason(row):
    return {
        'MISMATCH': 'The position on the deployment sheet differs from the RCA spreadsheet',
        'NEEDS_HITL': 'More than one spreadsheet row could be this deployment',
        'NO_POSITION': 'The spreadsheet holds no position for this deployment',
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
    return {
        'SENSOR_NOT_IN_BULK': 'The sheet names an asset the sensor bulk record does not have',
        'MOORING_NOT_IN_PLATFORM_BULK': 'The sheet names a mooring the platform record does not have',
        'CRUISE_NOT_IN_CRUISE_LIST': 'The sheet names a cruise the cruise list does not have',
        'DUPLICATE_ASSET_IN_DEPLOYMENT': 'The same asset appears twice in one deployment',
    }.get(_verdict(row, 'verdict'), 'Every entry names something another record knows')


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
DIFFERENCE_FIELDS = ['file', 'coefficient', 'github', 'expected', 'difference', 'source']


def asDifference(recorded):
    """One calibration difference, named rather than positional."""
    return dict(zip(DIFFERENCE_FIELDS, recorded))


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
