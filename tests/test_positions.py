"""Tests for resolving a deployment to the position in force, and for what that
position says the deployment sheet should hold.
"""

import datetime

import pandas as pd
import pytest

from rca_metadata.positions import (
    applyPositions,
    checkPositions,
    expectedValues,
    resolvePosition,
)

LJ01D = 'CE02SHBP-LJ01D-06-CTDBPN106'
PROFILER = 'RS01SBPS-SF01A-2A-CTDPFA102'
NAME_MAP = {LJ01D: 'LJ01D', PROFILER: 'SF01A'}

def record(start, lat=44.6, lon=-124.3, water=80.0, mooring=float('nan'), row=10):
    return {'positionStartTime': start, 'positionEndTime': None, 'lat': lat, 'lon': lon,
            'waterDepth': water, 'mooringDepth': mooring, 'sourceRow': row}

T2014 = pd.Timestamp('2014-09-10 15:43:00')
T2020 = pd.Timestamp('2020-07-01 00:00:00')
POSITIONS = {'LJ01D': {T2014: record(T2014), T2020: record(T2020, lat=44.7, row=20)},
             'SF01A': {T2014: record(T2014, water=200.0, mooring=195.0)}}


def resolve(refDes, when, deployNum=1, hitl=None):
    return resolvePosition(refDes, when, deployNum, POSITIONS, NAME_MAP, hitl or {})


def test_positionStartingThatYearIsTheOneInForce():
    rec, name, how = resolve(LJ01D, datetime.datetime(2020, 8, 1))
    assert (name, how, rec['sourceRow']) == ('LJ01D', 'YEAR', 20)


def test_otherwiseTheMostRecentPositionBeforeTheDeployment():
    rec, _, how = resolve(LJ01D, datetime.datetime(2018, 8, 1))
    assert how == 'PRIOR' and rec['sourceRow'] == 10


def test_deploymentBeforeAnyPositionHasNone():
    rec, _, how = resolve(LJ01D, datetime.datetime(2013, 1, 1))
    assert rec is None and how == 'NO_POSITION'


def test_twoPositionsInOneYearNeedAPersonRatherThanAGuess():
    positions = {'LJ01D': {T2020: record(T2020), pd.Timestamp('2020-09-01'): record(None, row=21)}}
    rec, _, how = resolvePosition(LJ01D, datetime.datetime(2020, 10, 1), 1, positions, NAME_MAP, {})
    assert rec is None and how == 'AMBIGUOUS'


def test_aPinnedPositionOutranksTheSpreadsheet():
    hitl = {LJ01D: [{'deployYear': 2020, 'deployNum': 1,
                     'positionStartTime': T2014, 'positionName': 'LJ01D'}]}
    rec, _, how = resolve(LJ01D, datetime.datetime(2020, 8, 1), hitl=hitl)
    assert how == 'HITL' and rec['sourceRow'] == 10


def test_unmappedReferenceDesignatorIsReported():
    rec, name, how = resolve('RS03AXBS-LJ03A-99-NOSUCH999', datetime.datetime(2020, 8, 1))
    assert rec is None and how == 'NO_POSITION_NAME'


## --- what the sheet should say ---

def test_profilerHasNoDeploymentDepth():
    assert expectedValues(PROFILER, POSITIONS['SF01A'][T2014])['deploymentDepth'] == 'N/A'


def test_mooringTopDepthIsTheDeploymentDepthWhereThereIsOne():
    assert expectedValues(LJ01D, record(T2014, water=2904.0, mooring=195.0))['deploymentDepth'] == 195


def test_withoutAMooringTheInstrumentSitsOnTheSeafloor():
    assert expectedValues(LJ01D, record(T2014, water=2904.0))['deploymentDepth'] == 2904


def test_depthsAreReportedAsPositiveWholeMetres():
    values = expectedValues(LJ01D, record(T2014, water=-1531.63))
    assert values['waterDepth'] == 1532


## --- the check ---

