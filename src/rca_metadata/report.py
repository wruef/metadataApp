"""The run report: one versioned JSON document per verification run.

Replaces the five loosely-shaped CSV and TXT files the notebooks wrote, which
could not reliably be read back -- the calibration report embedded a python list
literal containing commas in its last column, and the season lists wrote multi-
valued serial numbers unquoted.

Two things the dashboard should not have to work out for itself are settled
here. Every row carries a **severity**, so a queue can be ranked by consequence
rather than by row order. And every row that a reviewer has signed off carries
**cleared**, separately from its severity: a sign-off outranks a failing check,
but the failing check stays visible on the row.
"""

import datetime
import json
import math
import os
import subprocess

import numpy as np
import pandas as pd

SCHEMA_VERSION = 1

## Worst first. A row takes the worst severity of any of its verdicts.
SEVERITIES = ['problem', 'review', 'unchecked', 'ok']

## What a reviewer's sign-off looks like in the 2i-HITL sheets.
CLEARED = 'Clear'

## verdict -> severity, per field. A verdict absent here is 'review', so a new
## one surfaces in the queue rather than disappearing into a pass.
SEVERITY = {
    'sensorBulk': {'verdict': {
        'MATCH': 'ok', 'FORMAT_MATCH': 'review', 'MISMATCH': 'problem',
        'MISSING_FROM_RCA_LIST': 'review', 'MISSING_FROM_SENSOR_BULK': 'problem',
        'NO_BULK_SERIAL': 'unchecked'}},
    'calibrations': {
        'vendorMatch': {
            'COMPARED': 'ok', 'COMPARED_XML': 'ok', 'MISMATCH': 'problem',
            'MISSING_COEFFICIENT': 'problem', 'NO_VENDOR_FILE': 'problem',
            'CONSTANT_MISMATCH': 'review', 'PDF_NOTCOMPARED': 'unchecked',
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


## A recorded calibration difference, in the order compareCalCoefficients
## appends them.
DIFFERENCE_FIELDS = ['file', 'coefficient', 'github', 'expected', 'difference', 'source']


def asDifference(recorded):
    """One calibration difference, named rather than positional."""
    return dict(zip(DIFFERENCE_FIELDS, recorded))


def scoreRows(check, rows):
    """Each row with its severity, and whether a reviewer has cleared it."""
    scored = []
    for row in rows:
        scored.append({**row, 'severity': severityOf(check, row),
                       'cleared': str(row.get('HITLstatus', '')).strip() == CLEARED})
        if 'differences' in row and check == 'calibrations':
            scored[-1]['differences'] = [asDifference(d) for d in row['differences']]
    return scored


def summarise(rows):
    counts = {severity: 0 for severity in SEVERITIES}
    for row in rows:
        counts[row['severity']] += 1
    counts['cleared'] = sum(1 for row in rows if row['cleared'])
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
    return {'commit': commit or 'UNKNOWN', 'dirty': bool(dirty)}


def describeSource(source):
    """What a run read, and the exact state it read it in.

    The ref is what was asked for; the commit is what that resolved to. Only the
    commit makes two runs comparable -- ``master`` today and ``master`` next
    season are different states of the repository.
    """
    if source is None:
        return None
    return {'repo': source.repo, 'ref': source.ref, 'local': source.local,
            'commit': commitOf(source.local) if source.local else None}


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
