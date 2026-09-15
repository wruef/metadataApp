"""Verifying deployment positions against the RCA position spreadsheet.

The team spreadsheet is the authority on where anything was put: one row per
position a named site held, with the window it held it for. A deployment sheet
row should agree with whichever position was in force when it was deployed.

Reading the spreadsheet and writing the deployment sheets are deliberately
separate. :func:`checkPositions` answers what disagrees and is safe to run
anywhere; :func:`applyPositions` produces corrected sheets, and that output is a
change to asset-management -- it belongs in a pull request, like a HITL sign-off.
"""

import datetime

import numpy as np
import pandas as pd

POSITION_SHEET = 'RCA History'

## Profilers are mobile assets that hold no fixed depth, so their deployment
## depth is 'N/A' rather than a number: the shallow profilers SF01A, SF01B and
## SF03A, and the deep profilers DP01A, DP01B and DP03A. Everything they dock to
## stays put and keeps a real depth -- the profiler platforms PD0, the platform
## controllers PC0 and the shallow profiler cages SC0.
MOBILE_NODES = ('SF0', 'DP0')

## Deployment sheets carry this until a position is confirmed; once it is, the
## note is no longer true and is cleared.
PRELIMINARY_NOTE = 'The following parameters are preliminary'

## The fields a position governs, as (deployment sheet column, position key).
POSITION_FIELDS = [('lat', 'lat'), ('lon', 'lon'), ('water_depth', 'waterDepth'),
                   ('deployment_depth', 'deploymentDepth')]


def isProfiler(refDes):
    """Is this a mobile asset, with no fixed deployment depth?

    Read from the node field rather than the whole designator, so an instrument
    code carrying one of these prefixes cannot be mistaken for a profiler.
    """
    return refDes[9:14].startswith(MOBILE_NODES)


def loadPositions(xlsxPath, sheet=POSITION_SHEET):
    """Position name -> {start time: the position it held from then}.

    ``sourceRow`` is the spreadsheet row, so a finding can be taken back to the
    line a person would edit.
    """
    frame = pd.read_excel(xlsxPath, sheet_name=sheet)
    positions = {}
    for index, row in frame.iterrows():
        positions.setdefault(row['name'], {})[row['deployed position start'].round('s')] = {
            'positionStartTime': row['deployed position start'],
            'positionEndTime': row['deployed position end'],
            'lat': float(format(row['Latitude'], '.6f')),
            'lon': float(format(row['longitude'], '.6f')),
            ## The spreadsheet is hand-maintained, so a depth can be unusable --
            ## coerced rather than trusted, and reported by the check when it is.
            'waterDepth': pd.to_numeric(row['Seafloor depth (m)'], errors='coerce'),
            'mooringDepth': pd.to_numeric(row['Mooring top depth (m)'], errors='coerce'),
            'sourceRow': index + 2,
        }
    return positions


def loadPositionNameMap(path):
    """Reference designator -> the position name it sits at."""
    frame = pd.read_csv(path)
    return dict(zip(frame['referenceDesignator'], frame['positionName']))


def loadHITLPositions(path):
    """Positions a person has already pinned, where the spreadsheet is ambiguous."""
    frame = pd.read_csv(path)
    hitl = {}
    for _, row in frame.iterrows():
        hitl.setdefault(row['referenceDesignator'], []).append({
            'deployYear': row['deployYear'],
            'deployNum': row['deployNum'],
            'positionStartTime': pd.to_datetime(row['positionStartTime']),
            'positionName': row['positionName'],
        })
    return hitl


def _hitlEntry(refDes, deployYear, deployNum, hitl):
    for entry in hitl.get(refDes, []):
        if str(deployYear) in str(entry['deployYear']) and str(deployNum) in str(entry['deployNum']):
            return entry
    return None


def resolvePosition(refDes, deployDate, deployNum, positions, nameMap, hitl):
    """The position in force for one deployment.

    Returns ``(record, positionName, resolution)``. A reviewer's pinned position
    wins outright. Otherwise a single position starting that year is the answer;
    several mean the spreadsheet cannot say which, and that needs a person rather
    than a guess.
    """
    positionName = nameMap.get(refDes)
    if positionName is None:
        return None, None, 'NO_POSITION_NAME'

    entry = _hitlEntry(refDes, deployDate.year, deployNum, hitl)
    if entry:
        positionName = entry['positionName']
        record = positions.get(positionName, {}).get(entry['positionStartTime'])
        return record, positionName, 'HITL' if record else 'HITL_START_NOT_FOUND'

    held = positions.get(positionName, {})
    sameYear = [start for start in held if start.year == deployDate.year]
    if len(sameYear) > 1:
        return None, positionName, 'AMBIGUOUS'
    if len(sameYear) == 1:
        return held[sameYear[0]], positionName, 'YEAR'

    ## No position began that year, so the one in force is the most recent
    ## position established before the deployment.
    earlier = [start for start in held if start < deployDate]
    if earlier:
        return held[max(earlier)], positionName, 'PRIOR'
    return None, positionName, 'NO_POSITION'


def expectedValues(refDes, record):
    """What the deployment sheet should say, given the position in force."""
    waterDepth = abs(int(format(record['waterDepth'], '.0f')))
    if isProfiler(refDes):
        deploymentDepth = 'N/A'
    elif np.isnan(record['mooringDepth']):
        ## Nothing moored above the seafloor, so the instrument sits at depth.
        deploymentDepth = waterDepth
    else:
        deploymentDepth = abs(int(format(record['mooringDepth'], '.0f')))
    return {'lat': record['lat'], 'lon': record['lon'],
            'waterDepth': waterDepth, 'deploymentDepth': deploymentDepth}


