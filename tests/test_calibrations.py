"""Tests for the two defects that made the notebook-era check report success
without checking, plus the verdicts that rank above a plain pass.

FLNTU is used throughout because its vendor format is a single line per channel
and it has entries in coefficientConstants.csv, so one sensor exercises both the
vendor and the constant path.
"""

import pandas as pd
import pytest

from rca_metadata.calibrations import compareCalCoefficients

COEFF_MAP = {}
CONSTANTS = {'FLNTU': {'CC_angular_resolution': 1.096, 'CC_depolarization_ratio': 0.039}}

VENDOR_LINES = 'Chl=4\t0.0121\t50\nlambda=6\t0.00231\t48\t700\n'


@pytest.fixture
def vendorStem(tmp_path):
    """A vendor .dev.lambda whose path carries the FLNTU asset ID."""
    stem = tmp_path / 'ATAPL-70110-00001__20130422'
    stem.with_suffix('.dev.lambda').write_text(VENDOR_LINES)
    return str(stem)


def githubCal(**coeffs):
    ## object dtype, so a resolved sheet stays a list rather than being
    ## flattened into columns.
    return pd.DataFrame({'name': list(coeffs),
                         'value': pd.Series(list(coeffs.values()), dtype=object)})


def compare(cal, stem):
    return compareCalCoefficients(cal, stem, COEFF_MAP, CONSTANTS)


def test_matchingFileCompares(vendorStem):
    cal = githubCal(CC_scale_factor_chlorophyll_a=0.0121, CC_dark_counts_chlorophyll_a=50.0)
    assert compare(cal, vendorStem) == ['COMPARED']


def test_missingVendorFileNeverReportsSuccess(tmp_path):
    """The silent pass: a sensor with a comparison rule but no vendor file on
    disk must not come back COMPARED."""
    cal = githubCal(CC_scale_factor_chlorophyll_a=0.0121)
    verdict = compare(cal, str(tmp_path / 'ATAPL-70110-00001__20130422'))
    assert verdict == ['NO_VENDOR_FILE']


def test_pdfOnlyIsNotCompared(tmp_path):
    stem = tmp_path / 'ATAPL-70110-00001__20130422'
    stem.with_suffix('.pdf').write_text('')
    cal = githubCal(CC_scale_factor_chlorophyll_a=0.0121)
    assert compare(cal, str(stem))[0] == 'PDF_NOTCOMPARED'


def test_everyCoefficientIsCompared(vendorStem):
    """The loop-scope defect: the difference was computed outside the loop, so
    only the last coefficient decided the verdict. A disagreement on the first
    of several must still be found."""
    cal = githubCal(CC_scale_factor_chlorophyll_a=0.9999,   # differs
                    CC_dark_counts_chlorophyll_a=50.0,      # matches
                    CC_measurement_wavelength=700.0)        # matches, and is last
    verdict = compare(cal, vendorStem)
    assert verdict[0] == 'MISMATCH'
    assert [row[1] for row in verdict[1:]] == ['CC_scale_factor_chlorophyll_a']


def test_allDifferencesRecordedNotJustTheFirst(vendorStem):
    cal = githubCal(CC_scale_factor_chlorophyll_a=0.9999, CC_dark_counts_chlorophyll_a=1.0)
    verdict = compare(cal, vendorStem)
    assert len(verdict[1:]) == 2


def test_constantOnlyDifferenceIsItsOwnVerdict(vendorStem):
    """No vendor value is involved in a constant, so it is not a disagreement
    with the vendor."""
    cal = githubCal(CC_angular_resolution=2.0, CC_dark_counts_chlorophyll_a=50.0)
    verdict = compare(cal, vendorStem)
    assert verdict[0] == 'CONSTANT_MISMATCH'
    assert verdict[1][5] == 'constant'


def test_vendorMismatchOutranksConstant(vendorStem):
    cal = githubCal(CC_angular_resolution=2.0, CC_scale_factor_chlorophyll_a=0.9999)
    assert compare(cal, vendorStem)[0] == 'MISMATCH'


def test_verdictDoesNotDependOnRowOrder(vendorStem):
    """A weaker verdict arriving after a stronger one must not overwrite it."""
    first = githubCal(CC_scale_factor_chlorophyll_a=0.9999, CC_angular_resolution=2.0)
    second = githubCal(CC_angular_resolution=2.0, CC_scale_factor_chlorophyll_a=0.9999)
    assert compare(first, vendorStem)[0] == compare(second, vendorStem)[0] == 'MISMATCH'


