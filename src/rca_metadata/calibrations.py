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
``COMPARED`` / ``COMPARED_XML``  read and agreed
``PDF_NOTCOMPARED``      only a pdf is on file
``NO_VENDOR_FILE``       the sensor has a comparison rule but no vendor file
``NAN``                  no comparison rule for this sensor
"""

import ast
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
        'sources': [
            {'suffix': '.xmlcon', 'reader': vendor.readXmlcon, 'needsMap': True},
            {'suffix': '.cal', 'reader': vendor.readCTD},
        ],
    },
    'DOFSTA': {
        'assetIds': ['58694'],
        'parseGithub': 'raw',
        'sources': [
            {'suffix': '.cal', 'reader': vendor.readDOFSTA, 'keyBy': 'map'},
            {'suffix': '.xml', 'reader': vendor.readDofstaXml, 'needsMap': True,
             'verdict': 'COMPARED_XML'},
        ],
    },
    'FLNTU': {
        'assetIds': ['70110'],
        'parseGithub': 'float',
        'sources': [
            {'suffix': '.dev.lambda', 'reader': vendor.readFLNTU},
            {'suffix': '.dev', 'reader': vendor.readFLNTU},
        ],
    },
    'FLCDR': {
        'assetIds': ['70111'],
        'parseGithub': 'float',
        'sources': [{'suffix': '.dev', 'reader': vendor.readFLCDR}],
    },
    'FLORD': {
        'assetIds': ['58322'],
        'parseGithub': 'float',
        'sources': [
            {'suffix': '.dev.lambda', 'reader': vendor.readFLORD},
            {'suffix': '.dev', 'reader': vendor.readFLORD},
        ],
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
        'sources': [{'suffix': '.tdf', 'reader': vendor.readPARA, 'requires': 'CC_a0'}],
    },
    'SPKIR': {
        'assetIds': ['58341'],
        'parseGithub': 'list',
        'sources': [{'suffix': '.cal', 'reader': vendor.readSPKIR, 'requires': 'CC_scale'}],
        'pdf': False,
    },
    ## OPTAA calibrations are not machine-comparable yet; the sensor is listed so
    ## its files report NAN deliberately rather than by falling off the end.
    'OPTAA': {'assetIds': ['69943', '58332'], 'sources': []},
}


def identifySensor(vendorPath):
    for sensor, spec in SENSORS.items():
        if any(assetId in vendorPath for assetId in spec['assetIds']):
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
    if how == 'float':
        return float(raw)
    if how == 'list':
        return ast.literal_eval(raw)
    if how == 'floatOrList':
        return ast.literal_eval(raw) if '[' in str(raw) else float(raw)
    return raw


def _difference(githubCoeff, expected):
    """Scalars subtract; spectra compare as sets, which is how the vendor
    publishes them -- order carries no meaning."""
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

    for source in spec['sources']:
        path = vendorPath + source['suffix']
        if not os.path.isfile(path):
            continue
        vendorCals = (source['reader'](path, coeffMap, names) if source.get('needsMap')
                      else source['reader'](path))
        if source.get('requires') and not vendorCals.get(source['requires']):
            continue
        calCompare = [source.get('verdict', 'COMPARED')]

        for _, row in githubCal.iterrows():
            githubCoeff = _githubValue(row['value'], spec['parseGithub'])
            name = row['name']
            if name in constants.get(sensor, {}):
                coeffSource = 'constant'
                expected = constants[sensor][name]
            else:
                coeffSource = 'vendor'
                key = coeffMap[name][1] if source.get('keyBy') == 'map' else name
                if key not in vendorCals:
                    ## The vendor file does not carry it, so nothing was checked.
                    ## Reported rather than skipped -- an unchecked coefficient
                    ## reading as a pass is the failure mode this rewrite exists for.
                    recordDiff(calCompare, vendorPath, name, githubCoeff, None, None, 'missing')
                    continue
                expected = vendorCals[key]

            ## vendors publish scalars as text ('1.733339e+000'); the report
            ## carries the number, not the spelling
            if not isinstance(githubCoeff, list):
                expected = float(expected)
            coeffDiff = _difference(githubCoeff, expected)
            if coeffDiff:
                recordDiff(calCompare, vendorPath, name, githubCoeff, expected, coeffDiff, coeffSource)
        return calCompare

    if spec.get('pdf', True) and os.path.isfile(vendorPath + '.pdf'):
        calCompare[0] = 'PDF_NOTCOMPARED'
    return calCompare
