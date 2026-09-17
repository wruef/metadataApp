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
DOSTAD   ``.pdf``       the concentration and SVU foil coefficients. A
                        certificate with no 2-point recalibration prints no
                        concentration coefficient; the record is then held
                        to the identity, declared in ``defaults``
PCO2W    ``.pdf``       four coefficients and the calibration range; the E
                        values are the same on every RCA instrument and live
                        in coefficientConstants.csv
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
    'DOSTAD': {
        'assetIds': ['58320'],
        'parseGithub': 'floatOrList',
        ## Ordered: both coefficients are indexed, C0 through C6.
        'sources': [{'suffix': '.pdf', 'reader': vendor.readDOSTADpdf,
                     'requires': 'CC_csv', 'ordered': True}],
        ## A certificate without a 2-point recalibration prints no concentration
        ## coefficient at all, and the record then carries the identity: no
        ## correction. Held to that rather than reported unchecked, so a record
        ## claiming a correction the certificate never made still surfaces.
        'defaults': {'CC_conc_coef': [0.0, 1.0]},
    },
    'PCO2W': {
        'assetIds': ['58336', '70570'],
        'parseGithub': 'floatOrList',
        ## Ordered, because the calibration range is a low and a high: compared
        ## as a set, 200 to 600 and 600 to 200 would read the same.
        'sources': [{'suffix': '.pdf', 'reader': vendor.readPCO2Wpdf,
                     'requires': 'CC_cala', 'ordered': True}],
    },
    'PHSEN': {
        'assetIds': ['58337', '70571', '91990'],
        'parseGithub': 'raw',
        'sources': [{'suffix': '.pdf', 'reader': vendor.readPHSENpdf, 'requires': 'CC_ea434'}],
        ## The certificate carries the four E values and nothing else. Salinity
        ## is measured, not calibrated: four deployments record the real thing
        ## rather than the default 35, and nothing on the vendor's page could
        ## check it either way. Declared rather than reported missing on every
        ## row, which would bury the four values that can be checked.
        ##
        ## The ADC bit depth is not here: it is a constant of 12, so the two Rev
        ## K boards that run at 16 surface for a person instead of passing.
        'notVendor': ['CC_psal'],
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
    ## ---- no vendor file exists, and none ever will ----
    ## These carry fixed values rather than measurements: the same numbers on
    ## every instrument of the type, entered into asset-management by hand. So
    ## there is nothing to fetch from a vendor and the record is held to
    ## params/coefficientConstants.csv instead. They are identified through the
    ## RCA instrument list rather than by an asset-ID code, which is why
    ## 'assetIds' is empty.
    'ADCP': {
        'assetIds': [], 'parseGithub': 'floatOrList', 'sources': [], 'constantsOnly': True,
        ## How the instrument was set up for this deployment, not a property of
        ## it: bin size and depth change from one deployment to the next, so
        ## there is no constant to hold them to and nothing to compare.
        'notVendor': ('CC_bin_size', 'CC_dist_first_bin', 'CC_orientation', 'CC_depth'),
    },
    'VADCP': {
        'assetIds': [], 'parseGithub': 'floatOrList', 'sources': [], 'constantsOnly': True,
        ## The beam transformation matrix and its shape belong to the individual
        ## instrument, so they are configuration in the same sense.
        'notVendor': ('CC_rows', 'CC_columns', 'CC_TM', 'CC_vadcpb_orientation'),
    },
    'HYDBB': {'assetIds': [], 'parseGithub': 'float', 'sources': [], 'constantsOnly': True},
    'ZPLSC': {'assetIds': [], 'parseGithub': 'float', 'sources': [], 'constantsOnly': True},

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


def sensorForType(instrumentType):
    """Which sensor's rules an RCA instrument type falls under.

    An instrument type in ``params/RCA-InstrumentList.csv`` is a sensor name and
    a series letter -- ``OPTAA-C``, ``CTDPF-A``, ``FLOR-D`` -- so the rules are
    the longest :data:`SENSORS` key the name begins with once the hyphen is
    dropped. Longest, because ``DOSTA-D`` and ``DOFST-A`` differ by one letter
    and a shorter key must not shadow a longer one.
    """
    name = str(instrumentType).replace('-', '').upper()
    matched = [sensor for sensor in SENSORS if name.startswith(sensor)]
    return max(matched, key=len) if matched else None


def identifySensor(vendorPath, assets=None):
    """Which sensor's rules a vendor file is compared under.

    Matched against the asset ID field alone, not against the path as a string.
    A substring search finds an asset ID inside the calibration date: a file
    dated 2017-01-10 spells 70110, which is FLNTU's asset ID, and 2017-01-11
    spells 70111, which is FLCDR's. Two real calibrations -- a NUTNR and a
    SPKIR -- were checked against the wrong instrument's rules for years and
    reported as having no vendor file, while their .cal sat right beside them.

    That field holds a model code for an RCA-owned asset and a word for a
    borrowed one: ``ATSBE-LOANER-00001`` spells ``LOANER``, which is no model
    code, so nothing matched and a loaner OPTAA went uncompared with its vendor
    ``.dev`` sitting beside it. Where the field settles nothing, the RCA
    instrument list is asked what the asset is -- it is the record of what every
    RCA asset is, so the next oddly-named one needs no edit here.
    """
    assetId = assetIdOf(vendorPath)
    for sensor, spec in SENSORS.items():
        if assetId in spec['assetIds']:
            return sensor

    record = (assets or {}).get(os.path.basename(vendorPath).split('__')[0])
    if record is None:
        return None
    ## One asset can be listed under more than one type; the first with rules wins.
    types = record['instrumentType']
    for instrumentType in types if isinstance(types, list) else []:
        sensor = sensorForType(instrumentType)
        if sensor:
            return sensor
    return None


def recordDiff(calCompare, fileName, coeffName, githubCoeff, expectedCoeff, coeffDiff, coeffSource):
    """Append one difference and promote the verdict to match its severity.

    A coefficient checked against coefficientConstants.csv is not a disagreement
    with the vendor -- there is no vendor value involved -- so it carries its own
    verdict, and a real vendor disagreement always outranks it.
    """
    verdict = {'vendor': 'MISMATCH', 'constant': 'CONSTANT_MISMATCH',
               'default': 'CONSTANT_MISMATCH',
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


def isConstantsOnly(vendorPath, assets=None):
    """Whether this asset's coefficients are fixed values rather than measurements.

    Asked before the comparison, because the absence of a vendor original means
    two different things. For a CTD it is a finding. For these it is the normal
    state of the world -- no vendor has ever published one and none ever will --
    so reporting it as a missing file puts a row that agrees with everything it
    was checked against in front of a person for no reason.
    """
    sensor = identifySensor(vendorPath, assets)
    return bool(sensor and SENSORS[sensor].get('constantsOnly'))


def compareConstants(githubCal, spec, sensor, constants, stem):
    """Compare a calibration against the fixed values, where no vendor file exists.

    A handful of instruments carry the same coefficients on every unit of the
    type -- an ADCP's four scale factors, a hydrophone's gain, the water
    properties a ZPLSC is configured with. No vendor measures them, so nothing
    is ever published to compare against, and until now the whole file read as
    ``NAN``: not checked, and not checkable. It is checkable. The numbers are
    written down in ``params/coefficientConstants.csv``, and a file that
    disagrees with them is as much a transcription error as one that disagrees
    with a vendor.
    """
    declared = constants.get(sensor, {})
    if not declared:
        ## The sensor is marked as one to compare against constants and nobody
        ## has written any. Said out loud rather than passing.
        return ['NO_CONSTANTS']

    calCompare = ['COMPARED_CONSTANTS']
    compared = 0
    for _, row in githubCal.iterrows():
        name = row['name']
        if name in spec.get('notVendor', ()):
            ## Configuration rather than calibration -- how the instrument was
            ## set up for this deployment. Declared per sensor, so it reads as a
            ## stated limit of the check rather than a silence.
            continue
        githubCoeff = _githubValue(row['value'], spec['parseGithub'])
        if name not in declared:
            ## A coefficient with no constant written for it was not checked
            ## against anything, and an unchecked coefficient reading as a pass
            ## is the failure mode this rewrite exists for.
            recordDiff(calCompare, stem, name, githubCoeff, None, None, 'missing')
            continue
        expected = float(declared[name])
        compared += 1
        difference = githubCoeff - expected
        if difference:
            recordDiff(calCompare, stem, name, githubCoeff, expected, difference, 'constant')

    ## Four VADCP files hold nothing but configuration -- a transformation
    ## matrix and its shape -- so the loop above compares no coefficient at all
    ## and would otherwise report a pass. A verdict of COMPARED set before
    ## anything was read is the defect this whole rewrite exists for.
    if not compared:
        return ['CONFIGURATION_ONLY']
    return calCompare


def compareCalCoefficients(githubCal, vendorPath, coeffMap, constants, assets=None,
                           vendorPresent=True):
    """Compare one github calibration file against its vendor original.

    ``githubCal`` is the parsed github csv (``name``/``value`` rows), ``vendorPath``
    the vendor file path without its extension. ``assets`` is the RCA instrument
    list, consulted only for an asset whose ID carries no model code.
    ``vendorPresent`` is false when calibrationFiles holds nothing under this
    name at all, which only a constants-only sensor can be compared without.
    Returns ``[verdict, *differences]``.
    """
    sensor = identifySensor(vendorPath, assets)
    if sensor is None:
        return ['NAN']

    spec = SENSORS[sensor]
    if spec.get('constantsOnly'):
        return compareConstants(githubCal, spec, sensor, constants,
                                os.path.basename(vendorPath))
    if not vendorPresent:
        ## Everything else needs a vendor file, and there is not one.
        return ['NAN']

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
                    ## Some certificates leave a coefficient out because it does
                    ## not apply: an optode with no 2-point recalibration prints
                    ## no concentration coefficient, and the record then carries
                    ## the identity. Where a sensor says what that absence means,
                    ## the record is held to it, so a file claiming a correction
                    ## its certificate never made is still a finding.
                    expected = spec.get('defaults', {}).get(name)
                    if expected is None:
                        ## Otherwise nothing was checked. Reported rather than
                        ## skipped -- an unchecked coefficient reading as a pass
                        ## is the failure mode this rewrite exists for.
                        recordDiff(calCompare, stem, name, githubCoeff, None, None, 'missing')
                        continue
                    coeffSource = 'default'
                else:
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
