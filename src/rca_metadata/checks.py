"""The verification checks.

Each check returns rows, not files. A row carries its own verdict, so the
dashboard displays judgement rather than re-deriving it, and the report contract
is a serialization step rather than a rewrite.
"""

import datetime
import os

import numpy as np
import pandas as pd

from .calibrations import comparisonRule, compareCalCoefficients, isConstantsOnly
from .loading import RCA_ASSET_PREFIXES, inForceAt
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

## Instruments that share one asset ID because they are one instrument. The RAS
## and the D1000 beside it are the same hardware; two reference designators
## exist because two data streams are required of it, and the deployment sheets
## name the asset once under each. That is not the same instrument in two
## places, which is what the duplicate check is for, so it is declared here
## rather than found again every season.
ONE_INSTRUMENT_TWO_STREAMS = {frozenset({'RASFLA301', 'D1000A301'})}

## Which bulk record each asset column of a deployment sheet belongs in, and
## what to call it when the record has never heard of the asset.
##
## node.uid was not checked at all: 46 node assets across every deployment in
## the archive, against a record nothing compared them to. electrical.uid is
## empty in every sheet today and is checked anyway -- the day it is filled in
## is not the day to notice it was never looked at.
ASSET_COLUMNS = [
    ('sensor.uid', 'sensors', 'SENSOR_NOT_IN_BULK'),
    ('mooring.uid', 'platforms', 'MOORING_NOT_IN_PLATFORM_BULK'),
    ('node.uid', 'nodes', 'NODE_NOT_IN_NODE_BULK'),
    ('electrical.uid', 'eng', 'ELECTRICAL_NOT_IN_ENG_BULK'),
]


def _written(cell):
    """A sheet cell as text, where an empty one is empty.

    ``str(cell or '')`` does not do this. A blank cell reads as NaN, NaN is a
    float, and a float NaN is *truthy* -- so the ``or`` never fired and the
    empty cell came back as the string ``'nan'``. It reached the dashboard as a
    reviewer note reading "nan" on 335 of the 1,174 calibration rows, and
    pre-filled the sign-off box with it, so clearing one of those rows wrote
    "nan" into the sheet as the reason.
    """
    return '' if cell is None or pd.isna(cell) else str(cell).strip()


def signOff(sheet, key):
    """What a reviewer recorded for this row, if anything.

    The sheets are indexed by whatever identifies a row in them, so every check
    asks the same question the same way.
    """
    if key in sheet.index:
        return (_written(sheet.loc[key, 'Status']) or 'NA',
                _written(sheet.loc[key, 'HITLnotes']))
    return 'NA', ''


def checkSensorBulk(rcaAssets, serialByAsset, hitl=None):
    """Compare serial numbers between the RCA instrument list and OOI's sensor bulk.

    Both records should name the same instrument for the same asset ID. Where
    they disagree about formatting only -- a prefix one carries and the other
    does not -- that is worth knowing but is not the same as naming a different
    instrument.
    """
    ## The asset ID is what identifies one of these to a reviewer, so it is what
    ## a sign-off is written against.
    signed = hitl if hitl is not None else pd.DataFrame(
        columns=['Status', 'HITLnotes'], index=pd.Index([], name='assetID'))

    def scored(row, values=None):
        ## What the RCA instrument list calls this asset. Only that list knows:
        ## the bulk record describes equipment ('SENSOR CTD') rather than naming
        ## an instrument type. So an empty one is not a gap in the column, it is
        ## the finding itself -- these are the assets the RCA list has never
        ## heard of.
        types = values.get('instrumentType') if values is not None else None
        row['instrumentType'] = types if isinstance(types, list) else None
        row['hitlKey'] = str(row['assetID'])
        row['HITLstatus'], row['HITLnotes'] = signOff(signed, row['assetID'])
        return row

    rows = []
    for assetID, bulkSerial in serialByAsset.items():
        if str(assetID).startswith(RCA_ASSET_PREFIXES) and assetID not in rcaAssets:
            rows.append(scored({'assetID': assetID, 'rcaSerials': None, 'bulkSerial': bulkSerial,
                                'verdict': 'MISSING_FROM_RCA_LIST'}))

    for assetID, values in rcaAssets.items():
        if assetID not in serialByAsset:
            rows.append(scored({'assetID': assetID, 'rcaSerials': values['mfgSN'],
                                'bulkSerial': None, 'verdict': 'MISSING_FROM_SENSOR_BULK'},
                               values))
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
        rows.append(scored(row, values))
    return rows


