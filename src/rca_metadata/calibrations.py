"""Compare a github calibration file against the vendor original.

The notebook-era version of this check repeated the same twenty lines for each
of eight sensors, which is how two defects survived years of runs: a verdict of
COMPARED set before any vendor file was opened, and a difference computed
outside the coefficient loop. Here the per-sensor differences live in
:data:`SENSORS` -- asset IDs, which file extensions to try, how to read them --
and there is exactly one comparison loop.

Verdicts, strongest first:

``MISMATCH``             a coefficient disagrees with the vendor
``MISSING_COEFFICIENT``  the vendor file does not carry a coefficient the
                         github file claims, so it could not be checked
``CONSTANT_MISMATCH``    the only disagreements are with coefficientConstants.csv,
                         where no vendor value is involved
``COMPARED``             read and agreed
``PDF_NOTCOMPARED``      only a pdf is on file
``FORMAT_NOTCOMPARED``   a vendor file is on record, but not in the format this
                         instrument is compared against
``NO_VENDOR_FILE``       the sensor has a comparison rule but nothing on record
``NAN``                  no comparison rule for this sensor

Which vendor file each instrument is compared against
-----------------------------------------------------

One format per instrument, and no falling back to another. Where a vendor
publishes the same calibration twice, the two files do not carry the same
numbers at the same precision, and comparing against the wrong one produces
disagreements that are an artefact of the choice rather than a fault in the
data.

======== ============== =====================================================
sensor   file           why
======== ============== =====================================================
CTD      ``.xmlcon``    more resolution than the ``.cal`` or the pdf
DOFSTA   ``.cal``       more resolution than the ``.xml`` or the pdf
FLCDR    ``.dev``
FLNTU    ``.dev.lambda`` both ``.dev`` files are posted; only this one, which
                        carries volume scattering, is what asset-management is
                        generated from
FLORD    ``.dev.lambda``
NUTNR    ``.cal``
SPKIR    ``.cal``
OPTAA    ``.dev``       the pure-water calibration. The ``.cal`` beside it is
                        the air calibration and is not what asset-management
                        is built from.
PARA     ``.tdf``, then the ``.pdf`` certificate the coefficients were typed
         in from. Both require CC_a0, so a certificate for the other PAR
         family falls through rather than being half compared
PHSEN    ``.pdf``       the certificate carries the four E values and nothing
                        else; salinity and ADC bit depth are configuration,
                        listed in ``notVendor``
======== ============== =====================================================
"""

import ast
import functools
import math
import os

from . import vendor

RANK = {'MISMATCH': 3, 'MISSING_COEFFICIENT': 2, 'CONSTANT_MISMATCH': 1}