def _differences(row, expected):
    differences = []
    for column, key in POSITION_FIELDS:
        current = row[column]
        want = expected[key]
        if str(current) != str(want) and not (
                isinstance(current, float) and isinstance(want, (int, float))
                and not isinstance(want, str) and float(current) == float(want)):
            differences.append({'field': column, 'current': current, 'expected': want})
    return differences


def checkPositions(deployments, positions, nameMap, hitl):
    """Every deployment's position against the spreadsheet. Reads only."""
    rows = []
    for _, row in deployments.iterrows():
        refDes = row['Reference Designator']
        deployDate = datetime.datetime.strptime(row['startDateTime'], '%Y-%m-%dT%H:%M:%S')
        record, positionName, resolution = resolvePosition(
            refDes, deployDate, row['deploymentNumber'], positions, nameMap, hitl)

        result = {'refDes': refDes, 'deployNum': row['deploymentNumber'],
                  'deployYear': deployDate.year, 'positionName': positionName,
                  'resolution': resolution, 'sourceRow': record['sourceRow'] if record else None}
        if record is not None and np.isnan(record['waterDepth']):
            ## The spreadsheet row itself is unusable, so nothing can be compared.
            rows.append({**result, 'verdict': 'BAD_POSITION_RECORD', 'differences': []})
            continue
        if record is None:
            ## An unresolved position is not a pass -- the sheet may be right or
            ## wrong and nothing here can say which.
            result['verdict'] = 'NEEDS_HITL' if resolution == 'AMBIGUOUS' else 'NO_POSITION'
            result['differences'] = []
        else:
            result['differences'] = _differences(row, expectedValues(refDes, record))
            result['verdict'] = 'MISMATCH' if result['differences'] else 'MATCH'
        rows.append(result)
    return rows


def applyPositions(deployments, positions, nameMap, hitl):
    """Deployment sheets with positions corrected, and a log of what changed.

    This rewrites asset-management's own records, so its output is a proposal.
    It goes to a pull request on the author's own fork -- see
    :func:`publishPositions` -- never straight to the upstream repository.
    """
    corrected = deployments.copy()
    log = []
    for index, row in deployments.iterrows():
        refDes = row['Reference Designator']
        deployDate = datetime.datetime.strptime(row['startDateTime'], '%Y-%m-%dT%H:%M:%S')
        record, positionName, resolution = resolvePosition(
            refDes, deployDate, row['deploymentNumber'], positions, nameMap, hitl)
        if record is not None and np.isnan(record['waterDepth']):
            ## The spreadsheet row itself is unusable, so nothing can be compared.
            rows.append({**result, 'verdict': 'BAD_POSITION_RECORD', 'differences': []})
            continue
        if record is None or np.isnan(record['waterDepth']):
            continue

        expected = expectedValues(refDes, record)
        changed = []
        for column, key in POSITION_FIELDS:
            if str(row[column]) != str(expected[key]):
                corrected.at[index, column] = expected[key]
                changed.append(column)
        if PRELIMINARY_NOTE in str(row['notes']):
            corrected.at[index, 'notes'] = ''
        if changed:
            log.append({'refDes': refDes, 'deployYear': deployDate.year,
                        'deployNum': row['deploymentNumber'], 'positionName': positionName,
                        'sourceRow': record['sourceRow'], 'changed': changed})

    ## Deployment sheets carry blanks, not NaN, and whole numbers, not 1.0
    corrected = corrected.applymap(lambda v: '' if pd.isna(v) else v)
    corrected = corrected.applymap(
        lambda v: int(v) if isinstance(v, float) and v.is_integer() else v)
    return corrected, log


## A node is named SITE-NODE; an instrument adds a port and an instrument code.
NODE_REFDES_LENGTH = 14


def _asCsv(sheet):
    return sheet.to_csv(index=False, na_rep='', float_format='%.6f')


def positionFiles(corrected):
    """Corrected instrument deployment sheets as {path: text}, one per array.

    The checks work from every array concatenated, but asset-management keeps one
    sheet per array, so they are split back apart on the way out. Node rows are
    left out -- they belong to a different repository, and filing them here would
    append them to the wrong sheet.
    """
    refDes = corrected['Reference Designator']
    instruments = corrected[refDes.str.len() > NODE_REFDES_LENGTH]
    return {f'deployment/{array}_Deploy.csv': _asCsv(sheet)
            for array, sheet in instruments.groupby(refDes.str[0:8])}


def nodePositionFile(corrected):
    """Corrected node deployments, which the deployments repository holds."""
    refDes = corrected['Reference Designator']
    nodes = corrected[refDes.str.len() <= NODE_REFDES_LENGTH]
    return {'NODE_deployments.csv': _asCsv(nodes)} if len(nodes) else {}


def publishPositions(corrected, pullRequest, title=None):
    """Propose corrected deployment sheets to the author's fork of asset-management.

    Returns the pull request url, or None when the sheets already agree with the
    spreadsheet. What changed is in the position check's own rows, so no separate
    change log is written here.
    """
    return _propose(pullRequest, positionFiles(corrected), title, 'asset-management')


def publishNodePositions(corrected, pullRequest, title=None):
    """Propose corrected node deployments to the author's fork of the deployments repo."""
    return _propose(pullRequest, nodePositionFile(corrected), title, 'deployments')


def _propose(pullRequest, files, title, upstream):
    if not files:
        return None
    title = title or f'Deployment positions, {datetime.date.today().isoformat()}'
    return pullRequest.open(
        files, title,
        body='Latitude, longitude and depths taken from the RCA position '
             'spreadsheet.\n\n'
             f'Review here, then raise the pull request to the upstream {upstream} '
             'repository by hand.')
