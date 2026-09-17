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
| `deployments` | is the instrument on the sheet the one that was in the water, and did it have a calibration? |
| `positions` | do the deployment sheets agree with the RCA position spreadsheet? |
| `sensorBulk` | do serial numbers agree between the RCA instrument list and the OOI sensor bulk record? |
| `deploymentSheets` | is one asset deployed in two places at once, and is every asset a sheet names in the bulk record it belongs to? |

Every verdict each of them can return, and whether it counts as passing, is in
[docs/what-each-check-decides.md](docs/what-each-check-decides.md).

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

A comparison states whether it can be trusted and refuses itself when it cannot
— when the checks changed rather than the data, or when either run cannot name
the commit it read. [docs/report-contract.md](docs/report-contract.md) says why.

## The dashboard

**If you are here to review metadata rather than to work on the code, read
[docs/using-the-dashboard.md](docs/using-the-dashboard.md).** It covers creating
a token, finding your way around, recording a decision and starting a run, step
by step. The site is at **https://wruef.github.io/metadataApp/**.

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
review status, which is where a bad season shows up as a shape rather than a
number.

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
each so the distribution is visible without changing anything.

Every column header sorts: once for ascending, again for descending, a third
time back to the queue order the check opens in. **Review status** sorts by
consequence rather than alphabetically, because `problem` before `review` is the
order that means something and alphabetically it is the reverse. A row with
nothing in the sorted column goes last whichever way the column points — an
empty cell is the absence of a value, not the smallest one.

Beside it are dropdowns over the columns worth narrowing by: instrument and
comparison result for calibrations, site and year for deployments and positions,
verdict for the rest, and sign-off status for the two checks that have one. Their options come from the rows in the report rather than
from a list in the code, so a new instrument or a new verdict appears on its own.
Each option carries a count measured against every *other* active filter, so
narrowing one does not leave the numbers beside the alternatives stale.

Checks with more than 50 rows are paged. The report is around 2 MB, which gzips
to roughly 74 KB over the wire.

## Signing in, and signing off

Sign-offs are recorded in `2i_HITL/*.csv` — the team's record of who checked
what. Three checks are signed off: calibrations by file name, deployments by
reference designator, year and deployment number, and sensor bulk by asset ID.
The last is new: a serial number that disagrees between the RCA list and OOI's
record is mostly a judgement about which record is right, and there was nowhere
to write that judgement down, so 131 of them came back every run. Writing to them needs a GitHub token, entered under **Settings**:

