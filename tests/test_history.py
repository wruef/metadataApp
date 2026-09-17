"""Tests for the published deployment history and the season lists."""

import csv
import datetime

import pandas as pd
import pytest

from rca_metadata.history import (calibrationLinks, currentDeployments, deployedIn,
                                  deploymentHistory, recoveredIn, sensorTypeName,
                                  writeHistory, writeSeasonList)

CAM = 'RS01SBPS-PC01A-07-CAMDSB103'
CTD = 'CE02SHBP-LJ01D-06-CTDBPN106'

ASSETS = {
    'ATAPL-58317-00001': {'instrumentType': ['CAMDS-B', 'CAMDS-C'], 'mfgSN': ['1234']},
    'ATAPL-58317-00009': {'instrumentType': ['CAMDS'], 'mfgSN': ['5678']},
    'ATOSU-69827-00003': {'instrumentType': ['CTDBP-N'], 'mfgSN': ['3', '9651', '8643']},
}


class FakeSource:
    def blobUrl(self, path):
        return 'https://github.com/owner/repo/blob/master/' + path


def deployments(*rows):
    return pd.DataFrame([{
        'Reference Designator': refDes, 'sensor.uid': assetID, 'deploymentNumber': 1,
        'startDateTime': start, 'stopDateTime': stop, 'CUID_Deploy': 'TN407',
        'lat': 44.6, 'lon': -124.3} for refDes, assetID, start, stop in rows])


## --- sensor type naming ---

def test_multiTypeAssetGetsOneName():
    assert sensorTypeName(['CAMDS-B', 'CAMDS-C']) == 'CAMDSB_CAMDSC'


def test_singleTypeDropsItsHyphen():
    assert sensorTypeName(['CTDBP-N']) == 'CTDBPN'


## --- calibration assignment ---

def test_calibrationInForceIsTheMostRecentBeforeDeployment():
    links = calibrationLinks(FakeSource(), [
        ('calibration/CTDBPN', 'ATOSU-69827-00003__20131207.csv'),
        ('calibration/CTDBPN', 'ATOSU-69827-00003__20160101.csv')])
    rows = deploymentHistory(
        deployments((CTD, 'ATOSU-69827-00003', '2014-09-10T15:43:00', '')), ASSETS, links, {})
    assert rows[0]['githubCalibrationFile'].endswith('ATOSU-69827-00003__20131207.csv')


def test_calibrationDatedAfterDeploymentIsNotUsed():
    links = calibrationLinks(FakeSource(),
                             [('calibration/CTDBPN', 'ATOSU-69827-00003__20200101.csv')])
    rows = deploymentHistory(
        deployments((CTD, 'ATOSU-69827-00003', '2014-09-10T15:43:00', '')), ASSETS, links, {})
    assert rows[0]['githubCalibrationFile'] == 'noValidCalFile'


def test_assetWithNoCalibrationsAtAll():
    rows = deploymentHistory(
        deployments((CTD, 'ATOSU-69827-00003', '2014-09-10T15:43:00', '')), ASSETS, {}, {})
    assert rows[0]['githubCalibrationFile'] == 'none'


def test_assetMissingFromTheInstrumentList():
    rows = deploymentHistory(
        deployments((CTD, 'ATAPL-00000-00000', '2014-09-10T15:43:00', '')), ASSETS, {}, {})
    assert rows[0]['sensorType'] == 'noValidType'


## --- grouping into files ---

def test_aSensorTypeFileHoldsOnlyItsOwnType(tmp_path):
    """CAMDS and CAMDSB_CAMDSC are different types. Matching one inside the other
    put all 30 CAMDSB_CAMDSC rows into the CAMDS file as well."""
    rows = deploymentHistory(deployments(
        (CAM, 'ATAPL-58317-00001', '2020-07-01T00:00:00', ''),
        (CAM, 'ATAPL-58317-00009', '2021-07-01T00:00:00', '')), ASSETS, {}, {})
    writeHistory(rows, str(tmp_path))
    written = sorted(p.name for p in tmp_path.iterdir())
    assert written == ['CAMDSB_CAMDSC_deployments.csv', 'CAMDS_deployments.csv',
                       'refDesList.csv']
    camds = list(csv.DictReader(open(tmp_path / 'CAMDS_deployments.csv')))
    assert [row['sensorType'] for row in camds] == ['CAMDS']


def test_unrecoveredDeploymentHasAnEmptyEndTimeNotTheWordNan(tmp_path):
    rows = deploymentHistory(
        deployments((CTD, 'ATOSU-69827-00003', '2014-09-10T15:43:00', None)), ASSETS, {}, {})
    writeHistory(rows, str(tmp_path))
    written = list(csv.DictReader(open(tmp_path / 'CTDBPN_deployments.csv')))
    assert written[0]['endTime'] == ''


