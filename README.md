# rca-metadata

Verification of Regional Cabled Array deployment metadata and vendor calibration
files. Every deployed sensor should be correctly assigned, and every calibration
file in `asset-management` should match the vendor original in `calibrationFiles`.

This package replaces the notebooks in the `metadataVerification` repository.
The package is the source of truth; nothing is maintained in two places.

## Layout

    src/rca_metadata/
      calibrations.py   github cal file vs vendor original
      vendor.py         one reader per vendor file format
      rawarchive.py     listing the OOI raw data archive
      serials.py        serial numbers out of raw files
    params/             instrument list, coefficient map and constants
    tests/

## Running the tests

    pip install -e ".[test]"
    pytest

## Verdicts

A calibration comparison returns a verdict and the differences behind it:

| verdict | meaning |
|---|---|
| `MISMATCH` | a coefficient disagrees with the vendor |
| `MISSING_COEFFICIENT` | the vendor file does not carry a coefficient the github file claims |
| `CONSTANT_MISMATCH` | the only disagreements are with `coefficientConstants.csv`, where no vendor value is involved |
| `COMPARED` / `COMPARED_XML` | read and agreed |
| `PDF_NOTCOMPARED` | only a pdf is on file |
| `NO_VENDOR_FILE` | the sensor has a comparison rule but no vendor file |
| `NAN` | no comparison rule for this sensor |

Comparison is exact — there is no tolerance. Where a vendor file publishes fewer
significant figures than the github csv carries, that gap is a transcription to
fix in the data, not noise to absorb in code.

## Reports predating the correctness fixes are not a baseline

Two defects made the calibration check report success without checking: the
verdict was set to `COMPARED` before any vendor file was opened, and in the CTD
and DOFSTA `.cal` paths the difference was computed outside the coefficient loop
so only the last coefficient was compared. Both are fixed here, and
`tests/test_calibrations.py` covers exactly those failure modes.

Anything in the old `reportOuts/` predating `metadataVerification@0ac8bd8` was
produced by the buggy path. Baselines start at the first post-fix run.
