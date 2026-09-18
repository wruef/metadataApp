"""The pinned versions, and that the two files naming them agree.

Comparison is exact to the last digit a vendor file publishes, so the library
that parses the csv is part of what produced the numbers. Two files name it --
``constraints.txt`` for pip and ``environment.yml`` for conda -- and a reviewer
whose laptop reads a different pandas than the runner reaches different verdicts
without anything looking wrong. Nothing but a test keeps them together.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

## What a published run is produced with, and so what has to be pinned in both.
PINNED = ('pandas', 'numpy')


def read(name):
    with open(os.path.join(ROOT, name)) as handle:
        return handle.read()


def constraintPins():
    """``package==version`` lines, ignoring comments."""
    return dict(re.findall(r'^([A-Za-z0-9_.-]+)==([0-9][^\s]*)$', read('constraints.txt'),
                           re.MULTILINE))


def condaPins():
    """``- package=version`` entries, ignoring the unpinned ones."""
    return dict(re.findall(r'^\s*-\s+([A-Za-z0-9_.-]+)=([0-9][^\s]*)$', read('environment.yml'),
                           re.MULTILINE))


def test_bothFilesPinTheLibrariesThatReadTheNumbers():
    assert set(PINNED) <= set(constraintPins())
    assert set(PINNED) <= set(condaPins())


def test_thePipAndCondaPinsAgree():
    """A reviewer reproducing a run with conda has to get the versions the
    runner produced it with, or the two disagree about a coefficient and
    neither of them is wrong."""
    pip, conda = constraintPins(), condaPins()
    assert {name: pip[name] for name in PINNED} == {name: conda[name] for name in PINNED}


def test_theVerifyWorkflowInstallsAgainstTheConstraints():
    """The pins only bind what actually reads them."""
    assert '-c constraints.txt' in read('.github/workflows/verify.yaml')


def test_thePackageClaimsAFloorRatherThanThePin():
    """The floor is what the package can be installed against; the pin is what
    a published run is produced with. A pin here would stop the test matrix
    resolving anything else, and resolving something else is how pandas 3
    removing a function was caught at all."""
    pyproject = read('pyproject.toml')
    assert '"pandas>=2.1"' in pyproject
    assert f'"pandas=={constraintPins()["pandas"]}"' not in pyproject


def workflowPython(name):
    """The ``PYTHON_VERSION`` a workflow runs with."""
    return re.search(r'PYTHON_VERSION:\s*"?([0-9.]+)"?', read(f'.github/workflows/{name}')).group(1)


def test_theWorkflowsRunThePythonTheEnvironmentNames():
    """environment.yml says it matches the python in verify.yaml. Three
    workflows each spell that version out by hand, and the pinned pandas needs
    the version they name, so nothing but this keeps the four together."""
    conda = re.search(r'^\s*-\s+python=([0-9.]+)$', read('environment.yml'), re.MULTILINE).group(1)
    for workflow in ('verify.yaml', 'prune-runs.yaml', 'extract-serials.yaml'):
        assert workflowPython(workflow) == conda, workflow


def test_theTestMatrixDoesNotInstallAgainstTheConstraints():
    """It is the early-warning system. Pinning it would silence the one signal
    that says a future library will break this code. The file is named in a
    comment there, which is why this looks for the flag rather than the name."""
    assert '-c constraints.txt' not in read('.github/workflows/tests.yaml')
