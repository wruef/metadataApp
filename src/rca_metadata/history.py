"""Deployment history and season inventories.

Unlike the verification checks, these are published products rather than
findings: the per-instrument-type history is what the OOI-CabledArray
``deployments`` repository holds, and the season lists are what the team works
from around a cruise. They answer "what was where, and when", not "what is wrong".
"""

import csv
import datetime
import os

import pandas as pd

from .calibrations import comparisonRule
from .loading import (
    NO_CALIBRATION,
    NO_VALID_CALIBRATION,
    calFileBits,
    calibrationInForce,
)

HISTORY_COLUMNS = ['sensorType', 'referenceDesignator', 'startTime', 'endTime', 'assetID',
                   'instrumentSN', 'lat', 'lon', 'githubCalibrationFile', 'vendorCalibrationFile']

## The date column is named for what the list is about, so a deployed list and a
## recovered list do not both call it 'date'.
SEASON_COLUMNS = ['referenceDesignator', 'Cruise', 'instrumentType', '{date}', 'assetID',
                  'serialNumber']

## Published alongside the per-type files: which reference designators exist.
REFDES_FILE = 'refDesList.csv'


def sensorTypeName(instrumentTypes):
    """The file-name form of an instrument type.

    An asset can serve as more than one type -- a camera is both CAMDS-B and
    CAMDS-C -- and the published history keeps them together under one name.
    """
    return '_'.join(instrumentTypes).replace('-', '')


def calibrationLinks(source, files):
    """Asset ID -> [(calibration date, a link to the file)].

    ``files`` is (directory, file name) pairs, so this serves both repositories:
    asset-management's csv calibrations and the vendor originals beside them.
    """
    links = {}
    for directory, fileName in files:
        assetID, calDate = calFileBits(fileName)
        if assetID:
            links.setdefault(assetID, []).append(
                (calDate, source.blobUrl(f'{directory}/{fileName}')))
    return links


def comparedFile(urls, assets=None):
    """Of several files for one calibration, the one the comparison reads.

    A vendor calibration can be more than one file. OPTAA ships a ``.cal`` and a
    ``.dev`` for the same date: the ``.cal`` is the **air** calibration and the
    ``.dev`` is the pure-water one that asset-management is built from and that
    the check compares against. Ordered alphabetically the ``.cal`` wins, so the
    published history pointed a reader at the file the check never opens.

    The order comes from the same table the comparison uses, so the history and
    the check name the same file by construction rather than by agreement.
    Where nothing matches -- a format the sensor has no rule for -- the
    alphabetical pick stands, because one link is better than none.
    """
    spec = comparisonRule(os.path.basename(urls[0]), assets)
    for source in (spec['sources'] if spec else []):
        for url in sorted(urls):
            if url.lower().endswith(source['suffix']):
                return url
    return min(urls)


def _inForceAt(links, assetID, deployDate, assets=None):
    """The link to the calibration in force at deployment.

    Several files can carry one calibration, so which of them to name is a
    question only the history asks; which calibration it was is the rule the
    deployments check applies, and both read it from ``calibrationInForce``.
    """
    _, urls, problem = calibrationInForce(links.get(assetID), deployDate)
    if problem:
        return NO_CALIBRATION if problem == NO_CALIBRATION else NO_VALID_CALIBRATION
    return comparedFile(urls, assets)


def deploymentHistory(deployments, assets, githubCals, vendorCals):
    """One row per deployment, with the calibrations that were in force for it."""
    rows = []
    for _, row in deployments.iterrows():
        assetID = row['sensor.uid']
        asset = assets.get(assetID)
        if asset is None:
            print('AssetID not in RCA Asset List: ' + str(assetID))
        deployDate = datetime.datetime.strptime(row['startDateTime'], '%Y-%m-%dT%H:%M:%S')
        rows.append({
            'sensorType': sensorTypeName(asset['instrumentType']) if asset is not None else 'noValidType',
            'referenceDesignator': row['Reference Designator'],
            'startTime': deployDate,
            'endTime': row['stopDateTime'],
            'assetID': assetID,
            'instrumentSN': asset['mfgSN'] if asset is not None else ['noValidSN'],
            'lat': row['lat'],
            'lon': row['lon'],
            'githubCalibrationFile': _inForceAt(githubCals, assetID, deployDate, assets),
            'vendorCalibrationFile': _inForceAt(vendorCals, assetID, deployDate, assets),
        })
    return sorted(rows, key=lambda r: (r['referenceDesignator'], r['startTime']))


