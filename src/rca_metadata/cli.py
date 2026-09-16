"""Command line entry point for a verification run.

One run is against a specific state of the repositories, named as
``owner/repo@ref``. Where a clone of that repository is on disk it is read from
there; otherwise it is read over the GitHub API. The two produce the same
answers -- the clone is simply far cheaper, because the calibration comparison
probes the filesystem for vendor files and would otherwise pull down ~1,300 of
them over the wire.
"""

import argparse
import glob
import json
import os

import datetime

import pandas as pd

from . import history, loading, positions
from .compare import compareReports
from .publish import PullRequest
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
    args = parser.parse_args(argv)

    result = verify(
        parseSource(args.asset_management, args.clones),
        parseSource(args.calibration_files, args.clones),
        parseSource(args.deployments, args.clones, defaultRef=DEPLOY_REF),
        positionFile=args.positions or latestPositionFile(),
        paramsDir=args.params, hitlDir=args.hitl)

    report = buildReport(result)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    writeReport(report, args.out)

    for name, check in report['checks'].items():
        summary = check['summary']
        print(f"{name:18} {summary['total']:5} rows  "
              f"{summary['problem']:4} problem  {summary['review']:4} review  "
              f"{summary['unchecked']:4} unchecked  {summary['ok']:5} ok")
    print('wrote ' + args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


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


def _propose(files, fork, token, title, body, outDir):
    """Write the files, and offer them to a fork when one is named.

    Writing to disk always happens: a generated file you can look at before
    proposing it is the point. The pull request is the optional half.
    """
    os.makedirs(outDir, exist_ok=True)
    for name, content in files.items():
        path = os.path.join(outDir, name)
        os.makedirs(os.path.dirname(path) or outDir, exist_ok=True)
        with open(path, 'w') as handle:
            handle.write(content)
    print(f'wrote {len(files)} files to {outDir}')

    if not fork:
        print('no --fork given, so nothing was proposed')
        return 0
    url = PullRequest(fork, token=token, base=args_base(fork)).open(files, title, body)
    print(f'opened {url}' if url else f'{fork} already matches these files — nothing to propose')
    return 0


def args_base(fork):
    """The branch a fork's pull requests target."""
    return 'main' if fork.endswith('deployments') else 'master'


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
        return _propose(history.historyFiles(rows), args.fork, args.token,
                        f'Deployment history, {datetime.date.today().isoformat()}',
                        'Regenerated from the asset-management deployment sheets and the calibration '
                        'files in both repositories.\n\nReview here, then raise the pull request to the '
                        'upstream deployments repository by hand.', args.out_dir)

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
    body = ('Latitude, longitude and depths taken from the RCA position spreadsheet.\n\n'
            'Review here, then raise the pull request upstream by hand.')
    _propose(positions.positionFiles(corrected), args.fork, args.token, title, body, args.out_dir)
    nodeFiles = positions.nodePositionFile(corrected)
    if nodeFiles:
        _propose(nodeFiles, args.node_fork, args.token, title, body, args.out_dir)
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


def indexMain(argv=None):
    parser = argparse.ArgumentParser(description='Maintain the index of published runs.')
    parser.add_argument('--report', required=True)
    parser.add_argument('--name', required=True, help='the name the report was published under')
    parser.add_argument('--index', help='the existing index, if there is one')
    parser.add_argument('--out', default='reports/index.json')
    args = parser.parse_args(argv)

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
