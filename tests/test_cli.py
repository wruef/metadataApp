"""Tests for how a run is asked for on the command line."""


from rca_metadata.cli import latestPositionFile, parseSource


def test_repoWithoutARefTakesTheDefault():
    source = parseSource('oceanobservatories/asset-management')
    assert (source.repo, source.ref) == ('oceanobservatories/asset-management', 'master')


def test_refAfterAnAtSign():
    source = parseSource('oceanobservatories/asset-management@my-branch')
    assert source.ref == 'my-branch'


def test_aShaIsARefLikeAnyOther():
    assert parseSource('owner/repo@0ac8bd8').ref == '0ac8bd8'


def test_deploymentsDefaultsToMainNotMaster():
    assert parseSource('OOI-CabledArray/deployments', defaultRef='main').ref == 'main'


def test_aCloneIsPreferredWhenItIsThere(tmp_path):
    """Reading a clone and reading the API give the same answers; the clone is
    simply far cheaper, so it wins whenever it exists."""
    (tmp_path / 'asset-management').mkdir()
    source = parseSource('oceanobservatories/asset-management@master', str(tmp_path))
    assert source.local == str(tmp_path / 'asset-management')


def test_withoutACloneItReadsTheApi(tmp_path):
    source = parseSource('oceanobservatories/asset-management', str(tmp_path))
    assert source.local is None


def test_noClonesDirectoryMeansTheApi():
    assert parseSource('owner/repo').local is None


def test_theRefIsKeptEvenWhenReadingAClone():
    """The report names the ref it verified, and file links point at it."""
    source = parseSource('owner/repo@a-branch', None)
    assert source.ref == 'a-branch'


def test_theNewestPositionSpreadsheetIsUsed(tmp_path):
    for name in ['RSN_Positions_TEAM_20250318.xlsx', 'RSN_Positions_TEAM_20251113.xlsx']:
        (tmp_path / name).touch()
    found = latestPositionFile(str(tmp_path / 'RSN_Positions_TEAM_*.xlsx'))
    assert found.endswith('RSN_Positions_TEAM_20251113.xlsx')


def test_noSpreadsheetMeansThePositionCheckIsSkipped(tmp_path):
    """It is a periodic drop from the team, not something a run can fetch."""
    assert latestPositionFile(str(tmp_path / 'nothing_*.xlsx')) is None


## --- comparing two runs from the command line ---

REPORT = {
    'schemaVersion': 2,
    'runAt': '2026-09-15T12:00:00',
    'parameters': {'commit': 'abc', 'dirty': False},
    'sources': {'assetManagement': {'repo': 'o/am', 'ref': 'master', 'commit': 'aaa'}},
    'checks': {'deployments': {'rows': [{'refDes': 'X', 'deployNum': 1, 'severity': 'ok'}],
                               'summary': {'problem': 0, 'total': 1}}},
}


def written(tmp_path, name, report):
    import json
    path = tmp_path / name
    path.write_text(json.dumps(report))
    return str(path)


def test_comparingTwoRunsWritesWhatMoved(tmp_path, capsys):
    import json

    from rca_metadata.cli import compareMain

    worse = {**REPORT, 'checks': {'deployments': {
        'rows': [{'refDes': 'X', 'deployNum': 1, 'severity': 'problem'}],
        'summary': {'problem': 1, 'total': 1}}}}
    out = str(tmp_path / 'comparison.json')
    assert compareMain([written(tmp_path, 'a.json', REPORT),
                        written(tmp_path, 'b.json', worse), '--out', out]) == 0

    comparison = json.loads((tmp_path / 'comparison.json').read_text())
    assert comparison['comparable'] is True
    assert [entry['key'] for entry in comparison['checks']['deployments']['newlyFailing']] == [['X', '1']]
    assert 'newlyFailing 1' in capsys.readouterr().out


def test_aComparisonThatCannotBeTrustedSaysSoOnTheWayOut(tmp_path, capsys):
    """Two runs produced by different versions of the checks: a moved row could
    be the check having changed rather than the data."""
    from rca_metadata.cli import compareMain

    other = {**REPORT, 'parameters': {'commit': 'def', 'dirty': False}}
    compareMain([written(tmp_path, 'a.json', REPORT), written(tmp_path, 'b.json', other),
                 '--out', str(tmp_path / 'c.json')])
    printed = capsys.readouterr().out
    assert 'cannot be compared' in printed
    assert 'different commits' in printed


## --- the baseline the workflow hands the run ---

def test_theVerifyWorkflowTellsTheRunWhatItIsComparedAgainst():
    """The report records the baseline so the dashboard knows whether a
    comparison exists. Nothing else notices if the flag is renamed on one side:
    the run still succeeds, the report says no baseline, and the Changes view is
    quietly empty on every run that had one."""
    import os

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, '.github', 'workflows', 'verify.yaml')) as handle:
        workflow = handle.read()
    assert '--baseline "$BASELINE"' in workflow
    assert 'BASELINE: ${{ inputs.baseline_ref }}' in workflow


def test_theBaselineFlagIsTheOneTheWorkflowPasses():
    import argparse
    import contextlib
    import io

    from rca_metadata import cli

    ## argparse is the only thing that knows the flag exists, and the parser is
    ## built inside main(). --help prints it and exits, which is enough.
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed), contextlib.suppress(SystemExit):
        cli.main(['--help'])
    assert '--baseline' in printed.getvalue()


def test_aRunGivenNoBaselineRecordsNoneRatherThanAnEmptyString():
    """The workflow always passes the flag; the value is empty when there is no
    baseline. An empty string is truthy enough in a browser to send it looking
    for a comparison that is not there."""
    from rca_metadata.report import buildReport
    from tests.test_report import RESULT

    assert buildReport({**RESULT, 'comparedWith': ''})['comparedWith'] is None
