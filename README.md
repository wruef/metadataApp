# rca-metadata

Verification of Regional Cabled Array deployment metadata and vendor calibration
files. Every deployed sensor should be correctly assigned, and every calibration
file in `asset-management` should match the vendor original in `calibrationFiles`.

A run produces one JSON report. A dashboard reads that report, ranks what it
found by consequence, and lets a reviewer sign rows off — each sign-off going
back to GitHub as a pull request on the reviewer's own fork.

This package replaces the notebooks in the `metadataVerification` repository.
The package is the source of truth; nothing is maintained in two places.

## What is checked

| check | question it answers |
|---|---|
| `calibrations` | does each repository calibration file match the vendor original? |
| `deployments` | does each deployment have its calibration file, raw serial number and sign-off? |
| `positions` | do the deployment sheets agree with the RCA position spreadsheet? |
| `sensorBulk` | do serial numbers agree between the RCA instrument list and the OOI sensor bulk record? |
| `deploymentSheets` | does a sheet entry name something no other record knows about? |

## Running a verification

    pip install .
    verify-metadata --clones repos --out reports/report.json

Repositories are named `owner/repo@ref`, and a clone under `--clones` is used
when it is there. The two read paths give the same answers — a clone is simply
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
changed or because the *check* changed — fixing the silent-pass bug moved 114
rows with nothing in the repositories moving at all — so two runs produced by
different versions of the checks are refused rather than diffed.

A run must also record the commit of every repository it read, and a comparison
is refused when one does not. The ref is not enough: `master` today and `master`
next season are different data, so a moved row could not be attributed to either.
A directory copied rather than cloned has no `.git` to ask, which is exactly how
two runs came to be diffed while neither recorded which asset-management it had
seen — the commit now reads `UNKNOWN` rather than coming back empty.

## The dashboard

A Nuxt 4 single-page app that reads a published report. No backend: the report
is a file it fetches, and everything else happens in the browser.

    cd dashboard
    npm install
    npm run dev

**Node 22 or newer is required** — the build fails on older versions, and the
typecheck cannot run at all. To point it at a report other than the default
`/reports/latest.json`:

    NUXT_PUBLIC_REPORT_URL=/reports/report_20260915T162613Z.json npm run dev

The overview opens on **what needs a person**: not a count of problems, but the
situations behind them — *coefficients that disagree with the vendor*, *positions
the spreadsheet contradicts*, *deployments an extraction would settle* — each
with its count and a link that opens the check already filtered to exactly those
rows. The count and the table it opens are the same filter, so they cannot drift
apart. Below it, deployments by the year they went in the water, split by
severity, which is where a bad season shows up as a shape rather than a number.

The other views: one per check, ranked worst first; **Changes**, the diff between
two runs when a run was given a baseline; **Reference designators**, the list the
run saw; and **Sign-offs**, the queue of decisions waiting to be proposed. The run
stamp at the top of every page names the run being read — nothing refreshes on
its own, so a report older than a season is marked stale rather than left to look
current.

A filtered table is a URL. Sending someone
`/checks/calibrations?instrument=NUTNRA&vendorMatch=MISMATCH` sends them the view,
not instructions for reproducing it.

Opening a calibration row offers **the two files side by side** — the repository
CSV and the vendor original, at the refs the run read rather than at whatever the
branches hold now. The coefficients that disagree are marked on both sides and
each pane scrolls to the first one. The vendor side is matched on the parsed
number rather than its text, because the same value is written `1.022921e+003`
in one file and `1022.921` in the other and the two share no substring at all.
Nothing is marked on the vendor side for a `CONSTANT_MISMATCH`: the value came
from `params/coefficientConstants.csv` and is not in the vendor file to point at.
A PDF-only vendor calibration is left for a person to read.

A check opens on its queue — problems and rows needing a person — rather than on
everything, so a check with 1,558 agreeing rows does not bury the 105 that do
not. The segmented control at the top switches that, and carries the count for
each severity so the distribution is visible without changing anything.

Beside it are dropdowns over the columns worth narrowing by: instrument and
comparison result for calibrations, site and year for deployments and positions,
verdict for the rest. Their options come from the rows in the report rather than
from a list in the code, so a new instrument or a new verdict appears on its own.
Each option carries a count measured against every *other* active filter, so
narrowing one does not leave the numbers beside the alternatives stale.

