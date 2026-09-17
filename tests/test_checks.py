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