## Per sensor: the asset ID prefixes that identify it, how to read the value out
## of the github file, and the vendor formats to try in preference order.
##   needsMap  -- reader resolves names through coefficientMap.csv
##   keyBy     -- 'map' when the vendor dict is keyed by the vendor's own names
##   requires  -- the read only counts as a comparison if this key came back set
SENSORS = {
    'CTD': {
        'assetIds': ['66662', '69828', '69827', '67627'],
        'parseGithub': 'raw',
        ## .xmlcon only. A Seabird .cal publishes fewer significant figures than
        ## the .xmlcon, so comparing against it manufactures disagreements that
        ## are really rounding -- nine coefficients on ATAPL-67627-00001 differ
        ## by about one part in 10^7 for exactly that reason.
        'sources': [{'suffix': '.xmlcon', 'reader': vendor.readXmlcon, 'needsMap': True}],
    },
    'DOFSTA': {
        'assetIds': ['58694'],
        'parseGithub': 'raw',
        ## .cal only, which carries more resolution than the .xml or the pdf.
        'sources': [{'suffix': '.cal', 'reader': vendor.readDOFSTA, 'keyBy': 'map'}],
    },
    'FLNTU': {
        'assetIds': ['70110'],
        'parseGithub': 'float',
        ## Both .dev files are posted to the vendor repository, but only the
        ## .dev.lambda -- the one carrying volume scattering -- is what
        ## asset-management is generated from, so it is the only one to compare
        ## against. The plain .dev holds different numbers for the same names.
        'sources': [{'suffix': '.dev.lambda', 'reader': vendor.readFLNTU}],
    },
    'FLCDR': {
        'assetIds': ['70111'],
        'parseGithub': 'float',
        'sources': [{'suffix': '.dev', 'reader': vendor.readFLCDR}],
    },
    'FLORD': {
        'assetIds': ['58322'],
        'parseGithub': 'float',
        'sources': [{'suffix': '.dev.lambda', 'reader': vendor.readFLORD}],
    },
    'NUTNR': {
        'assetIds': ['68020'],
        'parseGithub': 'floatOrList',
        'sources': [{'suffix': '.cal', 'reader': vendor.readNUTNR}],
        'pdf': False,
    },
    'PARA': {
        'assetIds': ['66645', '78452'],
        'parseGithub': 'raw',
        ## The .tdf where the vendor shipped one; otherwise the certificate,
        ## which is where these three coefficients were typed in from. Both
        ## require CC_a0, so a certificate for a different PAR -- the ones
        ## carrying scaling and dark offset instead -- falls through rather
        ## than being half compared.
        'sources': [
            {'suffix': '.tdf', 'reader': vendor.readPARA, 'requires': 'CC_a0'},
            {'suffix': '.pdf', 'reader': vendor.readPARpdf, 'requires': 'CC_a0'},
        ],
    },
    'PHSEN': {
        'assetIds': ['58337', '70571', '91990'],
        'parseGithub': 'raw',
        'sources': [{'suffix': '.pdf', 'reader': vendor.readPHSENpdf, 'requires': 'CC_ea434'}],
        ## The certificate carries the four E values and nothing else. Salinity
        ## and the ADC bit depth are chosen when the instrument is configured --
        ## they vary across the archive, so they are not constants either -- and
        ## there is nothing on the vendor's page to check them against. Declared
        ## rather than reported missing on every row, which would bury the four
        ## values that can be checked.
        'notVendor': ['CC_psal', 'CC_sami_bits'],
    },
    'SPKIR': {
        'assetIds': ['58341'],
        'parseGithub': 'list',
        'sources': [{'suffix': '.cal', 'reader': vendor.readSPKIR, 'requires': 'CC_scale'}],
        'pdf': False,
    },
    ## The .dev is the pure-water calibration. The .cal posted beside it is the
    ## air calibration and is not what asset-management is generated from, so
    ## it is never read. One calibration is three files on the github side --
    ## the csv plus two .ext sheets it points at -- and the .dev carries all
    ## three, so the sheets are resolved before the comparison sees them.
    'OPTAA': {
        'assetIds': ['69943', '58332'],
        'parseGithub': 'floatOrList',
        'sources': [{'suffix': '.dev', 'reader': vendor.readOPTAA, 'ordered': True}],
    },
}


@functools.lru_cache(maxsize=None)
def _directoryIndex(directory):
    """Lowercased file name -> the name as the directory actually spells it."""
    try:
        return {name.lower(): name for name in os.listdir(directory)}
    except OSError:
        return {}


def anyVendorFile(vendorPath):
    """Whether the vendor repository holds anything at all for this stem.

    Used to tell two silences apart: nothing on record, and something on record
    in a format this instrument is not compared against.
    """
    directory, stem = os.path.split(vendorPath)
    prefix = (stem + '.').lower()
    return any(name.startswith(prefix) for name in _directoryIndex(directory))


