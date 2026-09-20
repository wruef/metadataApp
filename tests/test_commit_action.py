"""The publish step's shell, run against real git repositories.

Two workflows write to reports/: a verification run publishing and a prune
deleting. They can run at the same time, which is why the step rebases over
whatever landed meanwhile and resolves the conflict itself -- the -latest copies
are this run's, and the index is rebuilt from the reports now on disk.

That reasoning was only ever reasoning. It ran on a runner, against a conflict
nobody could arrange on purpose, and a mistake in it would show up as a lost
run. So the shell is read out of the action here and run for real: two clones
of one repository, both publishing, the second one rebasing over the first.
"""

import json
import os
import shutil
import subprocess
import sys
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTION = os.path.join(ROOT, '.github', 'actions', 'commit-reports', 'action.yml')

pytestmark = pytest.mark.skipif(shutil.which('git') is None, reason='needs git')


def actionShell():
    """The step's script, exactly as the runner would execute it.

    Sliced out of the yaml rather than parsed, so this needs no yaml library:
    the action has one step and one block scalar, and a second one would show up
    here as a test that stopped covering the interesting half.
    """
    with open(ACTION) as handle:
        text = handle.read()
    head, marker, body = text.partition('\n      run: |\n')
    assert marker, 'the action no longer has a single `run: |` block'
    assert 'run: |' not in head, 'the action grew a second step'
    return textwrap.dedent(body)


def git(cwd, *args, check=True):
    return subprocess.run(['git', *args], cwd=cwd, check=check,
                          capture_output=True, text=True)


def report(runAt):
    """The smallest thing rebuildIndex will read: it takes runAt off each one."""
    return {'runAt': runAt, 'checks': {}, 'sources': {}}


