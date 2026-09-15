"""Loading the inputs a verification run reads.

Three kinds of input, and the distinction matters for provenance: the two
repositories at a chosen ref, this repository's own parameter files, and the
2i-HITL sign-offs that record what a reviewer has already judged.
"""

import datetime
import os

import numpy as np
import pandas as pd

## The cabled array deployment sheets, by array.
CABLED_ARRAYS = ['CE02SHBP', 'CE04OSBP', 'CE04OSPD', 'CE04OSPS', 'RS01SBPD', 'RS01SBPS',
                 'RS01SLBS', 'RS01SUM1', 'RS01SUM2', 'RS03ASHS', 'RS03AXBS', 'RS03AXPD',
                 'RS03AXPS', 'RS03CCAL', 'RS03ECAL', 'RS03INT1', 'RS03INT2']

## Cabled array assets are the ones whose IDs carry these prefixes.
RCA_ASSET_PREFIXES = ('ATAPL', 'ATOSU')


def loadParams(paramsDir='params'):
    """This repository's parameter files, which git history is the provenance for."""
    assets = pd.read_csv(os.path.join(paramsDir, 'RCA-InstrumentList.csv'))
    assets['mfgSN'] = assets['mfgSN'].str.split(', ')
    assets['instrumentType'] = assets['instrumentType'].str.split(',')

    coeffMap = pd.read_csv(os.path.join(paramsDir, 'coefficientMap.csv'))
    coeffMap = coeffMap.set_index('github').transpose().to_dict('list')

    constantRows = pd.read_csv(os.path.join(paramsDir, 'coefficientConstants.csv'),
                               converters={'value': np.float64}, float_precision='round_trip')
    constants = {}
    for _, row in constantRows.iterrows():
        constants.setdefault(row.sensor, {})[row.coeff] = row.constant

    return {
        'assets': assets.set_index('assetID').T.to_dict('series'),
        'coeffMap': coeffMap,
        'constants': constants,
        'rawSN': pd.read_csv(os.path.join(paramsDir, 'rawFileSN.csv')),
        'imageSN': pd.read_csv(os.path.join(paramsDir, 'imageSN.csv')),
    }


def loadHITL(hitlDir='2i_HITL'):
    """What a reviewer has already signed off on."""
    return {
        'calibrations': pd.read_csv(os.path.join(hitlDir, '2i_HITL_calibrationVerification.csv')),
        'deployments': pd.read_csv(os.path.join(hitlDir, '2i_HITL_deploymentVerification.csv')),
    }


def loadBulk(amSource):
    """OOI's bulk asset records and cruise list, at the chosen ref."""
    sensors = pd.read_csv(amSource.path('bulk/sensor_bulk_load-AssetRecord.csv'))
    return {
        'sensors': sensors,
        'platforms': pd.read_csv(amSource.path('bulk/platform_bulk_load-AssetRecord.csv')),
        'cruises': pd.read_csv(amSource.path('cruise/CruiseInformation.csv')),
        ## asset ID -> the manufacturer serial number OOI has on record
        'serialByAsset': pd.Series(sensors["Manufacturer's Serial No./Other Identifier"].values,
                                   index=sensors['ASSET_UID']).to_dict(),
    }


def loadDeployments(amSource):
    """Every cabled array deployment, one row each."""
    sheets = [amSource.path(f'deployment/{array}_Deploy.csv') for array in CABLED_ARRAYS]
    return pd.concat([readDeploymentSheet(f) for f in sheets], ignore_index=True)


def readDeploymentSheet(path):
    """One deployment sheet, keeping ``N/A`` as the value it is.

    Profilers carry a literal ``N/A`` deployment depth because a depth is
    meaningless for them. Pandas reads that as a missing value by default, which
    makes an already-correct sheet look like it needs correcting -- so only a
    genuinely empty cell counts as missing here.
    """
    return pd.read_csv(path, skip_blank_lines=True, comment='#',
                       keep_default_na=False, na_values=[''])


def deploymentsByRefDes(deployments):
    """Deployments grouped by reference designator, newest first.

    Each deployment carries its ``deployNum``, which is what identifies it --
    a reference designator and a year do not, because an instrument can be
    deployed more than once in a season.
    """
    ordered = deployments.sort_values(['Reference Designator', 'startDateTime'], ascending=False)
    byRefDes = {}
    for _, row in ordered.iterrows():
        byRefDes.setdefault(row['Reference Designator'], []).append({
            'refDes': row['Reference Designator'],
            'deployNum': row['deploymentNumber'],
            'deployDate': datetime.datetime.strptime(row['startDateTime'], '%Y-%m-%dT%H:%M:%S'),
            'deployEnd': row['stopDateTime'],
            'AssetID': row['sensor.uid'],
        })
    return byRefDes


def loadCalFileIndex(amSource):
    """Calibration files in asset-management, as (instrument directory, file name).

    Sensor directories are read from the repo rather than hardcoded, because the
    two repos do not always name a sensor the same way: the PHSEN-H calibrations
    live in asset-management ``PHSENH0`` but in calibrationFiles ``PHSENH``.
    """
    return [(instrument, fileName)
            for instrument in amSource.listDirs('calibration')
            for fileName in amSource.listFiles(f'calibration/{instrument}', suffix='.csv')]


def calFileBits(fileName):
    """The asset ID and calibration date in ``AT<assetID>__<YYYYMMDD>.<ext>``."""
    import re
    bits = re.match(r'(.*)__([0-9]{8})', fileName)
    if not bits:
        return None, None
    return bits.group(1), datetime.datetime.strptime(bits.group(2), '%Y%m%d')


def calibrationHistory(calFiles):
    """Asset ID -> its calibration files, as (date, file name)."""
    history = {}
    for _, fileName in calFiles:
        assetID, calDate = calFileBits(fileName)
        if assetID:
            history.setdefault(assetID, []).append((calDate, fileName))
    return history
