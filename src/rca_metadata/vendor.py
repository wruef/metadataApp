"""Readers for vendor calibration files.

Each vendor ships a different text format. A reader turns one file into a flat
``{coefficient name: value}`` dict using the OOI ``CC_*`` names, so the
comparison in :mod:`rca_metadata.calibrations` never has to know which vendor
it is looking at.

Values are returned as the file spells them -- strings for scalars, lists of
floats where the vendor publishes a spectrum. The comparison casts.
"""

import re
import xml.etree.ElementTree as ET


def _lines(path):
    with open(path, errors='ignore') as fp:
        yield from fp


## DOFSTA .cal keys are named by the vendor, and coefficientMap.csv maps the
## github CC_* name onto them.
DOFSTA_KEYS = {
    'SOC=': 'Soc',
    'VOFFSET=': 'offset',
    'A=': 'A',
    'B=': 'B',
    'C=': 'C',
    'E=': 'E',
    'Tau20=': 'Tau20',
}


def readDOFSTA(path):
    cals = {}
    for line in _lines(path):
        for prefix, name in DOFSTA_KEYS.items():
            if line.startswith(prefix):
                cals[name] = re.match(r"^" + re.escape(prefix) + r"\s*(\S+)", line).group(1)
                break
    return cals


def readFLCDR(path):
    cals = {}
    for line in _lines(path):
        mat = re.match(r"^CDOM=\d\s*(\S+)\s*(\S+)", line)
        if mat:
            cals['CC_scale_factor_cdom'] = mat.group(1)
            cals['CC_dark_counts_cdom'] = mat.group(2)
    return cals


def readFLNTU(path):
    ## A plain .dev carries no scattering channel; only the .dev.lambda does.
    ## Absent channels report NAN rather than going missing, so a comparison
    ## against them fails loudly instead of raising KeyError.
    cals = {}
    if '.lambda' not in path:
        cals['CC_scale_factor_volume_scatter'] = 'NAN'
        cals['CC_dark_counts_volume_scatter'] = 'NAN'
        cals['CC_measurement_wavelength'] = 'NAN'
    for line in _lines(path):
        mat = re.match(r"^Chl=4\s*(\S+)\s*(\S+)", line)
        if mat and 'CC_scale_factor_chlorophyll_a' not in cals:
            cals['CC_scale_factor_chlorophyll_a'] = mat.group(1)
            cals['CC_dark_counts_chlorophyll_a'] = mat.group(2)
        mat = re.match(r"^lambda=6\s*(\S+)\s*(\S+)\s*(\S+)\s*.*", line, re.I)
        if mat:
            cals['CC_scale_factor_volume_scatter'] = mat.group(1)
            cals['CC_dark_counts_volume_scatter'] = mat.group(2)
            cals['CC_measurement_wavelength'] = mat.group(3)
    return cals


def readFLORD(path):
    cals = {}
    for line in _lines(path):
        mat = re.match(r"^lambda=4\s*(\S+)\s*(\S+)\s*(\S+)\s*.*", line, re.I)
        if mat:
            cals['CC_scale_factor_volume_scatter'] = mat.group(1)
            cals['CC_dark_counts_volume_scatter'] = mat.group(2)
            cals['CC_measurement_wavelength'] = mat.group(3)
        mat = re.match(r"^Chl=6\s*(\S+)\s*(\S+)", line, re.I)
        if mat:
            cals['CC_scale_factor_chlorophyll_a'] = mat.group(1)
            cals['CC_dark_counts_chlorophyll_a'] = mat.group(2)
        mat = re.match(r"^CDOM=8\s*(\S+)\s*(\S+)", line, re.I)
        if mat:
            cals['CC_scale_factor_cdom'] = mat.group(1)
            cals['CC_dark_counts_cdom'] = mat.group(2)
    return cals


def readNUTNR(path):
    ## Spectral instrument: one E row per wavelength, accumulated into parallel lists.
    cals = {'CC_wl': [], 'CC_eno3': [], 'CC_eswa': [], 'CC_di': []}
    num = r"([-+]?\d*\.\d+|\d+)"
    for line in _lines(path):
        mat = re.match(r"H,T_CAL(?:_SWA)?\s+" + num + r".*", line)
        if mat:
            cals['CC_cal_temp'] = float(mat.group(1))
        mat = re.match(r"^E," + ",".join([num] * 5) + r".*", line)
        if mat:
            cals['CC_wl'].append(float(mat.group(1)))
            cals['CC_eno3'].append(float(mat.group(2)))
            cals['CC_eswa'].append(float(mat.group(3)))
            cals['CC_di'].append(float(mat.group(5)))
    return cals


