"""Tests for the run report: severity, the two-state rule, and round-tripping."""

import json
import os
import subprocess

import pytest

from rca_metadata.report import (SCHEMA_VERSION, asDifference, buildReport, scoreRows,
                                 severityOf, summarise, writeReport)


def test_agreeingRowIsOk():
    assert severityOf('sensorBulk', {'verdict': 'MATCH'}) == 'ok'


def test_disagreementIsAProblem():
    assert severityOf('sensorBulk', {'verdict': 'MISMATCH'}) == 'problem'


def test_nothingComparedIsNotAPass():
    assert severityOf('calibrations', {'vendorMatch': 'NOTCOMPARED'}) == 'unchecked'


def test_aRowTakesItsWorstVerdict():
    """A deployment whose raw serial matches but whose calibration file is
    missing is not a pass."""
    row = {'verificationStatus': 'VERIFIED', 'rawFile_verify': 'MATCH',
           'image_verify': 'NAN', 'calFile_verify': 'NO_VALID_FILE'}
    assert severityOf('deployments', row) == 'problem'


def test_verdictDetailAfterAColonIsIgnored():
    row = {'rawFile_verify': 'MISMATCH: raw: 1130: ATAPL-58322-00003'}
    assert severityOf('deployments', row) == 'problem'


def test_anUnmappedVerdictGoesInFrontOfAPersonRatherThanPassing():
    assert severityOf('positions', {'verdict': 'SOMETHING_NEW'}) == 'review'


def test_aCheckWithNoMappingIsNotScored():
    assert severityOf('nosuchcheck', {'verdict': 'MISMATCH'}) == 'ok'


## --- the two-state rule ---

def test_aSignedOffRowKeepsItsFailingCheck():
    """A sign-off puts the row in its own category rather than among the
    problems, and the check it failed stays visible on it -- cleared, and
    noted. Some signed-off calibrations still hold real transcription errors."""
    rows = scoreRows('calibrations', [{'vendorMatch': 'MISMATCH', 'HITLstatus': 'Clear'}])
    assert rows[0]['cleared'] is True
    assert rows[0]['severity'] == 'cleared'
    assert rows[0]['finding'] == 'problem'


def test_notClearIsNotCleared():
    rows = scoreRows('calibrations', [{'vendorMatch': 'MISMATCH', 'HITLstatus': 'NotClear'}])
    assert rows[0]['cleared'] is False


def test_rowWithNoSignOffIsNotCleared():
    assert scoreRows('positions', [{'verdict': 'MATCH'}])[0]['cleared'] is False


def test_summaryCountsEverySeverityAndTheClearedRows():
    rows = scoreRows('sensorBulk', [
        {'verdict': 'MATCH'}, {'verdict': 'MISMATCH'},
        {'verdict': 'MISMATCH', 'HITLstatus': 'Clear'}, {'verdict': 'NO_BULK_SERIAL'}])
    assert summarise(rows) == {
        'problem': 1, 'review': 0, 'unchecked': 1, 'cleared': 1, 'ok': 1,
        'attention': 1, 'verified': 2, 'total': 4}


def test_aClearedRowIsItsOwnCategoryRatherThanAProblem():
    """Both rows disagree with the sensor bulk record. The signed-off one is not
    a problem and not work; the other is both."""
    signed, open_ = scoreRows('sensorBulk', [
        {'verdict': 'MISMATCH', 'HITLstatus': 'Clear'}, {'verdict': 'MISMATCH'}])
    assert signed['severity'] == 'cleared'
    assert open_['severity'] == 'problem'
    counts = summarise([signed, open_])
    assert counts['problem'] == 1
    assert counts['attention'] == 1
    assert counts['cleared'] == 1


def test_aClearedRowKeepsWhatTheCheckFound():
    """Three signed-off calibrations turned out to hold real transcription
    errors, so the finding may never be discarded by the sign-off."""
    row = scoreRows('sensorBulk', [{'verdict': 'MISMATCH', 'HITLstatus': 'Clear'}])[0]
    assert row['severity'] == 'cleared'
    assert row['finding'] == 'problem'


