"""Command line entry point for a verification run.

One run is against a specific state of the repositories, named as
``owner/repo@ref``. Where a clone of that repository is on disk it is read from
there; otherwise it is read over the GitHub API. The two produce the same
answers -- the clone is simply far cheaper, because the calibration comparison
probes the filesystem for vendor files and would otherwise pull down ~1,300 of
them over the wire.
"""

import argparse
import datetime
import glob
import json
import os

import pandas as pd

from . import history, loading, positions, publish
from .compare import compareReports
from .report import buildReport, writeReport
from .run import AM_REPO, CAL_REPO, DEPLOY_REF, DEPLOY_REPO, NODE_DEPLOYMENTS, verify
from .sources import RepoSource

DEFAULT_REF = 'master'
POSITION_GLOB = 'inputs/RSN_Positions_TEAM_*.xlsx'


def parseSource(spec, clonesDir=None, defaultRef=DEFAULT_REF):
    """``owner/repo`` or ``owner/repo@ref`` into a RepoSource.

    A clone under ``clonesDir`` named for the repository is preferred when it is
    there, so the same command serves a workflow that clones and a laptop that
    has the repositories already.
    """
    repo, _, ref = spec.partition('@')
    local = os.path.join(clonesDir, repo.split('/')[-1]) if clonesDir else None
    return RepoSource(repo, ref or defaultRef,
                      local=local if local and os.path.isdir(local) else None)


def latestPositionFile(pattern=POSITION_GLOB):
    """The most recent position spreadsheet drop, by name."""
    found = sorted(glob.glob(pattern))
    return found[-1] if found else None


def main(argv=None):
    parser = argparse.ArgumentParser(description='Verify RCA deployment metadata.')
    parser.add_argument('--asset-management', default=AM_REPO, metavar='OWNER/REPO[@REF]')
    parser.add_argument('--calibration-files', default=CAL_REPO, metavar='OWNER/REPO[@REF]')
    parser.add_argument('--deployments', default=f'{DEPLOY_REPO}@{DEPLOY_REF}', metavar='OWNER/REPO[@REF]',
                        help='node deployments, for the position check')
    parser.add_argument('--clones', metavar='DIR',
                        help='directory holding clones of those repositories')
    parser.add_argument('--positions', metavar='XLSX',
                        help=f'position spreadsheet (default: newest {POSITION_GLOB})')
    parser.add_argument('--params', default='params')
    parser.add_argument('--hitl', default='2i_HITL')
    parser.add_argument('--out', default='reports/report.json')
    ## Recorded in the report rather than inferred from the files beside it. A
    ## comparison is published only when a run was given a baseline, and until
    ## the report said so the dashboard asked for one every time and took a 404
    ## for an answer on every run that had none.
    parser.add_argument('--baseline', metavar='REF',
                        help='the ref this run is being compared against, for the report to record')
    ## Published beside the report rather than inside it: the dashboard fetches
    ## it only when a reviewer opens the history, and it is half a megabyte.
    parser.add_argument('--history-out', default='reports/history.json',
                        help='the published deployment history, for the dashboard to propose')
    args = parser.parse_args(argv)

    result = verify(
        parseSource(args.asset_management, args.clones),
        parseSource(args.calibration_files, args.clones),
        parseSource(args.deployments, args.clones, defaultRef=DEPLOY_REF),
        positionFile=args.positions or latestPositionFile(),
        paramsDir=args.params, hitlDir=args.hitl, baseline=args.baseline)

    report = buildReport(result)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    writeReport(report, args.out)

    bundle = history.historyBundle(result)
    os.makedirs(os.path.dirname(args.history_out) or '.', exist_ok=True)
    with open(args.history_out, 'w') as handle:
        json.dump(bundle, handle, indent=1)

    for name, check in report['checks'].items():
        summary = check['summary']
        print(f"{name:18} {summary['total']:5} rows  "
              f"{summary['verification']:4} to verify  "
              f"{summary['unchecked']:4} unchecked  {summary['cleared']:5} cleared  "
              f"{summary['ok']:5} ok")
    print('wrote ' + args.out)
    print(f"wrote {args.history_out} ({len(bundle['files'])} history files)")
    return 0



