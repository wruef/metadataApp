"""Tests for the pure parts of serial extraction: which files get tried and in
what order, the two binary formats, the text patterns, and how a run's rows go
back into the parameter file. Nothing here touches the network.
"""

import datetime
import struct

import pandas as pd

from rca_metadata.serials import (MISSING, SNfromFirstRaw, SNfromRaw, SNfromRawBinary, _candidates,
                                  acsSerial, mergeSerials, openDeployments, partialMatch, pd0Serial,
                                  portAgentPayload, searchLines, FIRST_RAW_PATTERNS, DATA_LINE_PATTERNS)

CTD = 'CE02SHBP-LJ01D-06-CTDBPN106'
ADCP = 'RS01SBPS-PC01A-05-ADCPTB104'
DP = 'RS01SBPD-DP01A-06-DOSTAD104'
DP_BINARY = 'RS01SBPD-DP01A-05-OPTAAC102'

DEPLOY = datetime.datetime(2020, 1, 5, 10, 30)
RECOVER = datetime.datetime(2020, 12, 1)


def fileList(n, start=datetime.datetime(2020, 1, 1)):
    """One file a day from ``start``, stamped midnight as the archive does."""
    return [(start + datetime.timedelta(days=i), f'file_{i}.log') for i in range(n)]


## --- which files are read ---

def test_theDeploymentDayIsTheFirstFileTried():
    """A daily file is stamped midnight, before a mid-morning deployment, and
    the power-on banner is in it."""
    first = next(iter(_candidates(CTD, fileList(30), DEPLOY, RECOVER)))
    assert first == ('file_4.log', SNfromFirstRaw)


def test_filesBeforeTheDeploymentAreNeverRead():
    """They hold the previous deployment's instrument, and reading one is how
    the wrong serial gets confirmed."""
    names = [f for f, _ in _candidates(CTD, fileList(30), DEPLOY, RECOVER)]
    assert 'file_3.log' not in names and 'file_0.log' not in names


def test_filesAfterRecoveryAreNeverRead():
    recover = datetime.datetime(2020, 1, 8)
    names = {f for f, _ in _candidates(CTD, fileList(30), DEPLOY, recover)}
    assert names == {'file_4.log', 'file_5.log', 'file_6.log'}


def test_bannerFilesThenDataLineFilesFromTheMiddle():
    candidates = list(_candidates(CTD, fileList(30), DEPLOY, RECOVER))
    assert [e for _, e in candidates[:5]] == [SNfromFirstRaw] * 5
    ## the window runs to December and the files stop in January, so the files
    ## nearest the middle are the last ones; then the earliest past two days
    assert candidates[5:] == [(f'file_{i}.log', SNfromRaw) for i in (29, 28, 27, 26, 7, 8, 9)]


def test_serialsCarriedByEveryRecordAreReadFromTheMiddleOfTheDeployment():
    """The sheet's times are approximate: a profiler reported the recovered
    instruments 27 hours after the recorded start, and a turnaround day's ADCP
    file opens with the recovered unit's ensembles. The middle of the
    deployment is the instrument that was in the water."""
    recover = datetime.datetime(2020, 1, 25)
    for refDes in (ADCP, DP):
        names = [f for f, _ in _candidates(refDes, fileList(30), DEPLOY, recover)]
        ## deployed Jan 5 10:30, recovered Jan 25: the middle is Jan 15, file_14
        assert names[:4] == ['file_14.log', 'file_15.log', 'file_13.log', 'file_16.log']
        ## then the earliest files past the two-day settling time, never the
        ## turnaround day or the day after it
        assert names[4:] == ['file_7.log', 'file_8.log', 'file_9.log']
        assert 'file_4.log' not in names and 'file_5.log' not in names


def test_binarySensorsUseTheParserAndNoFallback():
    candidates = list(_candidates(ADCP, fileList(30), DEPLOY, RECOVER))
    assert all(e is SNfromRawBinary for _, e in candidates)
    assert len(candidates) == 7


def test_aBinaryFileStampedAtTheDeploymentMinuteIsNotAfterIt():
    stamped = [(DEPLOY, 'at_deploy.dat'), (DEPLOY + datetime.timedelta(hours=1), 'later.dat')]
    assert [f for f, _ in _candidates(ADCP, stamped, DEPLOY, RECOVER)] == ['later.dat']


def test_deepProfilerUsesItsOwnExtractor():
    candidates = list(_candidates(DP, fileList(30), DEPLOY, RECOVER))
    assert all(e not in (SNfromRaw, SNfromRawBinary, SNfromFirstRaw) for _, e in candidates)