def test_coefficientAbsentFromVendorFileIsReported(vendorStem):
    """An unchecked coefficient must not read as a pass."""
    cal = githubCal(CC_scale_factor_cdom=0.5)
    verdict = compare(cal, vendorStem)
    assert verdict[0] == 'MISSING_COEFFICIENT'
    assert verdict[1][1] == 'CC_scale_factor_cdom'


def test_sensorWithNoRuleReportsNan(tmp_path):
    cal = githubCal(CC_a=1.0)
    assert compare(cal, str(tmp_path / 'ATAPL-99999-00001__20130422')) == ['NAN']


def test_optaaIsComparedAgainstTheDevFile(tmp_path):
    """The .dev is the pure-water calibration, which is what asset-management
    is generated from."""
    cal = githubCal(**OPTAA_COEFFS)
    assert compare(cal, optaaStem(tmp_path)) == ['COMPARED']


## --- vendor files are found whatever case their extension is spelled in ---

def test_vendorFileIsFoundWhenItsExtensionIsUppercase(tmp_path):
    """27 vendor files carry .CAL or .DEV. A case-insensitive filesystem finds
    them and a case-sensitive one does not, so the check answered differently on
    a laptop than on a Linux runner."""
    from rca_metadata.calibrations import findVendorFile
    stem = tmp_path / 'ATOSU-68020-00005__20200801'
    stem.with_suffix('.CAL').write_text('')
    found = findVendorFile(str(stem), '.cal')
    ## the name as the directory spells it, not the name we asked for --
    ## which is what makes this independent of the filesystem
    assert found.endswith('.CAL')


def test_anUppercaseVendorFileIsActuallyCompared(tmp_path):
    stem = tmp_path / 'ATAPL-70110-00001__20130422'
    stem.with_suffix('.DEV.lambda').write_text(VENDOR_LINES)
    cal = githubCal(CC_scale_factor_chlorophyll_a=0.0121, CC_dark_counts_chlorophyll_a=50.0)
    assert compare(cal, str(stem)) == ['COMPARED']


def test_aVendorFileThatIsGenuinelyAbsentIsStillReported(tmp_path):
    from rca_metadata.calibrations import findVendorFile
    assert findVendorFile(str(tmp_path / 'ATOSU-68020-00005__20200801'), '.cal') is None


def test_missingDirectoryIsNotAnError():
    from rca_metadata.calibrations import findVendorFile
    assert findVendorFile('/no/such/directory/ATAPL-1__20200101', '.cal') is None


## --- one vendor format per instrument, and no falling back to another ---

def test_flntuIsNotComparedAgainstThePlainDevFile(tmp_path):
    """Both .dev files are posted to the vendor repository, but asset-management
    is generated from the .dev.lambda. Comparing against the plain .dev finds
    disagreements that are an artefact of reading the wrong file -- it did, on
    three real calibrations, every one of them reported as a MISMATCH."""
    stem = tmp_path / 'ATAPL-70110-00001__20130422'
    stem.with_suffix('.dev').write_text(VENDOR_LINES)
    cal = githubCal(CC_scale_factor_chlorophyll_a=0.0121)
    assert compare(cal, str(stem)) == ['FORMAT_NOTCOMPARED']


def test_ctdIsNotComparedAgainstTheLowerResolutionCalFile(tmp_path):
    """A Seabird .cal publishes fewer significant figures than the .xmlcon, so
    a comparison against it manufactures rounding disagreements."""
    stem = tmp_path / 'ATAPL-67627-00001__20150423'
    stem.with_suffix('.cal').write_text('irrelevant\n')
    cal = githubCal(CC_C1=1022.921)
    assert compare(cal, str(stem)) == ['FORMAT_NOTCOMPARED']


def test_nothingOnRecordIsNotTheSameAsTheWrongFormat(tmp_path):
    """The two silences ask different things of a person: find the vendor file,
    or go and fetch the format this instrument is compared against."""
    cal = githubCal(CC_scale_factor_chlorophyll_a=0.0121)
    assert compare(cal, str(tmp_path / 'ATAPL-70110-00001__20130422')) == ['NO_VENDOR_FILE']


