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
from .loading import calFileBits, readDeploymentSheet

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
    """The calibration in force at deployment: the most recent one before it."""
    history = links.get(assetID)
    if history is None:
        return 'none'
    earlier = [entry for entry in history if entry[0] < deployDate]
    if not earlier:
        return 'noValidCalFile'
    latest = max(date for date, _ in earlier)
    return comparedFile([url for date, url in earlier if date == latest], assets)


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


def publishHistory(rows, pullRequest, title=None):
    """Propose the published files to the author's fork of the deployments repo.

    Returns the pull request url, or None when nothing changed -- most runs
    between cruises change nothing, and an empty pull request is noise.
    """
    title = title or f'Deployment history, {datetime.date.today().isoformat()}'
    return pullRequest.open(
        historyFiles(rows), title,
        body='Regenerated from the asset-management deployment sheets and the '
             'calibration files in both repositories.\n\n'
             'Review here, then raise the pull request to the upstream '
             'deployments repository by hand.')


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