def findVendorFile(vendorPath, suffix):
    """The vendor file for a stem and suffix, whatever case it is spelled in.

    27 vendor files carry .CAL or .DEV rather than .cal or .dev. A
    case-insensitive filesystem finds those and a case-sensitive one does not,
    so probing for an exact name made the check answer differently on a laptop
    than on a Linux runner -- 9 NUTNR calibrations reported as having no vendor
    file in CI while appearing fully compared on macOS.
    """
    directory, stem = os.path.split(vendorPath)
    actual = _directoryIndex(directory).get((stem + suffix).lower())
    return os.path.join(directory, actual) if actual else None


def assetIdOf(vendorPath):
    """The asset ID field of a vendor file name.

    Names run ``PREFIX-ASSETID-SERIAL__DATE``, so the asset ID is the second
    field and nothing else.
    """
    parts = os.path.basename(vendorPath).split('__')[0].split('-')
    return parts[1] if len(parts) > 1 else ''


def identifySensor(vendorPath):
    """Which sensor's rules a vendor file is compared under.

    Matched against the asset ID field alone, not against the path as a string.
    A substring search finds an asset ID inside the calibration date: a file
    dated 2017-01-10 spells 70110, which is FLNTU's asset ID, and 2017-01-11
    spells 70111, which is FLCDR's. Two real calibrations -- a NUTNR and a
    SPKIR -- were checked against the wrong instrument's rules for years and
    reported as having no vendor file, while their .cal sat right beside them.
    """
    assetId = assetIdOf(vendorPath)
    for sensor, spec in SENSORS.items():
        if assetId in spec['assetIds']:
            return sensor
    return None


def recordDiff(calCompare, fileName, coeffName, githubCoeff, expectedCoeff, coeffDiff, coeffSource):
    """Append one difference and promote the verdict to match its severity.

    A coefficient checked against coefficientConstants.csv is not a disagreement
    with the vendor -- there is no vendor value involved -- so it carries its own
    verdict, and a real vendor disagreement always outranks it.
    """
    verdict = {'vendor': 'MISMATCH', 'constant': 'CONSTANT_MISMATCH',
               'missing': 'MISSING_COEFFICIENT'}[coeffSource]
    if RANK[verdict] > RANK.get(calCompare[0], 0):
        calCompare[0] = verdict
    calCompare.append([fileName, coeffName, githubCoeff, expectedCoeff, coeffDiff, coeffSource])


def _githubValue(raw, how):
    ## Already parsed: an OPTAA sheet resolved from the .ext file it points at,
    ## or None where that file was not there to resolve.
    if raw is None or isinstance(raw, list):
        return raw
    if how == 'float':
        return float(raw)
    if how == 'list':
        return ast.literal_eval(raw)
    if how == 'floatOrList':
        return ast.literal_eval(raw) if '[' in str(raw) else float(raw)
    return raw


def _cells(value):
    """Every number in a value, however deeply nested."""
    if isinstance(value, list):
        for item in value:
            yield from _cells(item)
    else:
        yield value


def _unresolved(value):
    """A sheet reference the loader could not resolve.

    Checked for NaN as well as None because ``DataFrame.iterrows`` turns a
    None in an object column into NaN, so the value this sees is not the one
    the loader put there.
    """
    return value is None or (isinstance(value, float) and math.isnan(value))


def _orderedDifference(githubCoeff, expected):
    """Element by element, because the position carries the meaning.

    An OPTAA coefficient is indexed by wavelength: the nth clean-water offset
    belongs to the nth wavelength, and the nth row of each temperature array
    with it. Compared as sets, a reordering would pass, and so would 85 values
    against 86 with a repeat among them.
    """
    if _unresolved(githubCoeff):
        return 'the sheet this points at is not in asset-management'
    github, vendorValues = list(_cells(githubCoeff)), list(_cells(expected))
    if len(github) != len(vendorValues):
        return f'{len(github)} values against {len(vendorValues)}'
    differing = [i for i, (a, b) in enumerate(zip(github, vendorValues)) if a != b]
    if not differing:
        return None
    first = differing[0]
    return (f'{len(differing)} of {len(github)} values differ, the first at '
            f'index {first}: {github[first]} against {vendorValues[first]}')


