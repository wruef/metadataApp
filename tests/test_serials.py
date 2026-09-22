"""Tests for the pure parts of serial extraction: which files get tried and in
what order, the two binary formats, the text patterns, and how a run's rows go
back into the parameter file. Nothing here touches the network.
"""

import datetime
import struct

import pandas as pd

from rca_metadata.instruments import partialMatch, sameSerial
from rca_metadata.serials import (
    DATA_LINE_PATTERNS,
    FIRST_RAW_PATTERNS,
    MISSING,
    SNfromFirstRaw,
    SNfromRaw,
    SNfromRawBinary,
    _candidates,
    acsSerial,
    mergeSerials,
    openDeployments,
    pd0Serial,
    portAgentPayload,
    searchLines,
)

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

def test_theLastFileBeforeTheDeploymentIsTheFirstOneTried():
    """The banner is printed when the instrument is powered up, and that happens
    during the deployment operation rather than on the calendar day the sheet
    records: one pressure sensor printed its serial at 23:00 the night
    before."""
    first = next(iter(_candidates(CTD, fileList(30), DEPLOY, RECOVER)))
    assert first == ('file_3.log', SNfromFirstRaw)


def test_theBannerPassReachesBackOneDayAndNoFurther():
    names = [f for f, _ in _candidates(CTD, fileList(30), DEPLOY, RECOVER)]
    assert 'file_3.log' in names
    assert 'file_2.log' not in names and 'file_0.log' not in names


def test_theBannerPassNeverReadsPastThePreviousRecovery():
    """A file from before the previous deployment came out holds the previous
    instrument, and reading one is how the wrong serial gets confirmed.

    The recovery time is as approximate as the deployment time, so the settling
    time applies to it too: a nitrate sensor recorded as recovered at midnight
    on the 6th left two files dated the 6th, both carrying the recovered
    instrument's serial, and the deployment that followed on the 7th would have
    been confirmed against the wrong one.
    """
    recovered = datetime.datetime(2020, 1, 4, 6, 0)
    names = [f for f, _ in _candidates(CTD, fileList(30), DEPLOY, RECOVER, recovered)]
    assert 'file_3.log' not in names
    assert names[0] == 'file_4.log'


def test_aTurnaroundLeavesNothingToReachBackTo():
    """Recovered and redeployed inside the settling time: there is no gap the
    banner could be in that the previous instrument is not also in. Finding
    nothing is the right answer, because the alternative is confirming the
    instrument that came out of the water."""
    recovered = DEPLOY - datetime.timedelta(hours=6)
    names = [f for f, _ in _candidates(CTD, fileList(30), DEPLOY, RECOVER, recovered)]
    assert names[0] == 'file_4.log'


def test_filesAfterRecoveryAreNeverRead():
    recover = datetime.datetime(2020, 1, 8)
    names = {f for f, _ in _candidates(CTD, fileList(30), DEPLOY, recover)}
    assert names == {'file_3.log', 'file_4.log', 'file_5.log', 'file_6.log'}


def test_bannerFilesThenDataLineFilesFromTheMiddle():
    candidates = list(_candidates(CTD, fileList(30), DEPLOY, RECOVER))
    ## one file from the day before, then five from inside the deployment
    assert [e for _, e in candidates[:6]] == [SNfromFirstRaw] * 6
    ## the window runs to December and the files stop in January, so the files
    ## nearest the middle are the last ones; then the earliest past two days
    assert candidates[6:] == [(f'file_{i}.log', SNfromRaw) for i in (29, 28, 27, 26, 7, 8, 9)]


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
    ## a string exactly as long as the match is a whole-string containment,
    ## and the rule is the same whichever side it is on
    assert partialMatch('1234567', '4567', 4) is True
    assert partialMatch('101', '0101', 3) is partialMatch('0101', '101', 3) is True
    ## shorter than the match, on either side, is not enough to go on
    assert partialMatch('12', '123456', 4) is False
    assert partialMatch('1234567', '9999', 4) is False


## --- whether a raw serial names the asset the record does ---

def test_theSameNumberInTwoDressesIsOneInstrument():
    """A pressure sensor reports 05400030 where both the RCA list and the sensor
    bulk record carry 5471540-0030: the dash dropped, the prefix cut to its last
    three digits and a zero put in front. Neither string contains the other."""
    assert sameSerial('05400030', '5471540-0030')
    assert sameSerial('05400047', '5471540-0047')
    ## pandas reads the parameter file's column as a number, so the leading zero
    ## is gone by the time the check sees it.
    assert sameSerial('5400030', '5471540-0030')


