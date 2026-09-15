"""Tests for the check logic that the notebook got wrong, and for the verdicts."""

import pandas as pd
import pytest

from rca_metadata.checks import _lookupRow, checkSensorBulk

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
