"""Tests for the check logic that the notebook got wrong, and for the verdicts."""

import datetime

import pandas as pd

from rca_metadata.checks import _lookupRow, checkDeploymentSheets, checkSensorBulk

SF01A = 'RS01SBPS-SF01A-3A-FLORTD101'

## Two deployments in 2018, as the shallow profilers usually have.
RAW = pd.DataFrame({
    'referenceDesignator': [SF01A] * 4,
    'deployNum': [4, 5, 6, 7],
    'deployYear': [2017, 2018, 2018, 2019],
    'rawSerialNumber': [1292, 1028, 1195, 1292],
})


def test_deploymentWithOneRowThatYearIsFound():
    assert _lookupRow(RAW, SF01A, 7, 2019).rawSerialNumber == 1292


def test_eachDeploymentInASharedYearGetsItsOwnRow():
    """The bug this replaces: both 2018 deployments took the first row's serial."""
    assert _lookupRow(RAW, SF01A, 5, 2018).rawSerialNumber == 1028
    assert _lookupRow(RAW, SF01A, 6, 2018).rawSerialNumber == 1195


def test_unkeyedRowIsNotGuessedAtWhenTheYearIsAmbiguous():
    """A row with no deployNum in a year holding two deployments is left for a
    person rather than attributed to whichever sorts first."""
    unkeyed = pd.DataFrame({'referenceDesignator': [SF01A, SF01A], 'deployNum': [None, None],
                            'deployYear': [2018, 2018], 'rawSerialNumber': [1028, 1195]})
    assert _lookupRow(unkeyed, SF01A, 5, 2018) is None


def test_yearFallbackWhenThatYearHasOneDeployment():
    unkeyed = pd.DataFrame({'referenceDesignator': [SF01A], 'deployNum': [None],
                            'deployYear': [2019], 'rawSerialNumber': [1292]})
    assert _lookupRow(unkeyed, SF01A, 7, 2019).rawSerialNumber == 1292


def test_missingReferenceDesignatorIsNotAMatch():
    assert _lookupRow(RAW, 'CE02SHBP-LJ01D-06-CTDBPN106', 1, 2018) is None


## --- sensor bulk ---

def assets(**kw):
    return {k: {'mfgSN': v} for k, v in kw.items()}


def test_identicalSerialsMatch():
    rows = checkSensorBulk(assets(**{'ATAPL-1': ['7232']}), {'ATAPL-1': '7232'})
    assert rows[0]['verdict'] == 'MATCH'


def test_prefixDifferenceIsAFormatMatchNotADisagreement():
    rows = checkSensorBulk(assets(**{'ATAPL-1': ['16-50031']}), {'ATAPL-1': '50031'})
    assert rows[0]['verdict'] == 'FORMAT_MATCH'


def test_differentInstrumentIsAMismatch():
    rows = checkSensorBulk(assets(**{'ATAPL-1': ['7232']}), {'ATAPL-1': '9999'})
    assert rows[0]['verdict'] == 'MISMATCH'


def test_absentBulkSerialIsNotReportedAsADisagreement():
    """Nothing was compared, so it must not read as a comparison that failed."""
    rows = checkSensorBulk(assets(**{'ATAPL-1': ['7232']}), {'ATAPL-1': float('nan')})
    assert rows[0]['verdict'] == 'NO_BULK_SERIAL'


def test_assetsMissingFromEitherSideAreReported():
    rows = checkSensorBulk(assets(**{'ATAPL-1': ['7232']}), {'ATOSU-9': '1'})
    verdicts = {r['assetID']: r['verdict'] for r in rows}
    assert verdicts['ATOSU-9'] == 'MISSING_FROM_RCA_LIST'
    assert verdicts['ATAPL-1'] == 'MISSING_FROM_SENSOR_BULK'


## --- the same asset deployed twice at once ---

def sheets(pairs, year='2014-06-01T00:00:00', deployNum=1, stop=None):
    """Deployment sheet rows: (reference designator, asset ID). No stop means
    still in the water."""
    return pd.DataFrame({
        'Reference Designator': [refDes for refDes, _ in pairs],
        'sensor.uid': [asset for _, asset in pairs],
        'mooring.uid': ['MOORING'] * len(pairs),
        'node.uid': ['NODE'] * len(pairs),
        'electrical.uid': [''] * len(pairs),
        'CUID_Deploy': ['CRUISE'] * len(pairs),
        'deploymentNumber': [deployNum] * len(pairs),
        'startDateTime': [year] * len(pairs),
        'stopDateTime': [stop] * len(pairs),
    })