def write(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as handle:
        json.dump(body, handle)


def publish(clone, stamp, latest=True):
    """What a verification run leaves on disk before the step runs.

    Every run rewrites the index, which is why two of them conflict on it. Only
    a production run rewrites latest.json.
    """
    write(os.path.join(clone, 'reports', f'report_{stamp}.json'), report(stamp))
    write(os.path.join(clone, 'reports', 'index.json'),
          [{'name': f'report_{stamp}.json', 'runAt': stamp}])
    if latest:
        write(os.path.join(clone, 'reports', 'latest.json'), report(stamp))


def runStep(clone, message='Verification run', branch='main'):
    """The action's shell, with index-metadata on PATH as the runner has it."""
    env = {**os.environ, 'MESSAGE': message, 'MESSAGE_FILE': '', 'BRANCH': branch,
           'PATH': os.path.dirname(sys.executable) + os.pathsep + os.environ['PATH']}
    return subprocess.run(['bash', '-c', actionShell()], cwd=clone, env=env,
                          capture_output=True, text=True)


@pytest.fixture
def origin(tmp_path):
    """A bare repository with one commit on main, and a way to clone it."""
    bare = tmp_path / 'origin.git'
    git(tmp_path, 'init', '--bare', '-b', 'main', str(bare))
    seed = tmp_path / 'seed'
    git(tmp_path, 'clone', str(bare), str(seed))
    git(seed, 'config', 'user.email', 'test@example.com')
    git(seed, 'config', 'user.name', 'Test')
    write(str(seed / 'reports' / 'index.json'), [])
    git(seed, 'add', '-A')
    git(seed, 'commit', '-q', '-m', 'seed')
    git(seed, 'push', '-q', 'origin', 'main')

    def clone(name):
        path = tmp_path / name
        git(tmp_path, 'clone', '-q', str(bare), str(path))
        git(path, 'config', 'user.email', 'test@example.com')
        git(path, 'config', 'user.name', 'Test')
        return path

    return clone


def test_aRunWithNothingToPublishSaysSoAndSucceeds(origin):
    result = runStep(origin('quiet'))
    assert result.returncode == 0, result.stderr
    assert 'Nothing to commit' in result.stdout


def test_aRunOnItsOwnPublishes(origin):
    clone = origin('alone')
    publish(clone, '20260101T000000Z')
    assert runStep(clone).returncode == 0

    read = origin('read')
    assert os.path.isfile(read / 'reports' / 'report_20260101T000000Z.json')


def test_twoRunsPublishingAtOnceBothLand(origin):
    """The second rebases over the first. Both reports have to survive it --
    losing one is the failure a shared concurrency group used to cause, and the
    reason this step resolves its own conflicts instead."""
    first, second = origin('first'), origin('second')
    publish(first, '20260101T000000Z')
    publish(second, '20260102T000000Z')

    assert runStep(first).returncode == 0
    result = runStep(second)
    assert result.returncode == 0, result.stdout + result.stderr

    read = origin('read')
    published = sorted(os.listdir(read / 'reports'))
    assert 'report_20260101T000000Z.json' in published
    assert 'report_20260102T000000Z.json' in published


def test_theLaterRunsLatestCopyWins(origin):
    """Both runs rewrite latest.json, so it conflicts every time. The run that
    finishes second is the newer state of the world, and its copy is the one
    everybody reads."""
    first, second = origin('first'), origin('second')
    publish(first, '20260101T000000Z')
    publish(second, '20260102T000000Z')

    runStep(first)
    assert runStep(second).returncode == 0

    read = origin('read')
    with open(read / 'reports' / 'latest.json') as handle:
        assert json.load(handle)['runAt'] == '20260102T000000Z'


def test_theIndexEndsUpNamingEveryPublishedRun(origin):
    """Rebuilt from the reports on disk rather than merged, which is the whole
    reason a conflict on it is not a problem."""
    first, second = origin('first'), origin('second')
    publish(first, '20260101T000000Z')
    publish(second, '20260102T000000Z')
    runStep(first)
    assert runStep(second).returncode == 0

    read = origin('read')
    with open(read / 'reports' / 'index.json') as handle:
        index = json.load(handle)
    assert {entry['name'] for entry in index} == {
        'report_20260101T000000Z.json', 'report_20260102T000000Z.json'}


def test_aRunThatPublishesNoLatestCopyStillRebases(origin):
    """A run against a branch publishes under its own name and leaves
    latest.json alone, so the conflicting paths are not all present. The step
    used to ask git to check out three of them in one command, which fails
    whole when one of them is not in conflict."""
    first, second = origin('first'), origin('second')
    publish(first, '20260101T000000Z')
    publish(second, '20260102T000000Z', latest=False)

    runStep(first)
    result = runStep(second)
    assert result.returncode == 0, result.stdout + result.stderr

    read = origin('read')
    published = sorted(os.listdir(read / 'reports'))
    assert 'report_20260101T000000Z.json' in published
    assert 'report_20260102T000000Z.json' in published


def test_aPruneDeletingRunsRebasesOverAPublish(origin):
    """The other workflow that writes here deletes rather than adds. Its side of
    a conflicting path is the file being gone, which is a resolution git cannot
    check out -- there is nothing to check out -- so it has to be removed."""
    pruner = origin('pruner')
    publish(pruner, '20260101T000000Z')
    assert runStep(pruner).returncode == 0

    ## Cloned after that run landed, so it starts from the published state.
    publisher = origin('publisher')
    publish(publisher, '20260102T000000Z')
    assert runStep(publisher).returncode == 0

    ## The prune deletes the older run and rewrites the index, over a tree that
    ## has moved on since it read it.
    os.remove(pruner / 'reports' / 'report_20260101T000000Z.json')
    write(str(pruner / 'reports' / 'index.json'), [])
    result = runStep(pruner, message='Delete published runs')
    assert result.returncode == 0, result.stdout + result.stderr

    read = origin('read')
    published = os.listdir(read / 'reports')
    assert 'report_20260101T000000Z.json' not in published
    assert 'report_20260102T000000Z.json' in published
    with open(read / 'reports' / 'index.json') as handle:
        assert [entry['name'] for entry in json.load(handle)] == [
            'report_20260102T000000Z.json']
