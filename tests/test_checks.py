"""Tests for the check logic that the notebook got wrong, and for the verdicts."""

import pandas as pd
import pytest

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

def sheets(pairs, year='2014-06-01T00:00:00', deployNum=1):
    """Deployment sheet rows: (reference designator, asset ID)."""
    return pd.DataFrame({
        'Reference Designator': [refDes for refDes, _ in pairs],
        'sensor.uid': [asset for _, asset in pairs],
        'mooring.uid': ['MOORING'] * len(pairs),
        'node.uid': ['NODE'] * len(pairs),
        'electrical.uid': [''] * len(pairs),
        'CUID_Deploy': ['CRUISE'] * len(pairs),
        'deploymentNumber': [deployNum] * len(pairs),
        'startDateTime': [year] * len(pairs),
    })


BULK = {'assetIDs': {'sensors': {'ATAPL-1', 'ATAPL-58340-00003'},
                     'platforms': {'MOORING'}, 'nodes': {'NODE'},
                     'eng': set(), 'arrays': set(), 'unclassified': {'ATAPL-FILED-WRONG'}},
        'cruises': pd.DataFrame({'CUID': ['CRUISE']})}


def duplicates(rows):
    return [r for r in rows if r['verdict'] == 'DUPLICATE_ASSET_IN_DEPLOYMENT']


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
    from rca_metadata.checks import signOff
    import pandas as pd

    sheet = pd.DataFrame({'Status': ['Clear'], 'HITLnotes': ['ingested by hand in 2019']},
                         index=pd.Index(['ATAPL-1__20140101.csv'], name='githubFile'))
    assert signOff(sheet, 'ATAPL-1__20140101.csv') == ('Clear', 'ingested by hand in 2019')
    assert signOff(sheet, 'ATAPL-2__20140101.csv') == ('NA', '')


## --- a raw serial that identifies nothing ---

def rawRow(rawSN, assetID, refDes='RS01SLBS-MJ01A-06-PRESTA101'):
    return {'firstRawFile': 'x.dat', 'rawSN': rawSN, 'AssetID': assetID, 'refDes': refDes}


def test_anExactSerialConfirmsTheAsset():
    from rca_metadata.checks import _rawVerdict

    assert _rawVerdict(rawRow('507', 'ATAPL-1'), {'ATAPL-1': '507'}) == 'MATCH'


def test_aTailThatFitsOnlyThisInstrumentConfirmsIt():
    """The extractor keeps a tail, because the two records spell a serial
    differently -- 05400030 against 5471540-0030 -- so agreement is containment
    rather than equality. 265 deployments are confirmed that way and are sound,
    because nothing else of the same model could answer to the number."""
    from rca_metadata.checks import _rawVerdict

    bulk = {'ATAPL-66662-00001': '16-50325', 'ATAPL-66662-00002': '16-50601'}
    assert _rawVerdict(rawRow('325', 'ATAPL-66662-00001'), bulk) == 'MATCH'


def test_aTailThatFitsTheInstrumentBesideItConfirmsNothing():
    """Four PREST deployments matched on a single digit, and the same digit fits
    the instrument beside them. That is not evidence, and it was reading as a
    confirmed deployment."""
    from rca_metadata.checks import _rawVerdict

    bulk = {'ATAPL-67639-00004': '5471540-0030', 'ATAPL-67639-00001': '5463757-0012'}
    verdict = _rawVerdict(rawRow('0', 'ATAPL-67639-00004'), bulk)
    assert verdict.startswith('AMBIGUOUS_SN')
    assert 'ATAPL-67639-00001' in verdict


def test_anotherModelEntirelyDoesNotMakeASerialAmbiguous():
    """A three-digit serial will appear inside something somewhere. Only an
    instrument of the same model could be confused with this one, because the
    deployment sheet already names the model."""
    from rca_metadata.checks import _rawVerdict

    bulk = {'ATAPL-66662-00001': '16-50325', 'ATOSU-99999-00001': '325-XYZ'}
    assert _rawVerdict(rawRow('325', 'ATAPL-66662-00001'), bulk) == 'MATCH'


def test_anAmbiguousSerialIsNotAMismatch():
    """Nothing disagrees, so it is not a mismatch; nothing was established
    either, so it is not a match."""
    from rca_metadata.report import severityOf, reasonOf

    row = {'verificationStatus': 'NOT_VERIFIED', 'rawFile_verify': 'AMBIGUOUS_SN: raw: 0: also X',
           'image_verify': 'NAN', 'calFile_verify': 'VALID_FILE', 'cleared': False}
    assert severityOf('deployments', row) == 'review'
    assert 'too short' in reasonOf('deployments', row)


def test_everyVerdictThisCheckEmitsIsRanked():
    """A verdict with no entry falls through to 'review' and gets the sentence
    for a row where nothing is wrong. Four of these were added without one."""
    from rca_metadata.report import SEVERITY, reasonOf, severityOf

    ranked = SEVERITY['deploymentSheets']['verdict']
    for verdict in ('SENSOR_NOT_IN_BULK', 'MOORING_NOT_IN_PLATFORM_BULK',
                    'NODE_NOT_IN_NODE_BULK', 'ELECTRICAL_NOT_IN_ENG_BULK',
                    'ASSET_IN_WRONG_BULK_RECORD', 'CRUISE_NOT_IN_CRUISE_LIST',
                    'DUPLICATE_ASSET_IN_DEPLOYMENT'):
        assert ranked.get(verdict) == 'problem', verdict

    row = {'verdict': 'ASSET_IN_WRONG_BULK_RECORD: unclassified', 'cleared': False}
    assert severityOf('deploymentSheets', row) == 'problem'
    assert 'unclassified' in reasonOf('deploymentSheets', row)