BULK = {'assetIDs': {'sensors': {'ATAPL-1', 'ATAPL-58340-00003'},
                     'platforms': {'MOORING'}, 'nodes': {'NODE'},
                     'eng': set(), 'arrays': set(), 'unclassified': {'ATAPL-FILED-WRONG'}},
        'cruises': pd.DataFrame({'CUID': ['CRUISE']})}


def duplicates(rows):
    return [r for r in rows if r['verdict'].startswith('DUPLICATE_ASSET_IN_DEPLOYMENT')]


def test_theSameAssetInTwoPlacesAtOnceIsAFinding():
    """An instrument cannot be on two moorings in one deployment."""
    rows = checkDeploymentSheets(sheets([
        ('RS01SBPD-DP01A-06-DOSTAD104', 'ATAPL-1'),
        ('RS03AXPS-PC03A-4A-DOSTAD303', 'ATAPL-1')]), BULK)
    assert len(duplicates(rows)) == 2


def test_theRasAndItsD1000AreOneInstrument():
    """They share an asset ID because they are the same hardware; two reference
    designators exist because two data streams are required of it. That is not
    the same instrument in two places, and it accounted for 24 of the 26 rows
    this check reported."""
    rows = checkDeploymentSheets(sheets([
        ('RS03INT1-MJ03C-07-RASFLA301', 'ATAPL-58340-00003'),
        ('RS03INT1-MJ03C-07-D1000A301', 'ATAPL-58340-00003')]), BULK)
    assert duplicates(rows) == []


def test_theExceptionIsThePairAndNotEitherAlone():
    """A RAS sharing an asset with something else is still a finding."""
    rows = checkDeploymentSheets(sheets([
        ('RS03INT1-MJ03C-07-RASFLA301', 'ATAPL-1'),
        ('RS03AXPS-PC03A-4A-DOSTAD303', 'ATAPL-1')]), BULK)
    assert len(duplicates(rows)) == 2


def test_anAssetRecoveredAndRedeployedElsewhereWasNotInTwoPlaces():
    """The one finding the old rule left standing: a DOSTA on the deep profiler
    until 22 September 2014 and on the platform from the 27th. Same year, same
    deployment number, never in the water twice at once."""
    frame = pd.concat([
        sheets([('RS01SBPD-DP01A-06-DOSTAD104', 'ATAPL-1')],
               year='2014-08-23T05:55:50', stop='2014-09-22T00:00:00'),
        sheets([('RS03AXPS-PC03A-4A-DOSTAD303', 'ATAPL-1')],
               year='2014-09-27T13:29:00', stop='2015-07-09T00:00:00'),
    ], ignore_index=True)
    assert duplicates(checkDeploymentSheets(frame, BULK)) == []


def test_overlappingDeploymentsAreFoundWhateverTheirNumbers():
    """Numbers count per designator, so one asset can be deployment 3 on one
    and 7 on another. The old rule compared only rows sharing a number, so this
    was never seen."""
    frame = pd.concat([
        sheets([('RS01SBPD-DP01A-06-DOSTAD104', 'ATAPL-1')], year='2020-08-01T00:00:00', deployNum=3),
        sheets([('RS03AXPS-PC03A-4A-DOSTAD303', 'ATAPL-1')], year='2020-09-01T00:00:00', deployNum=7),
    ], ignore_index=True)
    found = duplicates(checkDeploymentSheets(frame, BULK))
    assert len(found) == 2
    ## each row names the other place
    assert {r['verdict'] for r in found} == {
        'DUPLICATE_ASSET_IN_DEPLOYMENT: overlaps RS03AXPS-PC03A-4A-DOSTAD303 deployment 7',
        'DUPLICATE_ASSET_IN_DEPLOYMENT: overlaps RS01SBPD-DP01A-06-DOSTAD104 deployment 3'}


def test_aRedeploymentThatOverlapsTheLastOneIsStillTwoPlacesAtOnce():
    """This is where the error actually lives, and it was waved through as a
    redeployment. Deployment 4 of a velocity meter was never given a stop date
    and deployment 5 started a year later, so the sheet has said ever since that
    one asset is in the water twice. No deployment number can show that."""
    frame = pd.concat([
        sheets([('RS01SUM1-LJ01B-12-VEL3DB104', 'ATAPL-1')],
               year='2018-06-26T00:00:00', deployNum=4),
        sheets([('RS01SUM1-LJ01B-12-VEL3DB104', 'ATAPL-1')],
               year='2019-06-25T00:00:00', deployNum=5, stop='2024-08-20T00:00:00'),
    ], ignore_index=True)
    found = duplicates(checkDeploymentSheets(frame, BULK))
    assert len(found) == 2
    ## One designator, so naming it in the verdict would say nothing. The
    ## deployment number is what tells the two rows apart.
    assert {r['verdict'] for r in found} == {
        'DUPLICATE_ASSET_IN_DEPLOYMENT: overlaps deployment 5',
        'DUPLICATE_ASSET_IN_DEPLOYMENT: overlaps deployment 4'}