Checks with more than 50 rows are paged. The report is around 2 MB, which gzips
to roughly 74 KB over the wire.

## Signing in, and signing off

Sign-offs are recorded in `2i_HITL/*.csv` — the team's record of who checked
what. Writing to them needs a GitHub token, entered under **Settings**:

1. Create a [fine-grained token](https://github.com/settings/personal-access-tokens/new).
2. Under **Repository access**, select only *your own forks* of `metadataApp`,
   `asset-management` and `deployments`.
3. Under **Permissions**, set **Contents** and **Pull requests** to read and write.
4. On your `metadataApp` fork only, also set **Actions** to read and write. That is
   what lets you start a run from the dashboard; nothing else needs it.

Nothing else is needed — no organisation access, and no permission on any
upstream repository. The token is kept in the browser's local storage, is sent to
`api.github.com` and nowhere else, and is revalidated rather than trusted when a
session is restored.

Set your initials too: the HITL sheets identify reviewers by initials (`KB,WR`),
not by GitHub login.

Clearing or flagging a row queues a decision. Submitting the queue opens **one**
pull request carrying the whole batch, against **your own fork**. You raise the
onward pull request to the shared repository by hand — a person decides when a
batch is worth proposing to everyone else.

## Starting a run from the dashboard

The bar across the top says what a run would verify. **Production** is what has
been merged; **Testing** takes a repository and a ref, and optionally a baseline
to compare against — the pre-cruise check, without leaving for the Actions tab.
The bar turns amber the moment it points anywhere other than production, so a
run against a branch cannot be mistaken for a run against what is merged.

Starting one dispatches `verify.yaml` **in your own fork of this repository**,
so it runs against the parameter files you have. The run is then followed in a
tray, step by step. Closing the tray stops following the run; it does not stop
the run.

Nothing on screen changes when a run finishes. The report is a file, and it is
only replaced if the run was told to publish. Publishing commits the report,
which republishes the site with it a couple of minutes later. Reload from the
tray once it has.

Serial extraction is deliberately not here. It cannot complete without a person
in the middle, so a button implying otherwise would be a lie; run it by hand
until that changes.

## Publishing the generated files

Three products are generated rather than checked. Each is written to disk, and
proposed to **your own fork** when you name one — never to a shared repository.

    publish-metadata history --fork you/deployments
    publish-metadata seasons --year 2026
    publish-metadata positions --fork you/asset-management --node-fork you/deployments

Positions need two forks because instrument sheets live in `asset-management`
and node deployments live in `deployments`; a single combined write would file
half of them into the wrong sheet.

## In CI

`.github/workflows/verify.yaml` runs the checks on `workflow_dispatch` only.
There is no schedule: a run is an event someone chooses, usually once a season
after the cruise, and occasionally to check a branch before it merges. Inputs
select the asset-management repository and ref, an optional `baseline_ref` to
compare against, and whether to publish. The report is kept as a build artifact
either way, so a run that was only a look can still be read back.

Publishing **commits the report to this repository** under `reports/`, rather
than uploading it anywhere. A 2.1 MB report is roughly 75 KB as a git object, so
a decade of annual runs is under a megabyte — and the history then *is* the
provenance record, with every published run reachable as a baseline.

`.github/workflows/pages.yaml` builds the site and publishes it to **GitHub
Pages**, with typecheck and tests blocking. It runs on a push that changes
either half — the dashboard itself, or a report a run has committed — so a
published run redeploys the site that serves it. A pull request builds but does
not deploy.

Everything is inside GitHub. There is no bucket, no AWS credentials and no
secret of any kind: the site and the runs it reads are one artifact, and the
runs are bundled into it from `reports/` at build time. `reports/index.json`
lists every published run, which is what lets the dashboard open an earlier one.

Two things about a Pages project site are worth knowing, because both fail
silently:

- It is served from `/<repo>/`, so the base path is baked in at build time from
  the repository name. Every URL the app fetches is relative and joined to it —
  an absolute `/reports/latest.json` would ask `github.io` for a file that is
  not there.
- There are no rewrite rules, so a deep link like `/checks/calibrations` is a
  path with no file. Pages serves `404.html` for it, and because that file is
  the application shell, the router resolves the URL and the page appears.

**The published site is public.** Pages restricted to organisation members needs
GitHub Enterprise Cloud; from a private personal repository the site is readable
by anyone with the URL. That includes reviewer initials and HITL notes, so treat
a sign-off comment as something you are publishing.

Once, before the first deploy: **Settings → Pages → Source: GitHub Actions**.
Nothing else is configured, and nothing needs to be configured again.

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

Non-finite floats are written as `null`. Python emits `NaN` and `Infinity`
happily and neither is valid JSON, which a browser refuses to parse.

## Verdicts

A calibration comparison returns a verdict and the differences behind it:

| verdict | meaning |
|---|---|
| `MISMATCH` | a coefficient disagrees with the vendor |
| `MISSING_COEFFICIENT` | the vendor file does not carry a coefficient the github file claims |
| `CONSTANT_MISMATCH` | the only disagreements are with `coefficientConstants.csv`, where no vendor value is involved |
| `COMPARED` | read and agreed |
| `PDF_NOTCOMPARED` | only a pdf is on file |
| `FORMAT_NOTCOMPARED` | a vendor file is on record, but not in the format this instrument is compared against |
| `NO_VENDOR_FILE` | the sensor has a comparison rule but nothing on record |
| `NAN` | no comparison rule for this sensor |

Comparison is exact — there is no tolerance. Where a vendor file publishes fewer
significant figures than the github csv carries, that gap is a transcription to
fix in the data, not noise to absorb in code.

## Which vendor file each instrument is compared against

One format per instrument, and **no falling back to another**. Where a vendor
publishes the same calibration twice, the two files do not carry the same
numbers at the same precision, and comparing against the wrong one produces
disagreements that are an artefact of the choice rather than a fault in the data.

| instrument | file | why |
|---|---|---|
| CTD | `.xmlcon` | more resolution than the `.cal` or the pdf |
| DOFSTA | `.cal` | more resolution than the `.xml` or the pdf |
| FLCDRA | `.dev` | |
| FLNTUA | `.dev.lambda` | both `.dev` files are posted to the vendor repository; only the lambda one, which carries volume scattering, is what asset-management is generated from |
| FLORDD | `.dev.lambda` | |
| NUTNR | `.cal` | |
| SPKIRA | `.cal` | |
| OPTAA | `.dev` | the pure-water calibration. The `.cal` beside it is the **air** calibration and is not what asset-management is built from |
| PARA | `.tdf`, else `.pdf` | the vendor shipped a `.tdf` for some; the rest were typed in from the certificate |
| PHSEN | `.pdf` | typed in from the certificate |

Where the named format is absent but some other vendor file is on record, the
result is `FORMAT_NOTCOMPARED` rather than a comparison against whatever happens
to be there. Enforcing that moved five files out of the queue: four apparent
mismatches that were artefacts of reading the wrong file — including the nine
CTD coefficients differing by about one part in 10⁷ that had stood as a finding
for years — and one CTD that had been agreeing with a `.cal` it should never
have been read against.

### OPTAA is three files, and all three are compared

One OPTAA calibration is a csv plus two `.ext` sheets, each an 85 × 38 matrix
that the csv points at by name — `SheetRef:CC_taarray`. The vendor `.dev` carries
all of it: the calibration temperature from its header, the temperature bins, and
then one row per wavelength holding the two wavelengths, the two clean-water
offsets and both temperature-correction rows. The sheets are resolved when the
calibration is loaded, so the comparison sees matrices rather than the names of
files it would otherwise have skipped.

OPTAA coefficients are compared **in order**, unlike the other spectra. The index
is the wavelength: the nth offset belongs to the nth wavelength, and the nth row
of each array with it. Compared as sets — which is how the other spectra compare,
because a vendor publishes them unordered — a reversal would read as agreement,
and 85 values would match 86 with a repeat among them.

Of 110 OPTAA calibrations, **107 now compare and all 107 agree**. The other three
are two with no vendor file at all and one loaner instrument whose name carries
no asset-ID field.

### Certificates that were only ever published as a pdf

DOSTAD, PHSEN, PCO2W and PAR have no machine-readable vendor file, so their
coefficients are typed into asset-management by hand — about 400 RCA
calibrations, none of which anything checked. **Three quarters of those
certificates carry a text layer**, so the numbers can be read exactly rather
than recognised from an image; OCR is only needed for the 95 that are scans, and
is not implemented.

PAR and PHSEN are done: **119 calibrations that nothing had ever checked now
compare**, and the first run found a real transcription error — `CC_eb578`
entered as `38676.5` where the certificate says `38676.0`, with the other three
values on the same page correct.

Reading them is not "extract the text". The certificates are laid out for a
person, and every defect found while building this was in reassembling that
layout:

- Coefficient names are set with real **subscripts** — `Ea434` is `Ea` with a
  smaller `434` below and to the right — so they are joined by font size and
  position, which is the one thing every template agrees on.
- One certificate sets the `I` of `Im` a point lower than the `m`, which puts it
  at the end of its own line in draw order. Lines are therefore ordered by
  position, left to right, not by the order the page draws them.
- One breaks `2.5063877597725e-006` after the decimal point. Split numbers are
  rejoined **only** where a number is already expected, because widening that
  rule runs columns together: a PCO2W range of 202 to 1191 already reads as
  `2021191` once the en-dash between them — a glyph with no Unicode mapping —
  is silently dropped by a text extractor.

A coefficient the certificate does not carry at all is declared per sensor in
`notVendor` rather than reported missing on every row. PHSEN's salinity and ADC
bit depth are configuration, not vendor measurements — they vary across the
archive, so they are not constants either, and asset-management's own notes say
so: *"no sal listed on cal sheet; using default 35"*.

### A calibration date is not an asset ID

Sensors used to be identified by searching the whole file path for an asset ID.
A calibration dated 2017-01-10 spells `70110` inside its own date, which is
FLNTUA's asset ID, and 2017-01-11 spells `70111`, which is FLCDRA's. A NUTNR and
a SPKIR calibration were checked against the wrong instrument's rules for years
and reported as having no vendor file, while their `.cal` sat in the directory
beside them. Both compare and agree now. The asset ID is read from its own field
in the file name.

## Parameter files

`rawFileSN.csv` and `imageSN.csv` are cumulative: one row per deployment, with
new rows appended each year after the cruise. They were previously a series of
yearly snapshots (`rawFileSN_20250902.csv`, `imageSN_2025.csv`, ...), which meant
the check only ever read the newest one and earlier years' curation went unused.

Both are keyed on `referenceDesignator` + `deployNum`, not on year. An instrument
can be deployed more than once in a season — the shallow profilers usually are —
so a year is not enough to identify a deployment, and looking one up by year
silently returns whichever row came first.

A blank `deployNum` means the row could not be tied to a single deployment: the
reference designator has more than one deployment that year and nothing in the
row separates them. Those rows need a person, and are the ones to resolve first.

## Layout

    src/rca_metadata/
      run.py            one verification run, all five checks
      checks.py         the deployment, sensor-bulk and sheet checks
      calibrations.py   github cal file vs vendor original
      positions.py      deployment sheets vs the position spreadsheet
      vendor.py         one reader per vendor file format
      loading.py        reading the repositories and the parameter files
      sources.py        a repository at a ref, local clone or GitHub API
      report.py         the run report contract, and severity
      compare.py        two reports into what moved between them
      history.py        deployment history and the season lists
      publish.py        proposing generated files as a pull request
      rawarchive.py     listing the OOI raw data archive
      serials.py        serial numbers out of raw files
      cli.py            the four entry points
    dashboard/          the Nuxt SPA
    params/             instrument list, coefficient map and constants
    2i_HITL/            reviewer sign-off sheets
    inputs/             the RCA position spreadsheet drops
    tests/

## Running the tests

    pip install -e ".[test]"
    pytest

    cd dashboard && npm test

The dashboard tests cover the code that rewrites the HITL sheets, against the
real 380-row calibration sheet. A bug there corrupts years of sign-offs, and the
first version of it would have rewritten every line of the file on every commit.

## Reports predating the correctness fixes are not a baseline

Two defects made the calibration check report success without checking: the
verdict was set to `COMPARED` before any vendor file was opened, and in the CTD
and DOFSTA `.cal` paths the difference was computed outside the coefficient loop
so only the last coefficient was compared. Both are fixed here, and
`tests/test_calibrations.py` covers exactly those failure modes.

Anything in the old `reportOuts/` predating `metadataVerification@0ac8bd8` was
produced by the buggy path. Baselines start at the first post-fix run.
