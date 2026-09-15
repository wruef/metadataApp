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


def readCTD(path):
    ## Seabird .cal: NAME= value, one per line. Pressure coefficients (C*, D*, T*)
    ## keep their case; temperature ta0..ta3 and conductivity cg..cj drop the
    ## leading letter, which is how the github files name them.
    keepCase = {'C1', 'C2', 'C3', 'D1', 'D2', 'T1', 'T2', 'T3', 'T4', 'T5'}
    cals = {}
    for line in _lines(path):
        mat = re.match(r"(\S+)=\s*(\S+).*", line)
        if mat is None:
            continue
        name = mat.group(1)
        if name not in keepCase:
            name = name.lower()
            if name in ('ta0', 'ta1', 'ta2', 'ta3'):
                name = name.replace('t', '')
            elif name in ('cg', 'ch', 'ci', 'cj'):
                name = name.replace('c', '')
        cals['CC_' + name] = mat.group(2)
    return cals


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


def readDofstaXml(path, coeffMap, names):
    """Aanderaa .xml -- only the equation-1 calibration block is authoritative."""
    root = ET.parse(path).getroot()
    cals = {}
    for elem in root.findall('CalibrationCoefficients'):
        if float(elem.get('equation')) != 1:
            continue
        for sub in elem.iter():
            for name in names:
                if name in coeffMap and sub.tag == coeffMap[name][1]:
                    cals[name] = sub.text
    return cals
