"""The machine-readable vendor formats, one reader each.

The certificate readers have had tests since they were written; these nine had
none, and they are what 866 of the 1,174 calibrations are compared against. A
vendor changing a line's shape would not break anything loudly -- the reader
would return fewer coefficients, and every one it stopped returning would be
reported as a difference against the repository file. A format drift would
arrive looking like a page of data findings.

Every fixture below is the real shape, trimmed: the line spellings, the tabs
and the stray columns are as they appear in calibrationFiles.
"""

import pytest

from rca_metadata.vendor import (
    readDOFSTA,
    readFLCDR,
    readFLNTU,
    readFLORD,
    readNUTNR,
    readOPTAA,
    readPARA,
    readSPKIR,
    readXmlcon,
)


def written(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return str(path)


## ---- Seabird dissolved oxygen: key=value, the vendor's own names ----

DOFSTA_CAL = """INSTRUMENT_TYPE=SBE43
SERIALNO=2463
OCALDATE=05-Sep-13
SOC= 4.703274e-001
VOFFSET=-4.357669e-001
A=-2.546990e-003
B= 1.595364e-004
C=-2.690409e-006
E= 3.600000e-002
Tau20= 3.940000e+000
"""


def test_theDofstaKeysAreReadUnderTheVendorsNames(tmp_path):
    cals = readDOFSTA(written(tmp_path, 'd.cal', DOFSTA_CAL))
    assert cals == {'Soc': '4.703274e-001', 'offset': '-4.357669e-001',
                    'A': '-2.546990e-003', 'B': '1.595364e-004', 'C': '-2.690409e-006',
                    'E': '3.600000e-002', 'Tau20': '3.940000e+000'}


def test_aValueWrittenTightAgainstItsKeyIsStillRead(tmp_path):
    """The vendor writes `SOC= 4.7e-1` and `VOFFSET=-4.3e-1` in one file: a
    space where the number is positive and none where the sign supplies it."""
    cals = readDOFSTA(written(tmp_path, 'd.cal', 'SOC=4.703274e-001\nA= -2.5e-003\n'))
    assert cals == {'Soc': '4.703274e-001', 'A': '-2.5e-003'}


def test_aFileWithNoneOfThoseKeysReadsAsNothingRatherThanRaising(tmp_path):
    assert readDOFSTA(written(tmp_path, 'd.cal', 'SERIALNO=2463\n')) == {}


## ---- WET Labs ECO: one channel per line, the channel number in the key ----

def test_theFlcdrScaleAndDarkCountsComeFromItsCdomChannel(tmp_path):
    dev = 'ECO \tFLCDRTD-3098\nCreated on: \t4/22/2013\n\nCOLUMNS=3\nN/U=1\nN/U=2\nCDOM=3\t0.0918\t46\n'
    assert readFLCDR(written(tmp_path, 'c.dev', dev)) == {
        'CC_scale_factor_cdom': '0.0918', 'CC_dark_counts_cdom': '46'}


FLNTU_LAMBDA = """ECO \tFLNTURTD-3099\t
Created on: \t04/22/2013\t

COLUMNS=7\t\t
N/U=1\t\t
Chl=4\t0.0121\t50
N/U=5\t\t
Lambda=6\t2.10e-06\t55\t700\t700\t\t
N/U=7\t\t
"""


def test_theLambdaFileCarriesTheScatteringChannelAndThePlainOneDoesNot(tmp_path):
    """Both `.dev` files are posted for one calibration and only the lambda one
    carries volume scattering, which is what asset-management is built from."""
    lam = readFLNTU(written(tmp_path, 'f.dev.lambda', FLNTU_LAMBDA))
    assert lam['CC_scale_factor_volume_scatter'] == '2.10e-06'
    assert lam['CC_dark_counts_volume_scatter'] == '55'
    assert lam['CC_measurement_wavelength'] == '700'
    assert lam['CC_scale_factor_chlorophyll_a'] == '0.0121'

    plain = readFLNTU(written(tmp_path, 'f.dev', FLNTU_LAMBDA.replace('Lambda=6', 'N/U=6')))
    ## Absent rather than missing: a comparison against NAN fails loudly where a
    ## missing key would have raised.
    assert plain['CC_scale_factor_volume_scatter'] == 'NAN'
    assert plain['CC_measurement_wavelength'] == 'NAN'
    assert plain['CC_scale_factor_chlorophyll_a'] == '0.0121'


def test_theFirstChlorophyllRowWins(tmp_path):
    """A file repeating the channel does not have its first reading overwritten."""
    text = FLNTU_LAMBDA + 'Chl=4\t9.9999\t99\n'
    assert readFLNTU(written(tmp_path, 'f.dev.lambda', text))['CC_scale_factor_chlorophyll_a'] == '0.0121'


FLORD_LAMBDA = """ECO BBFL2W-1028
Created on: 12/13/12

Columns=9
N/U=1
Lambda=4\t2.10e-06\t55\t700\t700\t\t
N/U=5
chl=6   \t0.0121\t\t52\t\t
N/U=7
CDOM=8\t0.0918\t46
"""


def test_theFlordsThreeChannelsAreReadAndItsKeysAreCaseInsensitive(tmp_path):
    """The vendor spells one channel `chl` and another `CDOM` in the same file."""
    cals = readFLORD(written(tmp_path, 'f.dev.lambda', FLORD_LAMBDA))
    assert cals == {'CC_scale_factor_volume_scatter': '2.10e-06',
                    'CC_dark_counts_volume_scatter': '55',
                    'CC_measurement_wavelength': '700',
                    'CC_scale_factor_chlorophyll_a': '0.0121',
                    'CC_dark_counts_chlorophyll_a': '52',
                    'CC_scale_factor_cdom': '0.0918',
                    'CC_dark_counts_cdom': '46'}


## ---- Satlantic nitrate: a header line, then one row per wavelength ----

NUTNR_CAL = """H,SUNA 0234 Cal A  extinction coefficients and reference spectra,,,,
H,File format version 3,,,,
H,T_CAL_SWA 20.143281674398008,,,,
E,189.60,-0.00301775,0.00078692,0.00086828,34.00000000
E,190.39,0.00268737,-0.00227945,-0.00246668,33.00000000
"""


def test_theNutnrSpectrumIsAccumulatedIntoParallelLists(tmp_path):
    cals = readNUTNR(written(tmp_path, 'n.cal', NUTNR_CAL))
    assert cals['CC_cal_temp'] == pytest.approx(20.143281674398008)
    assert cals['CC_wl'] == [189.60, 190.39]
    assert cals['CC_eno3'] == [-0.00301775, 0.00268737]
    assert cals['CC_eswa'] == [0.00078692, -0.00227945]
    ## the fourth column is skipped: CC_di is the fifth
    assert cals['CC_di'] == [34.0, 33.0]


def test_theCalibrationTemperatureIsReadWhicheverWayItIsSpelled(tmp_path):
    """Files carry `T_CAL` and `T_CAL_SWA`, and both mean the same thing."""
    plain = readNUTNR(written(tmp_path, 'n.cal', 'H,T_CAL 18.5,,,,\n'))
    assert plain['CC_cal_temp'] == pytest.approx(18.5)


def test_aNutnrWithNoSpectrumReadsAsEmptyListsRatherThanMissingKeys(tmp_path):
    cals = readNUTNR(written(tmp_path, 'n.cal', 'H,File format version 3,,,,\n'))
    assert cals['CC_wl'] == [] and cals['CC_eno3'] == []


## ---- Satlantic irradiance: the same row shape, one set or seven ----

def test_theParCoefficientsAreTheOneCalibrationRow(tmp_path):
    tdf = '# Telemetry Definition File:\n# Type: Satlantic PAR Sensor 1399\n332224.5\t3.3587930077e-004\t1.3589\n'
    assert readPARA(written(tmp_path, 'p.tdf', tdf)) == {
        'CC_a0': '332224.5', 'CC_a1': '3.3587930077e-004', 'CC_Im': '1.3589'}


def test_theSpkirReadsOneRowPerChannelInOrder(tmp_path):
    cal = ('# Satlantic model # OCR-507\n'
           '2147446251.2\t2.04733022774e-007\t1.368\n'
           '2147781591.6\t1.96968395831e-007\t1.410\n'
           '2146686374.8\t2.13966994962e-007\t1.365\n')
    cals = readSPKIR(written(tmp_path, 's.cal', cal))
    assert cals['CC_offset'] == [2147446251.2, 2147781591.6, 2146686374.8]
    assert cals['CC_scale'] == pytest.approx([2.04733022774e-07, 1.96968395831e-07, 2.13966994962e-07])
    assert cals['CC_immersion_factor'] == [1.368, 1.410, 1.365]


def test_aCommentedHeaderIsNotReadAsACalibrationRow(tmp_path):
    """Both files open with a block of `#` lines carrying dates and numbers."""
    cal = '# 2013-02-15 |jennifer |1.9.0_11   |A   |ED\n1.0\t2.0e-007\t3.0\n'
    assert readSPKIR(written(tmp_path, 's.cal', cal))['CC_offset'] == [1.0]


## ---- Seabird CTD: an xml tree, the path per coefficient ----

XMLCON = """<?xml version="1.0" encoding="UTF-8"?>
<SBE_InstrumentConfiguration>
  <Instrument>
    <SensorArray Size="2">
      <Sensor index="0" SensorID="58">
        <TemperatureSensor SensorID="58">
          <SerialNumber>6914</SerialNumber>
          <CalibrationDate>05-Nov-23</CalibrationDate>
          <A0>1.24729948e-003</A0>
          <A1>2.7121945e-004</A1>
        </TemperatureSensor>
      </Sensor>
      <Sensor index="1" SensorID="3">
        <ConductivitySensor SensorID="3">
          <SerialNumber>6914</SerialNumber>
          <Coefficients equation="1">
            <G>-9.85261255e-001</G>
          </Coefficients>
        </ConductivitySensor>
      </Sensor>
    </SensorArray>
  </Instrument>
</SBE_InstrumentConfiguration>
"""

COEFF_MAP = {'CC_a0': ['Temperature', 'A0'], 'CC_a1': ['Temperature', 'A1'],
             'CC_g': ['Conductivity', 'G']}


def test_eachCoefficientIsReadFromItsOwnSensorBlock(tmp_path):
    """Both blocks carry a SerialNumber, so a search of the whole tree would
    find whichever came first. The block is part of the address."""
    path = written(tmp_path, 'c.xmlcon', XMLCON)
    cals = readXmlcon(path, COEFF_MAP, ['CC_a0', 'CC_a1', 'CC_g'])
    assert cals == {'CC_a0': '1.24729948e-003', 'CC_a1': '2.7121945e-004',
                    'CC_g': '-9.85261255e-001'}


def test_aCoefficientTheMapDoesNotCarryIsSkippedNotGuessedAt(tmp_path):
    path = written(tmp_path, 'c.xmlcon', XMLCON)
    assert readXmlcon(path, COEFF_MAP, ['CC_a0', 'CC_not_mapped']) == {'CC_a0': '1.24729948e-003'}


## ---- WET Labs ac-s: a header, then one row per wavelength ----

def optaaDev(tcal='"tcal: 21.3 C, ical: 22.7 C."'):
    """Two wavelengths against three temperature bins, in the real layout."""
    return '\n'.join([
        'ACS Meter',
        tcal,
        '3\t\t\t; number of temperature bins',
        '\t\t\t\t1.76\t2.44\t3.44\t\t\t; temperature bins',
        'C401.2\tA400.0\t8\t-2.540648\t-5.618652\t0.05\t0.04\t0.03\t0.02\t0.01\t0.00',
        'C402.5\tA401.3\t8\t-2.540000\t-5.610000\t0.15\t0.14\t0.13\t0.12\t0.11\t0.10',
        '',
    ])


def test_theAcsRowsSplitIntoWavelengthsOffsetsAndTwoCorrectionMatrices(tmp_path):
    cals = readOPTAA(written(tmp_path, 'o.dev', optaaDev()))
    assert cals['CC_tcal'] == pytest.approx(21.3)
    assert cals['CC_tbins'] == [1.76, 2.44, 3.44]
    assert cals['CC_cwlngth'] == [401.2, 402.5]
    assert cals['CC_awlngth'] == [400.0, 401.3]
    assert cals['CC_ccwo'] == pytest.approx([-2.540648, -2.540000])
    assert cals['CC_acwo'] == pytest.approx([-5.618652, -5.610000])
    ## as many of each correction as there are bins, c first then a
    assert cals['CC_tcarray'] == [[0.05, 0.04, 0.03], [0.15, 0.14, 0.13]]
    assert cals['CC_taarray'] == [[0.02, 0.01, 0.00], [0.12, 0.11, 0.10]]


@pytest.mark.parametrize('spelled', [
    '"tcal: 21.3 C, ical: 22.7 C."',
    'tcal: 21.3 C, ical: 22.7 C',
    'Tcal: 21.3 C, Ical: 22.7 C',
])
def test_theCalibrationTemperatureIsReadHoweverTheInstrumentSpelledIt(tmp_path, spelled):
    """Matching only the quoted lower-case spelling left CC_tcal unread on 30 of
    110 calibrations."""
    cals = readOPTAA(written(tmp_path, 'o.dev', optaaDev(spelled)))
    assert cals['CC_tcal'] == pytest.approx(21.3)


def test_theBinCountLineIsNotMistakenForTheBinsThemselves(tmp_path):
    """Both end in `temperature bins`; only one carries the values."""
    assert readOPTAA(written(tmp_path, 'o.dev', optaaDev()))['CC_tbins'] == [1.76, 2.44, 3.44]
