"""Tests for the pure parts of serial extraction -- which files get tried, and
in what order. The extractors themselves are network-bound and not covered here.
"""

import datetime

from rca_metadata.serials import SNfromFirstRaw, SNfromRaw, SNfromRawBinary, _candidates, partialMatch

CTD = 'CE02SHBP-LJ01D-06-CTDBPN106'
ADCP = 'RS01SBPS-PC01A-05-ADCPTB104'
DP = 'RS01SBPD-DP01A-06-DOSTAD104'
DP_BINARY = 'RS01SBPD-DP01A-05-OPTAAC102'

## Sits early in the archive, so files a few positions on still postdate it.
DEPLOY = datetime.datetime(2020, 1, 3)


def fileList(n, start=datetime.datetime(2020, 1, 1)):
    return [(start + datetime.timedelta(days=i), f'file_{i}.log') for i in range(n)]


def test_closestFileIsTriedFirst():
    first = next(iter(_candidates(CTD, fileList(10), 4, DEPLOY)))
    assert first == (4, SNfromFirstRaw)


def test_neighboursAreTriedBeforeMovingFurtherOut():
    offsets = [o for o, _ in _candidates(CTD, fileList(10), 4, DEPLOY)]
    assert offsets == [4, 3, 5, 7]


def test_singleFileArchiveTriesOnlyThatFile():
    assert [o for o, _ in _candidates(CTD, fileList(1), 0, DEPLOY)] == [0]


def test_noNegativeIndexAtTheStartOfTheArchive():
    """A negative offset would wrap to the newest file in the archive, which is
    the wrong deployment entirely."""
    offsets = [o for o, _ in _candidates(CTD, fileList(10), 0, DEPLOY)]
    assert all(o >= 0 for o in offsets)


def test_laterFilesAreSkippedWhenTheyPredateTheDeployment():
    """Reading further forward is only safe past the deployment date."""
    late = datetime.datetime(2021, 1, 1)
    offsets = [o for o, _ in _candidates(CTD, fileList(10), 4, late)]
    assert offsets == [4, 3, 5]


def test_binarySensorsGetTheDriverAndAnExtraAttempt():
    candidates = list(_candidates(ADCP, fileList(10), 4, DEPLOY))
    assert [o for o, _ in candidates] == [4, 3, 5, 7, 9]
    assert candidates[3][1] is SNfromRawBinary


def test_textSensorsFallBackToDataLines():
    candidates = list(_candidates(CTD, fileList(10), 4, DEPLOY))
    assert candidates[3][1] is SNfromRaw


def test_deepProfilerUsesItsOwnExtractor():
    candidates = list(_candidates(DP, fileList(10), 4, DEPLOY))
    assert candidates[3][1] not in (SNfromRaw, SNfromRawBinary, SNfromFirstRaw)


def test_binaryDriverWinsOverTheProfilerExtractor():
    """A deep profiler OPTAA matches both rules; the engineering file does not
    name it, so the driver has to run."""
    candidates = list(_candidates(DP_BINARY, fileList(10), 4, DEPLOY))
    assert candidates[3][1] is SNfromRawBinary


def test_partialMatchOnTrailingDigits():
    ## The vendor and the bulk record disagree about the prefix, so the shared
    ## tail is the match that counts.
    assert partialMatch('5471540-0030', '05400030', 4) is True
    assert partialMatch('1234567', '44567', 4) is True
    ## a string no longer than the match length is not enough to go on
    assert partialMatch('1234567', '4567', 4) is False
    assert partialMatch('12', '123456', 4) is False
    assert partialMatch('1234567', '9999', 4) is False