def test_aClearedRowThatAgreesKeepsAnAgreeingFinding():
    """The dashboard colours a sign-off by its finding -- green over an
    agreement, amber over a disagreement -- so the two must stay distinct."""
    row = scoreRows('sensorBulk', [{'verdict': 'MATCH', 'HITLstatus': 'Clear'}])[0]
    assert row['severity'] == 'cleared'
    assert row['finding'] == 'ok'


def test_signedOffRowsCountAsVerified():
    rows = scoreRows('sensorBulk', [
        {'verdict': 'MATCH'}, {'verdict': 'MISMATCH', 'HITLstatus': 'Clear'},
        {'verdict': 'MISMATCH'}])
    assert summarise(rows)['verified'] == 2


def test_aFlaggedRowIsStillWaitingOnSomeone():
    """NotClear is a reviewer asking for someone else, not a decision closing
    the row."""
    rows = scoreRows('sensorBulk', [{'verdict': 'MISMATCH', 'HITLstatus': 'NotClear'}])
    assert summarise(rows)['attention'] == 1


def test_theProblemCountLeavesOutWhatWasSignedOff():
    """The rail colours itself red on an open problem, so a problem somebody
    has already dealt with must not light it."""
    rows = scoreRows('sensorBulk', [
        {'verdict': 'MISMATCH', 'HITLstatus': 'Clear'}, {'verdict': 'MATCH'}])
    counts = summarise(rows)
    assert counts['problem'] == 0
    assert counts['attention'] == 0


def test_aSettledRowNobodySignedOffIsNotWork():
    rows = scoreRows('sensorBulk', [{'verdict': 'MATCH'}, {'verdict': 'NO_BULK_SERIAL'}])
    assert summarise(rows)['attention'] == 0


## --- the document ---

def test_differencesAreNamedNotPositional():
    recorded = ['ATAPL-67627-00001__20150423', 'CC_pa0', 1.73, 1.733, -3e-07, 'vendor']
    assert asDifference(recorded) == {
        'file': 'ATAPL-67627-00001__20150423', 'coefficient': 'CC_pa0',
        'github': 1.73, 'expected': 1.733, 'difference': -3e-07, 'source': 'vendor'}


RESULT = {
    'runAt': '2026-09-15T12:00:00',
    'sources': {'assetManagement': {'repo': 'o/am', 'ref': 'master', 'local': None}},
    'sensorBulk': [{'assetID': 'ATAPL-1', 'verdict': 'MISMATCH'}],
    'calibrations': {'files': [{'fileName': 'a.csv', 'vendorMatch': 'MISMATCH',
                                'differences': [['a', 'CC_x', 1.0, 2.0, -1.0, 'vendor']]}],
                     'missingFromGithub': ['b']},
    'deploymentSheets': [], 'deployments': [], 'positions': None,
}


def test_reportCarriesItsSchemaVersionAndProvenance(tmp_path):
    doc = buildReport(RESULT, str(tmp_path))
    assert doc['schemaVersion'] == SCHEMA_VERSION
    assert doc['runAt'] == '2026-09-15T12:00:00'
    assert doc['sources']['assetManagement']['ref'] == 'master'
    ## Comparison is exact to the last digit a vendor file publishes, so the
    ## libraries that parsed it belong in the provenance beside the commit.
    assert set(doc['parameters']) == {'commit', 'dirty', 'python', 'pandas'}


def test_theReportCarriesTheReasonsASignOffPicksFrom():
    """The dashboard offers the team's own wording, so the run has to hand it
    over -- the sheets hold notes for rows a run does not have."""
    result = {**RESULT, 'hitlNotes': {'deployments': ['verified with IP address ping']}}
    assert buildReport(result)['hitlNotes']['deployments'] == ['verified with IP address ping']


def test_aRunWithNoSheetsCarriesNoReasons():
    assert buildReport(RESULT)['hitlNotes'] == {}


def test_aCheckThatDidNotRunIsAbsentRatherThanEmpty():
    assert 'positions' not in buildReport(RESULT)['checks']


def test_vendorFilesWithNoGithubFileAreCarried():
    assert buildReport(RESULT)['checks']['calibrations']['missingFromGithub'] == ['b']


def test_theWholeReportSurvivesJsonRoundTrip(tmp_path):
    """The format this replaces could not be read back: its last column held a
    python list literal full of commas."""
    path = writeReport(buildReport(RESULT), str(tmp_path / 'report.json'))
    doc = json.load(open(path))
    difference = doc['checks']['calibrations']['rows'][0]['differences'][0]
    assert difference['coefficient'] == 'CC_x'
    assert difference['difference'] == -1.0