def _difference(githubCoeff, expected, ordered=False):
    """Scalars subtract; spectra compare as sets, which is how the vendor
    publishes them -- order carries no meaning."""
    if ordered:
        return _orderedDifference(githubCoeff, expected)
    if isinstance(githubCoeff, list):
        return set(githubCoeff).symmetric_difference(expected)
    return githubCoeff - expected


def compareCalCoefficients(githubCal, vendorPath, coeffMap, constants):
    """Compare one github calibration file against its vendor original.

    ``githubCal`` is the parsed github csv (``name``/``value`` rows), ``vendorPath``
    the vendor file path without its extension. Returns ``[verdict, *differences]``.
    """
    sensor = identifySensor(vendorPath)
    if sensor is None:
        return ['NAN']

    spec = SENSORS[sensor]
    calCompare = ['NO_VENDOR_FILE'] if spec['sources'] else ['NAN']
    names = list(githubCal['name'])
    ## Differences name the file, not where this run happened to keep it -- the
    ## report is published, and a local path means nothing to whoever reads it.
    stem = os.path.basename(vendorPath)

    for source in spec['sources']:
        path = findVendorFile(vendorPath, source['suffix'])
        if path is None:
            continue
        vendorCals = (source['reader'](path, coeffMap, names) if source.get('needsMap')
                      else source['reader'](path))
        if source.get('requires') and not vendorCals.get(source['requires']):
            continue
        calCompare = [source.get('verdict', 'COMPARED')]

        for _, row in githubCal.iterrows():
            githubCoeff = _githubValue(row['value'], spec['parseGithub'])
            name = row['name']
            if name in spec.get('notVendor', ()):
                ## The vendor file does not carry this and never will, so there
                ## is nothing to compare it against. Declared per sensor, so it
                ## reads as a stated limit of the check rather than a silence.
                continue
            if name in constants.get(sensor, {}):
                coeffSource = 'constant'
                expected = constants[sensor][name]
            else:
                coeffSource = 'vendor'
                key = coeffMap[name][1] if source.get('keyBy') == 'map' else name
                ## A reader also hands back None for a field its file does not
                ## spell -- an ac-s .dev with no tcal line -- and that reached
                ## float(None) and took the whole run down.
                if key not in vendorCals or vendorCals[key] is None:
                    ## The vendor file does not carry it, so nothing was checked.
                    ## Reported rather than skipped -- an unchecked coefficient
                    ## reading as a pass is the failure mode this rewrite exists for.
                    recordDiff(calCompare, stem, name, githubCoeff, None, None, 'missing')
                    continue
                expected = vendorCals[key]

            ## vendors publish scalars as text ('1.733339e+000'); the report
            ## carries the number, not the spelling
            ## Coerced only when the vendor value is a scalar. An OPTAA sheet is
            ## a matrix on both sides, and float() on one ends the run.
            if not isinstance(githubCoeff, list) and not isinstance(expected, list):
                expected = float(expected)
            coeffDiff = _difference(githubCoeff, expected, source.get('ordered', False))
            if coeffDiff:
                recordDiff(calCompare, stem, name, githubCoeff, expected, coeffDiff, coeffSource)
        return calCompare

    ## Nothing was read. Which of three reasons it was matters, because each
    ## asks something different of a person: find the vendor file, accept that
    ## a scan cannot be parsed, or go and fetch the format this instrument is
    ## actually compared against.
    if spec.get('pdf', True) and findVendorFile(vendorPath, '.pdf'):
        calCompare[0] = 'PDF_NOTCOMPARED'
    elif spec['sources'] and anyVendorFile(vendorPath):
        calCompare[0] = 'FORMAT_NOTCOMPARED'
    return calCompare