def test_aCleanTurnaroundOnOneDesignatorIsNotReported():
    """Recovered and redeployed in the same slot, with the dates to say so. The
    rule has to leave the ordinary case alone or every instrument on the array
    is a finding."""
    frame = pd.concat([
        sheets([('RS03AXPS-PC03A-4A-DOSTAD303', 'ATAPL-1')],
               year='2020-08-01T00:00:00', deployNum=6, stop='2021-07-01T00:00:00'),
        sheets([('RS03AXPS-PC03A-4A-DOSTAD303', 'ATAPL-1')],
               year='2021-07-01T00:00:00', deployNum=7),
    ], ignore_index=True)
    assert duplicates(checkDeploymentSheets(frame, BULK)) == []


def test_onlyTheLastDeploymentMayBeOpenEnded():
    """Two deployments of one asset with no stop date between them both run to
    the end of time, which is the same claim twice."""
    frame = pd.concat([
        sheets([('RS03AXBS-MJ03A-12-VEL3DB301', 'ATAPL-1')],
               year='2016-07-13T00:00:00', deployNum=2),
        sheets([('RS03AXBS-MJ03A-12-VEL3DB301', 'ATAPL-1')],
               year='2019-07-07T00:00:00', deployNum=3),
    ], ignore_index=True)
    assert len(duplicates(checkDeploymentSheets(frame, BULK))) == 2


def test_everyRowSaysWhichYearItWasDeployed():
    rows = checkDeploymentSheets(sheets([
        ('RS01SBPD-DP01A-06-DOSTAD104', 'ATAPL-1'),
        ('RS03AXPS-PC03A-4A-DOSTAD303', 'ATAPL-1')], year='2019-08-02T00:00:00'), BULK)
    assert {r['deployYear'] for r in rows} == {2019}


def test_anAssetTheBulkRecordDoesNotKnowIsStillReported():
    """The other three verdicts are unchanged, and they carry a year too."""
    rows = checkDeploymentSheets(sheets([('RS01SBPD-DP01A-06-DOSTAD104', 'ATAPL-UNKNOWN')]), BULK)
    assert [r['verdict'] for r in rows] == ['SENSOR_NOT_IN_BULK']
    assert rows[0]['deployYear'] == 2014


def test_everyAssetColumnIsCheckedAgainstItsOwnRecord():
    """node.uid was not checked at all: 46 node assets across every deployment
    in the archive, against a record nothing compared them to."""
    rows = checkDeploymentSheets(
        sheets([('RS01SBPD-DP01A-06-DOSTAD104', 'ATAPL-1')]).assign(**{'node.uid': 'NO-SUCH-NODE'}),
        BULK)
    assert [r['verdict'] for r in rows] == ['NODE_NOT_IN_NODE_BULK']


def test_anAssetInTheWrongRecordIsMisfiledNotMissing():
    """In a bulk record, just not the one this column calls for. That is a
    different answer from an asset nobody has heard of, and naming the record it
    is in is most of the fix."""
    rows = checkDeploymentSheets(
        sheets([('RS01SBPD-DP01A-06-DOSTAD104', 'ATAPL-FILED-WRONG')]), BULK)
    assert rows[0]['verdict'] == 'ASSET_IN_WRONG_BULK_RECORD: unclassified'


def test_anEmptyAssetColumnIsNotAFinding():
    """electrical.uid is empty in every sheet today. It is checked anyway, and
    an empty cell is not an asset that is missing."""
    rows = checkDeploymentSheets(sheets([('RS01SBPD-DP01A-06-DOSTAD104', 'ATAPL-1')]), BULK)
    assert rows == []


## --- serial numbers a reviewer has judged ---

def test_aSensorBulkRowCarriesItsSignOff():
    """131 serial-number disagreements came back every run because there was
    nowhere to write down which record is right."""
    from rca_metadata.checks import checkSensorBulk

    signed = pd.DataFrame({'Status': ['Clear'], 'HITLnotes': ['RCA list is correct']},
                          index=pd.Index(['ATAPL-9'], name='assetID'))
    rows = checkSensorBulk({'ATAPL-9': {'mfgSN': ['123']}}, {'ATAPL-9': '456'}, signed)
    assert rows[0]['verdict'] == 'MISMATCH'
    assert rows[0]['HITLstatus'] == 'Clear'
    assert rows[0]['HITLnotes'] == 'RCA list is correct'
    assert rows[0]['hitlKey'] == 'ATAPL-9'


