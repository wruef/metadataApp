"""Tests for comparing two runs.

The case that matters most is the one the roadmap warns about: a row can move
because the data changed or because the check changed, and a comparison that
cannot tell them apart is worse than none.
"""


from rca_metadata.compare import comparability, compareCheck, compareReports, rowKey


def row(severity='ok', **fields):
    return {'severity': severity, 'cleared': False, **fields}


def report(rows, commit='abc', dirty=False, schema=1, runAt='2026-09-15T12:00:00', sources=None):
    return {'schemaVersion': schema, 'runAt': runAt, 'parameters': {'commit': commit, 'dirty': dirty},
            'sources': sources or {}, 'checks': {'calibrations': {'rows': rows}}}


## --- what moved ---

def test_aRowThatGotWorseIsNewlyFailing():
    result = compareCheck('calibrations', [row('ok', fileName='a.csv')],
                          [row('problem', fileName='a.csv')])
    assert [entry['key'] for entry in result['newlyFailing']] == [('a.csv',)]
    assert result['newlyFailing'][0]['was'] == 'ok'
    assert result['newlyFailing'][0]['now'] == 'problem'


def test_aRowThatGotBetterIsNewlyPassing():
    result = compareCheck('calibrations', [row('problem', fileName='a.csv')],
                          [row('ok', fileName='a.csv')])
    assert len(result['newlyPassing']) == 1


def test_aRowOnlyInTheNewRunIsNew():
    result = compareCheck('calibrations', [], [row('ok', fileName='a.csv')])
    assert [entry['key'] for entry in result['new']] == [('a.csv',)]


def test_aRowOnlyInTheBaselineIsGone():
    result = compareCheck('calibrations', [row('ok', fileName='a.csv')], [])
    assert [entry['key'] for entry in result['gone']] == [('a.csv',)]


def test_sameSeverityButADifferentVerdictIsAChange():
    """CONSTANT_MISMATCH and MISMATCH are not the same finding even when they
    rank the same."""
    result = compareCheck('calibrations', [row('problem', fileName='a.csv', vendorMatch='MISMATCH')],
                          [row('problem', fileName='a.csv', vendorMatch='MISSING_COEFFICIENT')])
    assert result['changed'][0]['fields'] == ['vendorMatch']


def test_anUntouchedRowIsCountedNotListed():
    result = compareCheck('calibrations', [row('ok', fileName='a.csv')], [row('ok', fileName='a.csv')])
    assert result['unchanged'] == 1
    assert not any(result[key] for key in ('newlyFailing', 'newlyPassing', 'new', 'gone', 'changed'))


## --- row identity ---

def test_twoDeploymentsInOneYearAreDifferentRows():
    """The shallow profilers are deployed twice a season; keyed on the year
    alone they would collapse into one row and one would read as gone."""
    assert rowKey('deployments', {'refDes': 'RS01SBPS-SF01A-3A-FLORTD101', 'deployNum': 5}) != rowKey(
        'deployments', {'refDes': 'RS01SBPS-SF01A-3A-FLORTD101', 'deployNum': 6})


def test_aCalibrationIsIdentifiedByItsFile():
    assert rowKey('calibrations', {'fileName': 'a.csv', 'instrument': 'CTDBPN'}) == ('a.csv',)


## --- can these two runs be compared at all ---

def test_sameChecksAndParametersMeansADifferenceIsRealK():
    assert comparability(report([]), report([]))['comparable'] is True


def test_differentCheckVersionsCannotBeCompared():
    """Fixing the silent-pass bug moved 114 rows without anything in the
    repositories moving at all."""
    result = comparability(report([], commit='old'), report([], commit='new'))
    assert result['comparable'] is False
    assert 'different commits' in result['reasons'][0]


def test_anUncommittedRunCannotBeABaseline():
    result = comparability(report([]), report([], dirty=True))
    assert result['comparable'] is False


def test_aSchemaChangeIsFlagged():
    result = comparability(report([], schema=1), report([], schema=2))
    assert any('schema' in reason for reason in result['reasons'])


## --- the whole comparison ---

def test_theComparisonCarriesWhetherItCanBeTrusted():
    result = compareReports(report([row('ok', fileName='a.csv')], commit='old'),
                            report([row('problem', fileName='a.csv')], commit='new'))
    assert result['comparable'] is False
    assert len(result['checks']['calibrations']['newlyFailing']) == 1


def test_movedSourcesAreReported():
    """Which ref each run read is what a reader needs to see first."""
    before = report([], sources={'assetManagement': {'repo': 'o/am', 'ref': 'master', 'commit': 'aaa'}})
    after = report([], sources={'assetManagement': {'repo': 'o/am', 'ref': 'branch', 'commit': 'bbb'}})
    moved = compareReports(before, after)['sources']
    assert moved['assetManagement']['current']['ref'] == 'branch'


def test_aCheckAbsentFromTheBaselineIsAllNew():
    baseline = {'schemaVersion': 1, 'parameters': {'commit': 'abc'}, 'checks': {}}
    result = compareReports(baseline, report([row('ok', fileName='a.csv')]))
    assert len(result['checks']['calibrations']['new']) == 1


def test_aRunWithUnknownProvenanceCannotCertifyAComparison():
    """Without knowing which checks produced a run, a moved row cannot be
    attributed to the data rather than to the check."""
    result = comparability(report([], commit='UNKNOWN'), report([]))
    assert result['comparable'] is False
    assert any('which version of the checks' in reason for reason in result['reasons'])


def test_runsThatDoNotRecordWhichRepositoryStateTheyReadCannotBeCompared():
    """The parameter commit says which checks ran, not which data they ran
    against. A pair of reports whose sources carry no commit were being diffed
    happily, and a row reported as newly failing could not be attributed to the
    data at all."""
    unknown = report([], sources={'assetManagement': {'repo': 'o/am', 'ref': 'master', 'commit': None}})
    result = comparability(unknown, unknown)
    assert result['comparable'] is False
    assert 'assetManagement' in result['reasons'][0]


def test_sourcesAtDifferentCommitsAreTheWholePointOfComparing():
    before = report([], sources={'assetManagement': {'repo': 'o/am', 'ref': 'master', 'commit': 'a' * 40}})
    after = report([], sources={'assetManagement': {'repo': 'o/am', 'ref': 'branch', 'commit': 'b' * 40}})
    assert comparability(before, after)['comparable'] is True


def test_aSeverityThisCodeNeverWroteRanksAsNeedingAPersonRatherThanCrashing():
    from rca_metadata.compare import compareCheck

    result = compareCheck('deployments', [{'refDes': 'X', 'deployNum': 1, 'severity': 'bogus'}],
                          [{'refDes': 'X', 'deployNum': 1, 'severity': 'ok'}])
    assert [entry['key'] for entry in result['newlyPassing']] == [('X', '1')]