def compareMain(argv=None):
    """Diff two run reports into an answer about what a change did."""
    parser = argparse.ArgumentParser(description='Compare two verification runs.')
    parser.add_argument('baseline', help='the report to compare against')
    parser.add_argument('current', help='the report being judged')
    parser.add_argument('--out', default='reports/comparison.json')
    args = parser.parse_args(argv)

    with open(args.baseline) as handle:
        baseline = json.load(handle)
    with open(args.current) as handle:
        current = json.load(handle)
    result = compareReports(baseline, current)

    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w') as handle:
        json.dump(result, handle, indent=1)

    if not result['comparable']:
        print('These runs cannot be compared:')
        for reason in result['reasons']:
            print('  - ' + reason)
    for name, check in result['checks'].items():
        moved = {key: len(value) for key, value in check.items() if isinstance(value, list)}
        if any(moved.values()):
            print(f"{name:18} " + '  '.join(f'{key} {count}' for key, count in moved.items() if count))
    print('wrote ' + args.out)
    return 0


## ---- publishing the generated products ----

def _sources(args):
    return (parseSource(args.asset_management, args.clones),
            parseSource(args.calibration_files, args.clones),
            parseSource(args.deployments, args.clones, defaultRef=DEPLOY_REF))


def publishMain(argv=None):
    parser = argparse.ArgumentParser(description='Generate and propose the published files.')
    parser.add_argument('--asset-management', default=AM_REPO, metavar='OWNER/REPO[@REF]')
    parser.add_argument('--calibration-files', default=CAL_REPO, metavar='OWNER/REPO[@REF]')
    parser.add_argument('--deployments', default=f'{DEPLOY_REPO}@{DEPLOY_REF}', metavar='OWNER/REPO[@REF]')
    parser.add_argument('--clones', metavar='DIR')
    parser.add_argument('--params', default='params')
    parser.add_argument('--out-dir', default='out')
    parser.add_argument('--fork', metavar='OWNER/REPO', help='your own fork, to open a pull request against')
    parser.add_argument('--token', default=os.environ.get('GITHUB_TOKEN'))
    sub = parser.add_subparsers(dest='what', required=True)

    sub.add_parser('history', help='deployment history, one file per instrument type')
    season = sub.add_parser('seasons', help='deployed, recovered and current instrument lists')
    season.add_argument('--year', type=int, required=True)
    correct = sub.add_parser('positions', help='deployment sheets corrected from the position spreadsheet')
    correct.add_argument('--positions-file', metavar='XLSX')
    correct.add_argument('--node-fork', metavar='OWNER/REPO',
                         help='fork of the deployments repo, for node positions')

    args = parser.parse_args(argv)
    amSource, calSource, deploySource = _sources(args)
    params = loading.loadParams(args.params)

    if args.what == 'history':
        rows = history.deploymentHistory(
            loading.loadDeployments(amSource), params['assets'],
            history.calibrationLinks(amSource, [(f'calibration/{instrument}', name)
                                                for instrument, name in loading.loadCalFileIndex(amSource)]),
            history.calibrationLinks(calSource, [(sensor, name) for sensor in calSource.listDirs('')
                                                 for name in calSource.listFiles(sensor)]))
        publish.propose(history.historyFiles(rows), args.fork, args.token,
                        f'Deployment history, {datetime.date.today().isoformat()}',
                        publish.HISTORY_BODY, args.out_dir)
        return 0

    if args.what == 'seasons':
        deployments = loading.loadDeployments(amSource)
        assets = params['assets']
        os.makedirs(args.out_dir, exist_ok=True)
        for name, rows, header in [
                (f'currentDeployments_{args.year}.csv', history.currentDeployments(deployments, assets), 'deployDate'),
                (f'deployedInstruments_{args.year}.csv', history.deployedIn(deployments, args.year, assets), 'deployDate'),
                (f'recoveredInstruments_{args.year}.csv', history.recoveredIn(deployments, args.year, assets), 'recoverDate')]:
            history.writeSeasonList(rows, os.path.join(args.out_dir, name), header)
            print(f'{name}: {len(rows)} rows')
        return 0

    ## positions
    spreadsheet = args.positions_file or latestPositionFile()
    if not spreadsheet:
        parser.error(f'no position spreadsheet found ({POSITION_GLOB})')
    deployments = loading.loadDeployments(amSource)
    if deploySource:
        deployments = pd.concat(
            [deployments, loading.readDeploymentSheet(deploySource.path(NODE_DEPLOYMENTS))],
            ignore_index=True)
    corrected, log = positions.applyPositions(
        deployments, positions.loadPositions(spreadsheet),
        positions.loadPositionNameMap(os.path.join(args.params, 'positionNameMap.csv')),
        positions.loadHITLPositions(os.path.join(args.params, 'HITLpositionList.csv')))
    print(f'{len(log)} deployments corrected')

    title = f'Deployment positions, {datetime.date.today().isoformat()}'
    publish.propose(positions.positionFiles(corrected), args.fork, args.token, title,
                    publish.positionsBody('asset-management'), args.out_dir)
    nodeFiles = positions.nodePositionFile(corrected)
    if nodeFiles:
        publish.propose(nodeFiles, args.node_fork, args.token, title,
                        publish.positionsBody('deployments'), args.out_dir)
    return 0


