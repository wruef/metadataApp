"""Listing the OOI raw data archive.

The archive is served as Apache directory indexes, so listing means parsing
html -- there is no API. Everything here is read-only and network-bound.

A listing is limited to the years a deployment touches wherever a caller knows
them. An instrument folder holds one month folder per month since 2014, so a
full listing is 130-odd index pages and a couple of minutes; the two or three
years a deployment spans are a dozen pages.
"""

import datetime
import functools
import re

import requests
from bs4 import BeautifulSoup

RAW_URL_BASE = 'https://rawdata.oceanobservatories.org/files/'

## Filenames carry their date one of three ways.
DATE_FORMATS = [
    (re.compile(r".*_(\d{8}T\d{6})_UTC.*"), '%Y%m%dT%H%M%S'),
    (re.compile(r".*_(\d{8}T\d{4})_UTC.*"), '%Y%m%dT%H%M'),
    (re.compile(r".*_(\d{8})_UTC.*"), '%Y%m%d'),
]

## The archive's own index pages link back to /files/, which would walk upwards forever.
UPWARD_LINK = re.compile(r".*\/\/files.*")

YEAR_FOLDER = re.compile(r".*/(\d{4})/$")

## Only the deep profiler engineering files of this name carry serial numbers.
## They begin in 2020; the earlier msgpack engineering files hold profiler
## state and name no instrument.
DP_SERIAL_FILES = 'sernums_hi-res_'

## A five-beam ADCP is archived as two folders, MAIN and -5TH, and both contain
## the reference designator's instrument name. The fifth beam is a separate unit
## whose serial number belongs to no asset, so only the main unit is listed.
FIFTH_BEAM = '-5TH'


@functools.lru_cache(maxsize=None)
def listFD(url):
    """Files and subfolders linked from one archive directory index.

    Cached for the life of the process: the six instruments on a deep profiler
    share one engineering tree, and a run lists it once rather than six times.
    """
    soup = BeautifulSoup(requests.get(url, timeout=120).text, 'html.parser')
    base = url if url.endswith('/') else url + '/'
    links = [base + node.get('href') for node in soup.find_all('a') if node.get('href')]
    return [l for l in links if l.endswith('t')], [l for l in links if l.endswith('/')]


def fileDate(fileName):
    """The datetime in a raw filename, or None when it carries none.

    Returning None matters: the notebook-era version left the previous file's
    date in place, which silently paired a deployment with the wrong file.
    """
    for pattern, fmt in DATE_FORMATS:
        match = pattern.search(fileName)
        if match:
            return datetime.datetime.strptime(match.group(1), fmt)
    return None


def _walk(url, depth):
    """Files at this level and below, to ``depth`` further levels of folders."""
    files, folders = listFD(url)
    ## a copy: the listing is cached, and extending it in place would hand the
    ## next caller every file twice
    files = list(files)
    if depth:
        for folder in folders:
            if not UPWARD_LINK.search(folder):
                files += _walk(folder, depth - 1)
    return files


def instrumentFolders(folders, instrument):
    """The archive folders holding one instrument's files."""
    return [f for f in folders if instrument in f and FIFTH_BEAM not in f]


def _yearFolders(folders, years):
    """Year folders, limited to ``years`` when given."""
    dated = [(f, YEAR_FOLDER.match(f)) for f in folders if not UPWARD_LINK.search(f)]
    return [f for f, match in dated
            if match and (years is None or int(match.group(1)) in years)]


def _dated(files):
    return sorted((fileDate(f), f) for f in files if fileDate(f))


def createFileList(refDesg, years=None):
    """Dated raw files for a reference designator, newest last.

    The archive sorts into year and month folders, with some 2014-2017 files
    left at the top level, so both are searched. ``years`` limits the folders
    walked; the top-level files are always read, because they are one page.
    """
    site, node = refDesg[0:8], refDesg[9:14]
    instrument, instrumentPartial = refDesg[18:27], refDesg[18:23]
    nodeFiles, nodeFolders = listFD(f'{RAW_URL_BASE}{site}/{node}')

    fileList = [f for f in nodeFiles if instrumentPartial in f]
    for folder in instrumentFolders(nodeFolders, instrument):
        _, yearFolders = listFD(folder)
        for yearFolder in _yearFolders(yearFolders, years):
            fileList += _walk(yearFolder, depth=1)
    return _dated(fileList)


def createFileList_DP(refDesg, years=None):
    """Dated deep profiler serial-number files, newest last.

    These live under ``eng_data`` in year/month/day folders.
    """
    site = refDesg[0:8]
    node = refDesg[9:14].replace('DP', 'PD')
    _, yearFolders = listFD(f'{RAW_URL_BASE}{site}/{node}/eng_data/')

    fileList = []
    for yearFolder in _yearFolders(yearFolders, years):
        fileList += _walk(yearFolder, depth=2)
    return _dated(f for f in fileList if DP_SERIAL_FILES in f)
