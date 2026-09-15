"""Tests for proposing generated files as a pull request.

Nothing here touches the network: the http session is a stand-in that records
what would have been sent.
"""

import pandas as pd
import pytest

from rca_metadata.history import historyFiles, publishHistory
from rca_metadata.positions import nodePositionFile, positionFiles
from rca_metadata.publish import PullRequest

BASE_TREE = 'basetree'


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class Session:
    """Answers the git data API, and records what was asked of it."""

    def __init__(self, treeSha='newtree'):
        self.headers = {}
        self.treeSha = treeSha
        self.posts = []

    def get(self, url):
        if 'git/ref/heads/' in url:
            return Response({'object': {'sha': 'basecommit'}})
        if 'git/commits/' in url:
            return Response({'tree': {'sha': BASE_TREE}})
        raise AssertionError('unexpected GET ' + url)

    def post(self, url, json):
        self.posts.append((url.split('/')[-1], json))
        if url.endswith('git/trees'):
            return Response({'sha': self.treeSha})
        if url.endswith('git/commits'):
            return Response({'sha': 'newcommit'})
        if url.endswith('git/refs'):
            return Response({})
        if url.endswith('pulls'):
            return Response({'html_url': 'https://github.com/me/fork/pull/1'})
        raise AssertionError('unexpected POST ' + url)


def pullRequest(session, repo='me/deployments'):
    return PullRequest(repo, token='t', session=session)


def test_changedFilesBecomeOnePullRequest():
    session = Session()
    url = pullRequest(session).open({'a.csv': 'one\n'}, 'A title')
    assert url == 'https://github.com/me/fork/pull/1'
    assert [name for name, _ in session.posts] == ['trees', 'commits', 'refs', 'pulls']


def test_nothingChangedOpensNothing():
    """Most runs between cruises change nothing, and an empty pull request is
    noise -- so the tree is built, compared, and abandoned."""
    session = Session(treeSha=BASE_TREE)
    assert pullRequest(session).open({'a.csv': 'one\n'}, 'A title') is None
    assert [name for name, _ in session.posts] == ['trees']


def test_everyFileGoesInOneCommit():
    session = Session()
    pullRequest(session).open({'b.csv': 'two\n', 'a.csv': 'one\n'}, 'A title')
    tree = dict(session.posts)['trees']
    assert [entry['path'] for entry in tree['tree']] == ['a.csv', 'b.csv']
    assert {entry['mode'] for entry in tree['tree']} == {'100644'}
    assert tree['base_tree'] == BASE_TREE


def test_theTokenDecidesAuthorship():
    session = Session()
    pullRequest(session)
    assert session.headers['Authorization'] == 'Bearer t'


def test_itGoesToTheRepositoryItWasGiven():
    """The destination is the author's own fork, never an upstream default."""
    session = Session()
    pullRequest(session, 'someone/their-own-fork').open({'a.csv': 'one\n'}, 'A title')
    assert all('someone/their-own-fork' in url for url in
               ['https://api.github.com/repos/someone/their-own-fork/pulls'])
    assert PullRequest('someone/their-own-fork', session=session).repo == 'someone/their-own-fork'


def test_pullRequestNeedsARepository():
    with pytest.raises(TypeError):
        PullRequest()


def test_theBranchIsNewEachTime():
    session = Session()
    pullRequest(session).open({'a.csv': 'one\n'}, 'A title')
    ref = dict(session.posts)['refs']
    assert ref['ref'].startswith('refs/heads/metadata-')


def test_thePullRequestSaysWhatToDoNext():
    session = Session()
    rows = [{'sensorType': 'CTDBPN', 'referenceDesignator': 'CE02SHBP-LJ01D-06-CTDBPN106',
             'startTime': '2014-09-10 15:43:00', 'endTime': '', 'assetID': 'A',
             'instrumentSN': ['1'], 'lat': 1.0, 'lon': 2.0,
             'githubCalibrationFile': 'none', 'vendorCalibrationFile': 'none'}]
    publishHistory(rows, pullRequest(session))
    assert 'by hand' in dict(session.posts)['pulls']['body']


## --- what goes in which repository ---

def deployments(*refDes):
    return pd.DataFrame([{'Reference Designator': r, 'lat': 1.0, 'lon': 2.0} for r in refDes])


def test_nodeRowsDoNotLandInTheInstrumentSheets():
    """A node row filed into an array sheet would append it to the wrong record."""
    frame = deployments('CE02SHBP-LJ01D-06-CTDBPN106', 'CE02SHBP-LJ01D')
    files = positionFiles(frame)
    assert list(files) == ['deployment/CE02SHBP_Deploy.csv']
    assert 'CE02SHBP-LJ01D\n' not in files['deployment/CE02SHBP_Deploy.csv']


def test_nodeRowsGoToTheirOwnFile():
    files = nodePositionFile(deployments('CE02SHBP-LJ01D-06-CTDBPN106', 'CE02SHBP-LJ01D'))
    assert list(files) == ['NODE_deployments.csv']
    assert len(files['NODE_deployments.csv'].splitlines()) == 2


def test_noNodeRowsMeansNoNodeFile():
    assert nodePositionFile(deployments('CE02SHBP-LJ01D-06-CTDBPN106')) == {}


def test_referenceDesignatorListIsPublishedAlongsideTheHistory():
    rows = [{'sensorType': 'CTDBPN', 'referenceDesignator': 'CE02SHBP-LJ01D-06-CTDBPN106',
             'startTime': '2014-09-10 15:43:00', 'endTime': '', 'assetID': 'A',
             'instrumentSN': ['1'], 'lat': 1.0, 'lon': 2.0,
             'githubCalibrationFile': 'none', 'vendorCalibrationFile': 'none'}]
    files = historyFiles(rows)
    assert files['refDesList.csv'] == 'referenceDesignator\nCE02SHBP-LJ01D-06-CTDBPN106\n'
