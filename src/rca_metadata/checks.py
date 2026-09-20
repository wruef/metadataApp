"""The verification checks.

Each check returns rows, not files. A row carries its own verdict, so the
dashboard displays judgement rather than re-deriving it, and the report contract
is a serialization step rather than a rewrite.
"""

import datetime
import itertools
import os

import numpy as np
import pandas as pd

from .calibrations import compareCalCoefficients, comparisonRule, isConstantsOnly
from .instruments import expectsRawSerial, partialMatch, sameSerial
from .loading import (
    NO_CALIBRATION,
    NO_VALID_CALIBRATION,
    RCA_ASSET_PREFIXES,
    calibrationInForce,
)

## How many trailing characters make a serial number a format match rather than
## a disagreement -- vendors and OOI disagree about prefixes, not about digits.
SERIAL_TAIL = 3

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
    ## The serial is an identifier, not a number: read as one, 1234 becomes
    ## 1234.0 and never matches the record's '1234'.
    try:
        return pd.read_csv(path, converters={'value': np.float64}, dtype={'serial': str},
                           float_precision='round_trip'), 'SUCCESS_TYPE1'
    except ValueError:
        try:
            cal = pd.read_csv(path, dtype={'serial': str}, float_precision='round_trip')
            return _resolveSheets(cal, path), 'SUCCESS_TYPE2'
        except ValueError:
            return None, 'FAIL'


def _serialVerdict(githubCal, stem, serialByAsset):
    """Does the serial inside the file agree with the asset ID in its name?"""
    if 'serial' not in githubCal.columns:
        return 'NOTFOUND_FILE'
    ## A blank cell is not a second serial number.
    serials = githubCal['serial'].dropna().astype(str).str.strip().unique()
    if len(serials) > 1:
        return 'MULTIPLE'
    if len(serials) == 0:
        return 'NOTFOUND_FILE'
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


def _calibrationRow(amSource, instrument, fileName, vendorFiles, params, hitlCal):
    """One calibration file's row: five verdicts and what is behind them."""
    stem = os.path.splitext(fileName)[0]
    serialByAsset = params['serialByAsset']

    ## hitlKey for the same reason the deployment check carries one: the sheet's
    ## own identifier for this row, settled by the run.
    row = {'fileName': fileName, 'instrument': instrument, 'hitlKey': fileName}
    row['HITLstatus'], row['HITLnotes'] = signOff(hitlCal, fileName)

    if stem in vendorFiles:
        row['calRepo_check'] = 'MATCH'
    elif isConstantsOnly(stem, params['assets']):
        ## Nothing is on record because nothing ever will be: these coefficients
        ## are fixed values, not measurements. Not a finding, and not a gap --
        ## there is simply no vendor file to expect.
        row['calRepo_check'] = 'NOT_EXPECTED'
    else:
        row['calRepo_check'] = 'NOMATCH'

    ## Where the vendor original lives, so a reader can open it beside the
    ## repository file. The two repos do not always name a sensor directory the
    ## same way, so this cannot be derived from the instrument.
    entries = vendorFiles.stems.get(stem, [])
    if entries:
        row['vendorDirectory'] = entries[0][0]
        row['vendorFiles'] = sorted(name for _, name in entries)

    githubCal, row['fileParse'] = _loadGithubCal(
        amSource.path(f'calibration/{instrument}/{fileName}'))
    if githubCal is None:
        return row

    row['serialNumber'] = _serialVerdict(githubCal, stem, serialByAsset)
    row['duplicateCoeff'] = _duplicateVerdict(githubCal)

    ## A file with no vendor original is still worth reading: some instruments
    ## carry fixed values that no vendor ever measures, and those are compared
    ## against coefficientConstants.csv instead. The comparison is told there is
    ## no vendor file, so everything that needs one is left alone rather than
    ## reported as disagreeing with nothing.
    vendorPresent = row['calRepo_check'] == 'MATCH'
    verdict, *differences = compareCalCoefficients(
        githubCal, vendorFiles.stemPath(stem) if vendorPresent else stem,
        params['coeffMap'], params['constants'], params['assets'],
        vendorPresent=vendorPresent)
    if verdict == 'NAN' and not vendorPresent:
        verdict = _missingVendorVerdict(githubCal, stem, vendorFiles, params) or verdict
    row['vendorMatch'] = 'NOTCOMPARED' if verdict == 'NAN' else verdict
    row['differences'] = differences
    return row