## How a calibration csv points at a sheet kept in a file beside it.
SHEET_REF = 'SheetRef:'


def _readSheet(path):
    """One .ext sheet: a plain grid of numbers, no header."""
    with open(path) as handle:
        return [[float(cell) for cell in line.split(',')] for line in handle if line.strip()]


def _resolveSheets(cal, path):
    """Replace each SheetRef with the sheet it names.

    An OPTAA calibration is three files: the csv, and two .ext sheets it points
    at by name. Until those are read the csv carries the string
    ``SheetRef:CC_taarray`` where an 85 x 38 matrix belongs, and the larger part
    of the calibration cannot be compared at all.

    A sheet that is not there resolves to None rather than being left as its
    own name, so the comparison reports it missing instead of comparing a
    matrix against the string that should have pointed at one.
    """
    stem = os.path.splitext(path)[0]
    resolved, found = [], False
    for value in cal['value']:
        if isinstance(value, str) and value.startswith(SHEET_REF):
            found = True
            sheet = f'{stem}__{value[len(SHEET_REF):]}.ext'
            resolved.append(_readSheet(sheet) if os.path.isfile(sheet) else None)
        else:
            resolved.append(value)
    if found:
        cal['value'] = pd.Series(resolved, index=cal.index, dtype=object)
    return cal


def _loadGithubCal(path):
    """A github calibration csv, and which parse worked.

    Some files carry values the float converter rejects, so a second, looser
    parse is tried before the file is called unreadable. Only that looser parse
    can hold a sheet reference -- the float converter would have rejected one.
    """
    try:
        return pd.read_csv(path, converters={'value': np.float64},
                           float_precision='round_trip'), 'SUCCESS_TYPE1'
    except ValueError:
        try:
            cal = pd.read_csv(path, float_precision='round_trip')
            return _resolveSheets(cal, path), 'SUCCESS_TYPE2'
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


def _missingVendorVerdict(githubCal, stem, vendorFiles, params):
    """Why a calibration has no vendor original, where one was expected.

    An instrument with comparison rules and nothing on record is a finding, not
    a silence: it read as NOTCOMPARED, which is 'not checked', and 42 of them
    sat there looking like nothing was owed.

    Where the same asset has a vendor calibration a few days away, the answer is
    usually simpler than a missing file. Matching is on the whole file name, so
    a date one digit out matches nothing at all -- four FLORD calibrations name
    a date one day from the vendor's.

    So the near file is read rather than guessed at. Where every coefficient
    agrees, the two are one calibration under two dates and the fix is a file
    name: nothing about the numbers is in doubt, and the verdict says so.
    Where they differ, the near file is a different calibration and this one
    really has no original on record.
    """
    spec = comparisonRule(stem, params['assets'])
    if not spec or not spec['sources']:
        return None
    near = vendorFiles.nearestDate(stem)
    if not near:
        return 'NO_VENDOR_FILE'

    date, days = near
    apart = f'{date}, {days} day{"" if days == 1 else "s"} apart'
    nearStem = stem.partition('__')[0] + '__' + date
    verdict, *differences = compareCalCoefficients(
        githubCal, vendorFiles.stemPath(nearStem), params['coeffMap'],
        params['constants'], params['assets'])
    if verdict in ('COMPARED', 'COMPARED_XML', 'COMPARED_CONSTANTS') and not differences:
        return f'VENDOR_DATE_MISNAMED: {apart}, every coefficient agrees'
    if differences:
        return f'VENDOR_DATE_NEAR_MISS: {apart}, {len(differences)} coefficients differ'
    return f'VENDOR_DATE_NEAR_MISS: {apart}, and it could not be compared either'


