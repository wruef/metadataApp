"""Tests for reading the 2i-HITL sheets."""

import pandas as pd

from rca_metadata.loading import hitlNotes


def sheet(notes):
    return pd.DataFrame({'HITLnotes': notes})


def test_everyNoteInTheSheetIsOffered():
    """A reviewer picks from what the team has already written, so nothing in
    the sheet may be missing from the list."""
    written = ['shipboard cal?? sn 344', 'uses 2015 volume scatter calibration']
    assert set(hitlNotes({'calibrations': sheet(written)})['calibrations']) == set(written)


def test_theMostUsedReasonComesFirst():
    """The shared vocabulary is what a queue is worked with; the remarks about
    one particular file belong below it."""
    written = ['deployment sheet is correct; script pulled old file',
               'verified with IP address ping', 'verified with IP address ping']
    assert hitlNotes({'deployments': sheet(written)})['deployments'] == [
        'verified with IP address ping',
        'deployment sheet is correct; script pulled old file']


def test_aBlankNoteIsNotAReason():
    """Most rows carry none at all, and one note in the sheet today is a single
    space."""
    written = ['verified with deployment logs and images', None, '', ' ']
    assert hitlNotes({'deployments': sheet(written)})['deployments'] == [
        'verified with deployment logs and images']


def test_surroundingSpaceIsNotASecondReason():
    written = ['verified with post-recovery logs', ' verified with post-recovery logs ']
    assert hitlNotes({'deployments': sheet(written)})['deployments'] == [
        'verified with post-recovery logs']


def test_equallyUsedReasonsAreOrderedByTheirWording():
    """Two notes used the same number of times have to come back in the same
    order every run, or the report churns between two spellings of one list."""
    assert hitlNotes({'calibrations': sheet(['beta', 'alpha'])})['calibrations'] == [
        'alpha', 'beta']


def test_everySheetGetsItsOwnReasons():
    """A calibration reason means nothing on a deployment row."""
    notes = hitlNotes({'calibrations': sheet(['is this a duplicate file?']),
                       'deployments': sheet(['verified with IP address ping'])})
    assert notes == {'calibrations': ['is this a duplicate file?'],
                     'deployments': ['verified with IP address ping']}


def test_theRealSheetsAreReadable():
    """Against the team's own sheets, not a fixture: every note they hold is
    offered, and none of them is blank."""
    from rca_metadata.loading import loadHITL

    notes = hitlNotes(loadHITL())
    assert set(notes) == {'calibrations', 'deployments', 'sensorBulk'}
    ## sensorBulk is new and nobody has written in it yet; an empty vocabulary
    ## is a sheet waiting for its first sign-off, not a fault.
    for sheetNotes in notes.values():
        assert all(note.strip() for note in sheetNotes)
    assert notes['calibrations'] and notes['deployments']
