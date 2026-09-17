"""One verification run.

A run is against a specific state of both repositories. Everything it reads is
named in the result, so any row on screen can be traced back to the inputs that
produced it.
"""

import datetime
import os

import pandas as pd

from . import checks, loading, positions, report
from .sources import RepoSource, VendorFiles

AM_REPO = 'oceanobservatories/asset-management'
CAL_REPO = 'OOI-CabledArray/calibrationFiles'
DEPLOY_REPO = 'OOI-CabledArray/deployments'
DEPLOY_REF = 'main'

## The nodes the instruments hang off are deployed too, and their positions are
## checked the same way -- they just live in a different repository.
NODE_DEPLOYMENTS = 'NODE_deployments.csv'


def verify(amSource, calSource, deploySource=None, positionFile=None,
           paramsDir='params', hitlDir='2i_HITL'):
    """Run every check and return the result, with the inputs it read."""
    params = loading.loadParams(paramsDir)
    hitl = loading.loadHITL(hitlDir)
    params.update(loading.loadBulk(amSource))

    calFiles = loading.loadCalFileIndex(amSource)
    vendorFiles = VendorFiles(calSource)
    deployments = loading.loadDeployments(amSource)
    byRefDes = loading.deploymentsByRefDes(deployments)

    return {
        ## UTC, and said so. A naive stamp is read as local time by the browser
        ## and sorts against the UTC file stamp in the run index, so a laptop
        ## run and a runner run could order wrongly against each other.
        'runAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        ## Every input the run read, so any row can be traced back to it.
        'sources': {
            'assetManagement': report.describeSource(amSource),
            'calibrationFiles': report.describeSource(calSource),
            'deployments': report.describeSource(deploySource),
            'positionSpreadsheet': positionFile,
        },
        'sensorBulk': checks.checkSensorBulk(params['assets'], params['serialByAsset']),
        'calibrations': checks.checkCalibrations(amSource, calFiles, vendorFiles, params, hitl),
        'deploymentSheets': checks.checkDeploymentSheets(deployments, params),
        'deployments': checks.checkDeployments(
            byRefDes, params, hitl,
            loading.calibrationHistory(calFiles),
            amSource.listDirs('calibration')),
        'positions': _checkPositions(amSource, deploySource, positionFile, deployments, paramsDir),
        ## Not a check -- the inventory of what the run covered, which the
        ## dashboard offers as a view of its own.
        'referenceDesignators': sorted(set(deployments['Reference Designator'].dropna())),
        ## Not a check either -- the reasons a reviewer picks from when signing
        ## a row off, which are whatever the team has already written.
        'hitlNotes': loading.hitlNotes(hitl),
    }


def _checkPositions(amSource, deploySource, positionFile, deployments, paramsDir):
    """Positions for instruments and nodes alike, against the team spreadsheet.

    Skipped rather than guessed at when no spreadsheet is given -- it is a
    periodic drop from the team, not something a run can fetch for itself.
    """
    if not positionFile:
        return None
    if deploySource:
        nodes = loading.readDeploymentSheet(deploySource.path(NODE_DEPLOYMENTS))
        deployments = pd.concat([deployments, nodes], ignore_index=True)
    return positions.checkPositions(
        deployments,
        positions.loadPositions(positionFile),
        positions.loadPositionNameMap(os.path.join(paramsDir, 'positionNameMap.csv')),
        positions.loadHITLPositions(os.path.join(paramsDir, 'HITLpositionList.csv')))


def verifyLocal(amPath, calPath, deployPath=None, **kwargs):
    """Run against local clones -- the pre-cruise case, before anything is pushed."""
    return verify(RepoSource(AM_REPO, local=amPath), RepoSource(CAL_REPO, local=calPath),
                  RepoSource(DEPLOY_REPO, DEPLOY_REF, local=deployPath) if deployPath else None,
                  **kwargs)


def verifyToReport(amSource, calSource, outPath, **kwargs):
    """Run every check and write the report the dashboard reads."""
    result = verify(amSource, calSource, **kwargs)
    return report.writeReport(report.buildReport(result), outPath)
