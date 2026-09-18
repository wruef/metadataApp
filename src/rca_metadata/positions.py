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
    return dict(zip(frame['referenceDesignator'], frame['positionName'], strict=True))


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


def _spells(cell, value):
    """Whether a sheet cell names ``value``: 10, 10.0, '10' or a list '10,11'."""
    wanted = str(value).strip().removesuffix('.0')
    return wanted in [part.strip().removesuffix('.0') for part in str(cell).split(',')]


def _hitlEntry(refDes, deployYear, deployNum, hitl):
    """The pinned position for one deployment, or None.

    Matched exactly rather than by substring: deployment 1 is not deployment
    10, 11 or 12, which is what a contains-test made it on every profiler past
    its ninth season.
    """
    for entry in hitl.get(refDes, []):
        if _spells(entry['deployYear'], deployYear) and _spells(entry['deployNum'], deployNum):
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
            result['verdict'] = {'AMBIGUOUS': 'NEEDS_HITL',
                                 'HITL_START_NOT_FOUND': 'HITL_PIN_NOT_FOUND'}.get(resolution, 'NO_POSITION')
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
        ## An unresolved position, or a spreadsheet row whose depth is unusable,
        ## leaves the sheet as it is: nothing here can say what it should read.
        ## The check reports both -- NO_POSITION and BAD_POSITION_RECORD -- so
        ## they are visible rather than silently skipped.
        if record is None or np.isnan(record['waterDepth']):
            continue

        expected = expectedValues(refDes, record)
        ## The same test the check applies, so a value the check calls equal --
        ## 80.0 against 80 -- is not written and logged as a correction here.
        changed = [difference['field'] for difference in _differences(row, expected)]
        for column, key in POSITION_FIELDS:
            if column in changed:
                corrected.at[index, column] = expected[key]
        if PRELIMINARY_NOTE in str(row['notes']):
            corrected.at[index, 'notes'] = ''
        if changed:
            log.append({'refDes': refDes, 'deployYear': deployDate.year,
                        'deployNum': row['deploymentNumber'], 'positionName': positionName,
                        'sourceRow': record['sourceRow'], 'changed': changed})

    ## Deployment sheets carry blanks, not NaN, and whole numbers, not 1.0.
    ## ``DataFrame.map`` rather than ``applymap``: pandas removed applymap in
    ## 3.0, which is what a Python 3.11 install now resolves to, and map has
    ## been the same function under a better name since 2.1.
    corrected = corrected.map(lambda v: '' if pd.isna(v) else v)
    corrected = corrected.map(
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
