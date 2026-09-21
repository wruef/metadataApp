"""Serial numbers read out of raw data files.

A deployment's serial number is the one piece of metadata the raw archive can
settle without a person looking at a photograph, so these extractors decide how
much of the HITL queue survives a run.

Every extractor returns ``MISSING`` rather than raising when it finds nothing.
Text instruments print their serial in a power-on banner or on every data line;
the two binary instruments carry it in every record, in a fixed place, and are
read with a few lines of struct rather than the python2 instrument drivers the
notebooks shelled out to.
"""

import datetime
import os
import re
import struct

import pandas as pd
import requests

from .instruments import expectsRawSerial
from .rawarchive import createFileList, createFileList_DP

MISSING = '-99999'

## Sensors whose raw files are binary. The VADCPB is an ADCP by name only: a
## Nortek Signature rather than a Teledyne Workhorse, and it writes text.
BINARY_RAW = ['ADCP', 'OPTAA']
TEXT_DESPITE_NAME = ['VADCPB']

## Serial number reported by the sensor at power-on, in the first raw file.
## (sensor key in filename) -> (patterns, how many trailing digits are the serial)
FIRST_RAW_PATTERNS = {
    'CTD': ([r"<HardwareData.*SerialNumber\s=\s\'(\d{1,10})\'>",
             r"SerialNumber\s=\s'(\d{1,10})'>"], 4),
    'SPKIR': ([r"S\/N:\s+(\d{2,4})"], 3),
    'NUTNR': ([r"SUNA\sSN:(\d{1,4}).*"], 3),
    'FLOR': ([r"Ser\s.*-(\d{1,4}).*"], None),
    ## The instrument reports SerialNumber='05400030' where both the RCA list
    ## and the sensor bulk record carry 5471540-0030: the same number in vendor
    ## part-number dress, the dash gone and the prefix cut to its last three
    ## digits with a zero in front. The whole eight characters are kept, because
    ## seven of them agree with the record's digits exactly -- see `sameSerial`.
    ## The old pattern let `.*` eat the number and kept two characters of what
    ## was left, which is how five deployments came to record a single digit.
    'PREST': ([r"<HardwareData.*SerialNumber='(\d{1,10})'>",
               r"SerialNumber='(\d{4,10})'"], None),
    ## A Sea-Bird Deep SeapHox2, which answers `gethd` with the xml and `ds`
    ## with the plain block, and both spellings are in the archive:
    ##
    ##     <HardwareData DeviceType='Deep SeapHox2' SerialNumber='0002085'>
    ##       SerialNumber    = 0002106
    ##
    ## The record carries 721-2085 against the instrument's 0002085 -- the same
    ## number under a product prefix -- which `sameSerial` reconciles on the
    ## last four digits. Anchored on `SerialNumber=` so the circuit boards'
    ## `PCBSerialNum` and the internal pH and temperature sensors'
    ## `<SerialNumber desc=... value=...>` are left alone; those are parts of
    ## the instrument rather than the instrument.
    'PHSENH': ([r"SerialNumber='(\d{4,10})'", r"SerialNumber\s*=\s*(\d{4,10})"], None),
    'TMPSFA': ([r"RBR\s+XR-420\s+\d.\d{2,4}\s+(\d{1,9}).*"], 5),
    ## A Nortek Signature opens with "Nortek 104550 Data Interface", and every
    ## $PNORI information line carries the serial as its third field.
    'VADCPB': ([r"Nortek\s+(\d{4,7})\s+Data", r"\$PNORI\d?,\d+,(\d{4,7}),"], None),
}

