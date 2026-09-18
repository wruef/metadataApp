"""The two largest verdict producers driven end to end, on fixtures small
enough to read.

``checkDeployments`` and ``checkCalibrations`` each assemble a row from half a
dozen inputs and settle several verdicts on it. Their helpers were tested; the
assembly was not, and five of the defects a review found sat in the assembly.
"""

import datetime

import pandas as pd

from rca_metadata import loading
from rca_metadata.checks import checkCalibrations, checkDeployments
from rca_metadata.sources import RepoSource, VendorFiles

## ---- deployments ----

REFDES = {
    'ctd': 'RS01SLBS-LJ01A-12-CTDPFB101',      # writes its serial into its raw data
    'phsen': 'RS01SBPS-SF01A-2D-PHSENA101',    # does not
    'marum': 'RS03INT2-MJ03D-10-CTDPFA110',    # excluded: no raw data in the archive
}


def deployment(refDes, num, year, asset, end=''):
    return {'refDes': refDes, 'deployNum': num, 'deployDate': datetime.datetime(year, 8, 1),
            'deployEnd': end, 'AssetID': asset}


def sheet(rows, key):
    frame = pd.DataFrame(rows, columns=[key, 'Reviewers', 'DateReviewed', 'Status', 'HITLnotes'])
    return frame.set_index(key)


def table(rows, columns):
    return pd.DataFrame(rows, columns=columns)


RAW_COLUMNS = ['referenceDesignator', 'deployNum', 'deployYear', 'rawFile', 'rawSerialNumber']
IMAGE_COLUMNS = ['referenceDesignator', 'deployNum', 'deployYear', 'imageFile', 'imageSerialNumber',
                 'imageAssetID', 'notes']


def run(byRefDes, rawRows=(), imageRows=(), hitlRows=(), calHistory=None, calibrated=('CTDPFB',),
        aliases=None):
    params = {
        'serialByAsset': {'ATAPL-58345-00001': '0117', 'ATAPL-58345-00002': '0118', 'ATAPL-58345-00005': '23340', 'ATAPL-67639-00009': '999'},
        'rawSN': table(rawRows, RAW_COLUMNS),
        'imageSN': table(imageRows, IMAGE_COLUMNS),
        'serialAliases': aliases or {},
    }
    hitl = {'deployments': sheet(hitlRows, 'referenceDesignatorYearDeployNum')}
    return checkDeployments(byRefDes, params, hitl, calHistory or {}, list(calibrated))


def test_aRawSerialThatMatchesConfirmsTheDeployment():
    [row] = run({REFDES['ctd']: [deployment(REFDES['ctd'], 3, 2020, 'ATAPL-58345-00001')]},
                rawRows=[(REFDES['ctd'], 3, 2020, 'f.dat', '0117')])
    assert row['rawFile_verify'] == 'MATCH'
    assert row['verificationStatus'] == 'VERIFIED'
    assert row['hitlKey'] == f"{REFDES['ctd']}.2020.3"
    assert row['deployYear'] == 2020


def test_aRawSerialOfAnotherAssetNamesIt():
    [row] = run({REFDES['ctd']: [deployment(REFDES['ctd'], 3, 2020, 'ATAPL-58345-00001')]},
                rawRows=[(REFDES['ctd'], 3, 2020, 'f.dat', '0118')])
    assert row['rawFile_verify'] == 'MISMATCH: raw: 0118: ATAPL-58345-00002'
    assert row['verificationStatus'] == 'RAW_SN_POSSIBLE'


def test_anAliasedSerialConfirmsAFiveBeamAdcp():
    [row] = run({REFDES['ctd']: [deployment(REFDES['ctd'], 3, 2020, 'ATAPL-58345-00005')]},
                rawRows=[(REFDES['ctd'], 3, 2020, 'f.dat', '21829')], aliases={'ATAPL-58345-00005': '21829'})
    assert row['rawFile_verify'] == 'MATCH'


def test_aClassThatWritesASerialButHasNoneOnRecordIsLeftForExtraction():
    [row] = run({REFDES['ctd']: [deployment(REFDES['ctd'], 3, 2020, 'ATAPL-58345-00001')]})
    assert (row['rawSN'], row['firstRawFile'], row['rawFile_verify']) == ('-99999', 'none', 'NO_FILE')
    assert row['verificationStatus'] == 'RAW_SN_POSSIBLE'