def _field(column, value):
    ## instrumentSN is a list and is always quoted; an unrecovered deployment has
    ## no end time and says so by being empty, not by carrying the word 'nan'
    if column == 'instrumentSN':
        return f'"{value}"'
    if not isinstance(value, list) and pd.isna(value):
        return ''
    return str(value)


def referenceDesignators(rows):
    """Every reference designator that has a deployment."""
    return sorted({row['referenceDesignator'] for row in rows})


def historyFiles(rows):
    """The published files as {name: text} -- one csv per sensor type, plus the
    list of reference designators that have deployments.

    Written by hand rather than through pandas so the published format holds:
    instrumentSN is a list and is always quoted, whether or not it contains a
    comma, so a diff against the previous publication shows only real changes.
    """
    files = {}
    for sensorType in sorted({row['sensorType'] for row in rows}):
        lines = [','.join(HISTORY_COLUMNS)]
        lines += [','.join(_field(column, row[column]) for column in HISTORY_COLUMNS)
                  for row in rows if row['sensorType'] == sensorType]
        files[f'{sensorType}_deployments.csv'] = '\n'.join(lines) + '\n'

    files[REFDES_FILE] = '\n'.join(['referenceDesignator'] + referenceDesignators(rows)) + '\n'
    return files


def historyBundle(result):
    """The published history as the dashboard reads it: the finished files.

    The files rather than the rows, deliberately. A reviewer proposing the
    history is committing exactly these bytes, and a dashboard that rebuilt
    them from rows would have to reproduce this module's quoting rules in
    another language -- where the first divergence shows up as a diff against
    the previous publication full of lines that did not really change.

    Kept out of the run report and published beside it. It is half a megabyte
    of csv that every other page would otherwise carry.
    """
    return {
        'runAt': result['runAt'],
        'sources': result['sources'],
        'files': historyFiles(result['history']),
    }


def writeHistory(rows, outDir):
    """The published files, on disk."""
    os.makedirs(outDir, exist_ok=True)
    written = []
    for name, content in historyFiles(rows).items():
        path = os.path.join(outDir, name)
        with open(path, 'w') as handle:
            handle.write(content)
        written.append(path)
    return written


def _seasonRows(deployments, assets, dateColumn):
    rows = []
    for _, row in deployments.iterrows():
        asset = assets.get(row['sensor.uid'])
        rows.append({
            'referenceDesignator': row['Reference Designator'],
            'Cruise': row['CUID_Deploy'],
            'instrumentType': ','.join(asset['instrumentType']) if asset is not None else 'noValidType',
            '{date}': row[dateColumn],
            'assetID': row['sensor.uid'],
            'serialNumber': ','.join(asset['mfgSN']) if asset is not None else 'noValidSN',
        })
    return rows


def currentDeployments(deployments, assets):
    """Everything still in the water -- no recovery date on the sheet."""
    return _seasonRows(deployments[deployments['stopDateTime'].isnull()], assets, 'startDateTime')


def deployedIn(deployments, year, assets):
    """Everything put in the water in one season."""
    deployYear = pd.to_datetime(deployments['startDateTime']).dt.year
    return _seasonRows(deployments[deployYear == year], assets, 'startDateTime')


def recoveredIn(deployments, year, assets):
    """Everything brought back up in one season."""
    recovered = deployments[deployments['stopDateTime'].notnull()]
    recoverYear = pd.to_datetime(recovered['stopDateTime']).dt.year
    return _seasonRows(recovered[recoverYear == year], assets, 'stopDateTime')


def writeSeasonList(rows, path, dateHeader='deployDate'):
    """One season list, as a csv a reader can actually parse.

    An asset can carry several serial numbers and serve as several instrument
    types. Written plain, those commas split the row -- 27 of the 154 rows in the
    2022 list are malformed that way -- so the writer quotes what needs quoting.
    """
    with open(path, 'w', newline='') as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([column.format(date=dateHeader) for column in SEASON_COLUMNS])
        writer.writerows([row[column] for column in SEASON_COLUMNS] for row in rows)
    return path
