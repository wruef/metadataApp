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
        ## asset ID -> the serial its raw data reports, where that differs from
        ## the bulk record. Confirmed by a person, one row per asset.
        'serialAliases': serialAliases(os.path.join(paramsDir, 'serialAliases.csv')),
    }


def serialAliases(path):
    if not os.path.exists(path):
        return {}
    aliases = pd.read_csv(path, comment='#', dtype=str)
    return dict(zip(aliases.assetID.str.strip(), aliases.rawSerial.str.strip()))


## The sheet each signed-off check records in, and the column that identifies a
## row in it. Keyed by check name, which is what the dashboard signs off under.
HITL_SHEETS = {
    'calibrations': ('2i_HITL_calibrationVerification.csv', 'githubFile'),
    'deployments': ('2i_HITL_deploymentVerification.csv', 'referenceDesignatorYearDeployNum'),
    ## Serial numbers that disagree between the RCA list and OOI's record are
    ## mostly a judgement about which record is right, and there was nowhere to
    ## write that judgement down -- so 131 of them came back every run.
    'sensorBulk': ('2i_HITL_sensorVerification.csv', 'assetID'),
}


def loadHITL(hitlDir='2i_HITL'):
    """What a reviewer has already signed off on, indexed by what identifies a row."""
    return {check: pd.read_csv(os.path.join(hitlDir, sheet)).set_index(key)
            for check, (sheet, key) in HITL_SHEETS.items()}


def hitlNotes(hitl):
    """Every note already written in each sheet, most used first.

    These are the reasons the dashboard offers when a row is signed off, so a
    new sign-off reuses the wording the team already has rather than inventing
    a synonym for it. Frequency order puts the shared vocabulary at the top --
    'verified with deployment logs and images' and its neighbours -- and leaves
    the remarks about one particular file below it.

    Read from the sheets rather than from the rows of a run, because the two do
    not hold the same set: a note written against a calibration file that
    asset-management no longer carries is still a reason worth offering.
    """
    vocabulary = {}
    for sheet, frame in hitl.items():
        if 'HITLnotes' not in frame.columns:
            vocabulary[sheet] = []
            continue
        ## One note in the sheet today is a single space, which is not a reason.
        written = frame['HITLnotes'].dropna().str.strip()
        counts = written[written != ''].value_counts()
        ## Ties resolve on the wording, so the list is the same every run and a
        ## report does not churn between two orderings of the same notes.
        vocabulary[sheet] = sorted(counts.index, key=lambda note: (-counts[note], note))
    return vocabulary


## Every bulk asset record OOI keeps, by the name this package calls it. All of
## them are read, not only the two a deployment sheet is checked against: an
## asset filed in the wrong one is misfiled rather than missing, and saying
## which record holds it is the difference between a question and an answer.
BULK_RECORDS = {'sensors': 'sensor', 'platforms': 'platform', 'nodes': 'node',
                'eng': 'eng', 'arrays': 'array', 'unclassified': 'unclassified'}


def loadBulk(amSource):
    """OOI's bulk asset records and cruise list, at the chosen ref."""
    records = {name: pd.read_csv(amSource.path(f'bulk/{stem}_bulk_load-AssetRecord.csv'))
               for name, stem in BULK_RECORDS.items()}
    sensors = records['sensors']
    return {
        'sensors': sensors,
        'platforms': records['platforms'],
        'cruises': pd.read_csv(amSource.path('cruise/CruiseInformation.csv')),
        ## Every asset ID each record knows.
        'assetIDs': {name: set(frame['ASSET_UID'].dropna().astype(str))
                     for name, frame in records.items()},
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


def inForceAt(entries, deployDate):
    """Of ``(calibration date, anything)`` entries, those in force at a deployment.

    Compared by date rather than by timestamp. A calibration's date comes from
    its file name and so carries no time of day, which puts it at midnight; 76
    of the 1,413 deployments also start at exactly midnight, and a strict
    comparison then discarded a calibration dated the very day the instrument
    went in the water. It did so for two of them: RS03AXBS-LJ03A-09-HYDBBA302
    deployment 3 read as having no valid calibration when one was taken that
    morning, and RS03AXBS-LJ03A-10-ADCPTE303 deployment 3 fell back to a
    calibration two years older and picked up a stale-calibration warning for it.

    A calibration taken the day an instrument was deployed was in force for that
    deployment, whatever the clock said.
    """
    day = deployDate.date()
    return [entry for entry in entries if entry[0].date() <= day]


def calibrationHistory(calFiles):
    """Asset ID -> its calibration files, as (date, file name)."""
    history = {}
    for _, fileName in calFiles:
        assetID, calDate = calFileBits(fileName)
        if assetID:
            history.setdefault(assetID, []).append((calDate, fileName))
    return history