def test_aPdfStillOutranksAnUnparsedFormat(tmp_path):
    """A scan is the more useful thing to say: it names why no parser will ever
    read it, rather than implying some other format would do."""
    stem = tmp_path / 'ATAPL-70110-00001__20130422'
    stem.with_suffix('.dev').write_text(VENDOR_LINES)
    stem.with_suffix('.pdf').write_text('')
    cal = githubCal(CC_scale_factor_chlorophyll_a=0.0121)
    assert compare(cal, str(stem))[0] == 'PDF_NOTCOMPARED'




## --- a calibration date is not an asset ID ---

def test_aCalibrationDateIsNotMistakenForAnAssetId():
    """Asset IDs were matched as substrings of the whole path, and a date
    contains one: 2017-01-10 spells 70110, which is FLNTU's asset ID, and
    2017-01-11 spells 70111, which is FLCDR's.

    A NUTNR and a SPKIR calibration were checked against the wrong instrument's
    rules for years, reporting no vendor file while their .cal sat beside them.
    """
    from rca_metadata.calibrations import identifySensor

    assert identifySensor('/any/where/ATOSU-68020-00008__20170111') == 'NUTNR'
    assert identifySensor('/any/where/ATAPL-58341-00006__20170110') == 'SPKIR'
    ## and a PCO2W dated the same day is a PCO2W, not the FLCDR its date spells
    assert identifySensor('/any/where/ATAPL-58336-00001__20170111') == 'PCO2W'
    ## an instrument with no rule at all stays without one
    assert identifySensor('/any/where/ATAPL-12345-00001__20170111') is None


def test_theSurroundingPathCannotDecideTheSensor():
    """The path is a property of the machine the run happened on, not of the
    calibration. Two runs of the same file must identify it the same way."""
    from rca_metadata.calibrations import identifySensor

    assert identifySensor('/home/70110/ATOSU-68020-00008__20230209') == 'NUTNR'
    assert identifySensor('ATOSU-68020-00008__20230209') == 'NUTNR'


## --- OPTAA: one calibration, three files on the github side ---

OPTAA_DEV = (
    'ACS Meter\n'
    '5300008D\t\t; Serial number\n'
    '3\t; structure version number\n'
    '"tcal: 21.3 C, ical: 22.7 C. The offsets were saved to this file on 9/18/13."\n'
    '0\t0\t\t; Depth calibration\n'
    '0.25\t\t\t; Path length (meters)\n'
    '2\t\t\t; output wavelengths\n'
    '3\t\t\t; number of temperature bins\n'
    '\t\t\t1.0\t2.0\t3.0\t; temperature bins\n'
    'C401.2\tA400.0\t8\t-2.5\t-5.6\t\t0.1\t0.2\t0.3\t\t-0.9\t-0.8\t-0.7\t\t"; offsets"\n'
    'C404.6\tA403.9\t10\t-2.3\t-4.8\t\t0.4\t0.5\t0.6\t\t-0.6\t-0.5\t-0.4\t\t"; offsets"\n'
)

## What the cal script writes into asset-management from the .dev above: the six
## values in the csv, and the two arrays as sheets the csv points at.
OPTAA_COEFFS = {
    'CC_tcal': 21.3,
    'CC_tbins': [1.0, 2.0, 3.0],
    'CC_cwlngth': [401.2, 404.6],
    'CC_awlngth': [400.0, 403.9],
    'CC_ccwo': [-2.5, -2.3],
    'CC_acwo': [-5.6, -4.8],
    'CC_tcarray': [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
    'CC_taarray': [[-0.9, -0.8, -0.7], [-0.6, -0.5, -0.4]],
}


def optaaStem(tmp_path, suffix='.dev'):
    stem = tmp_path / 'ATAPL-69943-00001__20130918'
    (tmp_path / f'ATAPL-69943-00001__20130918{suffix}').write_text(OPTAA_DEV)
    return str(stem)


def test_optaaIsNotComparedAgainstTheAirCalibration(tmp_path):
    """Both files are posted to the vendor repository. The .cal is the air
    calibration and asset-management is not built from it, so a calibration with
    only a .cal on record has nothing to compare against."""
    cal = githubCal(**OPTAA_COEFFS)
    assert compare(cal, optaaStem(tmp_path, '.cal')) == ['FORMAT_NOTCOMPARED']


def test_optaaFindsACoefficientThatDisagrees(tmp_path):
    cal = githubCal(**{**OPTAA_COEFFS, 'CC_tcal': 21.4})
    verdict, *differences = compare(cal, optaaStem(tmp_path))
    assert verdict == 'MISMATCH'
    assert [d[1] for d in differences] == ['CC_tcal']


def test_optaaComparesEveryCellOfTheTemperatureArrays(tmp_path):
    """The arrays are the larger part of the calibration -- 85 x 38 apiece on a
    real instrument. One wrong cell has to be found."""
    wrong = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.99]]
    cal = githubCal(**{**OPTAA_COEFFS, 'CC_tcarray': wrong})
    verdict, *differences = compare(cal, optaaStem(tmp_path))
    assert verdict == 'MISMATCH'
    assert differences[0][1] == 'CC_tcarray'
    assert '1 of 6 values differ' in differences[0][4]