## ---- the list of runs the dashboard can open ----

def indexEntry(report, name):
    """One line in the run index: enough to choose a run without fetching it."""
    return {
        'name': name,
        'runAt': report.get('runAt'),
        'parameters': report.get('parameters'),
        'sources': {key: value for key, value in (report.get('sources') or {}).items()
                    if isinstance(value, dict)},
        'summary': {check: value['summary'] for check, value in (report.get('checks') or {}).items()},
    }


def updateIndex(index, report, name):
    """Add a run to the index, newest first, replacing any entry of the same name."""
    entries = [entry for entry in index if entry.get('name') != name]
    return sorted([indexEntry(report, name), *entries],
                  key=lambda entry: entry.get('runAt') or '', reverse=True)


def rebuildIndex(reportsDir):
    """The index as the published reports on disk would have it, newest first.

    Two runs publishing at once both rewrite the index, and a rebase between
    them conflicts on it every time. Built from the files instead, after the
    rebase, it needs no merging: whatever reports are there are the index.
    """
    index = []
    for path in sorted(glob.glob(os.path.join(reportsDir, 'report_*.json'))):
        with open(path) as handle:
            index = updateIndex(index, json.load(handle), os.path.basename(path))
    return index


def indexMain(argv=None):
    parser = argparse.ArgumentParser(description='Maintain the index of published runs.')
    parser.add_argument('--report', help='a report to add')
    parser.add_argument('--name', help='the name the report was published under')
    parser.add_argument('--index', help='the existing index, if there is one')
    parser.add_argument('--rebuild', metavar='DIR',
                        help='instead: rebuild the whole index from the report_*.json files in DIR')
    parser.add_argument('--out', default='reports/index.json')
    args = parser.parse_args(argv)
    if not args.rebuild and not (args.report and args.name):
        parser.error('either --rebuild DIR, or --report and --name')

    if args.rebuild:
        updated = rebuildIndex(args.rebuild)
    else:
        with open(args.report) as handle:
            report = json.load(handle)
        index = []
        if args.index and os.path.isfile(args.index):
            with open(args.index) as handle:
                index = json.load(handle)
        updated = updateIndex(index, report, args.name)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w') as handle:
        json.dump(updated, handle, indent=1)
    print(f'{len(updated)} runs in {args.out}')
    return 0


## ---- deleting runs that are no longer needed ----

## What one published run leaves in reports/, all named for the same stamp: the
## report, the comparison against its baseline where it was given one, and the
## deployment history it built. Only the first is always there, so a prune
## deletes whichever of them exist and says which.
COMPANIONS = ['comparison_{stamp}', 'history_{stamp}']


def runFiles(name):
    """Every file published under one run's name, existing or not."""
    stamp = name.removeprefix('report_')
    return [name, *(companion.format(stamp=stamp) for companion in COMPANIONS)]


def runsToRemove(index, productionRunAt, keep=None, before=None, remove=()):
    """Which runs a prune deletes, and which the rule spared.

    ``productionRunAt`` is when the run the dashboard opens on ran, read from
    latest.json. A rule -- ``keep`` or ``before`` -- never deletes that one:
    latest.json would go on serving a run the picker no longer lists, and the
    site would disagree with its own history. Naming it outright is refused
    instead of spared, because then the person asked for that run in particular.

    ``before`` is compared against the recorded stamp as text, which is exact
    because every run records UTC.
    """
    ordered = sorted(index, key=lambda entry: entry.get('runAt') or '', reverse=True)
    if remove:
        byName = {entry['name']: entry for entry in ordered}
        unknown = [name for name in remove if name not in byName]
        if unknown:
            raise ValueError('not a published run: ' + ', '.join(unknown))
        chosen = [byName[name] for name in remove]
    elif keep is not None:
        chosen = ordered[keep:]
    else:
        chosen = [entry for entry in ordered if (entry.get('runAt') or '') < before]

    spared = {entry['name'] for entry in chosen if entry.get('runAt') == productionRunAt}
    if spared and remove:
        raise ValueError(f"{', '.join(sorted(spared))} is the run the dashboard opens on")
    return ([entry for entry in chosen if entry['name'] not in spared],
            [entry for entry in chosen if entry['name'] in spared])


