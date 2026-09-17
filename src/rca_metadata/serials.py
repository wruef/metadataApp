"""Serial numbers read out of raw data files.

A deployment's serial number is the one piece of metadata the raw archive can
settle without a person looking at a photograph, so these extractors decide how
much of the HITL queue survives a run.

Every extractor returns ``MISSING`` rather than raising when it finds nothing.
"""

import datetime
import os
import re
import subprocess

import pandas as pd
import requests

from .rawarchive import createFileList, createFileList_DP

MISSING = '-99999'

## Sensors whose raw files are binary and have to go through an mi driver.
BINARY_RAW = ['ADCP', 'OPTAA']

## Serial number reported by the sensor at power-on, in the first raw file.
## (sensor key in filename) -> (patterns, how many trailing digits are the serial)
FIRST_RAW_PATTERNS = {
    'CTD': ([r"<HardwareData.*SerialNumber\s=\s\'(\d{1,10})\'>",
             r"SerialNumber\s=\s'(\d{1,10})'>"], 4),
    'SPKIR': ([r"S\/N:\s+(\d{2,4})"], 3),
    'NUTNR': ([r"SUNA\sSN:(\d{1,4}).*"], 3),
    'FLOR': ([r"Ser\s.*-(\d{1,4}).*"], None),
    ## TODO: two characters is barely a comparison at all, and this needs the
    ## records to agree how a PREST serial is written before it can be more.
    ## The instrument reports SerialNumber='05400030' where both the RCA list
    ## and the sensor bulk record carry 5471540-0030 -- the same number in
    ## vendor part-number dress, the prefix and the dash gone and a zero in
    ## front. Nothing lines the two spellings up, so only a tail can be
    ## compared, and two characters of one matches 5471540-0130 and a great many
    ## serials belonging to other instruments. What it yields in practice is in
    ## params/rawFileSN.csv: '0', '1', '7'.
    'PREST': ([r"SerialNumber=.*(\d{1,9}).*"], 2),
    'TMPSFA': ([r"RBR\s+XR-420\s+\d.\d{2,4}\s+(\d{1,9}).*"], 5),
}

## Serial number carried in the data lines themselves, for files that print no
## power-on banner. PARAD serials agree between the two records -- clean three
## and four digit numbers, spelled the same in both -- so keeping a tail here
## costs little.
DATA_LINE_PATTERNS = {
    'SPKIR': ([r".*SATDI70(\d{3}).*"], 3),
    'NUTNR': ([r"SATSDF(\d{1,4}).*"], 3),
    'PARAD': ([r"SATPAR(\d{1,4}).*", r"SATPRS(\d{1,4}).*"], 3),
}

## Deep profiler engineering files name each instrument on its own line.
DP_PATTERNS = {
    'ENG': r".*DPC\s*(\d+).*$",
    'CTDPFL': r".*ctd_1\s*(\d+).*$",
    'VEL3DA': r".*acm_1\s*(\d+).*$",
    'FLCDRA': r".*flcd_1\s*(\d+).*$",
    'FLNTUA': r".*flntu_1\s*(\d+).*$",
    'DOSTAD': r".*optode_1\s*(\d+).*$",
}

## mi drivers, and the csv each one leaves behind holding the serial number.
MI_DRIVERS = {
    'VADCP': ('mi.instrument.teledyne.workhorse.vadcp.driver', 'adcp_config.csv'),
    'ADCP': ('mi.instrument.teledyne.workhorse.adcp.driver', 'adcp_config.csv'),
    'OPTAA': ('mi.instrument.wetlabs.ac_s.ooicore.driver', 'optaa_sample.csv'),
}


def _stream(rawFileName):
    """Raw file lines, decoded lossily -- these files are not reliably utf-8."""
    response = requests.get(rawFileName, stream=True)
    return (line.decode('utf-8', errors='ignore') for line in response.iter_lines())


def _search(rawFileName, table):
    for key, (patterns, tail) in table.items():
        if key not in rawFileName:
            continue
        compiled = [re.compile(p) for p in patterns]
        for line in _stream(rawFileName):
            for pattern in compiled:
                match = pattern.search(line)
                if match:
                    return match.group(1)[-tail:] if tail else match.group(1)
        break
    return MISSING


def SNfromFirstRaw(rawFileName):
    """The serial number a sensor reports when it powers on."""
    return _search(rawFileName, FIRST_RAW_PATTERNS)


def SNfromRaw(rawFileName):
    """The serial number embedded in data lines, for files with no power-on banner."""
    return _search(rawFileName, DATA_LINE_PATTERNS)


def SNfromDP(rawFileName, sensor):
    """The serial number for one instrument on a deep profiler."""
    pattern = next((p for key, p in DP_PATTERNS.items() if key in sensor), None)
    if not pattern:
        return MISSING
    pattern = re.compile(pattern)
    for line in _stream(rawFileName):
        match = pattern.search(line)
        if match:
            return match.group(1)
    return MISSING