def test_theOtherPressureSensorsAreNotTheSameInstrument():
    """They share a seven-digit prefix, so a rule that matched loosely would
    confirm every one of them against every other."""
    for other in ('5471540-0028', '5471540-0029', '5471540-0031', '5471540-0046'):
        assert not sameSerial('05400030', other)


def test_aTailStillMatchesTheWayItAlwaysDid():
    """Most classes have only a tail extracted, and those comparisons are
    containment. Nothing here may change what they already decided."""
    assert sameSerial('325', '16-50325')
    assert sameSerial('1292', '1292')
    assert not sameSerial('325', '16-50326')


def test_ashortTailStillMatchesAndIsNotOnItsOwnEnough():
    """Containment is permissive by design, because a three-character tail is
    all most classes have extracted. It is the rival scan in the deployment
    check, not this function, that decides whether such a match identifies one
    instrument -- see the AMBIGUOUS_SN tests."""
    assert sameSerial('30', '5471540-0030')


def test_theDigitsOnlyPathNeedsFourOfThem():
    """The reconciliation exists for a seven-digit agreement. A shorter run of
    digits found only after both sides are stripped is a coincidence, not an
    identification."""
    ## Containment fails on both: neither string appears in the other.
    assert not sameSerial('0-30', '5471540-0030')
    assert sameSerial('0-0030', '5471540-0030')


def test_nothingOnEitherSideIsNotAMatch():
    for raw, recorded in (('', '5471540-0030'), ('05400030', ''), ('nan', '5471540-0030'),
                          ('05400030', 'nan')):
        assert not sameSerial(raw, recorded)


## --- the Sea-Bird pH sensor ---

PHSENH_FILE = 'PHSENH110_10.33.14.10_2101_20250828T1655_UTC.dat'

## What the instrument answers `gethd` with, trimmed to the lines that carry a
## number. Everything below the first line belongs to a part of the instrument
## rather than to the instrument.
GETHD = [
    "<HardwareData DeviceType='Deep SeapHox2' SerialNumber='0002085'>",
    "  <PCBAssembly PCBSerialNum='295820' AssemblyNum='42018.1E'/>",
    "      <SerialNumber desc='reference' value='MB21227'/>",
    "      <SerialNumber desc='isFET' value='20347'/>",
]


def test_theSeapHoxSerialIsReadFromTheHardwareBanner():
    assert searchLines(GETHD, PHSENH_FILE, FIRST_RAW_PATTERNS) == '0002085'


def test_theSeapHoxSerialIsAlsoReadFromThePlainStatusBlock():
    """`ds` prints the same number without the xml, and both spellings are in
    the archive."""
    block = ['[InstrumentInfo]', '  DeviceType      = Deep SeapHox2',
             '  SerialNumber    = 0002106', '  FirmwareVersion = 6.1.4 b30014']
    assert searchLines(block, PHSENH_FILE, FIRST_RAW_PATTERNS) == '0002106'


def test_theInstrumentsOwnSerialIsTakenAndNotItsPartsSerials():
    """The circuit boards and the internal pH and temperature sensors all print
    a serial in the same banner. Reading one of those would confirm a deployment
    against a component."""
    for line in GETHD[1:]:
        assert searchLines([line], PHSENH_FILE, FIRST_RAW_PATTERNS) == MISSING


def test_theSeapHoxSerialReconcilesWithTheRecordsSpelling():
    """The instrument writes 0002085 where both records carry 721-2085: the
    same number under a product prefix."""
    assert sameSerial('0002085', '721-2085')
    ## pandas reads the parameter file's column as a number, so the leading
    ## zeros are gone by the time the check sees it.
    assert sameSerial('2085', '721-2085')
    assert not sameSerial('0002085', '721-2069')