def test_anUnsignedSensorBulkRowSaysSo():
    from rca_metadata.checks import checkSensorBulk

    rows = checkSensorBulk({'ATAPL-9': {'mfgSN': ['123']}}, {'ATAPL-9': '456'})
    assert rows[0]['HITLstatus'] == 'NA'
    assert rows[0]['hitlKey'] == 'ATAPL-9'


def test_aSensorBulkRowSaysWhatTheInstrumentIs():
    """Only the RCA instrument list names a type -- the bulk record describes
    equipment rather than naming an instrument -- so an asset the list knows
    carries one."""
    from rca_metadata.checks import checkSensorBulk

    rows = checkSensorBulk({'ATAPL-9': {'mfgSN': ['123'], 'instrumentType': ['OPTAA-C']}},
                           {'ATAPL-9': '123'})
    assert rows[0]['instrumentType'] == ['OPTAA-C']


def test_anAssetTheRcaListNeverHeardOfHasNoType():
    """Which is not a gap in the column. It is the finding itself, and it is
    empty on exactly the 32 rows that say MISSING_FROM_RCA_LIST."""
    from rca_metadata.checks import checkSensorBulk

    rows = checkSensorBulk({}, {'ATAPL-9': '123'})
    assert rows[0]['verdict'] == 'MISSING_FROM_RCA_LIST'
    assert rows[0]['instrumentType'] is None


def test_aVendorFileWithNoRepositoryFileCarriesItsInstrument():
    """The vendor directory is the only thing on record that says what kind of
    instrument these are, so it travels with the name."""
    import pandas as pd

    from rca_metadata.checks import signOff

    sheet = pd.DataFrame({'Status': ['Clear'], 'HITLnotes': ['ingested by hand in 2019']},
                         index=pd.Index(['ATAPL-1__20140101.csv'], name='githubFile'))
    assert signOff(sheet, 'ATAPL-1__20140101.csv') == ('Clear', 'ingested by hand in 2019')
    assert signOff(sheet, 'ATAPL-2__20140101.csv') == ('NA', '')


## --- a raw serial that identifies nothing ---

def rawRow(rawSN, assetID, refDes='RS01SLBS-MJ01A-06-PRESTA101'):
    return {'firstRawFile': 'x.dat', 'rawSN': rawSN, 'AssetID': assetID, 'refDes': refDes}


def test_anExactSerialConfirmsTheAsset():
    from rca_metadata.checks import _rawVerdict

    assert _rawVerdict(rawRow('507', 'ATAPL-1'), {'ATAPL-1': '507'}) == ('MATCH', None)


def test_aTailThatFitsOnlyThisInstrumentConfirmsIt():
    """The extractor keeps a tail, because the two records spell a serial
    differently -- 05400030 against 5471540-0030 -- so agreement is containment
    rather than equality. 265 deployments are confirmed that way and are sound,
    because nothing else of the same model could answer to the number."""
    from rca_metadata.checks import _rawVerdict

    bulk = {'ATAPL-66662-00001': '16-50325', 'ATAPL-66662-00002': '16-50601'}
    assert _rawVerdict(rawRow('325', 'ATAPL-66662-00001'), bulk) == ('MATCH', None)


def test_aTailThatFitsTheInstrumentBesideItConfirmsNothing():
    """Four PREST deployments matched on a single digit, and the same digit fits
    the instrument beside them. That is not evidence, and it was reading as a
    confirmed deployment."""
    from rca_metadata.checks import _rawVerdict

    bulk = {'ATAPL-67639-00004': '5471540-0030', 'ATAPL-67639-00001': '5463757-0012'}
    verdict, named = _rawVerdict(rawRow('0', 'ATAPL-67639-00004'), bulk)
    ## an asset the serial *also* fits is not a correction to offer
    assert named is None
    assert verdict.startswith('AMBIGUOUS_SN')
    assert 'ATAPL-67639-00001' in verdict


def test_anotherModelEntirelyDoesNotMakeASerialAmbiguous():
    """A three-digit serial will appear inside something somewhere. Only an
    instrument of the same model could be confused with this one, because the
    deployment sheet already names the model."""
    from rca_metadata.checks import _rawVerdict

    bulk = {'ATAPL-66662-00001': '16-50325', 'ATOSU-99999-00001': '325-XYZ'}
    assert _rawVerdict(rawRow('325', 'ATAPL-66662-00001'), bulk) == ('MATCH', None)


