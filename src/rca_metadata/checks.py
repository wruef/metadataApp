"""The verification checks.

Each check returns rows, not files. A row carries its own verdict, so the
dashboard displays judgement rather than re-deriving it, and the report contract
is a serialization step rather than a rewrite.
"""

import datetime
import os

import numpy as np
import pandas as pd

from .calibrations import compareCalCoefficients
from .loading import RCA_ASSET_PREFIXES
from .serials import partialMatch

## How many trailing characters make a serial number a format match rather than
## a disagreement -- vendors and OOI disagree about prefixes, not about digits.
SERIAL_TAIL = 3

## Instrument types whose serial number can be read out of a raw file.
VERIFIABLE_BY_RAW_SN = ['CTD', 'SPK', 'NUT', 'PAR', 'FLOR', 'PREST', 'TMPSFA', 'OPTAA', 'ADCP']

## Deep profiler instruments whose serial number is in the engineering file.
VERIFIABLE_BY_RAW_SN_DP = ['ENG000000', 'VEL3DA105', 'FLCDRA103', 'FLNTUA103', 'DOSTAD105',
                           'VEL3DA103', 'FLCDRA102', 'FLNTUA102', 'DOSTAD104',
                           'VEL3DA303', 'FLCDRA302', 'FLNTUA302', 'DOSTAD304']

## The MARUM PI sensor has no raw data in the archive, so it is never a finding.
EXCLUDE_SENSORS = ['CTDPFA110']

## A calibration older than this at deployment is worth a second look.
CAL_AGE_LIMIT = datetime.timedelta(days=450)


def checkSensorBulk(rcaAssets, serialByAsset):
    """Compare serial numbers between the RCA instrument list and OOI's sensor bulk.

    Both records should name the same instrument for the same asset ID. Where
    they disagree about formatting only -- a prefix one carries and the other
    does not -- that is worth knowing but is not the same as naming a different
    instrument.
    """
    rows = []
    for assetID, bulkSerial in serialByAsset.items():
        if str(assetID).startswith(RCA_ASSET_PREFIXES) and assetID not in rcaAssets:
            rows.append({'assetID': assetID, 'rcaSerials': None, 'bulkSerial': bulkSerial,
                         'verdict': 'MISSING_FROM_RCA_LIST'})

    for assetID, values in rcaAssets.items():
        if assetID not in serialByAsset:
            rows.append({'assetID': assetID, 'rcaSerials': values['mfgSN'], 'bulkSerial': None,
                         'verdict': 'MISSING_FROM_SENSOR_BULK'})
            continue

        bulkSerial = str(serialByAsset[assetID]).strip()
        row = {'assetID': assetID, 'rcaSerials': values['mfgSN'], 'bulkSerial': bulkSerial}
        if 'nan' in bulkSerial:
            ## Nothing to compare against -- reported as its own verdict rather
            ## than as a disagreement that was never actually tested.
            row['verdict'] = 'NO_BULK_SERIAL'
        else:
            serials = [str(serial).strip() for serial in values['mfgSN']]
            if any(serial == bulkSerial for serial in serials):
                row['verdict'] = 'MATCH'
            elif any(partialMatch(serial, bulkSerial, SERIAL_TAIL) for serial in serials):
                row['verdict'] = 'FORMAT_MATCH'
            else:
                row['verdict'] = 'MISMATCH'
        rows.append(row)
    return rows


def _loadGithubCal(path):
    """A github calibration csv, and which parse worked.

    Some files carry values the float converter rejects, so a second, looser
    parse is tried before the file is called unreadable.
    """
    try:
        return pd.read_csv(path, converters={'value': np.float64},
                           float_precision='round_trip'), 'SUCCESS_TYPE1'
    except ValueError:
        try:
            return pd.read_csv(path, float_precision='round_trip'), 'SUCCESS_TYPE2'
        except ValueError:
            return None, 'FAIL'


def _serialVerdict(githubCal, stem, serialByAsset):
    """Does the serial inside the file agree with the asset ID in its name?"""
    if 'serial' not in githubCal.columns:
        return 'NOTFOUND_FILE'
    serials = np.unique(githubCal['serial'])
    if len(serials) > 1:
        return 'MULTIPLE'
    assetID = stem.split('__')[0]
    if assetID not in serialByAsset:
        return 'PARSING_ERROR'
    bulkSerial = str(serialByAsset[assetID]).strip()
    if 'nan' in bulkSerial:
        return 'NOTFOUND_SENSORBULK'
    return 'MATCH_SENSORBULK' if str(serials[0]) in bulkSerial else 'MISMATCH_SENSORBULK'


