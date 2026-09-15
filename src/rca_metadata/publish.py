"""Proposing generated files as a pull request, on the author's own fork.

Three things this package produces are changes to shared records rather than
findings of its own: the deployment history published to the ``deployments``
repository, the position corrections that rewrite asset-management's deployment
sheets, and 2i-HITL sign-offs.

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