def _vendorOnlyRows(vendorFiles, seen, hitlCal):
    """Vendor originals the repository holds nothing for.

    Not rows in the table, because there is no repository file to be a row --
    each carries the directory the vendor filed it under, which is the only
    thing on record that says what kind of instrument it is.

    Each is signed off in the calibration sheet under the name the repository
    file would have if it were ingested, so a decision taken now is already
    attached to the file on the day it arrives.
    """
    rows = []
    for stem in sorted(set(vendorFiles.stems) - set(seen)):
        key = stem + '.csv'
        status, notes = signOff(hitlCal, key)
        rows.append({'file': stem, 'instrument': vendorFiles.stems[stem][0][0],
                     'hitlKey': key, 'HITLstatus': status, 'HITLnotes': notes})
    return rows


def checkCalibrations(amSource, calFiles, vendorFiles, params, hitl):
    """Every github calibration file against its vendor original.

    Returns one row per file plus the vendor files that no github file claims --
    a calibration on record for an instrument the repo does not know about.
    """
    hitlCal = hitl['calibrations']
    rows, seen = [], []
    for instrument, fileName in calFiles:
        stem = os.path.splitext(fileName)[0]
        if '__' not in stem:
            print('invalid fileName format: ' + fileName)
            continue
        seen.append(stem)
        rows.append(_calibrationRow(amSource, instrument, fileName, vendorFiles, params, hitlCal))
    return {'files': rows, 'missingFromGithub': _vendorOnlyRows(vendorFiles, seen, hitlCal)}


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

    ## The same instrument cannot be in two places at once. Compared by the
    ## time it was in the water, not by deployment number: numbers count per
    ## designator, so one asset can be deployment 3 on one and 7 on another in
    ## the same season, and two unrelated designators can share a number. A
    ## deployment still in the water runs to the end of time here.
    starts = pd.to_datetime(deployments['startDateTime'])
    stops = pd.to_datetime(deployments['stopDateTime']).fillna(pd.Timestamp.max)
    designator = deployments['Reference Designator']
    for asset, group in deployments.groupby('sensor.uid'):
        if len(group) < 2 or not str(asset).strip():
            continue
        for first, second in itertools.combinations(group.index, 2):
            ## The same designator again is a redeployment, not a second place.
            if designator[first] == designator[second]:
                continue
            if not (starts[first] < stops[second] and starts[second] < stops[first]):
                continue
            ## Unless the two names are one instrument, which the RAS and its
            ## D1000 are: one asset, two data streams, named once under each.
            if frozenset(_instrumentOf(designator[k]) for k in (first, second)) in ONE_INSTRUMENT_TWO_STREAMS:
                continue
            for here, there in ((first, second), (second, first)):
                record(here, asset, 'DUPLICATE_ASSET_IN_DEPLOYMENT: also '
                       f"{designator[there]} deployment {deployments.at[there, 'deploymentNumber']}")
    return rows


def _lookupRow(table, refDes, deployNum, year, singleThatYear=True):
    """The parameter row for one deployment.

    Keyed on the deployment, falling back to the year only where the instrument
    had a single deployment that year *and* the table holds a single row for it.
    An instrument deployed twice in a season has two rows, and handing one
    unkeyed row to both deployments is how the wrong serial number gets
    attributed -- one would read as confirmed and the other as a mismatch, on
    the strength of a row that names neither.
    """
    rows = table[table.referenceDesignator == refDes]
    exact = rows[rows.deployNum == deployNum]
    if len(exact) == 1:
        return exact.iloc[0]
    if not singleThatYear:
        return None
    byYear = rows[rows.deployYear == year]
    return byYear.iloc[0] if len(byYear) == 1 else None


def _assignCalFile(deployment, calHistory):
    """The calibration file in force at deployment, and what to say about it."""
    calDate, files, problem = calibrationInForce(
        calHistory.get(deployment['AssetID']), deployment['deployDate'])
    if problem == NO_CALIBRATION:
        return 'undef', 'none'
    if problem:
        return NO_VALID_CALIBRATION, 'NO_VALID_FILE'
    if deployment['deployDate'] - calDate > CAL_AGE_LIMIT:
        return files[0], 'VALID_FILE_CAL_OLDER_THAN_15MONTHS'
    return files[0], 'VALID_FILE'


