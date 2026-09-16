"""Tests for the run index the dashboard picks from."""

from rca_metadata.cli import indexEntry, updateIndex

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
