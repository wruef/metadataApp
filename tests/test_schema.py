"""The report contract, checked from the python side.

`schema/report.json` names what a run report contains. The dashboard's
`schema.test.ts` reads the same file and checks the same committed report, so a
renamed field fails here, there, or both -- rather than turning into blank cells
in a published table with nothing complaining anywhere.
"""

import json
import os

import pytest

from rca_metadata.report import SCHEMA_VERSION, SEVERITIES, scoreRows, summarise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(*parts):
    with open(os.path.join(ROOT, *parts)) as handle:
        return json.load(handle)


@pytest.fixture(scope='module')
def schema():
    return load('schema', 'report.json')


@pytest.fixture(scope='module')
def report():
    """The committed report the dashboard's tests read, so both sides judge the
    same artifact rather than two that can drift apart."""
    return load('dashboard', 'test', 'fixtures', 'report.json')


def missing(required, present):
    return sorted(set(required) - set(present))


def test_everyOrphanedSignOffCarriesWhatTheContractNames(schema, report):
    """No check has a row for these, so the shape of the entry is the only thing
    standing between a judgement somebody made and a blank page."""
    orphaned = report['unmatchedSignOffs']
    assert orphaned, 'the committed report has orphaned sign-offs today'
    for rows in orphaned.values():
        for row in rows:
            assert not missing(schema['unmatchedSignOff'], row)
            assert row['status'].strip()


def test_theEmitterAndTheSchemaAgreeOnTheVersion(schema):
    assert schema['schemaVersion'] == SCHEMA_VERSION


def test_theEmitterAndTheSchemaAgreeOnTheCategories(schema):
    """Worst first, and the same list on both sides: the dashboard ranks a queue
    by the index of a severity in it."""
    assert schema['severities'] == SEVERITIES


def test_theReportCarriesEveryFieldTheContractNames(schema, report):
    assert not missing(schema['report'], report)
    assert report['schemaVersion'] == schema['schemaVersion']


def test_provenanceNamesWhatProducedTheNumbers(schema, report):
    """Comparison is exact to the last digit a vendor file publishes, so which
    library parsed the csv belongs in the record beside the commit."""
    assert not missing(schema['parameters'], report['parameters'])


def test_everySourceSaysWhichCommitItRead(schema, report):
    for name, source in report['sources'].items():
        if isinstance(source, dict):
            assert not missing(schema['source'], source), name
            ## the clone's path describes a machine, not the data it read
            assert 'local' not in source, name


def test_theRunStampIsUnambiguous(report):
    """A naive stamp is read as local time by the browser and sorts against the
    UTC file stamp in the run index."""
    assert report['runAt'].endswith('+00:00') or report['runAt'].endswith('Z')


def test_everyCheckSummarisesItself(schema, report):
    for name, check in report['checks'].items():
        assert not missing(schema['check'], check), name
        assert not missing(schema['summary'], check['summary']), name


def test_everyRowSaysWhatItIsAndWhy(schema, report):
    for name, check in report['checks'].items():
        for row in check['rows']:
            assert not missing(schema['row'], row), f'{name}: {row}'
            assert row['severity'] in schema['severities'], name
            assert row['finding'] in schema['severities'], name


def test_everyCheckCarriesItsOwnIdentifyingFields(schema, report):
    for name, required in schema['rows'].items():
        rows = report['checks'][name]['rows']
        assert rows, name
        for row in rows:
            assert not missing(required, row), f'{name}: {missing(required, row)}'


def test_theSummaryIsWhatTheEmitterWouldProduce(schema, report):
    """The counts are recomputed rather than trusted, so a fixture that has
    drifted from the emitter fails instead of quietly certifying it."""
    for name, check in report['checks'].items():
        assert summarise(check['rows']) == check['summary'], name


def test_scoringTheRowsBackProducesTheSameCategories(report):
    """Run the emitter over the report's own rows: what it settles -- severity,
    finding, cleared -- has to come back identical, which is what catches the
    emitter and this file drifting apart."""
    for name, check in report['checks'].items():
        raw = [{key: value for key, value in row.items()
                if key not in ('severity', 'finding', 'cleared', 'reason')}
               for row in check['rows']]
        for before, after in zip(check['rows'], scoreRows(name, raw), strict=True):
            assert after['severity'] == before['severity'], name
            assert after['finding'] == before['finding'], name
            assert after['cleared'] == before['cleared'], name
            assert after['reason'] == before['reason'], name
