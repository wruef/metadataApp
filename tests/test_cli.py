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