A [fine-grained token](https://github.com/settings/personal-access-tokens/new)
scoped to your own forks, with **Contents** and **Pull requests** set to read and
write, and **Actions** as well on your `metadataApp` fork so a run can be started
from the dashboard.
[docs/using-the-dashboard.md](docs/using-the-dashboard.md#signing-in) walks
through it field by field.

Nothing else is needed — no organisation access, and no permission on any
upstream repository. The token is kept in the browser's local storage, is sent to
`api.github.com` and nowhere else, and is revalidated rather than trusted when a
session is restored.

Set your initials too: the HITL sheets identify reviewers by initials (`KB,WR`),
not by GitHub login.

Clearing or flagging a row queues a decision. The reason comes from a dropdown
of every note the sheet already holds, ranked by how often each has been used, so
the wording the team works with is at the top. Where the calibration file itself
says something about the coefficients that disagree, that is offered first.
Anything not in either list is typed straight into the field beneath them.

Submitting the queue opens **one** pull request carrying the whole batch,
against **your own fork**. You raise the onward pull request to the shared
repository by hand — a person decides when a batch is worth proposing to
everyone else.

## Starting a run from the dashboard

The bar across the top says what a run would verify. **Production** is what has
been merged; **Testing** takes a repository and a ref, and optionally a baseline
to compare against — the pre-cruise check, without leaving for the Actions tab.
The bar turns amber the moment it points anywhere other than production, so a
run against a branch cannot be mistaken for a run against what is merged.

Tick **Publish for review** on a testing run and it is committed under its own
name and appears in the run picker, where you can read it and its comparison
like any other run. It does not become `latest.json`, so the figures everyone
else reads do not move. That is what makes a branch check readable in the
dashboard rather than a zip you download from the Actions tab; only a production
run replaces what the site opens on.

Starting one dispatches `verify.yaml` **in your own fork of this repository**,
so it runs against the parameter files you have. The run is then followed in a
tray, step by step. Closing the tray stops following the run; it does not stop
the run.

Nothing on screen changes when a run finishes. The report is a file, and it is
only written if the run was told to publish. Publishing commits it, which
rebuilds the site a couple of minutes later; the run then appears in the picker
in the run stamp, which is where you open it.

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
than uploading it anywhere. Every published run is committed under its own name
and added to `reports/index.json`, which is what the run picker reads. Only a
production run is also copied to `reports/latest.json` — the run the site opens
on, and the baseline later comparisons are measured against. A branch run
therefore publishes without moving anything, which is why publishing one is
offered rather than refused. `replace_production` overrides that, for a branch
you mean to promote. A 2.1 MB report is roughly 75 KB as a git object, so
a decade of annual runs is under a megabyte — and the history then *is* the
provenance record, with every published run reachable as a baseline.

`.github/workflows/pages.yaml` builds the site and publishes it to **GitHub
Pages**, with typecheck and tests blocking. It runs on a push that changes the
dashboard, and on the verification workflow **finishing**, so a published run
redeploys the site that serves it. A pull request builds but does not deploy.

That second trigger is not decoration. A published run commits the report using
the default `GITHUB_TOKEN`, and GitHub deliberately refuses to start a workflow
from a push made with that token — it is how a workflow is stopped from
triggering itself forever. So `on: push` never fires for a published run: the
report reaches the repository, the site goes on serving the deploy before it,
and the dashboard answers `404` for a report that is plainly there in git. A
`workflow_run` trigger fires on the run completing rather than on its push, and
is not suppressed. It also has to check out the **branch**, because the event
carries the commit the verification run *started* from — the one before it
published.

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

## Design notes

The reasoning behind the answers, kept out of this file so it stays a guide to
running the thing:

- [docs/using-the-dashboard.md](docs/using-the-dashboard.md) — the reviewer's
  walkthrough: token, navigation, sign-offs, runs, and what to do when GitHub
  refuses something.
- [docs/what-each-check-decides.md](docs/what-each-check-decides.md) — every
  verdict each check can return, and whether it counts as passing.
- [docs/report-contract.md](docs/report-contract.md) — what a run emits, the
  category every row carries, and when a comparison between two runs refuses
  itself.
- [docs/calibration-comparison.md](docs/calibration-comparison.md) — which
  vendor file each instrument is compared against and why, the verdicts, the pdf
  certificates, and the rules that cost real findings to get right.
- [schema/report.json](schema/report.json) — the report's fields, named once and
  checked from both the python and the dashboard test suites.

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
      report.py         the run report contract, and review status
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
    schema/             the report's fields, read by both test suites
    docs/               why the checks answer the way they do
    tests/

## Running the tests

    pip install -e ".[test]"
    pytest

    cd dashboard && npm test

`.github/workflows/tests.yaml` runs the python tests on every push, against the
version a verification run uses and the oldest the package claims to support.
The dashboard's own tests run in the Pages workflow, where they block a deploy.

The environment is pinned on both sides, because comparison is exact to the last
digit a vendor file publishes and a different pandas is a different answer.
`environment.yml` builds the python side and `dashboard/.nvmrc` names the node
the dashboard is built with; every run records the versions it ran with under
`parameters` in its report.

    conda env create -f environment.yml && conda activate rca-metadata
    pip install -e ".[test]"

The dashboard tests cover the code that rewrites the HITL sheets, against the
real 380-row calibration sheet. A bug there corrupts years of sign-offs, and the
first version of it would have rewritten every line of the file on every commit.