def readPARA(path):
    cals = {}
    for line in _lines(path):
        mat = re.match(r"^(\d+\.\d+)\s+(\d+\.\d+e-\d+)\s+(\d+\.\d+)\s*", line)
        if mat:
            cals['CC_a0'] = mat.group(1)
            cals['CC_a1'] = mat.group(2)
            cals['CC_Im'] = mat.group(3)
    return cals


def readSPKIR(path):
    ## Same line shape as PARA, but one row per channel rather than a single set.
    cals = {'CC_immersion_factor': [], 'CC_offset': [], 'CC_scale': []}
    for line in _lines(path):
        mat = re.match(r"^(\d+\.\d+)\s+(\d+\.\d+e-\d+)\s+(\d+\.\d+)\s*", line)
        if mat:
            cals['CC_offset'].append(float(mat.group(1)))
            cals['CC_scale'].append(float(mat.group(2)))
            cals['CC_immersion_factor'].append(float(mat.group(3)))
    return cals


def readXmlcon(path, coeffMap, names):
    """Seabird .xmlcon -- coefficients live at a per-sensor element path."""
    root = ET.parse(path).getroot()
    cals = {}
    for name in names:
        if name not in coeffMap:
            continue
        block, tag = coeffMap[name][0], coeffMap[name][1]
        for elem in root.findall("Instrument/SensorArray/Sensor/" + block + "Sensor/"):
            for sub in elem.iter():
                if sub.tag == tag:
                    cals[name] = sub.text
    return cals




## The calibration temperature, however the instrument spelled it.
TCAL = re.compile(r'tcal:\s*([-\d.]+)', re.IGNORECASE)


def readOPTAA(path):
    """WET Labs ac-s ``.dev`` -- the pure-water calibration.

    The ``.cal`` posted beside it is the air calibration and is not what
    asset-management is generated from, so it is never read.

    The file is tab separated with runs of empty fields as separators. A header
    declares how many wavelengths and temperature bins follow, then one row per
    wavelength::

        C401.2  A400.0  8  -2.540648  -5.618652  <38 c values>  <38 a values>

    The two blocks are the temperature corrections, and they become the two
    ``.ext`` sheets in asset-management -- 85 rows of 38 either way.
    """
    bins, rows = [], []
    tcal = None
    for line in open(path, errors='replace'):
        ## The instrument writes this line three ways across the archive:
        ## '"tcal: 21.3 C, ical: ..."', 'tcal: 18.6 C, ...' and
        ## 'Tcal: 22.7 C, Ical: ...'. Matching only the quoted lower-case
        ## spelling left CC_tcal unread on 30 of 110 calibrations.
        if tcal is None:
            found = TCAL.search(line)
            if found:
                tcal = float(found.group(1))
                continue
        fields = [f.strip() for f in line.split('\t') if f.strip()]
        if not fields:
            continue
        if fields[-1].endswith('temperature bins') and len(fields) > 2:
            bins = [float(f) for f in fields[:-1]]
        elif fields[0].startswith('C') and len(fields) > 1 and fields[1].startswith('A'):
            rows.append(fields)

    ## Each row carries the two wavelengths, a bin count, the two clean-water
    ## offsets, then the corrections -- as many of each as there are bins.
    count = len(bins)
    return {
        'CC_tcal': tcal,
        'CC_tbins': bins,
        'CC_cwlngth': [float(row[0][1:]) for row in rows],
        'CC_awlngth': [float(row[1][1:]) for row in rows],
        'CC_ccwo': [float(row[3]) for row in rows],
        'CC_acwo': [float(row[4]) for row in rows],
        'CC_tcarray': [[float(f) for f in row[5:5 + count]] for row in rows],
        'CC_taarray': [[float(f) for f in row[5 + count:5 + 2 * count]] for row in rows],
    }


## ---- vendor certificates that are only published as a pdf ----
##
## Four instruments have no machine-readable vendor file at all, so their
## coefficients are typed into asset-management by hand from a certificate.
## Three quarters of those certificates carry a text layer, so the numbers can
## be read exactly rather than recognised from an image.

## A subscript is set smaller than the word it belongs to, and sits below and to
## its right. This is how Ea434 and a0 are drawn -- as two pieces.
SUBSCRIPT_GAP = 2.0
## Words within this many points of each other vertically are one line.
ROW_TOLERANCE = 3.0
## Glyphs closer together than this are one token. Certificates draw `Im` as two
## letters a tenth of a point apart, and split `2.5063877597725e-006` after the
## point; ordinary column spacing is several points, so nothing else is joined.
FRAGMENT_GAP = 1.0