def checkCalibrations(amSource, calFiles, vendorFiles, params, hitl):
    """Every github calibration file against its vendor original.

    Returns one row per file plus the vendor files that no github file claims --
    a calibration on record for an instrument the repo does not know about.
    """
    serialByAsset = params['serialByAsset']
    hitlCal = hitl['calibrations']
    rows, seen = [], []

    for instrument, fileName in calFiles:
        stem = os.path.splitext(fileName)[0]
        if '__' not in stem:
            print('invalid fileName format: ' + fileName)
            continue
        seen.append(stem)

        ## hitlKey for the same reason the deployment check carries one: the
        ## sheet's own identifier for this row, settled by the run.
        row = {'fileName': fileName, 'instrument': instrument, 'hitlKey': fileName}
        row['HITLstatus'], row['HITLnotes'] = signOff(hitlCal, fileName)
        if stem in vendorFiles:
            row['calRepo_check'] = 'MATCH'
        elif isConstantsOnly(stem, params['assets']):
            ## Nothing is on record because nothing ever will be: these
            ## coefficients are fixed values, not measurements. Not a finding,
            ## and not a gap -- there is simply no vendor file to expect.
            row['calRepo_check'] = 'NOT_EXPECTED'
        else:
            row['calRepo_check'] = 'NOMATCH'
        ## Where the vendor original lives, so a reader can open it beside the
        ## repository file. The two repos do not always name a sensor directory
        ## the same way, so this cannot be derived from the instrument.
        entries = vendorFiles.stems.get(stem, [])
        if entries:
            row['vendorDirectory'] = entries[0][0]
            row['vendorFiles'] = sorted(name for _, name in entries)

        githubCal, row['fileParse'] = _loadGithubCal(
            amSource.path(f'calibration/{instrument}/{fileName}'))
        if githubCal is None:
            rows.append(row)
            continue

        row['serialNumber'] = _serialVerdict(githubCal, stem, serialByAsset)
        ## OPTAA .ext sheets carry no column headers, so duplicates cannot be read
        if not fileName.endswith('.ext'):
            row['duplicateCoeff'] = _duplicateVerdict(githubCal)

        ## A file with no vendor original is still worth reading: some
        ## instruments carry fixed values that no vendor ever measures, and
        ## those are compared against coefficientConstants.csv instead. The
        ## comparison is told there is no vendor file, so everything that needs
        ## one is left alone rather than reported as disagreeing with nothing.
        vendorPresent = row['calRepo_check'] == 'MATCH'
        verdict, *differences = compareCalCoefficients(
            githubCal, vendorFiles.stemPath(stem) if vendorPresent else stem,
            params['coeffMap'], params['constants'], params['assets'],
            vendorPresent=vendorPresent)
        if verdict == 'NAN' and not vendorPresent:
            verdict = _missingVendorVerdict(githubCal, stem, vendorFiles, params) or verdict
        row['vendorMatch'] = 'NOTCOMPARED' if verdict == 'NAN' else verdict
        row['differences'] = differences
        rows.append(row)

    ## Vendor originals the repository holds nothing for. Not rows in the table,
    ## because there is no repository file to be a row -- each carries the
    ## directory the vendor filed it under, which is the only thing on record
    ## that says what kind of instrument it is.
    ##
    ## Each is signed off in the calibration sheet under the name the repository
    ## file would have if it were ingested, so a decision taken now is already
    ## attached to the file on the day it arrives.
    missing = []
    for stem in sorted(set(vendorFiles.stems) - set(seen)):
        key = stem + '.csv'
        status, notes = signOff(hitlCal, key)
        missing.append({'file': stem, 'instrument': vendorFiles.stems[stem][0][0],
                        'hitlKey': key, 'HITLstatus': status, 'HITLnotes': notes})
    return {'files': rows, 'missingFromGithub': missing}


def _instrumentOf(refDes):
    """The instrument at the end of a reference designator."""
    return str(refDes).split('-')[-1]


