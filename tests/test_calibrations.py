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
    return pd.DataFrame({'name': list(coeffs), 'value': list(coeffs.values())})


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


def test_optaaHasNoComparisonRule(tmp_path):
    cal = githubCal(CC_a=1.0)
    assert compare(cal, str(tmp_path / 'ATAPL-69943-00001__20130422')) == ['NAN']


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