## Serial number carried in the data lines themselves, for files that print no
## power-on banner. PARAD serials agree between the two records -- clean three
## and four digit numbers, spelled the same in both -- so keeping a tail here
## costs little. The PAR sensor fitted since 2019 announces itself as SATPRL
## rather than SATPAR; without that spelling every PAR deployment from 2020 on
## read as having no serial.
DATA_LINE_PATTERNS = {
    'VADCPB': ([r"\$PNORI\d?,\d+,(\d{4,7}),"], None),
    'SPKIR': ([r".*SATDI70(\d{3}).*"], 3),
    'NUTNR': ([r"SATSDF(\d{1,4}).*"], 3),
    'PARAD': ([r"SATPAR(\d{1,4}).*", r"SATPRS(\d{1,4}).*", r"SATPRL(\d{1,4}).*"], 3),
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

## How much of a binary file to read. The serial is in every ADCP ensemble and
## every ac-s packet, so the first half megabyte holds it many times over.
BINARY_HEAD = 512 * 1024

## The columns of params/rawFileSN.csv. The last two record the attempt itself,
## so a row with no serial says which files were read to conclude that, and a
## later run can tell a deployment never tried from one tried and empty.
COLUMNS = ['referenceDesignator', 'deployNum', 'deployYear', 'rawFile', 'rawSerialNumber',
           'attemptedAt', 'filesTried']

## The serial is text, whatever it looks like. Read as a number, a Sea-Bird pH
## sensor's 0002085 comes back 2085 and a pressure sensor's 05400030 comes back
## 5400030 -- and the next extraction writes every one of them back without its
## leading zeros, so five rows nobody attempted turn up in the pull request the
## reviewer is told to read. The comparison tolerates either spelling; the
## parameter file should still say what the instrument actually printed.
SERIAL_COLUMN = {'rawSerialNumber': str}


def readSerialTable(path):
    """params/rawFileSN.csv, with the serial column left as it was written."""
    return pd.read_csv(path, dtype=SERIAL_COLUMN)


def _stream(rawFileName):
    """Raw file lines, decoded lossily -- these files are not reliably utf-8."""
    response = requests.get(rawFileName, stream=True, timeout=120)
    return (line.decode('utf-8', errors='ignore') for line in response.iter_lines())


def searchLines(lines, key, table):
    """The first serial one of ``table``'s patterns finds in ``lines``.

    ``key`` picks the patterns: it is the raw file's name, which carries the
    instrument's. Only the first sensor whose key it contains is tried.
    """
    for sensor, (patterns, tail) in table.items():
        if sensor not in key:
            continue
        compiled = [re.compile(p) for p in patterns]
        for line in lines:
            for pattern in compiled:
                match = pattern.search(line)
                if match:
                    return match.group(1)[-tail:] if tail else match.group(1)
        break
    return MISSING


def SNfromFirstRaw(rawFileName):
    """The serial number a sensor reports when it powers on."""
    return searchLines(_stream(rawFileName), rawFileName, FIRST_RAW_PATTERNS)


def SNfromRaw(rawFileName):
    """The serial number embedded in data lines, for files with no power-on banner."""
    return searchLines(_stream(rawFileName), rawFileName, DATA_LINE_PATTERNS)


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


## --- binary formats ---

PORT_AGENT_SYNC = b'\xa3\x9d\x7a'
PORT_AGENT_HEADER = 16
## The older wrapper: a text timestamp before each record and a closing tag
## after it, with the instrument's bytes in between. 2016 and 2017 files use it.
OOI_TIMESTAMP = re.compile(rb'<OOI-TS [^>]*>\r\n|<\\OOI-TS>\r\n')

PD0_SYNC = b'\x7f\x7f'
PD0_FIXED_LEADER = b'\x00\x00'
## Instrument serial number, bytes 55-58 of the fixed leader in the Workhorse
## output data format, counted from one there and from zero here.
PD0_SERIAL_OFFSET = 54

ACS_REGISTRATION = b'\xff\x00\xff\x00'
ACS_METER_TYPE = 0x53


def portAgentPayload(data):
    """The instrument's own bytes, unwrapped from the archive's log format.

    Every record the archive keeps for a serial instrument is wrapped. Today it
    is a port agent packet: three sync bytes, a type, a big-endian size, a
    checksum and an eight byte timestamp, then the bytes the instrument sent.
    Before 2018 it was a text timestamp tag before the bytes and a closing tag
    after. An instrument record can span wrappers either way, so the payloads
    are joined back into one stream -- an ADCP ensemble with a timestamp tag
    inside it fails its checksum, and a 2017 deployment read as having no
    serial for that. Data with no wrapper in it is returned as it is.
    """
    if b'<OOI-TS ' in data:
        return OOI_TIMESTAMP.sub(b'', data)
    payloads, i = [], data.find(PORT_AGENT_SYNC)
    if i < 0:
        return data
    while 0 <= i <= len(data) - PORT_AGENT_HEADER:
        size = struct.unpack_from('>H', data, i + 4)[0]
        payloads.append(data[i + PORT_AGENT_HEADER:i + size])
        i = data.find(PORT_AGENT_SYNC, i + max(size, PORT_AGENT_HEADER))
    return b''.join(payloads)


def pd0Serial(stream):
    """The serial number in the first intact Teledyne PD0 ensemble, or None.

    An ensemble is header, then data types at the offsets the header lists, then
    a checksum over everything before it. The checksum is what separates an
    ensemble from a pair of sync bytes that happen to occur in the data: without
    it one file in eight yields a number belonging to nothing.
    """
    i = stream.find(PD0_SYNC)
    while 0 <= i <= len(stream) - 6:
        length = struct.unpack_from('<H', stream, i + 2)[0]
        if (len(stream) >= i + length + 2
                and sum(stream[i:i + length]) & 0xFFFF == struct.unpack_from('<H', stream, i + length)[0]):
            for k in range(stream[i + 5]):
                offset = i + struct.unpack_from('<H', stream, i + 6 + 2 * k)[0]
                if stream[offset:offset + 2] == PD0_FIXED_LEADER and offset + PD0_SERIAL_OFFSET + 4 <= len(stream):
                    return struct.unpack_from('<I', stream, offset + PD0_SERIAL_OFFSET)[0]
        i = stream.find(PD0_SYNC, i + 2)
    return None


def acsSerial(stream):
    """The serial number in the first WET Labs ac-s packet, or None.

    A packet opens with a registration word, a record length, a packet type, a
    reserved byte, the meter type and then three bytes of serial number.
    """
    i = stream.find(ACS_REGISTRATION)
    while 0 <= i <= len(stream) - 12:
        if stream[i + 8] == ACS_METER_TYPE:
            return int.from_bytes(stream[i + 9:i + 12], 'big')
        i = stream.find(ACS_REGISTRATION, i + 4)
    return None


def SNfromRawBinary(rawFileName):
    """The serial number in a binary raw file: an ADCP ensemble or an ac-s packet."""
    head = requests.get(rawFileName, headers={'Range': f'bytes=0-{BINARY_HEAD - 1}'}, timeout=120).content
    parse = acsSerial if 'OPTAA' in rawFileName else pd0Serial
    serial = parse(portAgentPayload(head))
    return str(serial) if serial else MISSING


## --- which files to read, and the run over deployments ---

def _extractors(refDes):
    """(the extractor to try first, the one to fall back to) for an instrument.

    A deep profiler OPTAA is both binary and on a profiler; the binary parser
    wins, because the profiler's engineering file does not name it.
    """
    instrument = refDes[18:27]
    if (any(sensor in instrument for sensor in BINARY_RAW)
            and not any(sensor in instrument for sensor in TEXT_DESPITE_NAME)):
        return SNfromRawBinary, None
    if 'PD' in refDes and 'DP' in refDes:
        return (lambda fileName: SNfromDP(fileName, refDes)), None
    return SNfromFirstRaw, SNfromRaw


## How many files are read for a banner before giving up; how many are read
## from the middle of a deployment for a serial that every record carries; and
## how many early files are read when the middle yields nothing.
BANNER_FILES = 5
SETTLED_FILES = 4
EARLY_FILES = 3
## How long after the recorded deployment time a file is trusted to hold the
## new instrument. A deep profiler reported the recovered profiler's
## instruments 27 hours after the recorded start of the next deployment.
SETTLING_TIME = datetime.timedelta(days=2)
## How far before the recorded deployment date the power-on banner is looked
## for. The banner is printed when the instrument is powered up, which happens
## during the deployment operation and need not fall on the calendar day the
## sheet records: one pressure sensor printed its serial at 23:00 the night
## before, an hour outside a window that began at midnight.
BANNER_LOOKBACK = datetime.timedelta(days=1)


def _settled(inWindow, deployDate, endDate):
    """Files from well inside the deployment, the one nearest its middle first.

    The sheet's times are approximate. A deep profiler reported the recovered
    profiler's instruments 27 hours after the recorded start of the next
    deployment, and a turnaround day's ADCP file opens with the recovered
    unit's ensembles. Where every record carries the serial there is no reason
    to read near either end: the file nearest the middle of the deployment is
    the instrument that was in the water, and its neighbours are the retries.

    An instrument that failed mid-deployment is missing from those files, so
    the earliest files past the settling time follow as a last resort.
    """
    after = [(date, fileName) for date, fileName in inWindow if date > deployDate]
    middle = deployDate + (endDate - deployDate) / 2
    nearest = [fileName for _, fileName in sorted(after, key=lambda entry: abs(entry[0] - middle))[:SETTLED_FILES]]
    early = [fileName for date, fileName in after
             if date >= deployDate + SETTLING_TIME and fileName not in nearest][:EARLY_FILES]
    return nearest + early


def _candidates(refDes, files, deployDate, endDate, priorEnd=None):
    """Files worth trying for one deployment, in the order they are worth trying.

    Files dated within the deployment are the candidates: from the day the
    instrument went in the water to the day it came out. A file from before
    holds the previous deployment's instrument, and reading it is how the wrong
    serial gets confirmed.

    A power-on banner is printed once, when the instrument is switched on, and
    that moment belongs to the deployment operation rather than to the calendar
    day the sheet records. So the banner pass reaches back a day, to the files
    nearest the deployment moment on either side of it -- but never back to
    where the previous deployment could still be writing, which is
    ``priorEnd``, its recorded recovery, plus the settling time. Everything else -- a serial on the data lines, in
    every ADCP ensemble, in every ac-s packet, in every profiler engineering
    file -- is read from the middle of the deployment instead.
    """
    start = datetime.datetime.combine(deployDate.date(), datetime.time.min)
    inWindow = [(date, fileName) for date, fileName in files if start <= date < endDate]
    first, fallback = _extractors(refDes)
    if first is SNfromFirstRaw:
        ## The recovery time is as approximate as the deployment time, and a
        ## daily file stamped midnight covers the whole day before it. A nitrate
        ## sensor recovered at midnight on the 6th left two files dated the 6th,
        ## both full of the recovered instrument's serial; reaching back to the
        ## recorded recovery would have confirmed the wrong one. So the settling
        ## time applies to the previous deployment's end the same way it applies
        ## to this one's start -- which usually leaves nothing to reach back to,
        ## and finding nothing is the right answer where the alternative is
        ## confirming the instrument that came out of the water.
        floor = start - BANNER_LOOKBACK
        if priorEnd:
            floor = max(floor, priorEnd + SETTLING_TIME)
        before = sorted(entry for entry in files if floor <= entry[0] < start)
        ## Outward from the deployment moment: the last files before it, newest
        ## first, then the first files after it.
        for _, fileName in list(reversed(before[-BANNER_FILES:])) + inWindow[:BANNER_FILES]:
            yield fileName, first
        for fileName in _settled(inWindow, deployDate, endDate):
            yield fileName, fallback
    else:
        for fileName in _settled(inWindow, deployDate, endDate):
            yield fileName, first


def _endDate(deployment):
    """When the deployment ended, or now for one still in the water."""
    end = str(deployment['deployEnd'] or '')
    if not end.strip() or end == 'nan' or end == 'None':
        return datetime.datetime.now()
    return datetime.datetime.strptime(end, '%Y-%m-%dT%H:%M:%S')


def _isDeepProfiler(refDes):
    return 'PD' in refDes and 'DP' in refDes


def extractSerials(byRefDes, wanted=None, log=print):
    """Serial numbers for deployments, read from the archive.

    ``byRefDes`` is what ``loading.deploymentsByRefDes`` returns. ``wanted``
    limits the run to a set of ``(refDes, deployNum)`` pairs; None attempts every
    deployment. The archive is listed once per reference designator and only for
    the years its wanted deployments span.

    Returns one parameter-file row per deployment attempted, whether or not a
    serial was found -- a row that says which files were read and found nothing
    is a result too.
    """
    rows = []
    for refDes, deployments in byRefDes.items():
        todo = [d for d in deployments if wanted is None or (refDes, d['deployNum']) in wanted]
        if not todo:
            continue
        years = {year for d in todo for year in range(d['deployDate'].year, _endDate(d).year + 1)}
        log(f'{refDes}: listing {min(years)}-{max(years)}')
        lister = createFileList_DP if _isDeepProfiler(refDes) else createFileList
        files = lister(refDes, years)
        priorEnd = _priorEnds(deployments)
        for deployment in todo:
            rows.append(_extractOne(refDes, deployment, files, log,
                                    priorEnd.get(deployment['deployNum'])))
    return rows


def _priorEnds(deployments):
    """When the deployment before each one was recovered, by deployment number.

    None for the first, which has nothing before it. This is the floor on how
    far back the banner pass may reach, so it is taken from every deployment on
    record rather than from the ones being attempted.
    """
    ends, previous = {}, None
    for deployment in sorted(deployments, key=lambda d: d['deployDate']):
        ends[deployment['deployNum']] = previous
        previous = _endDate(deployment)
    return ends


def _extractOne(refDes, deployment, files, log, priorEnd=None):
    tried, serial, found = [], MISSING, 'none'
    for fileName, extract in _candidates(refDes, files, deployment['deployDate'],
                                         _endDate(deployment), priorEnd):
        tried.append(os.path.basename(fileName))
        serial = extract(fileName)
        if MISSING not in str(serial):
            found = fileName
            break
        serial = MISSING
    log(f"  deploy {deployment['deployNum']} ({deployment['deployDate']:%Y-%m-%d}): "
        f"{serial if found != 'none' else 'no serial'} after {len(tried)} file(s)")
    return {
        'referenceDesignator': refDes,
        'deployNum': deployment['deployNum'],
        'deployYear': deployment['deployDate'].year,
        'rawFile': found,
        'rawSerialNumber': serial,
        'attemptedAt': datetime.date.today().isoformat(),
        'filesTried': ' '.join(tried),
    }


def openDeployments(byRefDes, table, refDes=None, everything=False):
    """The ``(refDes, deployNum)`` pairs worth attempting.

    Those whose instrument class writes a serial into its data and -- unless
    ``everything`` -- that have no serial in the parameter file yet, whether
    because they were never attempted or because an attempt found nothing.
    """
    have = {(row.referenceDesignator, row.deployNum) for row in table.itertuples()
            if MISSING not in str(row.rawSerialNumber)}
    return {(rd, d['deployNum']) for rd, deployments in byRefDes.items()
            if expectsRawSerial(rd) and (not refDes or rd in refDes)
            for d in deployments if everything or (rd, d['deployNum']) not in have}


def mergeSerials(table, rows):
    """The parameter file with these attempts applied.

    A deployment attempted again replaces its row; one attempted for the first
    time is added. Rows the run did not touch are kept as they are, including
    those with no deployment number, which nothing can key on.
    """
    new = pd.DataFrame(rows, columns=COLUMNS)
    new['deployNum'] = new['deployNum'].astype(float)
    key = ['referenceDesignator', 'deployNum']
    replaced = table.set_index(key).index.isin(new.set_index(key).index)
    merged = pd.concat([table[~replaced], new], ignore_index=True).reindex(columns=COLUMNS)
    return merged.sort_values(key, na_position='last', kind='stable').reset_index(drop=True)