def _duplicateVerdict(githubCal):
    """Repeated coefficient names are only a problem when the values differ."""
    duplicates = githubCal[githubCal.duplicated('name')]
    if duplicates.empty:
        return 'NONE'
    for name in duplicates['name']:
        if not githubCal[githubCal['name'] == name].drop_duplicates(keep=False).empty:
            return 'DUPLICATES_NOTIDENTICAL'
    return 'DUPLICATES_IDENTICAL'


def checkCalibrations(amSource, calFiles, vendorFiles, params, hitl):
    """Every github calibration file against its vendor original.

    Returns one row per file plus the vendor files that no github file claims --
    a calibration on record for an instrument the repo does not know about.
    """
    serialByAsset = params['serialByAsset']
    hitlCal = hitl['calibrations'].set_index('githubFile')
    rows, seen = [], []

    for instrument, fileName in calFiles:
        stem = os.path.splitext(fileName)[0]
        if '__' not in stem:
            print('invalid fileName format: ' + fileName)
            continue
        seen.append(stem)

        row = {'fileName': fileName, 'instrument': instrument,
               'HITLstatus': 'NA', 'HITLnotes': ' '}
        if fileName in hitlCal.index:
            row['HITLstatus'] = hitlCal.loc[fileName, 'Status']
            row['HITLnotes'] = hitlCal.loc[fileName, 'HITLnotes']
        row['calRepo_check'] = 'MATCH' if stem in vendorFiles else 'NOMATCH'

        githubCal, row['fileParse'] = _loadGithubCal(
            amSource.path(f'calibration/{instrument}/{fileName}'))
        if githubCal is None:
            rows.append(row)
            continue

        row['serialNumber'] = _serialVerdict(githubCal, stem, serialByAsset)
        ## OPTAA .ext sheets carry no column headers, so duplicates cannot be read
        if not fileName.endswith('.ext'):
            row['duplicateCoeff'] = _duplicateVerdict(githubCal)

        if row['calRepo_check'] == 'NOMATCH':
            row['vendorMatch'] = 'NAN'
        else:
            verdict, *differences = compareCalCoefficients(
                githubCal, vendorFiles.stemPath(stem), params['coeffMap'], params['constants'])
            row['vendorMatch'] = 'NOTCOMPARED' if verdict == 'NAN' else verdict
            row['differences'] = differences
        rows.append(row)

    missing = sorted(set(vendorFiles.stems) - set(seen))
    return {'files': rows, 'missingFromGithub': missing}


def checkDeploymentSheets(deployments, bulk):
    """Integrity of the deployment sheets themselves.

    These checks only printed to the notebook before, so nothing they found ever
    reached a report.
    """
    rows = []
    for column, reference, verdict in [
            ('sensor.uid', bulk['sensors'].ASSET_UID, 'SENSOR_NOT_IN_BULK'),
            ('mooring.uid', bulk['platforms'].ASSET_UID, 'MOORING_NOT_IN_PLATFORM_BULK'),
            ('CUID_Deploy', bulk['cruises'].CUID, 'CRUISE_NOT_IN_CRUISE_LIST')]:
        missing = deployments[~deployments[column].isin(reference)]
        rows += [{'refDes': r['Reference Designator'], 'deployNum': r['deploymentNumber'],
                  'value': r[column], 'verdict': verdict} for _, r in missing.iterrows()]

    ## The same instrument cannot be in two places in one deployment.
    years = pd.to_datetime(deployments['startDateTime']).dt.year
    for (year, deployNum), group in deployments.groupby([years, 'deploymentNumber']):
        repeated = group[group['sensor.uid'].duplicated(keep=False)]
        rows += [{'refDes': r['Reference Designator'], 'deployNum': deployNum,
                  'value': r['sensor.uid'], 'verdict': 'DUPLICATE_ASSET_IN_DEPLOYMENT'}
                 for _, r in repeated.iterrows()]
    return rows


def _lookupRow(table, refDes, deployNum, year):
    """The parameter row for one deployment.

    Keyed on the deployment, falling back to the year only where that year holds
    a single deployment. An instrument deployed twice in a season has two rows,
    and picking the first of them is how the wrong serial number gets attributed.
    """
    rows = table[table.referenceDesignator == refDes]
    exact = rows[rows.deployNum == deployNum]
    if len(exact) == 1:
        return exact.iloc[0]
    byYear = rows[rows.deployYear == year]
    return byYear.iloc[0] if len(byYear) == 1 else None