def test_aClassThatWritesNoSerialIsExcludedFromTheRawCheckNotUnchecked():
    [row] = run({REFDES['phsen']: [deployment(REFDES['phsen'], 1, 2020, 'ATAPL-67639-00009')]})
    assert (row['rawSN'], row['rawFile_verify']) == ('undef', 'NAN')
    assert row['verificationStatus'] == 'NOT_VERIFIED'


def test_theMarumSensorIsNeverAFinding():
    [row] = run({REFDES['marum']: [deployment(REFDES['marum'], 1, 2020, 'ATAPL-67639-00009')]})
    assert row['rawFile_verify'] == 'NAN'
    assert row['verificationStatus'] == 'NOT_VERIFIED'


def test_aSignOffConfirmsWhatNoSerialCould():
    [row] = run({REFDES['phsen']: [deployment(REFDES['phsen'], 1, 2020, 'ATAPL-67639-00009')]},
                hitlRows=[(f"{REFDES['phsen']}.2020.1", 'WR', '9/18/26', 'Clear', 'checked the logs')])
    assert (row['HITLstatus'], row['HITLnotes']) == ('Clear', 'checked the logs')
    assert row['verificationStatus'] == 'VERIFIED'


def test_twoDeploymentsInOneYearDoNotShareAnUnkeyedRow():
    """One row for the year with no deployment number belongs to neither
    deployment, so neither is confirmed by it."""
    both = {REFDES['ctd']: [deployment(REFDES['ctd'], 4, 2020, 'ATAPL-58345-00001'),
                            deployment(REFDES['ctd'], 5, 2020, 'ATAPL-58345-00002')]}
    rows = run(both, rawRows=[(REFDES['ctd'], None, 2020, 'f.dat', '0117')])
    assert [row['rawFile_verify'] for row in rows] == ['NO_FILE', 'NO_FILE']


def test_thePhotographIsReportedButConfirmsNothing():
    one = {REFDES['ctd']: [deployment(REFDES['ctd'], 3, 2020, 'ATAPL-58345-00001')]}
    [agree] = run(one, imageRows=[(REFDES['ctd'], 3, 2020, 'a.jpg', '117', 'ATAPL-58345-00001', '')])
    [differ] = run(one, imageRows=[(REFDES['ctd'], 3, 2020, 'a.jpg', '118', 'ATAPL-58345-00002', '')])
    [unread] = run(one, imageRows=[(REFDES['ctd'], 3, 2020, 'a.jpg', '118', None, '')])
    [none] = run(one)
    assert [r['image_verify'] for r in (agree, differ, unread, none)] == ['MATCH', 'MISMATCH', 'NO_IMAGE_ASSET', 'NAN']
    ## none of the four confirms the deployment
    assert {r['verificationStatus'] for r in (agree, differ, unread, none)} == {'RAW_SN_POSSIBLE'}


def test_theCalibrationInForceIsTheNewestBeforeTheDeployment():
    history = {'ATAPL-58345-00001': [(datetime.datetime(2019, 1, 1), 'ATAPL-1__20190101.csv'),
                           (datetime.datetime(2020, 6, 1), 'ATAPL-1__20200601.csv'),
                           (datetime.datetime(2021, 1, 1), 'ATAPL-1__20210101.csv')]}
    [row] = run({REFDES['ctd']: [deployment(REFDES['ctd'], 3, 2020, 'ATAPL-58345-00001')]}, calHistory=history)
    assert (row['calFile'], row['calFile_verify']) == ('ATAPL-1__20200601.csv', 'VALID_FILE')


def test_aCalibrationOlderThanFifteenMonthsIsAWarningNotAFinding():
    history = {'ATAPL-58345-00001': [(datetime.datetime(2018, 1, 1), 'ATAPL-1__20180101.csv')]}
    [row] = run({REFDES['ctd']: [deployment(REFDES['ctd'], 3, 2020, 'ATAPL-58345-00001')]}, calHistory=history)
    assert row['calFile_verify'] == 'VALID_FILE_CAL_OLDER_THAN_15MONTHS'


def test_calibrationsAllDatedAfterTheDeploymentAreNoCalibration():
    history = {'ATAPL-58345-00001': [(datetime.datetime(2021, 1, 1), 'ATAPL-1__20210101.csv')]}
    [row] = run({REFDES['ctd']: [deployment(REFDES['ctd'], 3, 2020, 'ATAPL-58345-00001')]}, calHistory=history)
    assert (row['calFile'], row['calFile_verify']) == ('noValidCalFile', 'NO_VALID_FILE')