def _rawVerdict(deployment, serialByAsset, aliases=None):
    """Does the serial number in the raw file match the deployed asset?

    Returns ``(verdict, asset)``, where ``asset`` is the one the serial actually
    belongs to and is None unless the verdict is a mismatch that could place it.
    Carried as a field of its own rather than left inside the verdict string,
    because the correction the dashboard offers is exactly "make the sheet say
    this asset" and reading it back out of a sentence is not a contract.

    ``aliases`` maps an asset ID to the serial its raw data reports where that
    is a different number from the one the bulk record carries -- the five-beam
    ADCPs, whose electronics answer to a serial of their own. A person confirms
    each alias once, in params/serialAliases.csv, and the check is deterministic
    from then on.
    """
    aliases = aliases or {}
    if deployment['firstRawFile'] == 'undef':
        return 'NAN', None
    if deployment['firstRawFile'] == 'none':
        return ('NO_FILE' if expectsRawSerial(deployment['refDes']) else 'NAN'), None
    rawSN = str(deployment['rawSN'])
    if '-99999' in rawSN:
        return 'NO_SN', None

    assetID = deployment['AssetID']
    bulkSerial = str(serialByAsset.get(assetID, ''))
    if sameSerial(rawSN, bulkSerial) or rawSN == aliases.get(assetID):
        ## Agreement is not always equality. The extractor keeps a tail of the
        ## serial for most instrument classes, and a pressure sensor reports
        ## 05400030 where the record carries 5471540-0030 -- the same number in
        ## two dresses. So the serial that agrees here may also agree with the
        ## instrument beside it, and a match that fits two assets settles
        ## nothing. Ask the rest of the family before calling it.
        family = str(assetID)[:11]
        rival = next((other for other, serial in serialByAsset.items()
                      if other != assetID and str(other).startswith(family)
                      and sameSerial(rawSN, serial)), None)
        if rival:
            ## The rival is an asset the serial *also* fits, which is the reason
            ## this row cannot be settled -- the opposite of a correction to
            ## offer -- so it is named in the verdict and nowhere else.
            return f'AMBIGUOUS_SN: raw: {rawSN}: also {rival}', None
        return 'MATCH', None
    ## Name the asset the raw serial actually belongs to, where one can be found --
    ## a swapped pair is the common cause and the answer is more useful than the finding.
    found = None
    for assetID, serial in serialByAsset.items():
        if str(deployment['AssetID'])[0:11] in assetID and (
                sameSerial(rawSN, serial) or rawSN == aliases.get(assetID)):
            found = assetID
    return f'MISMATCH: raw: {rawSN}: {found or "unknown"}', found


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

            ## Whether a row keyed on the year alone could belong to this deployment.
            single = sum(1 for each in deployments if each['deployDate'].year == year) == 1
            rawRow = _lookupRow(params['rawSN'], refDes, deployment['deployNum'], year, single)
            if rawRow is not None:
                row['rawSN'], row['firstRawFile'] = rawRow.rawSerialNumber, rawRow.rawFile
            elif expectsRawSerial(refDes):
                row['rawSN'], row['firstRawFile'] = '-99999', 'none'
            else:
                row['rawSN'], row['firstRawFile'] = 'undef', 'undef'
            row['rawFile_verify'], named = _rawVerdict(
                row, serialByAsset, params.get('serialAliases'))
            ## Only where the run could place it. Absent is absent: a row that
            ## names nothing must not read as naming something.
            if named:
                row['rawAssetID'] = named
            ## What the archive was asked for, so a row holding no serial says
            ## which files were read to conclude that rather than sending a
            ## reviewer to the parameter file to find out.
            if rawRow is not None:
                for field, column in (('rawFilesTried', 'filesTried'),
                                      ('rawAttemptedAt', 'attemptedAt')):
                    value = getattr(rawRow, column, None)
                    if value is not None and not pd.isna(value) and str(value).strip():
                        row[field] = str(value).strip()

            imageRow = _lookupRow(images, refDes, deployment['deployNum'], year, single)
            imageAsset = (None if imageRow is None or pd.isna(imageRow.imageAssetID)
                          else str(imageRow.imageAssetID).strip())
            row['imageAssetID'] = imageAsset or 'undef'
            ## A photograph nobody could read an asset from contradicts nothing.
            ## The blank used to become the string 'nan', which is in no asset ID,
            ## and 48 deployments carried a warning no photograph ever raised.
            if imageRow is None:
                row['image_verify'] = 'NAN'
            elif not imageAsset:
                row['image_verify'] = 'NO_IMAGE_ASSET'
            else:
                row['image_verify'] = 'MATCH' if imageAsset in str(deployment['AssetID']) else 'MISMATCH'

            ## Two things confirm a deployment, and either alone is enough: the
            ## serial number recovered from the first raw file, or a reviewer's
            ## sign-off. A photograph is not one of them. It agrees or it
            ## disagrees -- a disagreement is still a finding, and it is still
            ## reported in image_verify -- but a photograph of an instrument is
            ## not evidence of which instrument went in the water, and 127
            ## deployments were reading as confirmed on that alone.
            if row['rawFile_verify'] == 'MATCH' or row['HITLstatus'] == 'Clear':
                row['verificationStatus'] = 'VERIFIED'
            elif expectsRawSerial(refDes):
                row['verificationStatus'] = 'RAW_SN_POSSIBLE'
            else:
                row['verificationStatus'] = 'NOT_VERIFIED'
            rows.append(row)
    return rows