def test_serialNumberListSurvivesTheRoundTrip(tmp_path):
    rows = deploymentHistory(
        deployments((CTD, 'ATOSU-69827-00003', '2014-09-10T15:43:00', '')), ASSETS, {}, {})
    writeHistory(rows, str(tmp_path))
    written = list(csv.DictReader(open(tmp_path / 'CTDBPN_deployments.csv')))
    assert written[0]['instrumentSN'] == "['3', '9651', '8643']"


## --- season lists ---

SEASON = deployments(
    (CTD, 'ATOSU-69827-00003', '2022-08-19T05:55:00', '2023-08-01T00:00:00'),
    (CAM, 'ATAPL-58317-00001', '2021-07-01T00:00:00', None),
    (CAM, 'ATAPL-58317-00009', '2023-06-01T00:00:00', '2023-09-01T00:00:00'))


def test_currentIsWhateverHasNoRecoveryDate():
    assert [row['referenceDesignator'] for row in currentDeployments(SEASON, ASSETS)] == [CAM]


def test_deployedInAYearUsesTheDeploymentDate():
    assert len(deployedIn(SEASON, 2022, ASSETS)) == 1
    assert len(deployedIn(SEASON, 2021, ASSETS)) == 1


def test_recoveredInAYearUsesTheRecoveryDate():
    recovered = recoveredIn(SEASON, 2023, ASSETS)
    assert len(recovered) == 2


def test_multiValuedFieldsDoNotSplitTheRow(tmp_path):
    """An asset with several serial numbers wrote unquoted commas, so 27 of the
    154 rows in the 2022 list had more fields than the header."""
    path = tmp_path / 'deployed.csv'
    writeSeasonList(deployedIn(SEASON, 2022, ASSETS), str(path))
    rows = list(csv.reader(open(path)))
    assert all(len(row) == 6 for row in rows)
    assert rows[1][5] == '3,9651,8643'


def test_theDateColumnIsNamedForWhatTheListIsAbout(tmp_path):
    path = tmp_path / 'recovered.csv'
    writeSeasonList(recoveredIn(SEASON, 2023, ASSETS), str(path), 'recoverDate')
    assert list(csv.reader(open(path)))[0][3] == 'recoverDate'


## --- which of several vendor files a deployment is pointed at ---

def vendorUrls(stem, *extensions):
    return [f'https://github.com/o/calibrationFiles/blob/master/X/{stem}{e}' for e in extensions]


def linked(stem, *extensions):
    from rca_metadata.history import comparedFile

    return comparedFile(vendorUrls(stem, *extensions)).rsplit('/', 1)[-1]


def test_anOptaaIsPointedAtThePureWaterCalibration():
    """OPTAA ships a .cal and a .dev for the same date. The .cal is the air
    calibration; the .dev is what asset-management is built from and what the
    check compares against. Alphabetically the .cal wins, so the published
    history pointed a reader at the file the check never opens."""
    assert linked('ATAPL-69943-00001__20190212', '.cal', '.dev').endswith('.dev')


def test_aCtdIsPointedAtItsXmlcon():
    """The same defect, and not only for OPTAA: a CTD linked whichever of .cal,
    .con and .xmlcon sorted first."""
    assert linked('ATAPL-66662-00008__20221019', '.con', '.xmlcon').endswith('.xmlcon')
    assert linked('ATOSU-69828-00002__20221028', '.cal', '.xmlcon').endswith('.xmlcon')


def test_aFluorometerIsPointedAtTheLambdaFile():
    """Both .dev files are posted; only the lambda one carries volume
    scattering, and it is the one compared against."""
    assert linked('ATAPL-70110-00001__20140527', '.dev', '.dev.lambda').endswith('.dev.lambda')


def test_theExtensionIsMatchedWhateverItsCase():
    """27 vendor files are spelled .CAL or .DEV."""
    assert linked('ATAPL-69943-00001__20190212', '.cal', '.DEV').endswith('.DEV')


def test_oneFileIsTheFileLinked():
    assert linked('ATAPL-58324-00003__20140805', '.dev').endswith('.dev')


def test_aFormatWithNoRuleFallsBackRatherThanLinkingNothing():
    """An instrument the comparison has no rule for still deserves a link; one
    link is better than none."""
    assert linked('ATAPL-12345-00001__20140805', '.aaa', '.zzz').endswith('.aaa')