def test_noCalibrationAtAllIsAFindingOnlyWhereOneIsOwed():
    one = {REFDES['ctd']: [deployment(REFDES['ctd'], 3, 2020, 'ATAPL-58345-00001')]}
    [owed] = run(one, calibrated=('CTDPFB',))
    [notOwed] = run(one, calibrated=())
    assert (owed['calibrationRequired'], owed['calFile_verify']) == (True, 'none')
    assert (notOwed['calibrationRequired'], notOwed['calFile_verify']) == (False, 'EXCLUDED')


## ---- calibrations ----

def repo(tmp_path, name, files):
    """A local clone holding these files, readable through RepoSource."""
    root = tmp_path / name
    root.mkdir(exist_ok=True)
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)
    return RepoSource(f'o/{name}', 'master', local=str(root))


ADCP = 'ATOSU-69826-00002'      # an RCA ADCP: held to fixed values, no vendor file expected
ADCP_FILE = f'{ADCP}__20200101.csv'


def adcpCsv(scale='4.500000e-001'):
    lines = ['serial,name,value,notes', f'19003,CC_scale_factor1,{scale},']
    lines += [f'19003,CC_scale_factor{n},4.500000e-001,' for n in (2, 3, 4)]
    return '\n'.join(lines) + '\n'


def runCalibrations(tmp_path, github, vendor=None, hitlRows=()):
    params = loading.loadParams('params')
    params['serialByAsset'] = {ADCP: '19003'}
    amSource = repo(tmp_path, 'asset-management', {f'calibration/ADCP/{name}': text for name, text in github.items()})
    vendorFiles = VendorFiles(repo(tmp_path, 'calibrationFiles', vendor or {}))
    hitl = {'calibrations': sheet(hitlRows, 'githubFile')}
    return checkCalibrations(amSource, [('ADCP', name) for name in github], vendorFiles, params, hitl)


def test_aConstantsOnlyInstrumentComparesAndAgrees(tmp_path):
    result = runCalibrations(tmp_path, {ADCP_FILE: adcpCsv()})
    [row] = result['files']
    assert row['vendorMatch'] == 'COMPARED_CONSTANTS'
    ## no vendor publishes one, so none is owed: excluded rather than a finding
    assert row['calRepo_check'] == 'NOT_EXPECTED'
    assert row['fileParse'] == 'SUCCESS_TYPE1'
    assert row['serialNumber'] == 'MATCH_SENSORBULK'
    assert row['duplicateCoeff'] == 'NONE'
    assert row['hitlKey'] == ADCP_FILE and row['HITLstatus'] == 'NA'
    assert result['missingFromGithub'] == []


def test_aConstantThatDisagreesIsAFindingWithTheValuesBehindIt(tmp_path):
    [row] = runCalibrations(tmp_path, {ADCP_FILE: adcpCsv(scale='4.600000e-001')})['files']
    assert row['vendorMatch'] == 'CONSTANT_MISMATCH'
    assert any('CC_scale_factor1' in str(d) for d in row['differences'])


def test_aVendorFileWithNoRepositoryFileIsListedUnderTheNameItWouldHave(tmp_path):
    vendor = {'ADCP/ATOSU-69826-00003__20200101.dev': 'x'}
    result = runCalibrations(tmp_path, {ADCP_FILE: adcpCsv()}, vendor=vendor,
                             hitlRows=[('ATOSU-69826-00003__20200101.csv', 'WR', '9/18/26', 'Clear', 'ordered')])
    [missing] = result['missingFromGithub']
    assert missing['file'] == 'ATOSU-69826-00003__20200101'
    assert missing['instrument'] == 'ADCP'
    assert missing['hitlKey'] == 'ATOSU-69826-00003__20200101.csv'
    assert (missing['HITLstatus'], missing['HITLnotes']) == ('Clear', 'ordered')


def test_aSignOffIsCarriedOnTheRowWithoutErasingTheFinding(tmp_path):
    [row] = runCalibrations(tmp_path, {ADCP_FILE: adcpCsv(scale='4.600000e-001')},
                            hitlRows=[(ADCP_FILE, 'KB', '9/18/26', 'Clear', 'deliberate')])['files']
    assert (row['HITLstatus'], row['HITLnotes']) == ('Clear', 'deliberate')
    assert row['vendorMatch'] == 'CONSTANT_MISMATCH'


def test_aFileWhoseNameCarriesNoDateIsSkippedNotCrashedOn(tmp_path):
    result = runCalibrations(tmp_path, {ADCP_FILE: adcpCsv(), 'ATOSU-69826-00002.csv': adcpCsv()})
    assert [row['fileName'] for row in result['files']] == [ADCP_FILE]