def test_anAmbiguousSerialIsNotAMismatch():
    """Nothing disagrees, so it is not a mismatch; nothing was established
    either, so it is not a match."""
    from rca_metadata.report import reasonOf, severityOf

    row = {'verificationStatus': 'NOT_VERIFIED', 'rawFile_verify': 'AMBIGUOUS_SN: raw: 0: also X',
           'image_verify': 'NAN', 'calFile_verify': 'VALID_FILE', 'cleared': False}
    assert severityOf('deployments', row) == 'verification'
    assert 'too short' in reasonOf('deployments', row)


def test_everyVerdictThisCheckEmitsIsRanked():
    """A verdict with no entry falls through to the catch-all and gets the
    sentence for a row where nothing is wrong. Four of these were added without
    one.

    Presence in the table is what is asserted, not the severity it maps to: the
    fallback is now the same category as the mapping, so comparing values would
    pass for a verdict nobody had listed.
    """
    from rca_metadata.report import SEVERITY, reasonOf, severityOf

    ranked = SEVERITY['deploymentSheets']['verdict']
    for verdict in ('SENSOR_NOT_IN_BULK', 'MOORING_NOT_IN_PLATFORM_BULK',
                    'NODE_NOT_IN_NODE_BULK', 'ELECTRICAL_NOT_IN_ENG_BULK',
                    'ASSET_IN_WRONG_BULK_RECORD', 'CRUISE_NOT_IN_CRUISE_LIST',
                    'DUPLICATE_ASSET_IN_DEPLOYMENT', 'DUPLICATE_NODE_IN_DEPLOYMENT',
                    'DUPLICATE_MOORING_IN_DEPLOYMENT', 'DEPLOYMENT_MISSING_END_DATE'):
        assert verdict in ranked, verdict

    row = {'verdict': 'ASSET_IN_WRONG_BULK_RECORD: unclassified', 'cleared': False}
    assert severityOf('deploymentSheets', row) == 'verification'
    ## The sentence is what says which of these it was, now that the category
    ## does not.
    assert 'unclassified' in reasonOf('deploymentSheets', row)


## --- a calibration taken the day of the deployment ---

def test_aCalibrationDatedTheDeploymentDayIsValid():
    """Its date carries no time of day, so it sits at midnight, and 76 of the
    1,413 deployments start at exactly midnight too. Comparing timestamps read
    RS03AXBS-LJ03A-09-HYDBBA302 deployment 3 as having no valid calibration
    when one was taken that morning, which made the row a problem."""
    from rca_metadata.checks import _assignCalFile

    deployment = {'AssetID': 'A', 'deployDate': datetime.datetime(2016, 7, 12)}
    history = {'A': [(datetime.datetime(2016, 7, 12), 'A__20160712.csv')]}
    assert _assignCalFile(deployment, history) == ('A__20160712.csv', 'VALID_FILE')


def test_aCalibrationDatedTheDayAfterIsNotValid():
    from rca_metadata.checks import _assignCalFile

    deployment = {'AssetID': 'A', 'deployDate': datetime.datetime(2016, 7, 12)}
    history = {'A': [(datetime.datetime(2016, 7, 13), 'A__20160713.csv')]}
    assert _assignCalFile(deployment, history) == ('noValidCalFile', 'NO_VALID_FILE')


def test_theDeploymentDayCalibrationIsNotAlsoCalledStale():
    """It fell back to a calibration two years older and then warned that the
    calibration was stale -- a warning caused entirely by the comparison."""
    from rca_metadata.checks import _assignCalFile

    deployment = {'AssetID': 'A', 'deployDate': datetime.datetime(2016, 7, 12)}
    history = {'A': [(datetime.datetime(2014, 8, 5), 'A__20140805.csv'),
                     (datetime.datetime(2016, 7, 12), 'A__20160712.csv')]}
    assert _assignCalFile(deployment, history) == ('A__20160712.csv', 'VALID_FILE')


## --- a blank reviewer note ---

def test_aBlankReviewerNoteIsEmptyRatherThanTheWordNan():
    """A blank cell reads as NaN, NaN is a float, and a float NaN is truthy --
    so `str(cell or '')` returned it and the note came back as 'nan'. It showed
    on 335 calibration rows and pre-filled the sign-off box, so clearing one
    wrote 'nan' into the sheet as the reason."""
    from rca_metadata.checks import signOff

    sheet = pd.DataFrame({'Status': ['Clear'], 'HITLnotes': [float('nan')]},
                         index=pd.Index(['a.csv'], name='githubFile'))
    assert signOff(sheet, 'a.csv') == ('Clear', '')


