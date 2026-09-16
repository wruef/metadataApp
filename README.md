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

## Parameter files

`rawFileSN.csv` and `imageSN.csv` are cumulative: one row per deployment, with
new rows appended each year after the cruise. They were previously a series of
yearly snapshots (`rawFileSN_20250902.csv`, `imageSN_2025.csv`, ...), which meant
the check only ever read the newest one and earlier years' curation went unused.

Both are keyed on `referenceDesignator` + `deployNum`, not on year. An instrument
can be deployed more than once in a season -- the shallow profilers usually are --
so a year is not enough to identify a deployment, and looking one up by year
silently returns whichever row came first.

A blank `deployNum` means the row could not be tied to a single deployment: the
reference designator has more than one deployment that year and nothing in the
row separates them. Those rows need a person, and are the ones to resolve first.

## Running a verification

    pip install .
    verify-metadata --clones repos --out reports/report.json

Repositories are named `owner/repo@ref`, and a clone under `--clones` is used
when it is there. The two read paths give the same answers -- a clone is simply
far cheaper, because the calibration comparison probes the filesystem for vendor
files and would otherwise pull down ~1,300 of them over the wire.

    verify-metadata \
      --asset-management someone/asset-management@a-branch \
      --calibration-files OOI-CabledArray/calibrationFiles@master \
      --clones repos

Two runs can be compared, which is what turns a report into an answer about
whether a change is safe:

    compare-metadata reports/baseline.json reports/report.json

Every comparison says whether it can be trusted. A row can move because the data
changed or because the *check* changed -- fixing the silent-pass bug moved 114
rows with nothing in the repositories moving at all -- so two runs produced by
different versions of the checks are refused rather than diffed.

## Publishing the generated files

Three products are generated rather than checked. Each is written to disk, and
proposed to **your own fork** when you name one -- never to a shared repository.
The onward pull request is raised by hand.

    publish-metadata history --fork you/deployments
    publish-metadata seasons --year 2026
    publish-metadata positions --fork you/asset-management --node-fork you/deployments

The same run happens in CI through `.github/workflows/verify.yaml`, on
`workflow_dispatch` only. There is no schedule: a run is an event someone
chooses, usually once a season after the cruise, and occasionally to check a
branch before it merges.

## Running the tests

    pip install -e ".[test]"
    pytest

## The run report

A run emits one versioned JSON document — `schemaVersion`, when it ran, every
input it read (both repository refs and the parameter-file commit), and the five
checks. It replaces five CSV and TXT files that could not reliably be read back:
the calibration report embedded a python list literal containing commas in its
last column, and the season lists wrote multi-valued serial numbers unquoted, so
27 of 154 rows in the 2022 list had more fields than the header.

Every row carries two things the dashboard should not have to work out itself:

- **`severity`** — `problem`, `review`, `unchecked` or `ok`, taken as the worst
  of the row's verdicts, so a queue can be ranked by consequence rather than by
  row order. A verdict with no mapping counts as `review`, so a new one reaches a
  person instead of quietly passing.
- **`cleared`** — whether a reviewer signed the row off, kept separate from its
  severity. A sign-off outranks a failing check, but the failing check stays
  visible on the row: *cleared, calibration noted*, never a plain pass.

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