NUMBER = re.compile(r'^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?$')


def _joinSubscripts(words):
    """``Ea`` + ``434`` -> ``Ea434``.

    Vendor certificates set coefficient names with real subscripts, so a plain
    text dump either splits them across two lines or flattens them by luck --
    and the two templates of each certificate disagree about which. Joined here
    by font size and position, which every template does agree on.
    """
    words = [dict(word) for word in words]
    taken = set()
    for index, sub in enumerate(words):
        for base in words:
            if base is sub or sub['size'] >= base['size'] - 0.5:
                continue
            if (base['top'] < sub['top'] < base['top'] + base['size']
                    and base['x0'] <= sub['x0'] <= base['x1'] + SUBSCRIPT_GAP):
                base['text'] += sub['text']
                taken.add(index)
                break
    return [word for index, word in enumerate(words) if index not in taken]


def pdfRows(path):
    """A pdf as lines of words, left to right, subscripts joined to their base."""
    import pdfplumber

    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = sorted(_joinSubscripts(page.extract_words(extra_attrs=['size'])),
                           key=lambda word: (word['top'], word['x0']))
            line = []
            for word in words:
                if line and word['top'] - line[0]['top'] > ROW_TOLERANCE:
                    rows.append(_readAcross(line))
                    line = []
                line.append(word)
            if line:
                rows.append(_readAcross(line))
    return rows


def _readAcross(line):
    """One visual line, left to right, with touching glyphs joined.

    Sorted by position rather than by the order the page draws them: a
    certificate sets the I of Im a point lower than the m, which put the I at
    the end of its own line and left the coefficient unreadable on four files.
    """
    words = sorted(line, key=lambda word: word['x0'])
    cells = []
    for word in words:
        if cells and word['x0'] - cells[-1]['x1'] < FRAGMENT_GAP:
            cells[-1] = {'text': cells[-1]['text'] + word['text'], 'x1': word['x1']}
        else:
            cells.append({'text': word['text'], 'x1': word['x1']})
    return [cell['text'] for cell in cells]


def _value(cells):
    """The number a label is set equal to, allowing for one split.

    A certificate breaks ``2.5063877597725e-006`` after the decimal point, with
    three points of space in the middle of a number. Rejoined only here, where a
    number is what is expected: widening the general rule would risk running two
    columns of figures together, which is how a range of 202 to 1191 reads as
    2021191 once its dash is dropped.
    """
    for joined in (cells[0], ''.join(cells[:2])):
        if NUMBER.match(joined):
            return float(joined)
    return None


def _labelled(rows, names):
    """``name = value``, wherever on the page it appears."""
    found = {}
    for row in rows:
        for index, cell in enumerate(row[:-2]):
            if cell in names and row[index + 1] == '=':
                value = _value(row[index + 2:index + 4])
                if value is not None:
                    found[cell] = value
    return found


def _tabulated(rows, names):
    """A header row naming the coefficients, and the values on the row below."""
    for index, row in enumerate(rows[:-1]):
        if [cell for cell in row if cell in names] == list(names):
            values = [cell for cell in rows[index + 1] if NUMBER.match(cell)]
            if len(values) >= len(names):
                ## the row can carry more numbers than names, and the leading ones are the coefficients
                return {name: float(value) for name, value in zip(names, values)}  # noqa: B905
    return {}


def readPARpdf(path):
    """Satlantic in-water PAR calibration certificate.

    Two templates, a decade apart, and they disagree about the order the three
    coefficients are printed in -- so they are read by name, never by position.
    """
    return {f'CC_{name}': value
            for name, value in _labelled(pdfRows(path), {'Im', 'a0', 'a1'}).items()}


## The certificate prints these four; the rest of a PHSEN calibration does not
## come from the vendor.
PHSEN_EVALUES = ('Ea434', 'Eb434', 'Ea578', 'Eb578')


def readPHSENpdf(path):
    """Sunburst SAMI2 pH validation certificate.

    The older template prints ``Ea434 = 17533`` a line at a time; the newer one
    prints a table with the names across the top. Both are read.
    """
    rows = pdfRows(path)
    found = _labelled(rows, set(PHSEN_EVALUES)) or _tabulated(rows, PHSEN_EVALUES)
    return {f'CC_{name.lower()}': value for name, value in found.items()}


## Table 1 of the newer SAMI2 CO2 certificate, in the order it prints them. The
## two K values are on the page but are not carried in asset-management.
PCO2W_TABLE = ('A', 'B', 'C', 'K434', 'K620', 'Tavg')
PCO2W_COLUMNS = {'A': 'CC_cala', 'B': 'CC_calb', 'C': 'CC_calc', 'Tavg': 'CC_calt'}
## The older certificate prints one per line, and names the same four differently.
PCO2W_LABELS = {'a': 'CC_cala', 'b': 'CC_calb', 'c': 'CC_calc', 'T': 'CC_calt'}

