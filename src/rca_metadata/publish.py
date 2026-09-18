"""Proposing generated files as a pull request, on the author's own fork.

Three things this package produces are changes to shared records rather than
findings of its own: the deployment history published to the ``deployments``
repository, the position corrections that rewrite asset-management's deployment
sheets, and 2i-HITL sign-offs. Everything about proposing them -- which branch a
fork's requests target, what each request says, writing the files to disk first
-- is here and only here. It used to be spread across cli.py, positions.py and
history.py, each building its own body.

None of them go to the upstream repository. Each author works from their own
fork or clone, and that is what this opens a pull request against -- the author
chooses which, and nothing here defaults to an upstream. The onward pull request
from the fork to the upstream repository is raised by hand, so a person decides
when generated output is worth proposing to everyone else.

The shape is the same each time: one commit carrying every changed file, on a
new branch, under whoever's token is doing the asking.
"""

import datetime
import os

import requests

from . import history, positions

API = 'https://api.github.com/repos/'

## Regular file, as git spells it in a tree entry.
FILE_MODE = '100644'


class PullRequest:
    """Opens pull requests against one repository -- the author's own fork.

    ``repo`` is required and deliberately has no default: pointing this at a
    shared repository by accident is exactly what the fork step prevents. The
    token decides authorship, which is the point -- from the dashboard it is the
    reviewer's own, so the ``Reviewers`` column fills honestly.
    """

    def __init__(self, repo, token=None, base='main', session=None):
        self.repo, self.base = repo, base
        self.session = session or requests.Session()
        token = token or os.environ.get('GITHUB_TOKEN')
        if token:
            self.session.headers['Authorization'] = 'Bearer ' + token
        self.session.headers['Accept'] = 'application/vnd.github+json'

    def _get(self, path):
        response = self.session.get(f'{API}{self.repo}/{path}')
        response.raise_for_status()
        return response.json()

    def _post(self, path, body):
        response = self.session.post(f'{API}{self.repo}/{path}', json=body)
        response.raise_for_status()
        return response.json()

    def open(self, files, title, body='', branch=None):
        """Propose ``files`` -- a {path: text} mapping -- as a pull request.

        Returns the pull request's url, or None when the files match what the
        repository already holds. Nothing is created in that case: an empty
        pull request is noise, and telling the caller nothing changed is more
        useful than opening one.
        """
        branch = branch or 'metadata-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
        ## Every write lands on a branch of the author's fork, reviewed there
        ## before they raise the onward pull request to the upstream repository.
        baseRef = self._get(f'git/ref/heads/{self.base}')
        baseSha = baseRef['object']['sha']
        baseTree = self._get(f'git/commits/{baseSha}')['tree']['sha']

        ## Content goes inline in the tree, so each file needs no separate blob.
        tree = self._post('git/trees', {
            'base_tree': baseTree,
            'tree': [{'path': path, 'mode': FILE_MODE, 'type': 'blob', 'content': content}
                     for path, content in sorted(files.items())]})
        if tree['sha'] == baseTree:
            return None

        commit = self._post('git/commits', {
            'message': title, 'tree': tree['sha'], 'parents': [baseSha]})
        self._post('git/refs', {'ref': f'refs/heads/{branch}', 'sha': commit['sha']})
        return self._post('pulls', {
            'title': title, 'body': body, 'head': branch, 'base': self.base})['html_url']


## ---- the products, and what each one's pull request says ----

## The branch each repository's pull requests target, by repository name. The
## fork is the reviewer's own, so the owner varies and the name does not.
## Inferred from the fork's name before, which made a fork called anything else
## -- deployments-2026, or a rename -- propose against a branch that is not
## there, and the failure arrives from the GitHub API rather than from here.
BASE_BRANCH = {'deployments': 'main', 'metadataApp': 'main',
               'asset-management': 'master', 'calibrationFiles': 'master'}
DEFAULT_BASE = 'master'

## What every pull request ends with: it is proposed to a fork and raised
## upstream by a person, and that has to be said where the reviewer reads it.
BY_HAND = 'Review here, then raise the pull request to the upstream {upstream} repository by hand.'

HISTORY_BODY = ('Regenerated from the asset-management deployment sheets and the calibration '
                'files in both repositories.\n\n' + BY_HAND.format(upstream='deployments'))


def positionsBody(upstream):
    return ('Latitude, longitude and depths taken from the RCA position spreadsheet.\n\n'
            + BY_HAND.format(upstream=upstream))


def baseBranchOf(fork):
    """The branch a fork's pull requests target."""
    return BASE_BRANCH.get(fork.split('/')[-1], DEFAULT_BASE)


def writeFiles(files, outDir):
    """The generated files on disk, so they can be read before they are proposed."""
    os.makedirs(outDir, exist_ok=True)
    for name, content in files.items():
        path = os.path.join(outDir, name)
        os.makedirs(os.path.dirname(path) or outDir, exist_ok=True)
        with open(path, 'w') as handle:
            handle.write(content)
    return len(files)


def propose(files, fork, token, title, body, outDir):
    """Write the files, and offer them to a fork when one is named.

    Writing to disk always happens: a generated file you can look at before
    proposing it is the point. The pull request is the optional half.
    """
    print(f'wrote {writeFiles(files, outDir)} files to {outDir}')
    if not fork:
        print('no --fork given, so nothing was proposed')
        return None
    url = PullRequest(fork, token=token, base=baseBranchOf(fork)).open(files, title, body)
    print(f'opened {url}' if url else f'{fork} already matches these files -- nothing to propose')
    return url


def publishHistory(rows, pullRequest, title=None):
    """Propose the deployment history to the author's fork of the deployments repo.

    Returns the pull request url, or None when nothing changed -- most runs
    between cruises change nothing, and an empty pull request is noise.
    """
    title = title or f'Deployment history, {datetime.date.today().isoformat()}'
    return pullRequest.open(history.historyFiles(rows), title, body=HISTORY_BODY)


def publishPositions(corrected, pullRequest, title=None):
    """Propose corrected deployment sheets to the author's fork of asset-management.

    Returns the pull request url, or None when the sheets already agree with the
    spreadsheet. What changed is in the position check's own rows, so no separate
    change log is written here.
    """
    return _proposePositions(pullRequest, positions.positionFiles(corrected), title, 'asset-management')


def publishNodePositions(corrected, pullRequest, title=None):
    """Propose corrected node deployments to the author's fork of the deployments repo."""
    return _proposePositions(pullRequest, positions.nodePositionFile(corrected), title, 'deployments')


def _proposePositions(pullRequest, files, title, upstream):
    if not files:
        return None
    title = title or f'Deployment positions, {datetime.date.today().isoformat()}'
    return pullRequest.open(files, title, body=positionsBody(upstream))
