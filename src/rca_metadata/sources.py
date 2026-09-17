"""Reading the two repositories, from a local clone or from GitHub at a ref.

A run is always against a specific state of ``asset-management`` and
``calibrationFiles``: production master, or a branch being checked before it
merges. Both look the same to the checks -- that is what makes a pre-cruise
branch check the same code path as a post-cruise run.

Listing uses the GitHub contents API rather than scraping the directory page,
so a rename of a class in GitHub's html cannot quietly empty a file list.
"""

import datetime
import os

import requests

API = 'https://api.github.com/repos/'
RAW = 'https://raw.githubusercontent.com/'

## Sensor directories are named for the instrument, and calibration files for the
## asset they belong to: AT<assetID>__<YYYYMMDD>.<ext>
CAL_FILE_PREFIX = 'AT'


class RepoSource:
    """One repository at one ref, read locally or over the API.

    ``local`` takes precedence when given, so a clone with uncommitted changes
    can be verified before anything is pushed.
    """

    def __init__(self, repo, ref='master', local=None, token=None):
        self.repo, self.ref, self.local = repo, ref, local
        self.session = requests.Session()
        if token:
            self.session.headers['Authorization'] = 'Bearer ' + token
        self._cache = {}

    def __repr__(self):
        return f'{self.repo}@{self.ref}' + (f' (local: {self.local})' if self.local else '')

    def _contents(self, path):
        if path not in self._cache:
            url = f'{API}{self.repo}/contents/{path}?ref={self.ref}'
            response = self.session.get(url)
            response.raise_for_status()
            self._cache[path] = response.json()
        return self._cache[path]

    def listDirs(self, path):
        """Subdirectory names under ``path``."""
        if self.local:
            full = os.path.join(self.local, path)
            return sorted(d for d in os.listdir(full) if os.path.isdir(os.path.join(full, d)))
        return sorted(e['name'] for e in self._contents(path) if e['type'] == 'dir')

    def listFiles(self, path, suffix=None, prefix=CAL_FILE_PREFIX):
        """File names under ``path`` starting with ``prefix``.

        ``suffix`` restricts by extension. It is explicit because the two repos
        want different answers -- asset-management holds OPTAA ``.ext`` sheets
        alongside the ``.csv`` calibrations, while a vendor file can carry any
        extension at all.
        """
        def wanted(name):
            return name.startswith(prefix) and (suffix is None or name.endswith(suffix))

        if self.local:
            full = os.path.join(self.local, path)
            if not os.path.isdir(full):
                print('directory does not exist: ' + full)
                return []
            return sorted(f for f in os.listdir(full) if wanted(f))
        return sorted(e['name'] for e in self._contents(path)
                      if e['type'] == 'file' and wanted(e['name']))

    def path(self, path):
        """A local path or a raw URL -- either is readable by pandas."""
        if self.local:
            return os.path.join(self.local, path)
        return f'{RAW}{self.repo}/{self.ref}/{path}'

    def blobUrl(self, path):
        """A link a person can open, as opposed to one pandas can read."""
        return f'https://github.com/{self.repo}/blob/{self.ref}/{path}'

    def fetch(self, path):
        return self.session.get(f'{RAW}{self.repo}/{self.ref}/{path}').content


## How many days apart two calibration dates can be before they are two
## calibrations rather than one recorded twice.
NEAR_DAYS = 7


def _asDate(value):
    """A YYYYMMDD file-name date, or None if it is not one."""
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return datetime.date(int(value[:4]), int(value[4:6]), int(value[6:]))
    except ValueError:
        return None


class VendorFiles:
    """Vendor originals, resolved to a file stem on disk.

    The comparison probes for sibling extensions with ``os.path.isfile``, so a
    remote run has to put the files somewhere first. PDFs are only ever probed,
    never read, so an empty placeholder stands in for one rather than pulling
    down a scan.
    """

    def __init__(self, source, cacheDir='tmp/calCache'):
        self.source, self.cacheDir = source, cacheDir
        ## file stem -> [(sensor directory, file name), ...]
        self.stems = {}
        for sensor in source.listDirs(''):
            for fileName in source.listFiles(sensor):
                self.stems.setdefault(fileName.split('.')[0], []).append((sensor, fileName))

        ## asset ID -> every calibration date on record for it. A file name that
        ## matches nothing can then still say whether the vendor has one for the
        ## same instrument a day or two away, which is what a mistyped date
        ## looks like from here.
        self.datesByAsset = {}
        for stem in self.stems:
            asset, _, date = stem.partition('__')
            if len(date) == 8 and date.isdigit():
                self.datesByAsset.setdefault(asset, set()).add(date)

    def __contains__(self, stem):
        return stem in self.stems

    def nearestDate(self, stem, within=NEAR_DAYS):
        """A vendor calibration for the same asset close to this one's date.

        Returns ``(date, daysApart)`` or None. Matching is on the whole stem, so
        a file name whose date is a day out matches nothing at all and the
        calibration reads as having no vendor original -- when the original is
        sitting there under a date one digit different. Four FLORD calibrations
        are exactly that.
        """
        asset, _, date = stem.partition('__')
        want = _asDate(date)
        if want is None:
            return None
        nearest, apart = None, None
        for candidate in self.datesByAsset.get(asset, ()):
            other = _asDate(candidate)
            if other is None:
                continue
            gap = abs((other - want).days)
            if apart is None or gap < apart:
                nearest, apart = candidate, gap
        return (nearest, apart) if apart is not None and apart <= within else None

    def stemPath(self, stem):
        """Path to the vendor files for ``stem``, without an extension."""
        entries = self.stems.get(stem)
        if not entries:
            return None
        sensor = entries[0][0]
        if self.source.local:
            return os.path.join(self.source.local, sensor, stem)

        cacheDir = os.path.join(self.cacheDir, sensor)
        os.makedirs(cacheDir, exist_ok=True)
        for sensor, fileName in entries:
            ## keep the stem's own spelling, lowercase the extension
            target = os.path.join(cacheDir, stem + fileName[len(stem):].lower())
            if os.path.isfile(target):
                continue
            if target.endswith('.pdf'):
                open(target, 'wb').close()
            else:
                open(target, 'wb').write(self.source.fetch(f'{sensor}/{fileName}'))
        return os.path.join(cacheDir, stem)