def test_aWrittenReviewerNoteSurvives():
    from rca_metadata.checks import signOff

    sheet = pd.DataFrame({'Status': ['Clear'], 'HITLnotes': ['  shipboard cal?? sn 344 ']},
                         index=pd.Index(['a.csv'], name='githubFile'))
    assert signOff(sheet, 'a.csv') == ('Clear', 'shipboard cal?? sn 344')


def test_aRowWithNoSignOffAtAllIsNotApplicable():
    from rca_metadata.checks import signOff

    sheet = pd.DataFrame({'Status': [], 'HITLnotes': []},
                         index=pd.Index([], name='githubFile'))
    assert signOff(sheet, 'a.csv') == ('NA', '')


def test_anAliasedSerialConfirmsTheAsset():
    """A five-beam ADCP reports its electronics' serial, not the system serial
    the bulk record holds. Once a person has paired the two, the raw number
    confirms the asset; and it names the asset when it turns up elsewhere."""
    from rca_metadata.checks import _rawVerdict

    bulk = {'ATAPL-58345-00004': '23340', 'ATAPL-58345-00003': '19075'}
    aliases = {'ATAPL-58345-00004': '21829'}
    assert _rawVerdict(rawRow('21829', 'ATAPL-58345-00004'), bulk, aliases) == ('MATCH', None)
    assert _rawVerdict(rawRow('21829', 'ATAPL-58345-00004'), bulk)[0].startswith('MISMATCH')
    assert _rawVerdict(rawRow('21829', 'ATAPL-58345-00003'), bulk, aliases) == (
        'MISMATCH: raw: 21829: ATAPL-58345-00004', 'ATAPL-58345-00004')


## --- review fixes, each caught by one row ---

def test_aPhotographWithNoAssetReadFromItContradictsNothing():
    """params/imageSN.csv holds 48 rows with a photo but a blank imageAssetID.
    The blank became the string 'nan', which is in no asset ID, and every one of
    those deployments carried a warning no photograph ever raised."""
    import datetime

    import pandas as pd

    from rca_metadata.checks import checkDeployments

    byRefDes = {'RS01SLBS-LJ01A-12-CTDPFB101': [{
        'refDes': 'RS01SLBS-LJ01A-12-CTDPFB101', 'deployNum': 3,
        'deployDate': datetime.datetime(2020, 8, 1), 'deployEnd': '', 'AssetID': 'ATAPL-1'}]}
    images = pd.DataFrame([{'referenceDesignator': 'RS01SLBS-LJ01A-12-CTDPFB101', 'deployNum': 3,
                            'deployYear': 2020, 'imageFile': 'x.jpg', 'imageSerialNumber': '7',
                            'imageAssetID': None, 'notes': ''}])
    params = {'serialByAsset': {'ATAPL-1': '123'}, 'imageSN': images,
              'rawSN': pd.DataFrame(columns=['referenceDesignator', 'deployNum', 'deployYear',
                                             'rawFile', 'rawSerialNumber'])}
    hitl = {'deployments': pd.DataFrame(columns=['Status', 'HITLnotes']).set_index(
        pd.Index([], name='referenceDesignatorYearDeployNum'))}
    [row] = checkDeployments(byRefDes, params, hitl, {}, [])
    assert row['image_verify'] == 'NO_IMAGE_ASSET'
    assert row['imageAssetID'] == 'undef'


def test_aBlankSerialCellIsNotASecondSerialAndANumberStillMatches():
    import numpy as np
    import pandas as pd

    from rca_metadata.checks import _serialVerdict

    ## as _loadGithubCal now reads it: the serial column is text
    cal = pd.DataFrame({'serial': ['1234', '1234', np.nan], 'name': ['a', 'b', 'c'], 'value': [1, 2, 3]})
    assert _serialVerdict(cal, 'ATAPL-1__20200101', {'ATAPL-1': '1234'}) == 'MATCH_SENSORBULK'
    blank = pd.DataFrame({'serial': [np.nan], 'name': ['a'], 'value': [1]})
    assert _serialVerdict(blank, 'ATAPL-1__20200101', {'ATAPL-1': '1234'}) == 'NOTFOUND_FILE'


