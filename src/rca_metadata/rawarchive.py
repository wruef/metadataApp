"""Listing the OOI raw data archive.

The archive is served as Apache directory indexes, so listing means parsing
html -- there is no API. Everything here is read-only and network-bound.
"""

import datetime
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


def listFD(url):
    """Files and subfolders linked from one archive directory index."""
    soup = BeautifulSoup(requests.get(url).text, 'html.parser')
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
    if depth:
        for folder in folders:
            if not UPWARD_LINK.search(folder):
                files += _walk(folder, depth - 1)
    return files


def createFileList(refDesg):
    """Dated raw files for a reference designator, newest last.

    The archive sorts into year and month folders, with some 2014-2017 files
    left at the top level, so both are searched.
    """
    site, node = refDesg[0:8], refDesg[9:14]
    instrument, instrumentPartial = refDesg[18:27], refDesg[18:23]
    nodeFiles, nodeFolders = listFD(f'{RAW_URL_BASE}{site}/{node}')

    fileList = [f for f in nodeFiles if instrumentPartial in f]
    for folder in nodeFolders:
        if instrument in folder:
            fileList += _walk(folder, depth=2)

    return sorted((fileDate(f), f) for f in fileList if fileDate(f))


def createFileList_DP(refDesg):
    """Dated deep profiler serial-number files, newest last.

    These live under ``eng_data`` in year/month/day folders, and only the
    ``sernums_hi-res_`` files carry serial numbers.
    """
    site = refDesg[0:8]
    node = refDesg[9:14].replace('DP', 'PD')
    _, yearFolders = listFD(f'{RAW_URL_BASE}{site}/{node}/eng_data/')

    fileList = []
    for yearFolder in yearFolders:
        if not UPWARD_LINK.search(yearFolder) and re.search(r".*202.*", yearFolder):
            fileList += _walk(yearFolder, depth=2)

    fileList = [f for f in fileList if 'sernums_hi-res_' in f]
    return sorted((fileDate(f), f) for f in fileList if fileDate(f))