def _expectsRawSerial(refDes):
    instrument = refDes[18:27]
    if any(sensor in instrument for sensor in EXCLUDE_SENSORS):
        return False
    return any(sensor in instrument for sensor in VERIFIABLE_BY_RAW_SN + VERIFIABLE_BY_RAW_SN_DP)


def _assignCalFile(deployment, calHistory):
    """The calibration in force at deployment: the most recent one before it."""
    history = calHistory.get(deployment['AssetID'])
    if not history:
        return 'undef', 'none'
    earlier = [entry for entry in history if entry[0] < deployment['deployDate']]
    if not earlier:
        return 'noValidCalFile', 'NO_VALID_FILE'
    calDate, fileName = max(earlier, key=lambda entry: entry[0])
    if deployment['deployDate'] - calDate > CAL_AGE_LIMIT:
        return fileName, 'VALID_FILE_CAL_OLDER_THAN_15MONTHS'
    return fileName, 'VALID_FILE'


def _rawVerdict(deployment, serialByAsset):
    """Does the serial number in the raw file match the deployed asset?"""
    if deployment['firstRawFile'] == 'undef':
        return 'NAN'
    if deployment['firstRawFile'] == 'none':
        return 'NO_FILE' if _expectsRawSerial(deployment['refDes']) else 'NAN'
    rawSN = str(deployment['rawSN'])
    if '-99999' in rawSN:
        return 'NO_SN'
    if rawSN in str(serialByAsset.get(deployment['AssetID'], '')):
        return 'MATCH'
    ## Name the asset the raw serial actually belongs to, where one can be found --
    ## a swapped pair is the common cause and the answer is more useful than the finding.
    found = 'unknown'
    for assetID, serial in serialByAsset.items():
        if deployment['AssetID'][0:11] in assetID and rawSN in str(serial):
            found = assetID
    return f'MISMATCH: raw: {rawSN}: {found}'


def checkDeployments(byRefDes, params, hitl, calHistory, calibratedInstruments, imageSN=None):
    """Every deployment: its calibration file, its raw serial number, its sign-off.

    ``imageSN`` defaults to the parameter file. Once the curated fuzzy-match
    handoff is settled it becomes whatever that produces, and nothing else here
    changes.
    """
    serialByAsset = params['serialByAsset']
    images = params['imageSN'] if imageSN is None else imageSN
    hitlDeploy = hitl['deployments'].set_index('referenceDesignatorYearDeployNum')
    rows = []

    for refDes, deployments in byRefDes.items():
        for deployment in deployments:
            row = dict(deployment)
            year = deployment['deployDate'].year

            key = f"{refDes}.{year}.{deployment['deployNum']}"
            row['HITLstatus'] = hitlDeploy.loc[key, 'Status'] if key in hitlDeploy.index else 'NA'
            row['HITLnotes'] = hitlDeploy.loc[key, 'HITLnotes'] if key in hitlDeploy.index else ''

            row['calFile'], row['calFile_verify'] = _assignCalFile(deployment, calHistory)
            row['calibrationRequired'] = any(name in refDes for name in calibratedInstruments)

            rawRow = _lookupRow(params['rawSN'], refDes, deployment['deployNum'], year)
            if rawRow is not None:
                row['rawSN'], row['firstRawFile'] = rawRow.rawSerialNumber, rawRow.rawFile
            elif _expectsRawSerial(refDes):
                row['rawSN'], row['firstRawFile'] = '-99999', 'none'
            else:
                row['rawSN'], row['firstRawFile'] = 'undef', 'undef'
            row['rawFile_verify'] = _rawVerdict(row, serialByAsset)

            imageRow = _lookupRow(images, refDes, deployment['deployNum'], year)
            row['imageAssetID'] = imageRow.imageAssetID if imageRow is not None else 'undef'
            row['image_verify'] = 'NAN' if imageRow is None else (
                'MATCH' if str(row['imageAssetID']) in str(deployment['AssetID']) else 'MISMATCH')

            ## A sign-off outranks a failing mechanical check, but the check stays on the row.
            if (row['rawFile_verify'] == 'MATCH' or row['HITLstatus'] == 'Clear'
                    or row['image_verify'] == 'MATCH'):
                row['verificationStatus'] = 'VERIFIED'
            elif _expectsRawSerial(refDes):
                row['verificationStatus'] = 'RAW_SN_POSSIBLE'
            else:
                row['verificationStatus'] = 'NOT_VERIFIED'
            rows.append(row)
    return rows