def test_theYearFallbackNeedsASingleDeploymentThatYear():
    """One unkeyed row for a year with two deployments must not be handed to
    both -- one would read confirmed and the other a mismatch, on a row that
    names neither."""
    import pandas as pd

    from rca_metadata.checks import _lookupRow

    table = pd.DataFrame([{'referenceDesignator': 'X', 'deployNum': None, 'deployYear': 2020,
                           'rawFile': 'f', 'rawSerialNumber': '7'}])
    assert _lookupRow(table, 'X', 5, 2020, singleThatYear=True) is not None
    assert _lookupRow(table, 'X', 5, 2020, singleThatYear=False) is None


def test_aBlankAssetOnTheSheetDoesNotCrashTheRawVerdict():
    from rca_metadata.checks import _rawVerdict

    row = {'firstRawFile': 'x.dat', 'rawSN': '999', 'AssetID': float('nan'),
           'refDes': 'RS01SBPS-SF01A-2A-CTDPFA102'}
    assert _rawVerdict(row, {'ATAPL-1': '123'})[0].startswith('MISMATCH')


## --- a node is in one place at a time too ---

def nodeDuplicates(rows):
    return [r for r in rows if r['verdict'].startswith('DUPLICATE_NODE_IN_DEPLOYMENT')]


def test_oneNodeHostingManyInstrumentsAtOnceIsNotAFinding():
    """That is a node doing its job. Its asset is on a row per instrument
    hanging off it, all at the same time and all at the same place, so the rows
    are not the comparison -- the places are."""
    frame = sheets([('RS03AXBS-MJ03A-05-HYDLFA301', 'ATAPL-1'),
                    ('RS03AXBS-MJ03A-06-PRESTA301', 'ATAPL-58340-00003'),
                    ('RS03AXBS-MJ03A-12-VEL3DB301', 'ATAPL-1')])
    assert nodeDuplicates(checkDeploymentSheets(frame, BULK)) == []


def test_aNodeAtTwoPlacesOverTheSameDaysIsAFinding():
    """A junction box recorded at RS03AXBS-MJ03A since 2014 and never closed
    out, while the same box is at RS03CCAL-MJ03F from 2018, is one box on two
    parts of the seafloor."""
    frame = pd.concat([
        sheets([('RS03AXBS-MJ03A-05-HYDLFA301', 'ATAPL-1')], year='2014-08-08T00:00:00'),
        sheets([('RS03CCAL-MJ03F-08-SCTAAA301', 'ATAPL-1')], year='2018-07-06T00:00:00'),
    ], ignore_index=True)
    found = nodeDuplicates(checkDeploymentSheets(frame, BULK))
    assert len(found) == 2
    assert {r['verdict'] for r in found} == {
        'DUPLICATE_NODE_IN_DEPLOYMENT: also at RS03CCAL-MJ03F from 2018-07-06',
        'DUPLICATE_NODE_IN_DEPLOYMENT: also at RS03AXBS-MJ03A from 2014-08-08'}


def test_aNodeMovedBetweenPlacesIsNotAFinding():
    """Closed out at one place before appearing at the next, which is what
    moving a box looks like when the sheets are right."""
    frame = pd.concat([
        sheets([('RS03AXBS-MJ03A-05-HYDLFA301', 'ATAPL-1')],
               year='2014-08-08T00:00:00', stop='2018-07-06T00:00:00'),
        sheets([('RS03CCAL-MJ03F-08-SCTAAA301', 'ATAPL-1')], year='2018-07-06T00:00:00'),
    ], ignore_index=True)
    assert nodeDuplicates(checkDeploymentSheets(frame, BULK)) == []


def test_aNodeAtThreePlacesIsOneFindingPerPlace():
    """A box at three places is one thing wrong, not six. Each place names the
    others rather than each pair naming itself."""
    frame = pd.concat([
        sheets([('RS03AXBS-MJ03A-05-HYDLFA301', 'ATAPL-1')], year='2014-08-08T00:00:00'),
        sheets([('RS03CCAL-MJ03F-08-SCTAAA301', 'ATAPL-1')], year='2018-07-06T00:00:00'),
        sheets([('RS03INT2-MJ03D-12-VEL3DB304', 'ATAPL-1')], year='2018-07-05T00:00:00'),
    ], ignore_index=True)
    found = nodeDuplicates(checkDeploymentSheets(frame, BULK))
    assert len(found) == 3
    assert all(r['verdict'].count('from') == 2 for r in found)