def deployment(**kw):
    row = {'Reference Designator': LJ01D, 'deploymentNumber': 1,
           'startDateTime': '2020-08-01T00:00:00', 'lat': 44.7, 'lon': -124.3,
           'water_depth': 80, 'deployment_depth': 80, 'notes': ''}
    row.update(kw)
    return pd.DataFrame([row])


def test_agreeingSheetIsAMatch():
    assert checkPositions(deployment(), POSITIONS, NAME_MAP, {})[0]['verdict'] == 'MATCH'


def test_disagreeingLatitudeIsReportedWithTheSpreadsheetRow():
    result = checkPositions(deployment(lat=44.9), POSITIONS, NAME_MAP, {})[0]
    assert result['verdict'] == 'MISMATCH'
    assert result['differences'] == [{'field': 'lat', 'current': 44.9, 'expected': 44.7}]
    assert result['sourceRow'] == 20


def test_literalNotApplicableDepthIsNotADifference():
    """Profiler sheets carry 'N/A' already; reading it as missing made every one
    of them look like it needed correcting."""
    rows = checkPositions(
        deployment(**{'Reference Designator': PROFILER, 'startDateTime': '2014-10-01T00:00:00',
                      'lat': 44.6, 'lon': -124.3, 'water_depth': 200, 'deployment_depth': 'N/A'}),
        POSITIONS, NAME_MAP, {})
    assert rows[0]['differences'] == []


def test_unusablePositionRecordIsItsOwnVerdict():
    positions = {'LJ01D': {T2020: record(T2020, water=float('nan'))}}
    rows = checkPositions(deployment(), positions, NAME_MAP, {})
    assert rows[0]['verdict'] == 'BAD_POSITION_RECORD'


## --- mobile assets ---

@pytest.mark.parametrize('refDes', [
    'RS01SBPS-SF01A-2A-CTDPFA102', 'CE04OSPS-SF01B-2A-CTDPFA107', 'RS03AXPS-SF03A-2A-CTDPFA302',
    'RS01SBPD-DP01A-00-ENG000000', 'CE04OSPD-DP01B-00-ENG000000', 'RS03AXPD-DP03A-00-ENG000000'])
def test_everyProfilerNodeHasNoFixedDepth(refDes):
    assert expectedValues(refDes, record(T2014, water=2900.0, mooring=195.0))['deploymentDepth'] == 'N/A'


@pytest.mark.parametrize('refDes', [
    'RS01SBPS-PC01A-4A-CTDPFA103',   # platform controller
    'RS01SBPD-PD01A-00-ENG000000',   # profiler docking platform
    'RS01SBPS-SC01A-00-ENG000000'])  # shallow profiler cage
def test_whatTheProfilerDocksToKeepsItsDepth(refDes):
    assert expectedValues(refDes, record(T2014, water=2900.0, mooring=195.0))['deploymentDepth'] == 195


def test_profilerIsReadFromTheNodeFieldNotTheWholeDesignator():
    """An instrument code carrying the prefix must not be taken for a profiler."""
    assert expectedValues('RS01SLBS-LJ01A-05-SF0XXX101',
                          record(T2014, water=2900.0, mooring=195.0))['deploymentDepth'] == 195


## --- correcting the sheets ---

def test_aDisagreeingSheetIsCorrectedToTheSpreadsheet():
    corrected, log = applyPositions(deployment(lat=44.0), POSITIONS, NAME_MAP, {})
    assert corrected.loc[0, 'lat'] == 44.7
    assert log[0]['changed'] == ['lat']


def test_anAgreeingSheetIsNotLogged():
    _, log = applyPositions(deployment(), POSITIONS, NAME_MAP, {})
    assert log == []


def test_correctingThePositionClearsThePreliminaryNote():
    """The note says the position is provisional. Correcting it is what makes it
    not, so a sheet that kept the claim would contradict itself."""
    sheet = deployment(lat=44.0, notes='The following parameters are preliminary and will be '
                                       'verified after deployment: lat; lon.')
    corrected, _ = applyPositions(sheet, POSITIONS, NAME_MAP, {})
    assert corrected.loc[0, 'notes'] == ''


