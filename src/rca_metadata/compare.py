"""Comparing two runs.

Verifying a branch in isolation produces a report; verifying it *against* a
baseline produces an answer about whether a change is safe. That is the whole
point of the pre-cruise check.

The trap this has to avoid: a row can change because the data changed, or
because the check itself changed. Phase 00 is exactly that case -- fixing the
silent-pass bug moved 114 rows without anything in the repositories moving at
all. A comparison that cannot tell those apart is worse than none, so every
comparison says whether the two runs were produced by the same checks.
"""

from .report import SEVERITIES

## What identifies the same row across two runs. A row is "the same row" when
## these match; anything else about it is free to change.
ROW_KEYS = {
    'calibrations': ('fileName',),
    'deployments': ('refDes', 'deployNum'),
    'positions': ('refDes', 'deployNum'),
    'sensorBulk': ('assetID',),
    ## A sheet finding has no identity of its own -- the finding *is* the row.
    'deploymentSheets': ('refDes', 'deployNum', 'value', 'verdict'),
}

## Fields worth reporting as changed when severity stayed the same.
IGNORED_FIELDS = {'severity', 'differences'}


def rowKey(check, row):
    return tuple(str(row.get(field)) for field in ROW_KEYS.get(check, ('refDes',)))


def _severityMoved(before, after):
    """Positive when a row got worse, negative when it got better.

    SEVERITIES runs worst first, so a lower index is a worse row.
    """
    return _rank(before) - _rank(after)


def _rank(severity):
    """A severity this code never wrote -- a hand-edited baseline, or one from a
    future version -- ranks as needing a person rather than ending the run."""
    return SEVERITIES.index(severity if severity in SEVERITIES else 'verification')


def _changedFields(before, after):
    fields = (set(before) | set(after)) - IGNORED_FIELDS
    return sorted(field for field in fields if before.get(field) != after.get(field))


def comparability(baseline, current):
    """Whether the two runs can be compared, and what differs about them.

    Same checks and same parameters means a difference is a difference in the
    data. Anything else and a moved row may just be the check having changed.
    """
    reasons = []
    commits = [report.get('parameters', {}).get('commit') for report in (baseline, current)]
    if 'UNKNOWN' in commits or None in commits:
        ## Without knowing which checks produced a run, a moved row cannot be
        ## attributed to the data rather than to the check.
        reasons.append('a run does not record which version of the checks produced it')
    if baseline.get('schemaVersion') != current.get('schemaVersion'):
        reasons.append('the report schema changed between these runs')
    if baseline.get('parameters', {}).get('commit') != current.get('parameters', {}).get('commit'):
        reasons.append('the checks and parameter files are at different commits')
    if baseline.get('parameters', {}).get('dirty') or current.get('parameters', {}).get('dirty'):
        reasons.append('one of the runs had uncommitted changes')
    ## The parameter commit says which checks ran; it says nothing about which
    ## state of the repositories they ran against. 'master' today and 'master'
    ## next season are different data, so a source whose commit was never
    ## resolved makes a moved row unattributable just as surely.
    for report in (baseline, current):
        for name, source in (report.get('sources') or {}).items():
            if isinstance(source, dict) and source.get('commit') in (None, 'UNKNOWN'):
                reasons.append(f'a run does not record which commit of {name} it read')
    return {'comparable': not reasons, 'reasons': reasons}


def sources(baseline, current):
    """What each run read, for the runs that moved."""
    moved = {}
    for name, after in (current.get('sources') or {}).items():
        before = (baseline.get('sources') or {}).get(name)
        if before != after and isinstance(after, dict):
            moved[name] = {'baseline': before, 'current': after}
    return moved


def compareCheck(check, baselineRows, currentRows):
    """One check's rows, sorted into what a reader needs to act on."""
    before = {rowKey(check, row): row for row in baselineRows}
    after = {rowKey(check, row): row for row in currentRows}

    result = {'newlyFailing': [], 'newlyPassing': [], 'new': [], 'gone': [],
              'changed': [], 'unchanged': 0}

    for key, row in after.items():
        previous = before.get(key)
        if previous is None:
            result['new'].append({'key': key, 'row': row})
            continue
        moved = _severityMoved(previous['severity'], row['severity'])
        entry = {'key': key, 'row': row, 'was': previous['severity'], 'now': row['severity']}
        if moved > 0:
            result['newlyFailing'].append(entry)
        elif moved < 0:
            result['newlyPassing'].append(entry)
        else:
            fields = _changedFields(previous, row)
            if fields:
                result['changed'].append({**entry, 'fields': fields})
            else:
                result['unchanged'] += 1

    for key, row in before.items():
        if key not in after:
            result['gone'].append({'key': key, 'row': row})

    return result


def compareReports(baseline, current):
    """Two run reports into an answer about what moved between them."""
    checks = {}
    for name, check in (current.get('checks') or {}).items():
        baselineCheck = (baseline.get('checks') or {}).get(name, {'rows': []})
        checks[name] = compareCheck(name, baselineCheck.get('rows', []), check.get('rows', []))

    return {
        'baselineRunAt': baseline.get('runAt'),
        'currentRunAt': current.get('runAt'),
        **comparability(baseline, current),
        'sources': sources(baseline, current),
        'checks': checks,
    }