def SNfromRawBinary(rawFileName):
    """The serial number in a binary raw file, via the mi instrument drivers.

    Shells out to the python2 ``mi`` environment, which must exist -- see mi.yml.
    Without it ADCP and OPTAA serials silently never resolve, so a failure here
    is worth reading rather than ignoring.
    """
    driverKey = next((key for key in MI_DRIVERS if key in rawFileName), None)
    if driverKey == 'ADCP' and 'VADCP' in rawFileName:
        driverKey = 'VADCP'
    if not driverKey:
        return MISSING
    driver, outputFile = MI_DRIVERS[driverKey]

    ## Only the first chunk is needed -- the serial number is in the file header.
    downloadFile = re.search(r"https://\S+/\S+/\S+/\S+/(.*)", rawFileName).group(1)
    response = requests.get(rawFileName, stream=True)
    with open(downloadFile, 'wb') as handle:
        for chunk in response.iter_content(chunk_size=512 * 6):
            handle.write(chunk)
            break

    playback = (f'conda run -n mi-racle python2 -m mi.core.instrument.playback '
                f'datalog {driver} emptyField log:// csv:// {downloadFile}')
    print(playback)
    failed = subprocess.call(playback, shell=True)
    os.remove(downloadFile)

    if failed or not os.path.isfile(outputFile):
        print(f'no serial number produced for {rawFileName}')
        return MISSING
    serial = str(int(pd.read_csv(outputFile, nrows=1).serial_number.iloc[0]))
    os.remove(outputFile)
    return serial


def partialMatch(str1, str2, minCharacters):
    """True when the strings share a tail of at least ``minCharacters``.

    Vendors and the sensor bulk record disagree about serial number prefixes, so
    a trailing-digit match is often all there is to go on.
    """
    if len(str1) < minCharacters or len(str2) <= minCharacters:
        return False
    return str1 in str2 or str2 in str1 or str1[-minCharacters:] in str2


def searchITM(RF_assignment, RF_key, ITM_dict):
    for key, values in ITM_dict.items():
        if any(RF_key[18:24] in instType.replace('-', '') for instType in values['instrumentType']):
            if any(RF_assignment in assign for assign in values['assignments']):
                return key
    return None


def _candidates(key, sortedFileList, index, deployDate):
    """Files to try for one deployment, in the order they are worth trying.

    The file closest in time to the deployment is the best guess, then its
    immediate neighbours. Those three are read for a power-on banner. Failing
    that the search moves further forward, where the banner is long past and the
    serial number has to come out of the data lines themselves -- and only if
    that file postdates the deployment, so a previous deployment's instrument is
    never read back.
    """
    ## A deep profiler OPTAA is both binary and on a profiler; the driver wins,
    ## because the profiler's engineering file does not name it.
    if any(sensor in key[18:27] for sensor in BINARY_RAW):
        deepExtract = SNfromRawBinary
    elif 'PD' in key and 'DP' in key:
        deepExtract = lambda f: SNfromDP(f, key)
    else:
        deepExtract = SNfromRaw

    yield index, SNfromFirstRaw
    if len(sortedFileList) == 1:
        return
    if index - 1 >= 0:
        yield index - 1, SNfromFirstRaw
    yield index + 1, SNfromFirstRaw

    if len(sortedFileList) > index + 3 and sortedFileList[index + 3][0] > deployDate:
        yield index + 3, deepExtract
        if deepExtract is SNfromRawBinary:
            yield index + 5, SNfromRawBinary


def rawFileMatchExtract(RefDes_dict):
    """Fill in ``firstRawFile`` and ``rawSN`` for every deployment, from the archive.

    Deployments with no resolvable serial number are left as they came in; they
    are the ones that need a person and a photograph.
    """
    for key, deployments in RefDes_dict.items():
        print('creating file list for: ' + key)
        if 'PD' in key and 'DP' in key:
            sortedFileList = createFileList_DP(key)
        else:
            sortedFileList = createFileList(key)
        if not sortedFileList:
            continue

        for deployment in deployments:
            if 'nan' in str(deployment['deployEnd']):
                endDate = datetime.datetime.now()
            else:
                endDate = datetime.datetime.strptime(deployment['deployEnd'], '%Y-%m-%dT%H:%M:%S')

            closest = min(sortedFileList, key=lambda entry: abs(entry[0] - deployment['deployDate']))
            index = sortedFileList.index(closest)

            for offset, extract in _candidates(key, sortedFileList, index, deployment['deployDate']):
                if not 0 <= offset < len(sortedFileList):
                    continue
                fileDate, fileName = sortedFileList[offset]
                serial = extract(fileName)
                if MISSING not in serial and fileDate < endDate:
                    deployment['firstRawFile'] = fileName
                    deployment['rawSN'] = serial
                    break

    return RefDes_dict