## ``206–1197``, and the same range where the en-dash arrived as an unmapped
## glyph. A separator that vanished altogether leaves ``2021191``, which is not
## read as a range at all: there is no way to know where to split it, and
## guessing would invent a number.
RANGE = re.compile(r'^(\d+)(?:[-‐-―]|\(cid:\d+\))(\d+)$')


def _span(cells):
    """A low and a high, however the page broke them apart."""
    for index, cell in enumerate(cells):
        after = cells[index + 1] if index + 1 < len(cells) else ''
        for joined in (cell, cell + after):
            found = RANGE.match(joined)
            if found:
                ## Sorted, because these are the ends of an interval and one
                ## certificate prints them the wrong way round: 1388-200 for a
                ## range the record sensibly keeps as 200 to 1388.
                return sorted([int(found.group(1)), int(found.group(2))])
    return None


def _calibrationRange(rows):
    """The calibration range, taken only from where the page labels it.

    Anchored rather than searched for: a line higher up carries the part number,
    ``4830-58336``, which reads as a perfectly good range and is not one.
    """
    for index, row in enumerate(rows):
        ## One template writes the column head as `Range (ppm)` and another as
        ## `Range(ppm)`, which is a different token.
        if not any(cell.startswith('Range') for cell in row):
            continue
        ## The older certificate puts the label and the value on one line; the
        ## newer one labels the column and prints the value on the row beneath.
        beneath = rows[index + 1] if index + 1 < len(rows) else []
        for cells in (list(row), list(beneath)):
            span = _span(cells)
            if span:
                return span
    return None


def readPCO2Wpdf(path):
    """Sunburst SAMI2 CO2 calibration certificate.

    Four coefficients and the calibration range. The blank intensities and the
    two K values printed alongside them are not carried in asset-management, and
    the four E values are the same on every RCA instrument -- they live in
    coefficientConstants.csv, which is why the certificate never prints them.
    """
    rows = pdfRows(path)
    found = {PCO2W_COLUMNS[name]: value
             for name, value in _tabulated(rows, PCO2W_TABLE).items()
             if name in PCO2W_COLUMNS}
    if not found:
        found = {PCO2W_LABELS[name]: value
                 for name, value in _labelled(rows, set(PCO2W_LABELS)).items()}
    span = _calibrationRange(rows)
    if span:
        found['CC_cal_range'] = span
    return found


## An Aanderaa optode certificate names its two coefficients five ways across
## three templates. Two of those spellings are typographical errors on the
## vendor's own page -- SUVFoilCoef for SVUFoilCoef, and Conentration for
## Concentration -- and they are matched rather than corrected, because the file
## on record is the file on record.
DOSTAD_CONC = ('conccoef', 'concentrationcoef', 'conentrationcoef')
## One template prints all seven across a row; another splits them C0-C3, C4-C6.
DOSTAD_CSV = ('svufoilcoef', 'suvfoilcoef')
DOSTAD_CSV_PARTS = ('svuc0-c3', 'svuc4-c6')


def _leadingLabel(row):
    """What a row is called, and the numbers printed after the name."""
    index = 0
    while index < len(row) and not NUMBER.match(row[index]):
        index += 1
    label = ''.join(row[:index]).lower()
    return label, [float(cell) for cell in row[index:] if NUMBER.match(cell)]


def readDOSTADpdf(path):
    """Aanderaa oxygen optode calibration certificate.

    Two coefficients: the concentration offset and slope, and the seven SVU foil
    coefficients. Both are indexed, so both are compared in order.
    """
    return dostadCoefficients(pdfRows(path))


def dostadCoefficients(rows):
    conc, csv = [], []
    for row in rows:
        label, values = _leadingLabel(row)
        if not values:
            continue
        if label in DOSTAD_CONC:
            conc = values
        elif label in DOSTAD_CSV:
            csv = values
        elif label in DOSTAD_CSV_PARTS:
            ## C0-C3 prints above C4-C6, and rows arrive in the order the page
            ## sets them, so appending keeps the coefficients on their indices.
            csv = csv + values

    ## Reported only when the whole coefficient is there. A half-read set would
    ## compare four values against seven and call it a disagreement, which says
    ## the data is wrong when it is the reading that fell short.
    found = {}
    if len(conc) == 2:
        found['CC_conc_coef'] = conc
    if len(csv) == 7:
        found['CC_csv'] = csv
    return found
