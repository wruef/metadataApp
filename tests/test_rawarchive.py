"""The pure parts of listing the archive: which folders belong to an instrument
and which years are walked. The listing itself is network-bound."""

import datetime

from rca_metadata.rawarchive import _yearFolders, fileDate, instrumentFolders

NODE = 'https://rawdata.oceanobservatories.org/files/RS01SBPS/PC01A/'


def test_theFifthBeamFolderIsNotTheInstrument():
    """A five-beam ADCP is archived as MAIN and -5TH, and both contain the
    instrument's name. The fifth beam's serial belongs to no asset, and taking
    both folders is why no VADCP serial was ever read: 0 of 22."""
    folders = [NODE + 'ADCPTD102/', NODE + 'VADCPA101-5TH/', NODE + 'VADCPA101MAIN/', NODE + 'VADCPB101/']
    assert instrumentFolders(folders, 'VADCPA101') == [NODE + 'VADCPA101MAIN/']
    assert instrumentFolders(folders, 'ADCPTD102') == [NODE + 'ADCPTD102/']


def test_onlyTheYearsAskedForAreWalked():
    folders = [NODE + f'ADCPTD102/{y}/' for y in (2019, 2020, 2021, 2022)] + ['https://rawdata.oceanobservatories.org//files/']
    assert _yearFolders(folders, {2020, 2021}) == [NODE + 'ADCPTD102/2020/', NODE + 'ADCPTD102/2021/']
    assert len(_yearFolders(folders, None)) == 4


def test_fileDateReadsTheThreeSpellings():
    assert fileDate('X_20210824T101530_UTC.dat') == datetime.datetime(2021, 8, 24, 10, 15, 30)
    assert fileDate('X_20210824T1015_UTC.dat') == datetime.datetime(2021, 8, 24, 10, 15)
    assert fileDate('X_20210824_UTC.dat') == datetime.datetime(2021, 8, 24)
    assert fileDate('style.css') is None


def test_walkingDoesNotExtendTheCachedListing(monkeypatch):
    """listFD is cached. The walker used to extend the cached list in place, so
    the second instrument on a profiler saw every file twice and its retries
    all read the same file."""
    from rca_metadata import rawarchive

    shared = ['https://x/2020/01/a_20200101_UTC.txt']
    monkeypatch.setattr(rawarchive, 'listFD', lambda url: (shared, ['https://x/2020/01/'] if url.endswith('2020/') else []))
    first = rawarchive._walk('https://x/2020/', depth=1)
    second = rawarchive._walk('https://x/2020/', depth=1)
    assert len(shared) == 1 and len(first) == len(second) == 2
