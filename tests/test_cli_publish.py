"""Tests for the run index the dashboard picks from, and for deleting runs out of it."""

import json

import pytest

from rca_metadata.cli import indexEntry, pruneMain, runFiles, runsToRemove, updateIndex

REPORT = {
    'runAt': '2026-09-15T12:00:00',
    'parameters': {'commit': 'abc', 'dirty': False},
    'sources': {'assetManagement': {'repo': 'o/am', 'ref': 'master', 'commit': 'aaa'},
                'positionSpreadsheet': 'inputs/x.xlsx'},
    'checks': {'calibrations': {'rows': [{'severity': 'problem'}],
                                'summary': {'problem': 1, 'total': 1}}},
}


def test_anEntryCarriesEnoughToChooseWithoutFetchingTheRun():
    entry = indexEntry(REPORT, 'report_1.json')
    assert entry['name'] == 'report_1.json'
    assert entry['summary']['calibrations']['problem'] == 1
    assert entry['parameters']['commit'] == 'abc'


def test_anEntryDoesNotCarryTheRowsThemselves():
    """The index is fetched on every load; the runs are not."""
    assert 'rows' not in str(indexEntry(REPORT, 'report_1.json'))


def test_nonRepositorySourcesAreLeftOut():
    assert 'positionSpreadsheet' not in indexEntry(REPORT, 'report_1.json')['sources']


def test_runsAreListedNewestFirst():
    older = {**REPORT, 'runAt': '2026-01-01T00:00:00'}
    index = updateIndex(updateIndex([], older, 'old.json'), REPORT, 'new.json')
    assert [entry['name'] for entry in index] == ['new.json', 'old.json']


def test_republishingARunReplacesItsEntry():
    index = updateIndex(updateIndex([], REPORT, 'a.json'), REPORT, 'a.json')
    assert len(index) == 1


## ---- deleting runs no longer needed ----

## Newest first, as the index is kept.
INDEX = [
    {'name': 'report_d.json', 'runAt': '2026-09-18T00:00:00+00:00'},
    {'name': 'report_c.json', 'runAt': '2026-09-17T00:00:00+00:00'},
    {'name': 'report_b.json', 'runAt': '2026-09-16T00:00:00+00:00'},
    {'name': 'report_a.json', 'runAt': '2026-09-15T00:00:00+00:00'},
]

PRODUCTION = '2026-09-15T00:00:00+00:00'


def published(tmp_path, index=INDEX, latestRunAt=None, companions=()):
    """A reports directory holding these runs, as a publish would leave it."""
    reports = tmp_path / 'reports'
    reports.mkdir()
    (reports / 'index.json').write_text(json.dumps(index))
    for entry in index:
        (reports / entry['name']).write_text('{}')
    for name in companions:
        (reports / name).write_text('{}')
    if latestRunAt:
        (reports / 'latest.json').write_text(json.dumps({'runAt': latestRunAt}))
    return reports


def test_aRunIsTheReportAndWhateverWasPublishedBesideIt():
    assert runFiles('report_20260918T155127Z.json') == [
        'report_20260918T155127Z.json',
        'comparison_20260918T155127Z.json',
        'history_20260918T155127Z.json']


def test_keepingTheNewestDeletesTheRest():
    removing, spared = runsToRemove(INDEX, None, keep=2)
    assert [entry['name'] for entry in removing] == ['report_b.json', 'report_a.json']
    assert spared == []


def test_anIndexInAnyOrderIsStillReadNewestFirst():
    shuffled = [INDEX[2], INDEX[0], INDEX[3], INDEX[1]]
    removing, _ = runsToRemove(shuffled, None, keep=1)
    assert [entry['name'] for entry in removing] == [
        'report_c.json', 'report_b.json', 'report_a.json']


def test_beforeTakesTheRunsThatRanEarlierAndNotTheDayItself():
    removing, _ = runsToRemove(INDEX, None, before='2026-09-17')
    assert [entry['name'] for entry in removing] == ['report_b.json', 'report_a.json']


