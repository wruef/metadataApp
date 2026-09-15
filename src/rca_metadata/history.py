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

from .loading import calFileBits, readDeploymentSheet

HISTORY_COLUMNS = ['sensorType', 'referenceDesignator', 'startTime', 'endTime', 'assetID',
                   'instrumentSN', 'lat', 'lon', 'githubCalibrationFile', 'vendorCalibrationFile']

## The date column is named for what the list is about, so a deployed list and a
## recovered list do not both call it 'date'.
SEASON_COLUMNS = ['referenceDesignator', 'Cruise', 'instrumentType', '{date}', 'assetID',
                  'serialNumber']


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


def _inForceAt(links, assetID, deployDate):
    """The calibration in force at deployment: the most recent one before it."""
    history = links.get(assetID)
    if history is None:
        return 'none'
    earlier = [entry for entry in history if entry[0] < deployDate]
    if not earlier:
        return 'noValidCalFile'
    ## TODO: a vendor calibration can be more than one file -- OPTAAC ships a
    ## .cal and a .dev -- and only one is linked here.
    latest = max(date for date, _ in earlier)
    return min(url for date, url in earlier if date == latest)


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
            'githubCalibrationFile': _inForceAt(githubCals, assetID, deployDate),
            'vendorCalibrationFile': _inForceAt(vendorCals, assetID, deployDate),
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


def writeHistory(rows, outDir):
    """One csv per sensor type, as the deployments repository publishes them.

    Written by hand rather than through pandas so the published format holds:
    instrumentSN is a list and is always quoted, whether or not it contains a
    comma, so a diff against the previous publication shows only real changes.
    """
    os.makedirs(outDir, exist_ok=True)
    written = []
    for sensorType in sorted({row['sensorType'] for row in rows}):
        path = os.path.join(outDir, f'{sensorType}_deployments.csv')
        with open(path, 'w') as handle:
            handle.write(','.join(HISTORY_COLUMNS) + '\n')
            for row in rows:
                if row['sensorType'] != sensorType:
                    continue
                handle.write(','.join(_field(column, row[column])
                                      for column in HISTORY_COLUMNS) + '\n')
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