def test_binaryParserWinsOverTheProfilerExtractor():
    """A deep profiler OPTAA matches both rules; the engineering file does not
    name it, so the binary parser has to run."""
    candidates = list(_candidates(DP_BINARY, fileList(30), DEPLOY, RECOVER))
    assert candidates[0][1] is SNfromRawBinary


def test_anEmptyWindowYieldsNothing():
    assert list(_candidates(CTD, [], DEPLOY, RECOVER)) == []


## --- the text patterns ---

def test_theNewerParSensorSpellsItselfSatprl():
    """The PAR fitted since 2019 announces SATPRL, and without that spelling
    every PAR deployment from 2020 on read as having no serial: 17 of them."""
    line = 'SATPRL1399,903632.627,-0.032,1.9,0.9,12.5,LOG,332154'
    assert searchLines([line], 'PARADA101_x.dat', DATA_LINE_PATTERNS) == '399'
    assert searchLines(['SATPAR0464,14238553.95,2157484928,150'], 'PARADA101_x.dat', DATA_LINE_PATTERNS) == '464'


def test_onlyTheFileOwnInstrumentPatternsAreTried():
    assert searchLines(['SATPRL1399,1'], 'CTDBPN106_x.dat', DATA_LINE_PATTERNS) == MISSING


def test_aNortekSignatureIsTextDespiteBeingAnAdcp():
    """The VADCPB replaced the Teledyne five-beam in 2024. It writes text, with
    the serial in its opening banner and on every $PNORI line."""
    banner = ['', 'Nortek 104550 Data Interface', '$PNORI1,4,104550,1,70,0.50,1.00,0*5A']
    assert searchLines(banner, 'VADCPB301_x.dat', FIRST_RAW_PATTERNS) == '104550'
    assert searchLines(banner[2:], 'VADCPB301_x.dat', DATA_LINE_PATTERNS) == '104550'
    _, extractor = next(_candidates('RS03AXPS-PC03A-06-VADCPB301', fileList(30), DEPLOY, RECOVER))
    assert extractor is SNfromFirstRaw


def test_aCtdBannerYieldsTheLastFourDigits():
    line = "<HardwareData DeviceType = 'SBE16plus' SerialNumber = '01650117'>"
    assert searchLines([line], 'CTDBPN106_x.dat', FIRST_RAW_PATTERNS) == '0117'


## --- the binary formats ---

def portAgentPacket(payload, kind=1):
    header = b'\xa3\x9d\x7a' + bytes([kind]) + struct.pack('>H', 16 + len(payload)) + b'\x00\x00' + b'\x00' * 8
    return header + payload


def pd0Ensemble(serial, fixedLeaderAt=8):
    """A minimal PD0 ensemble: header naming one data type, a fixed leader
    carrying ``serial`` at byte 54, then the checksum."""
    fixedLeader = bytearray(60)
    fixedLeader[0:2] = b'\x00\x00'
    fixedLeader[2:4] = bytes([50, 41])
    struct.pack_into('<I', fixedLeader, 54, serial)
    length = fixedLeaderAt + len(fixedLeader)
    header = b'\x7f\x7f' + struct.pack('<H', length) + b'\x00' + b'\x01' + struct.pack('<H', fixedLeaderAt)
    body = header + bytes(fixedLeader)
    assert len(body) == length
    return body + struct.pack('<H', sum(body) & 0xFFFF)


def test_theAdcpSerialIsReadOutOfTheFixedLeader():
    stream = portAgentPayload(portAgentPacket(pd0Ensemble(22115)))
    assert pd0Serial(stream) == 22115


def test_anEnsembleSplitAcrossPortAgentPacketsIsRejoined():
    ensemble = pd0Ensemble(19075)
    data = portAgentPacket(ensemble[:20]) + portAgentPacket(ensemble[20:])
    assert pd0Serial(portAgentPayload(data)) == 19075


def test_aSyncPairInTheDataIsNotAnEnsemble():
    """Two 0x7f bytes occur in data. Without the checksum one file in eight
    yielded a number belonging to nothing."""
    decoy = b'\x7f\x7f' + struct.pack('<H', 40) + b'\x00\x01' + struct.pack('<H', 8) + b'\x00\x00' + b'\x11' * 60
    assert pd0Serial(decoy + pd0Ensemble(18493)) == 18493
    assert pd0Serial(decoy) is None