def pruneMain(argv=None):
    """Delete published runs, and take them out of the index the picker reads.

    A run costs about 75 KB as a git object, so this is housekeeping rather than
    a space problem: fifteen runs from one afternoon of testing make the run
    picker useless long before they make the repository large. Nothing is lost
    that git does not still hold -- a deleted run is recoverable from the commit
    that removed it -- but the site stops offering it.
    """
    parser = argparse.ArgumentParser(description='Delete published runs no longer needed.')
    parser.add_argument('--reports', default='reports', metavar='DIR')
    rule = parser.add_mutually_exclusive_group(required=True)
    rule.add_argument('--keep', type=int, metavar='N',
                      help='keep the N newest runs and delete the rest')
    rule.add_argument('--before', metavar='DATE',
                      help='delete runs that ran before this date, e.g. 2026-01-01')
    rule.add_argument('--remove', action='append', default=[], metavar='REPORT',
                      help='delete this run by name (repeatable)')
    parser.add_argument('--dry-run', action='store_true',
                        help='say what would go, and change nothing')
    args = parser.parse_args(argv)
    if args.keep is not None and args.keep < 1:
        parser.error('--keep has to leave at least one run')

    indexPath = os.path.join(args.reports, 'index.json')
    with open(indexPath) as handle:
        index = json.load(handle)

    ## Which run the site opens on, matched on when it ran: latest.json is a
    ## copy and does not carry the name it was published under.
    latestPath = os.path.join(args.reports, 'latest.json')
    productionRunAt = None
    if os.path.isfile(latestPath):
        with open(latestPath) as handle:
            productionRunAt = json.load(handle).get('runAt')

    try:
        removing, spared = runsToRemove(index, productionRunAt, args.keep, args.before, args.remove)
    except ValueError as refusal:
        parser.error(str(refusal))

    for entry in spared:
        print(f"keeping {entry['name']} -- the run the dashboard opens on")
    if not removing:
        print('nothing to delete')
        return 0

    verb = 'would delete' if args.dry_run else 'deleted'
    for entry in removing:
        files = [name for name in runFiles(entry['name'])
                 if os.path.isfile(os.path.join(args.reports, name))]
        print(f"{verb} {entry['name']} ({entry.get('runAt')}): {', '.join(files)}")
        if not args.dry_run:
            for name in files:
                os.remove(os.path.join(args.reports, name))

    gone = {entry['name'] for entry in removing}
    kept = [entry for entry in index if entry['name'] not in gone]
    if args.dry_run:
        print(f'{len(kept)} runs would be left in the index; nothing was changed')
        return 0
    with open(indexPath, 'w') as handle:
        json.dump(kept, handle, indent=1)
    print(f'{len(kept)} runs left in {indexPath}')
    return 0


def extractMain(argv=None):
    """Read deployment serial numbers out of the raw data archive.

    Writes the parameter file the deployment check reads. Nothing here decides a
    verdict: the file is proposed as a pull request and read by the next run.
    """
    from .serials import MISSING, extractSerials, mergeSerials, openDeployments

    parser = argparse.ArgumentParser(description='Read deployment serial numbers out of the raw archive.')
    parser.add_argument('--asset-management', default=AM_REPO, metavar='OWNER/REPO[@REF]')
    parser.add_argument('--clones', metavar='DIR')
    parser.add_argument('--params', default='params')
    parser.add_argument('--refdes', action='append', metavar='REFDES',
                        help='only these reference designators (repeatable)')
    parser.add_argument('--all', action='store_true',
                        help='attempt every deployment, not only those without a serial on record')
    parser.add_argument('--out', help='where to write the updated file (default: in place)')
    args = parser.parse_args(argv)

    path = os.path.join(args.params, 'rawFileSN.csv')
    table = pd.read_csv(path)
    deployments = loading.loadDeployments(parseSource(args.asset_management, args.clones))
    byRefDes = loading.deploymentsByRefDes(deployments)
    wanted = openDeployments(byRefDes, table, refDes=args.refdes, everything=args.all)
    print(f'{len(wanted)} deployment(s) across {len({rd for rd, _ in wanted})} reference designator(s) to attempt')

    rows = extractSerials(byRefDes, wanted)
    merged = mergeSerials(table, rows)
    merged.to_csv(args.out or path, index=False)

    found = [r for r in rows if r['rawSerialNumber'] != MISSING]
    print(f"\n{len(found)} serial(s) found, {len(rows) - len(found)} deployment(s) still without one")
    for row in found:
        print(f"  {row['referenceDesignator']} deploy {row['deployNum']} ({row['deployYear']}): {row['rawSerialNumber']}")
    print('wrote ' + (args.out or path))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
