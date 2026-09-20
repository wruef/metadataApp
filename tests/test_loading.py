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


def test_hitlNotesSurvivesASheetWhoseNotesAreAllBlank():
    """pandas reads an all-blank column as float, and .str on a float column
    raises. The sensor sheet is empty today, so the first note-less sign-off
    written from the dashboard would have taken every later run down."""
    import numpy as np
    import pandas as pd

    from rca_metadata.loading import hitlNotes

    sheet = pd.DataFrame({'Reviewers': ['WR'], 'DateReviewed': ['9/18/26'], 'Status': ['Clear'],
                          'HITLnotes': [np.nan]}, index=pd.Index(['ATAPL-1'], name='assetID'))
    assert hitlNotes({'sensorBulk': sheet}) == {'sensorBulk': []}


## --- sign-offs that no longer match anything ---

def signOffSheet(rows):
    """A 2i-HITL sheet: the key is the index, as loadHITL leaves it."""
    columns = ['key', 'Reviewers', 'DateReviewed', 'Status', 'HITLnotes']
    frame = pd.DataFrame(rows, columns=columns).set_index('key')
    frame.index.name = 'githubFile'
    return frame


def test_aSignOffNoRowClaimsIsReported():
    """The calibration file it was written against is gone from
    asset-management, so no row carries the sign-off and no screen shows it."""
    from rca_metadata.loading import unmatchedSignOffs

    sheet = signOffSheet([
        {'key': 'ATAPL-1__20140101.csv', 'Reviewers': 'WR', 'DateReviewed': '5/1/19',
         'Status': 'Clear', 'HITLnotes': 'checked against the vendor original'},
        {'key': 'ATAPL-2__20150101.csv', 'Reviewers': 'WR', 'DateReviewed': '5/1/19',
         'Status': 'Clear', 'HITLnotes': ''},
    ])
    found = unmatchedSignOffs({'calibrations': sheet},
                              {'calibrations': {'ATAPL-2__20150101.csv'}})
    assert [row['key'] for row in found['calibrations']] == ['ATAPL-1__20140101.csv']
    assert found['calibrations'][0]['notes'] == 'checked against the vendor original'
    assert found['calibrations'][0]['reviewers'] == 'WR'


def test_aSignOffWithNoDecisionIsNotReported():
    """A key with nothing written against it is a line somebody added and never
    came back to. Listing those buries the judgements that were actually made."""
    from rca_metadata.loading import unmatchedSignOffs

    sheet = signOffSheet([{'key': 'ATAPL-3__20160101.csv', 'Reviewers': '',
                           'DateReviewed': '', 'Status': '', 'HITLnotes': ''}])
    assert unmatchedSignOffs({'calibrations': sheet}, {'calibrations': set()}) == {
        'calibrations': []}


def test_everyCheckGetsAnEntryEvenWithNothingOrphaned():
    """The dashboard reads a count per check, and a missing key is a different
    thing from a zero."""
    from rca_metadata.loading import unmatchedSignOffs

    sheet = signOffSheet([{'key': 'ATAPL-4__20170101.csv', 'Reviewers': 'WR',
                           'DateReviewed': '5/1/19', 'Status': 'Clear', 'HITLnotes': ''}])
    found = unmatchedSignOffs({'calibrations': sheet, 'sensorBulk': signOffSheet([])},
                              {'calibrations': {'ATAPL-4__20170101.csv'}})
    assert found == {'calibrations': [], 'sensorBulk': []}


def test_theRealSheetsHaveOrphansAndTheyCarryDecisions():
    """Against the team's own sheets and the committed report: the orphans are
    real, and every one of them is a judgement somebody made."""
    import json

    from rca_metadata.loading import loadHITL, unmatchedSignOffs

    with open('dashboard/test/fixtures/report.json') as handle:
        report = json.load(handle)
    seen = {name: {str(row.get('hitlKey')) for row in check.get('rows', [])}
            for name, check in report['checks'].items()}
    found = unmatchedSignOffs(loadHITL(), seen)
    assert found['deployments'], 'the deployment sheet has orphans today'
    assert all(row['status'].strip() for rows in found.values() for row in rows)