def test_theOlderTimestampWrapperIsStrippedFromInsideAnEnsemble():
    """2016 and 2017 files wrap each record in text tags rather than port agent
    packets, and a tag landing inside an ensemble fails its checksum."""
    ensemble = pd0Ensemble(23442)
    data = (b'<OOI-TS 2017-07-29T19:21:31.375477Z TS>\r\n' + ensemble[:30] + b'<\\OOI-TS>\r\n'
            + b'<OOI-TS 2017-07-29T19:21:33.018009Z TS>\r\n' + ensemble[30:] + b'<\\OOI-TS>\r\n')
    assert pd0Serial(portAgentPayload(data)) == 23442


def test_dataWithNoPortAgentPacketsPassesThrough():
    assert portAgentPayload(b'plain bytes') == b'plain bytes'


def acsPacket(serial, meterType=0x53):
    return b'\xff\x00\xff\x00' + struct.pack('>H', 720) + b'\x05\x01' + bytes([meterType]) + serial.to_bytes(3, 'big') + b'\x00' * 20


def test_theOptaaSerialIsThreeBytesAfterTheMeterType():
    assert acsSerial(acsPacket(244)) == 244
    assert acsSerial(acsPacket(346)) == 346


def test_aPacketOfAnotherMeterTypeIsSkipped():
    assert acsSerial(acsPacket(999, meterType=0x00) + acsPacket(250)) == 250
    assert acsSerial(b'\x00' * 40) is None


## --- the parameter file ---

def table(rows):
    return pd.DataFrame(rows, columns=['referenceDesignator', 'deployNum', 'deployYear', 'rawFile', 'rawSerialNumber'])


def deployment(refDes, num, year):
    return {'refDes': refDes, 'deployNum': num, 'deployDate': datetime.datetime(year, 8, 1),
            'deployEnd': '', 'AssetID': 'ATAPL-1'}


def test_openDeploymentsAreThoseWithoutASerial():
    """Never attempted and attempted-but-empty alike; an instrument class that
    writes no serial is not one of them."""
    byRefDes = {CTD: [deployment(CTD, 1, 2014), deployment(CTD, 2, 2015), deployment(CTD, 3, 2016)],
                'RS01SBPS-SF01A-2A-PHSENA101': [deployment('RS01SBPS-SF01A-2A-PHSENA101', 1, 2014)]}
    existing = table([(CTD, 1.0, 2014, 'x.dat', '0117'), (CTD, 2.0, 2015, 'none', MISSING)])
    assert openDeployments(byRefDes, existing) == {(CTD, 2), (CTD, 3)}
    assert openDeployments(byRefDes, existing, everything=True) == {(CTD, 1), (CTD, 2), (CTD, 3)}
    assert openDeployments(byRefDes, existing, refDes=['nothing']) == set()


def test_mergeReplacesAttemptedRowsAndAddsNewOnes():
    existing = table([(CTD, 1.0, 2014, 'x.dat', '0117'), (CTD, 2.0, 2015, 'none', MISSING),
                      (CTD, float('nan'), 2017, 'none', MISSING)])
    rows = [{'referenceDesignator': CTD, 'deployNum': 2, 'deployYear': 2015, 'rawFile': 'y.dat',
             'rawSerialNumber': '0118', 'attemptedAt': '2026-09-18', 'filesTried': 'y.dat'},
            {'referenceDesignator': CTD, 'deployNum': 3, 'deployYear': 2016, 'rawFile': 'none',
             'rawSerialNumber': MISSING, 'attemptedAt': '2026-09-18', 'filesTried': 'a.dat b.dat'}]
    merged = mergeSerials(existing, rows)
    assert merged.deployNum.tolist()[:3] == [1.0, 2.0, 3.0] and pd.isna(merged.deployNum.iloc[3])
    assert merged.rawSerialNumber.tolist()[:3] == ['0117', '0118', MISSING]
    ## the untouched row keeps its place and gains empty attempt columns
    assert pd.isna(merged.attemptedAt.iloc[0]) and merged.filesTried.iloc[2] == 'a.dat b.dat'
    assert len(merged) == 4


def test_partialMatchOnTrailingDigits():
    ## The vendor and the bulk record disagree about the prefix, so the shared
    ## tail is the match that counts.
    assert partialMatch('5471540-0030', '05400030', 4) is True
    assert partialMatch('1234567', '44567', 4) is True
    ## a string no longer than the match length is not enough to go on
    assert partialMatch('1234567', '4567', 4) is False
    assert partialMatch('12', '123456', 4) is False
    assert partialMatch('1234567', '9999', 4) is False