def test_onlyTheSeabirdPhSensorIsVerifiableByRawFile():
    """PHSEND and PHSENA are Sunburst SAMI2-pH. Their records carry a one-byte
    device id that is not the serial and changes between deployments, so nothing
    in their raw data identifies the instrument."""
    from rca_metadata.instruments import expectsRawSerial

    assert expectsRawSerial('CE02SHBP-LJ01D-10-PHSENH110')
    assert expectsRawSerial('CE04OSPS-PC01B-4C-PHSENH109')
    assert not expectsRawSerial('CE02SHBP-LJ01D-10-PHSEND103')
    assert not expectsRawSerial('RS01SBPS-PC01A-4B-PHSENA102')


def test_aSerialKeepsItsLeadingZerosThroughTheParameterFile(tmp_path):
    """Read as a number, a Sea-Bird pH sensor's 0002085 comes back 2085, and the
    next extraction writes every untouched row back without its leading zeros --
    so rows nobody attempted turn up in the pull request a reviewer is told to
    read. The comparison tolerates either spelling; the file should still say
    what the instrument printed."""
    from rca_metadata.serials import readSerialTable

    path = tmp_path / 'rawFileSN.csv'
    path.write_text(
        'referenceDesignator,deployNum,deployYear,rawFile,rawSerialNumber,attemptedAt,filesTried\n'
        'CE02SHBP-LJ01D-10-PHSENH110,1.0,2025,http://x/a.dat,0002085,2026-09-21,\n'
        'RS01SLBS-MJ01A-06-PRESTA101,1.0,2014,http://x/b.dat,05400030,2026-09-19,\n')

    table = readSerialTable(str(path))
    assert list(table['rawSerialNumber']) == ['0002085', '05400030']

    ## Merging an unrelated attempt leaves both spellings alone.
    merged = mergeSerials(table, [{
        'referenceDesignator': 'RS01SUM1-LJ01B-09-PRESTB102', 'deployNum': 1.0,
        'deployYear': 2014, 'rawFile': 'http://x/c.dat', 'rawSerialNumber': '05400031',
        'attemptedAt': '2026-09-21', 'filesTried': ''}])
    assert set(merged['rawSerialNumber']) == {'0002085', '05400030', '05400031'}


## --- every serial an asset is on record for ---

def test_everySerialIsBothRecords():
    """The bulk record carries one number, the primary component of the
    assembly. The RCA instrument list carries the rest and says what each
    belongs to."""
    from rca_metadata.instruments import everySerial

    serialByAsset = {'ATAPL-70248-00002': 'P2-SUBC13114'}
    assets = {'ATAPL-70248-00002': {'mfgSN': ['13114', '12099', '12100', '70501'],
                                    'SNnotes': 'Prod2Cam, LEDs, LEDs, PT'}}
    assert everySerial('ATAPL-70248-00002', serialByAsset, assets) == [
        'P2-SUBC13114', '13114', '12099', '12100', '70501']


def test_everySerialDropsWhatIsNotANumber():
    from rca_metadata.instruments import everySerial

    assert everySerial('ATAPL-1', {'ATAPL-1': 'nan'}, {'ATAPL-1': {'mfgSN': [' 24494', '']}}) \
        == ['24494']
    assert everySerial('ATAPL-2', {}, {}) == []


def test_aComponentSerialStillNamesTheAssetItBelongsTo():
    """A camera's pressure-tilt unit reads 70501. The bulk record carries only
    the Prod2Cam, so until every recorded serial was read this placed nothing."""
    from rca_metadata.instruments import everySerial

    assets = {'ATAPL-70248-00002': {'mfgSN': ['13114', '12099', '12100', '70501']}}
    held = everySerial('ATAPL-70248-00002', {'ATAPL-70248-00002': 'P2-SUBC13114'}, assets)
    assert any(sameSerial('70501', serial) for serial in held)
    assert not sameSerial('70501', 'P2-SUBC13114')


def test_aSerialMatchesFromTheEndAndNotFromTheMiddle():
    """`117` sits inside the vendor part number `16P71176-7231`, which belongs
    to another instrument entirely. Matching anywhere inside made a confirmed
    CTD read as ambiguous against it."""
    assert sameSerial('117', '16-50117')
    assert not sameSerial('117', '16P71176-7231')


def test_aSerialRecordedBesideItsTagNumberIsStillFound():
    """One asset carries `5277187-0138/TAG#: 116117`. Each part is compared on
    its own, so the serial is found and the tag number does not swallow it."""
    assert sameSerial('138', '5277187-0138/TAG#: 116117')
    assert not sameSerial('99', '5277187-0138/TAG#: 116117')
