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
import os

from .report import buildReport, writeReport
from .run import AM_REPO, CAL_REPO, DEPLOY_REF, DEPLOY_REPO, verify
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