def test_anUnusablePositionRecordLeavesTheSheetAlone():
    """The check reports BAD_POSITION_RECORD for these, so they are visible
    rather than silently skipped -- but nothing here can say what the sheet
    should read, so nothing is written. This used to raise a NameError."""
    positions = {'LJ01D': {T2020: record(T2020, water=float('nan'))}}
    corrected, log = applyPositions(deployment(lat=44.0), positions, NAME_MAP, {})
    assert corrected.loc[0, 'lat'] == 44.0
    assert log == []


def test_anUnresolvedPositionLeavesTheSheetAlone():
    corrected, log = applyPositions(deployment(lat=44.0), POSITIONS, {}, {})
    assert corrected.loc[0, 'lat'] == 44.0
    assert log == []


## --- review fixes ---

def test_aPinNamesOneDeploymentNotEveryNumberContainingIt():
    from rca_metadata.positions import _hitlEntry

    hitl = {'X': [{'deployYear': 2022, 'deployNum': 10, 'positionName': 'P', 'positionStartTime': 't'}]}
    assert _hitlEntry('X', 2022, 1, hitl) is None
    assert _hitlEntry('X', 2022, 10, hitl) is not None
    ## the sheets also spell a number as 10.0, and a pin can list several
    assert _hitlEntry('X', 2022, '10.0', hitl) is not None
    hitl['X'][0]['deployNum'] = '10,11'
    assert _hitlEntry('X', 2022, 11, hitl) is not None


def test_aPinToARowThatIsGoneIsItsOwnFinding():
    """The reason used to read 'the spreadsheet holds no position', which is
    false: a person pinned one and the row moved."""
    import datetime

    import pandas as pd

    from rca_metadata.positions import checkPositions

    sheet = pd.DataFrame([{'Reference Designator': 'RS03AXPS-SF03A-2A-CTDPFA302', 'deploymentNumber': 3,
                           'startDateTime': '2022-08-01T00:00:00', 'lat': '1', 'lon': '2',
                           'water_depth': '3', 'deployment_depth': '4', 'notes': ''}])
    hitl = {'RS03AXPS-SF03A-2A-CTDPFA302': [{'deployYear': 2022, 'deployNum': 3, 'positionName': 'SF03A',
                                             'positionStartTime': datetime.datetime(2022, 7, 1)}]}
    [row] = checkPositions(sheet, {'SF03A': {}}, {'RS03AXPS-SF03A-2A-CTDPFA302': 'SF03A'}, hitl)
    assert row['verdict'] == 'HITL_PIN_NOT_FOUND'


def test_applyPositionsAgreesWithTheCheckAboutWhatDiffers():
    """80.0 on the sheet against 80 in the spreadsheet is the same depth. The
    check said so; the correction logged it as a change anyway."""
    import pandas as pd

    from rca_metadata.positions import applyPositions, expectedValues

    sheet = pd.DataFrame([{'Reference Designator': 'RS03AXPS-SF03A-2A-CTDPFA302', 'deploymentNumber': 3,
                           'startDateTime': '2022-08-01T00:00:00', 'lat': 45.5, 'lon': -125.5,
                           'water_depth': 80.0, 'deployment_depth': 'N/A', 'notes': ''}])
    record = {'lat': 45.5, 'lon': -125.5, 'waterDepth': 80, 'deploymentDepth': 'N/A', 'sourceRow': 1}
    positions = {'SF03A': {pd.Timestamp('2022-07-01').to_pydatetime(): record}}
    expected = expectedValues('RS03AXPS-SF03A-2A-CTDPFA302', record)
    _, log = applyPositions(sheet, positions, {'RS03AXPS-SF03A-2A-CTDPFA302': 'SF03A'}, {})
    assert log == [] or all(entry.get('changed') != ['water_depth'] for entry in log), (log, expected)