def test_theFindingPointsAtASheetRowSomebodyCanOpen():
    """The earliest deployment at the place, rather than whichever instrument
    happened to be compared first."""
    frame = pd.concat([
        sheets([('RS03AXBS-MJ03A-12-VEL3DB301', 'ATAPL-1')], year='2016-01-01T00:00:00'),
        sheets([('RS03AXBS-MJ03A-05-HYDLFA301', 'ATAPL-58340-00003')],
               year='2014-08-08T00:00:00'),
        sheets([('RS03CCAL-MJ03F-08-SCTAAA301', 'ATAPL-1')], year='2018-07-06T00:00:00'),
    ], ignore_index=True)
    found = nodeDuplicates(checkDeploymentSheets(frame, BULK))
    here = [r for r in found if r['refDes'].startswith('RS03AXBS')]
    assert [r['refDes'] for r in here] == ['RS03AXBS-MJ03A-05-HYDLFA301']


## --- a deployment that was never closed out ---

def missingEnd(rows):
    return [r for r in rows if r['verdict'].startswith('DEPLOYMENT_MISSING_END_DATE')]


def test_anOpenDeploymentFollowedByAnotherIsMissingItsEndDate():
    """The later deployment is the proof that the earlier one ended. Nobody
    wrote down when, so the earlier runs to the end of time everywhere it is
    read and swallows every deployment of that slot after it."""
    frame = pd.concat([
        sheets([('RS01SUM1-LJ01B-12-VEL3DB104', 'ATAPL-1')],
               year='2018-06-26T00:00:00', deployNum=4),
        sheets([('RS01SUM1-LJ01B-12-VEL3DB104', 'ATAPL-1')],
               year='2019-06-25T00:00:00', deployNum=5, stop='2024-08-20T00:00:00'),
    ], ignore_index=True)
    found = missingEnd(checkDeploymentSheets(frame, BULK))
    assert [r['deployNum'] for r in found] == [4]
    assert found[0]['verdict'] == 'DEPLOYMENT_MISSING_END_DATE: deployment 5 starts 2019-06-25'


def test_theSlotBeingRefittedWithADifferentInstrumentIsStillFound():
    """This is the case the rule exists for. Two assets in one place is not two
    places, so the duplicate-asset rule cannot see it, and the sheet is just as
    wrong."""
    frame = pd.concat([
        sheets([('RS01SUM1-LJ01B-12-VEL3DB104', 'ATAPL-1')],
               year='2018-06-26T00:00:00', deployNum=4),
        sheets([('RS01SUM1-LJ01B-12-VEL3DB104', 'ATAPL-58340-00003')],
               year='2019-06-25T00:00:00', deployNum=5),
    ], ignore_index=True)
    rows = checkDeploymentSheets(frame, BULK)
    assert [r['deployNum'] for r in missingEnd(rows)] == [4]
    ## Different assets, so nothing is in two places.
    assert duplicates(rows) == []


def test_theDeploymentInTheWaterNowIsNotAFinding():
    """An open deployment with nothing after it is the current one."""
    frame = pd.concat([
        sheets([('RS01SUM1-LJ01B-12-VEL3DB104', 'ATAPL-1')],
               year='2018-06-26T00:00:00', deployNum=4, stop='2019-06-25T00:00:00'),
        sheets([('RS01SUM1-LJ01B-12-VEL3DB104', 'ATAPL-58340-00003')],
               year='2019-06-25T00:00:00', deployNum=5),
    ], ignore_index=True)
    assert missingEnd(checkDeploymentSheets(frame, BULK)) == []


def test_anOpenDeploymentOnADifferentDesignatorIsNotEvidence():
    """Another slot being redeployed says nothing about this one."""
    frame = pd.concat([
        sheets([('RS01SUM1-LJ01B-12-VEL3DB104', 'ATAPL-1')],
               year='2018-06-26T00:00:00', deployNum=4),
        sheets([('RS03AXBS-MJ03A-12-VEL3DB301', 'ATAPL-58340-00003')],
               year='2019-06-25T00:00:00', deployNum=5),
    ], ignore_index=True)
    assert missingEnd(checkDeploymentSheets(frame, BULK)) == []


def test_onlyTheEarlierOfTwoOpenDeploymentsIsReported():
    """Both run to the end of time, but the later one is legitimately open."""
    frame = pd.concat([
        sheets([('RS03AXBS-MJ03A-12-VEL3DB301', 'ATAPL-1')],
               year='2016-07-13T00:00:00', deployNum=2),
        sheets([('RS03AXBS-MJ03A-12-VEL3DB301', 'ATAPL-1')],
               year='2019-07-07T00:00:00', deployNum=3),
    ], ignore_index=True)
    assert [r['deployNum'] for r in missingEnd(checkDeploymentSheets(frame, BULK))] == [2]