def checkDeploymentSheets(deployments, bulk):
    """Integrity of the deployment sheets themselves.

    These checks only printed to the notebook before, so nothing they found ever
    reached a report.
    """
    years = pd.to_datetime(deployments['startDateTime']).dt.year
    rows = []

    def record(index, value, verdict):
        row = deployments.loc[index]
        rows.append({'refDes': row['Reference Designator'],
                     'deployNum': row['deploymentNumber'],
                     'deployYear': int(years.loc[index]), 'value': value, 'verdict': verdict})

    known = bulk['assetIDs']
    for column, expected, verdict in ASSET_COLUMNS:
        values = deployments[column].dropna().astype(str).str.strip()
        for index, value in values[values != ''].items():
            if value in known[expected]:
                continue
            ## In a bulk record, just not the one this column calls for. That is
            ## a different answer from an asset nobody has ever heard of, and
            ## naming the record it is in is most of the fix.
            elsewhere = [name for name in known if value in known[name]]
            record(index, value, f'ASSET_IN_WRONG_BULK_RECORD: {", ".join(elsewhere)}'
                   if elsewhere else verdict)

    cruises = set(bulk['cruises'].CUID.dropna().astype(str))
    sailed = deployments['CUID_Deploy'].dropna().astype(str).str.strip()
    for index, value in sailed[sailed != ''].items():
        if value not in cruises:
            record(index, value, 'CRUISE_NOT_IN_CRUISE_LIST')

    ## The same instrument cannot be in two places in one deployment.
    for (year, deployNum), group in deployments.groupby([years, 'deploymentNumber']):
        repeated = group[group['sensor.uid'].duplicated(keep=False)]
        for asset, shared in repeated.groupby('sensor.uid'):
            ## Unless the two names are one instrument, which the RAS and its
            ## D1000 are: one asset, two data streams, named once under each.
            if frozenset(_instrumentOf(r['Reference Designator'])
                         for _, r in shared.iterrows()) in ONE_INSTRUMENT_TWO_STREAMS:
                continue
            rows += [{'refDes': r['Reference Designator'], 'deployNum': deployNum,
                      'deployYear': int(year), 'value': asset,
                      'verdict': 'DUPLICATE_ASSET_IN_DEPLOYMENT'} for _, r in shared.iterrows()]
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
    """The calibration in force at deployment: the most recent one up to it.

    The same rule the published history applies, from the same function, so a
    row's verdict and its published calibration link cannot disagree.
    """
    history = calHistory.get(deployment['AssetID'])
    if not history:
        return 'undef', 'none'
    earlier = inForceAt(history, deployment['deployDate'])
    if not earlier:
        return 'noValidCalFile', 'NO_VALID_FILE'
    calDate, fileName = max(earlier, key=lambda entry: entry[0])
    if deployment['deployDate'] - calDate > CAL_AGE_LIMIT:
        return fileName, 'VALID_FILE_CAL_OLDER_THAN_15MONTHS'
    return fileName, 'VALID_FILE'