## --- provenance ---

def test_provenanceThatCannotBeDeterminedSaysSo(tmp_path, monkeypatch):
    """A report nobody can trace back to its inputs should look wrong, not fine."""
    monkeypatch.delenv('GITHUB_SHA', raising=False)
    from rca_metadata.report import gitProvenance
    assert gitProvenance(str(tmp_path))['commit'] == 'UNKNOWN'


def test_theWorkflowsShaIsAuthoritative(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_SHA', 'abc123')
    from rca_metadata.report import gitProvenance
    assert gitProvenance(str(tmp_path))['commit'] == 'abc123'


def test_aSourceRecordsWhatItsRefResolvedTo():
    """A ref names what was asked for; only the commit makes two runs
    comparable, because master moves."""
    from rca_metadata.report import describeSource

    class Source:
        repo, ref = 'o/r', 'master'
        ## This repository, found rather than written down. The path was fixed
        ## to one laptop, so the test passed only there: anywhere else the
        ## directory is absent, the commit reads UNKNOWN, and the assertion
        ## below fails for a reason that has nothing to do with the code.
        local = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    described = describeSource(Source())
    assert described['ref'] == 'master'
    assert len(described['commit']) == 40


def test_theClonedRepositoriesDoNotMakeARunLookDirty():
    """A run clones the repositories it reads into repos/, and a baseline run
    into baseline/. Untracked, they made `git status --porcelain` report the
    tree as dirty, so every CI run stamped itself `dirty: true` and disqualified
    itself as a comparison baseline — which is the one thing the pre-cruise
    check needs. They are inputs, and the commit each was read at is recorded
    under `sources` where it belongs.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(os.path.join(root, '.git')):
        pytest.skip('not a git checkout')
    for directory in ('repos', 'baseline'):
        ignored = subprocess.run(
            ['git', '-C', root, 'check-ignore', '-q', directory + '/asset-management'])
        assert ignored.returncode == 0, f'{directory}/ is not ignored, so a run reads as dirty'


def test_anUncommittedInputStillMakesARunDirty():
    """The position spreadsheet is picked up by a glob, so an uncommitted drop
    is read by the run and has to show. Ignoring untracked files wholesale would
    have hidden exactly that."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(os.path.join(root, '.git')):
        pytest.skip('not a git checkout')
    ignored = subprocess.run(
        ['git', '-C', root, 'check-ignore', '-q', 'inputs/RSN_Positions_TEAM_20260918.xlsx'])
    assert ignored.returncode != 0, 'a spreadsheet drop must not be ignored'


def test_anUnresolvedCommitSaysUnknownRatherThanNothing():
    """Read over the API, or from a directory copied rather than cloned,
    there is nothing to ask for a commit. That has to read as unknown, not
    as absent: absent looked fine, and two runs were compared while neither
    recorded which asset-management they had read."""
    from rca_metadata.report import describeSource

    class NoCheckout:
        repo, ref, local = 'o/r', 'master', None

    class NotAClone:
        repo, ref, local = 'o/r', 'master', '/tmp'

    assert describeSource(NoCheckout())['commit'] == 'UNKNOWN'
    assert describeSource(NotAClone())['commit'] == 'UNKNOWN'


## --- the report has to be readable by something other than python ---

def test_nonFiniteValuesBecomeNull(tmp_path):
    """Python writes float('nan') as the bare token NaN, which is valid Python
    and invalid JSON. Python reads it back without complaint, so the report can
    look fine from this side while every browser refuses to parse it."""
    result = {**RESULT, 'sensorBulk': [{'assetID': 'A', 'bulkSerial': float('nan'),
                                        'verdict': 'MISMATCH'}]}
    path = writeReport(buildReport(result), str(tmp_path / 'report.json'))
    row = json.load(open(path))['checks']['sensorBulk']['rows'][0]
    assert row['bulkSerial'] is None


def test_noPythonOnlyTokensSurviveIntoTheFile(tmp_path):
    result = {**RESULT, 'sensorBulk': [
        {'assetID': 'A', 'bulkSerial': float('nan'), 'verdict': 'MISMATCH'},
        {'assetID': 'B', 'bulkSerial': float('inf'), 'verdict': 'MISMATCH'},
    ]}
    path = writeReport(buildReport(result), str(tmp_path / 'report.json'))
    text = open(path).read()
    for token in ('NaN', 'Infinity', '-Infinity'):
        assert token not in text


def test_nonFiniteValuesNestedInAListAreCaughtToo(tmp_path):
    """Calibration differences carry the values that disagree, and a missing
    vendor coefficient is nan."""
    result = {**RESULT, 'calibrations': {
        'files': [{'fileName': 'a.csv', 'vendorMatch': 'MISMATCH',
                   'differences': [['a', 'CC_x', 1.0, float('nan'), float('nan'), 'vendor']]}],
        'missingFromGithub': []}}
    path = writeReport(buildReport(result), str(tmp_path / 'report.json'))
    assert 'NaN' not in open(path).read()
    difference = json.load(open(path))['checks']['calibrations']['rows'][0]['differences'][0]
    assert difference['expected'] is None


## --- why a row reads the way it does ---

def test_everyRowCarriesAReasonAPersonCanRead():
    """A queue is worked by people, and 'MISMATCH: raw: 379: ATAPL-68020-00002'
    is a verdict, not a reason."""
    from rca_metadata.report import reasonOf

    assert reasonOf('deployments', {'rawFile_verify': 'MISMATCH: raw: 379: ATAPL-68020-00002',
                                    'cleared': False}) == \
        'The serial number in the raw archive is not the asset on the deployment sheet'


def test_aSignOffChangesWhatTheRowMeans():
    """The same verdict reads differently once a reviewer has looked at it, so
    the reason is taken after cleared is known."""
    from rca_metadata.report import reasonOf

    mismatch = {'vendorMatch': 'MISMATCH', 'cleared': False}
    assert 'nobody has reviewed it' in reasonOf('calibrations', mismatch)
    assert 'reviewed and cleared' in reasonOf('calibrations', {**mismatch, 'cleared': True})


def test_aRowWithNothingWrongSaysSo():
    from rca_metadata.report import reasonOf

    assert reasonOf('positions', {'verdict': 'MATCH', 'cleared': False}) == \
        'Latitude, longitude and depth match the spreadsheet'


def test_theWorstFindingIsTheOneReported():
    """A row can fail several checks at once; the reason names the one that
    decides its severity, in the same order the severity is taken."""
    from rca_metadata.report import reasonOf

    row = {'rawFile_verify': 'MISMATCH', 'image_verify': 'MISMATCH',
           'calFile_verify': 'NO_VALID_FILE', 'cleared': False}
    assert 'raw archive' in reasonOf('deployments', row)


def test_everyCheckCanExplainItself():
    from rca_metadata.report import REASONS, SEVERITY

    assert set(REASONS) == set(SEVERITY)
    for check, reason in REASONS.items():
        assert reason({'cleared': False}), check


def test_noReasonIsGivenToBothASettledRowAndAnOpenOne():
    """The sentence explains the badge, so the two must never contradict: a row
    reading 'a photograph confirms the asset' above a badge saying 'not checked'
    helps nobody. Run over every combination of verdicts each check can return.

    This caught 442 real deployments confirmed by one piece of evidence while
    the other had never been looked at.
    """
    import itertools

    from rca_metadata.report import REVIEWER_REASONS, SEVERITY, scoreRows

    for check, fields in SEVERITY.items():
        names = list(fields)
        rows = [dict(zip(names, values), HITLstatus=hitl)
                for values in itertools.product(*(list(fields[name]) for name in names))
                for hitl in ('NA', 'Clear', 'NotClear')]
        settled, open_ = set(), set()
        for row in scoreRows(check, rows):
            ## A sign-off describes what a person did, not what the check
            ## found, so it sits beside any severity.
            if row['reason'] in REVIEWER_REASONS:
                continue
            ## A cleared badge claims neither. It says a reviewer has been, and
            ## the sentence beside it names whatever they were looking at --
            ## which is the finding, open or settled.
            if row['cleared']:
                continue
            (settled if row['severity'] == 'ok' else open_).add(row['reason'])
        assert not settled & open_, f'{check}: {settled & open_}'