def test_removingByNameTakesExactlyThose():
    removing, _ = runsToRemove(INDEX, None, remove=['report_c.json'])
    assert [entry['name'] for entry in removing] == ['report_c.json']


def test_aRuleNeverDeletesTheRunTheDashboardOpensOn():
    """latest.json is a copy of one of these runs. Deleting that run would leave
    the site serving a report its own picker no longer lists."""
    removing, spared = runsToRemove(INDEX, PRODUCTION, keep=2)
    assert [entry['name'] for entry in removing] == ['report_b.json']
    assert [entry['name'] for entry in spared] == ['report_a.json']


def test_namingTheProductionRunIsRefusedRatherThanQuietlySpared():
    """A rule that happens to reach it is one thing; asking for that run by name
    is another, and a prune that silently did nothing would be a lie."""
    with pytest.raises(ValueError, match='the run the dashboard opens on'):
        runsToRemove(INDEX, PRODUCTION, remove=['report_a.json'])


def test_aNameThatIsNotAPublishedRunIsRefused():
    with pytest.raises(ValueError, match='not a published run'):
        runsToRemove(INDEX, None, remove=['report_z.json'])


def test_pruningTakesTheFilesAndTheIndexEntryTogether(tmp_path):
    reports = published(tmp_path)
    pruneMain(['--reports', str(reports), '--keep', '3'])
    assert not (reports / 'report_a.json').exists()
    assert (reports / 'report_b.json').exists()
    left = json.loads((reports / 'index.json').read_text())
    assert [entry['name'] for entry in left] == ['report_d.json', 'report_c.json', 'report_b.json']


def test_theComparisonAndHistoryGoWithTheirRun(tmp_path):
    reports = published(tmp_path, companions=['comparison_a.json', 'history_a.json'])
    pruneMain(['--reports', str(reports), '--keep', '3'])
    assert not (reports / 'comparison_a.json').exists()
    assert not (reports / 'history_a.json').exists()


def test_aRunWithNoComparisonOrHistoryIsDeletedAnyway(tmp_path):
    """Most runs were given no baseline, so most have neither."""
    reports = published(tmp_path)
    pruneMain(['--reports', str(reports), '--keep', '3'])
    assert not (reports / 'report_a.json').exists()


def test_theRunTheSiteOpensOnSurvivesEvenAtKeepOne(tmp_path):
    reports = published(tmp_path, latestRunAt=PRODUCTION)
    pruneMain(['--reports', str(reports), '--keep', '1'])
    assert (reports / 'report_d.json').exists()
    assert (reports / 'report_a.json').exists()
    assert not (reports / 'report_b.json').exists()


def test_aDryRunChangesNothing(tmp_path):
    reports = published(tmp_path)
    pruneMain(['--reports', str(reports), '--keep', '1', '--dry-run'])
    assert (reports / 'report_a.json').exists()
    assert len(json.loads((reports / 'index.json').read_text())) == 4


def test_keepingNothingIsRefused(tmp_path):
    reports = published(tmp_path)
    with pytest.raises(SystemExit):
        pruneMain(['--reports', str(reports), '--keep', '0'])


def test_theIndexCanBeRebuiltFromWhatIsOnDisk(tmp_path):
    """Two runs publishing at once both rewrite the index and conflict on it.
    Rebuilt from the files after the rebase, it needs no merging."""
    from rca_metadata.cli import rebuildIndex

    reports = tmp_path / 'reports'
    reports.mkdir()
    older = {**REPORT, 'runAt': '2026-01-01T00:00:00'}
    (reports / 'report_a.json').write_text(json.dumps(older))
    (reports / 'report_b.json').write_text(json.dumps(REPORT))
    (reports / 'latest.json').write_text(json.dumps(REPORT))   # not a run of its own
    assert [entry['name'] for entry in rebuildIndex(str(reports))] == ['report_b.json', 'report_a.json']