def _rawVerdict(deployment, serialByAsset, aliases=None):
    """Does the serial number in the raw file match the deployed asset?

    ``aliases`` maps an asset ID to the serial its raw data reports where that
    is a different number from the one the bulk record carries -- the five-beam
    ADCPs, whose electronics answer to a serial of their own. A person confirms
    each alias once, in params/serialAliases.csv, and the check is deterministic
    from then on.
    """
    aliases = aliases or {}
    if deployment['firstRawFile'] == 'undef':
        return 'NAN'
    if deployment['firstRawFile'] == 'none':
        return 'NO_FILE' if _expectsRawSerial(deployment['refDes']) else 'NAN'
    rawSN = str(deployment['rawSN'])
    if '-99999' in rawSN:
        return 'NO_SN'

    assetID = deployment['AssetID']
    bulkSerial = str(serialByAsset.get(assetID, ''))
    if rawSN == bulkSerial or rawSN == aliases.get(assetID):
        return 'MATCH'
    if rawSN in bulkSerial:
        ## The extractor keeps only a tail of the serial, because the two
        ## records spell one differently -- an instrument reporting 05400030
        ## against a record carrying 5471540-0030 -- so agreement is containment
        ## rather than equality. 265 deployments are confirmed that way and are
        ## sound, because nothing else of the same model could answer to the
        ## number. Four PREST deployments match on a single digit, which
        ## identifies nothing: the same digit fits the instrument beside it.
        family = str(assetID)[:11]
        rival = next((other for other, serial in serialByAsset.items()
                      if other != assetID and str(other).startswith(family)
                      and rawSN in str(serial)), None)
        if rival:
            return f'AMBIGUOUS_SN: raw: {rawSN}: also {rival}'
        return 'MATCH'
    ## Name the asset the raw serial actually belongs to, where one can be found --
    ## a swapped pair is the common cause and the answer is more useful than the finding.
    found = 'unknown'
    for assetID, serial in serialByAsset.items():
        if deployment['AssetID'][0:11] in assetID and (rawSN in str(serial) or rawSN == aliases.get(assetID)):
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
    hitlDeploy = hitl['deployments']
    rows = []

    for refDes, deployments in byRefDes.items():
        for deployment in deployments:
            row = dict(deployment)
            year = deployment['deployDate'].year

            ## The line this deployment occupies in the 2i-HITL sheet, carried
            ## on the row so a sign-off writes to the line the check read. The
            ## browser rebuilt it from the deployment date, in whatever timezone
            ## the reader happened to be in, and a date near a year boundary
            ## shifts -- which appends a second line for a deployment that
            ## already has one rather than updating it.
            ## The year the deployment went in the water, settled here rather
            ## than sliced off a timestamp in the browser. The positions check
            ## has carried one all along; this is the same field.
            row['deployYear'] = year
            key = f"{refDes}.{year}.{deployment['deployNum']}"
            row['hitlKey'] = key
            row['HITLstatus'], row['HITLnotes'] = signOff(hitlDeploy, key)

            row['calFile'], row['calFile_verify'] = _assignCalFile(deployment, calHistory)
            row['calibrationRequired'] = any(name in refDes for name in calibratedInstruments)
            ## asset-management holds no calibration directory for this
            ## instrument at all, so there is nothing to compare and nothing was
            ## missed. Said outright rather than left as 'none', which reads as
            ## a calibration that should be there and is not -- 32 deployments
            ## are exactly that, and they keep the 'none' they have earned.
            if not row['calibrationRequired'] and row['calFile_verify'] == 'none':
                row['calFile_verify'] = 'EXCLUDED'

            rawRow = _lookupRow(params['rawSN'], refDes, deployment['deployNum'], year)
            if rawRow is not None:
                row['rawSN'], row['firstRawFile'] = rawRow.rawSerialNumber, rawRow.rawFile
            elif _expectsRawSerial(refDes):
                row['rawSN'], row['firstRawFile'] = '-99999', 'none'
            else:
                row['rawSN'], row['firstRawFile'] = 'undef', 'undef'
            row['rawFile_verify'] = _rawVerdict(row, serialByAsset, params.get('serialAliases'))

            imageRow = _lookupRow(images, refDes, deployment['deployNum'], year)
            row['imageAssetID'] = imageRow.imageAssetID if imageRow is not None else 'undef'
            row['image_verify'] = 'NAN' if imageRow is None else (
                'MATCH' if str(row['imageAssetID']) in str(deployment['AssetID']) else 'MISMATCH')

            ## Two things confirm a deployment, and either alone is enough: the
            ## serial number recovered from the first raw file, or a reviewer's
            ## sign-off. A photograph is not one of them. It agrees or it
            ## disagrees -- a disagreement is still a finding, and it is still
            ## reported in image_verify -- but a photograph of an instrument is
            ## not evidence of which instrument went in the water, and 127
            ## deployments were reading as confirmed on that alone.
            if row['rawFile_verify'] == 'MATCH' or row['HITLstatus'] == 'Clear':
                row['verificationStatus'] = 'VERIFIED'
            elif _expectsRawSerial(refDes):
                row['verificationStatus'] = 'RAW_SN_POSSIBLE'
            else:
                row['verificationStatus'] = 'NOT_VERIFIED'
            rows.append(row)
    return rows