def test_optaaComparesInOrderBecauseTheIndexIsTheWavelength(tmp_path):
    """The nth offset belongs to the nth wavelength. Compared as sets -- which is
    how the other spectra compare -- a reversal would read as agreement."""
    cal = githubCal(**{**OPTAA_COEFFS, 'CC_cwlngth': [404.6, 401.2]})
    verdict, *differences = compare(cal, optaaStem(tmp_path))
    assert verdict == 'MISMATCH'
    assert differences[0][1] == 'CC_cwlngth'


def test_aSheetMissingFromAssetManagementIsReportedNotPassed(tmp_path):
    """The csv points at two .ext sheets. If one is not there the loader hands
    across None, and that must read as unchecked rather than as agreement."""
    cal = githubCal(**{**OPTAA_COEFFS, 'CC_taarray': None})
    verdict, *differences = compare(cal, optaaStem(tmp_path))
    assert verdict == 'MISMATCH'
    assert 'not in asset-management' in differences[0][4]


def test_aDevFileMissingItsTcalDoesNotTakeTheRunDown(tmp_path):
    """float(None) ended the whole verification. A field the vendor file does
    not spell is an unchecked coefficient, which the check already has a
    verdict for."""
    stem = tmp_path / 'ATAPL-69943-00001__20130918'
    stem.with_suffix('.dev').write_text(OPTAA_DEV.replace('"tcal: 21.3 C,', '"ical: 22.7 C,'))
    cal = githubCal(**OPTAA_COEFFS)
    verdict, *differences = compare(cal, str(stem))
    assert verdict == 'MISSING_COEFFICIENT'
    assert differences[0][1] == 'CC_tcal'


def test_theCalibrationTemperatureIsFoundHoweverTheInstrumentSpeltIt(tmp_path):
    """Three spellings across the archive. Matching only the quoted lower-case
    one left CC_tcal unread on 30 of 110 calibrations, every one of them
    reported as a missing coefficient."""
    from rca_metadata.vendor import readOPTAA

    for header in ['"tcal: 21.3 C, ical: 22.7 C."',
                   'tcal: 21.3 C, ical: 22.7 C. Saved on 4/2/2021.',
                   'Tcal: 21.3 C, Ical: 20.7 C. Saved on 5/16/2023. ']:
        path = tmp_path / 'ATAPL-69943-00001__20130918.dev'
        path.write_text(OPTAA_DEV.replace(
            '"tcal: 21.3 C, ical: 22.7 C. The offsets were saved to this file on 9/18/13."',
            header))
        assert readOPTAA(str(path))['CC_tcal'] == 21.3, header


## --- a coefficient the certificate leaves out on purpose ---

def test_aCoefficientTheVendorOmitsIsHeldToItsDeclaredDefault(vendorStem, monkeypatch):
    """An optode with no 2-point recalibration prints no concentration
    coefficient, and the record carries the identity. That is not an unchecked
    coefficient -- it is one the certificate answers by saying nothing."""
    from rca_metadata.calibrations import SENSORS

    monkeypatch.setitem(SENSORS['FLNTU'], 'defaults', {'CC_absent': 7.0})
    assert compare(githubCal(CC_absent=7.0), vendorStem) == ['COMPARED']


def test_aRecordClaimingMoreThanTheCertificateShowsIsStillAFinding(vendorStem, monkeypatch):
    from rca_metadata.calibrations import SENSORS

    monkeypatch.setitem(SENSORS['FLNTU'], 'defaults', {'CC_absent': 7.0})
    verdict, *differences = compare(githubCal(CC_absent=9.0), vendorStem)
    assert verdict == 'CONSTANT_MISMATCH'
    assert differences[0][5] == 'default'


def test_withoutADefaultAnOmittedCoefficientIsStillUnchecked(vendorStem):
    verdict, *differences = compare(githubCal(CC_absent=7.0), vendorStem)
    assert verdict == 'MISSING_COEFFICIENT'
