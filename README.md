# rca-metadata

Verification of Regional Cabled Array deployment metadata and vendor calibration
files. Every deployed sensor should be correctly assigned, and every calibration
file in `asset-management` should match the vendor original in `calibrationFiles`.

A run produces one JSON report. A dashboard reads that report, ranks what it
found by consequence, and lets a reviewer sign rows off and correct the files
behind them — each batch of decisions going back to GitHub as a pull request on
the reviewer's own fork.

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
[docs/post-cruise-review.md](docs/post-cruise-review.md)** for the whole review
in order, and [docs/using-the-dashboard.md](docs/using-the-dashboard.md) for
the detail of any step: creating a token, finding your way around, recording a
decision, starting a run. The site is at **https://wruef.github.io/metadataApp/**.

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
run saw; **Not in asset-management**, the vendor calibrations with no repository
file; **Sign-offs with nothing to sign**, the decisions whose key matches no row
any more; **Deployment history**, the product the run built; and **Queued
changes**, everything decided and not yet proposed. The run stamp at the top of every page
names the run being read — nothing refreshes on its own, so a report older than a
season is marked stale rather than left to look current.

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
verdict for the rest, and sign-off status for the three checks that have one.
Their options come from the rows in the report rather than from a list in the
code, so a new instrument or a new verdict appears on its own.
Each option carries a count measured against every *other* active filter, so
narrowing one does not leave the numbers beside the alternatives stale.

Checks with more than 50 rows are paged. The report is just under 3 MB, which
gzips to roughly 110 KB over the wire.

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

### The queue, and what each batch becomes

Everything decided waits under **Queued changes** and goes over as **one pull
request per batch**, against **your own forks**. You raise each onward request to
the shared repository by hand — a person decides when a batch is worth proposing
to everyone else.

A batch is keyed by the repository it writes to *and* by what the change is:

| batch | fork | what it carries |
|---|---|---|
| Sign-offs | `metadataApp` | the 2i-HITL sheets, all three in one request |
| Calibration coefficients | `asset-management` | `calibration/<instrument>/*.csv` |
| Deployment sheets | `asset-management` | `deployment/<array>_Deploy.csv` |
| Node positions | `deployments` | `NODE_deployments.csv` |

Both halves of that key matter. The repository is a hard boundary, because a
pull request cannot span two of them. The kind is a boundary of review:
coefficients and deployment sheets share a fork, and somebody approving a page
of numbers has not agreed to move an instrument on the seabed, so the two travel
separately. What shares a *file* does not get split further, though — where a
deployment sat and which instrument it was are both corrections to one row of
one sheet, so they ride together. Two requests editing `RS03AXPS_Deploy.csv` on
branches cut from the same base would conflict the moment the first merged.

Opening every batch at once runs one request after another rather than
together — two branches cut from the same base at once is how the second lands
empty.

Each record keeps its own section of the body, with every value before and after
it, so batching changes how many requests there are and not what a reviewer has
to read. What closes the request — who proposed it, and what merging it would
change — is said once rather than once per record.

A batch is refused whole rather than proposed in part. One record that no longer
reads what the run read means the files have moved since the report on screen,
and writing the rest would be writing from a report already known to be stale.
The refusal names the records that failed.

### Correcting the asset-management file itself

A sign-off records a judgement about a file. Correcting one changes the file,
and every data product computed from it changes too, so it never rides with
sign-offs — a different repository, and a batch of its own. Three things are
offered: a calibration file's coefficients, one deployment's position on its
array's sheet, and the asset ID that names which instrument was in the water.

A node's position is the fourth. A node is named `SITE-NODE` and its deployment
lives in `NODE_deployments.csv` in the `deployments` repository rather than on
an array's sheet, so it is the same correction to a different file in a
different repository — its own batch, on that fork, guarded the same way.

The asset ID is corrected from the deployments view, under the row. It is the
answer to the check's commonest finding: a serial number read out of the raw
archive that belongs to a different asset of the same model. The run writes that
asset as `rawAssetID`, so it is offered to take with a click, and anything else
is typed. The pre-deploy
photograph names an asset too and is deliberately **not** offered, for the same
reason it does not confirm a deployment: a photograph of an instrument is not
evidence of which instrument went in the water.

It happens on the line. The table of what disagrees gains a **Correct to**
column, and for a calibration a note column, so the value being copied and the
box it goes into are side by side; clicking the vendor's own number takes it.
There used to be a read-only table and an editable copy of it behind a button,
which showed every number twice and invited reading one pair while typing at the
other. A coefficient holding several numbers is edited as the file
writes it and each element is written back in its own notation; above eight
values the line says so instead of offering a box, and a link to the file's
GitHub editor covers those.

It refuses rather than warns. The reviewer's `asset-management` fork has to be
exactly `oceanobservatories/asset-management` — behind, and the request reverts
whatever landed upstream meanwhile; ahead, and the onward request carries
unrelated commits along with the correction. The refusal says which way it has
moved, because the remedies differ: a fork that is behind is fixed by Sync fork,
and a fork that is ahead is not — Sync fork offers to *discard* the commits it
is ahead by, which is the correction itself.

The correction therefore travels on the branch the dashboard wrote it on. The
reviewer opens a second pull request from that branch on the shared repository's
compare page, rather than merging the fork's own request into their `master`,
which would add a merge commit and leave the fork ahead, blocking the next batch
until upstream catches up. [docs/post-cruise-review.md](docs/post-cruise-review.md)
walks through it click by click. It refuses again if a value no
longer reads what the run read, which means upstream moved and the report is out
of date. Between them, a correction can only start from the file the finding
came from.

Everything the edit did not touch comes back byte for byte, because both files
are hand-maintained records and reformatting one while fixing a digit in it
buries the fix in the diff. A calibration value is written in the notation its
line already uses — the repository files write `-5.064574e-001` where a vendor
publishes `-0.4839777`. A position correction rewrites one row of a
two-hundred-row sheet, found by reference designator *and* deployment number,
because an instrument can be deployed twice in a season. Where that row's notes
say the parameters are preliminary, they are cleared along with the position,
which is what `applyPositions` does to the same column.

A coefficient that is a short list is editable as the list the file writes,
with each element kept in its own notation and the length held fixed. The cutoff
is eight: every array-valued disagreement in the report is two values long,
while an OPTAA's `CC_acwo` is eighty-three, where typing the array back would be
guessing rather than correcting.

### Publishing the deployment history

Not a finding but a product: one csv per instrument type saying what was where
and when, each row carrying the calibration that was in force for that
deployment, plus `refDesList.csv` naming every reference designator that has one.
It is what the `deployments` repository holds.

Every run builds it, because a run already has everything it needs -- the
deployment sheets and both repositories' calibration indexes -- so building it
costs no further reads. It is published beside the report as
`reports/history_<stamp>.json` rather than inside it, because it is 400 KB of
csv that every other page of the dashboard would otherwise carry, and as
`history-latest.json` for whichever run became the current one.

The dashboard proposes it as one pull request on the reviewer's own fork, every
file at once: the history describes one state of the deployment sheets, and half
of it from one run and half from another would describe no state at all.
The commit is built on the fork's own tree, so files the repository holds that
the history does not name -- `NODE_deployments.csv` -- are left untouched. The
same fork-sync rule applies, for the same reason.

The reviewer commits the bytes the run wrote. Nothing regenerates the files in
the browser, so this module's quoting rules exist in one place: `instrumentSN`
is a list and is always quoted whether or not it contains a comma, so a diff
against the previous publication shows only real changes.

Rebuilding a history that has not been rebuilt in a while moves rows for reasons
other than new deployments, and the diff is worth reading rather than merging on
its size. Three have come up: an instrument still in the water has no end time,
which is written as an empty field where the older files carry the word `nan`; a
vendor calibration published as several files for one date now links the one the
comparison reads, which moved every OPTAA from its air calibration to its
pure-water one; and a row whose `sensorType` does not match the file it sits in
moves to the file that is named for it. The last of those is why a rebuild drops
30 rows from `CAMDS_deployments.csv` -- all 30 are `CAMDSB_CAMDSC` rows that
`CAMDSB_CAMDSC_deployments.csv` already holds, so nothing is lost.

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

The other two workflows are started from **Workflows** in the rail rather than
from this bar, because neither produces a report. **Extract serial numbers**
reads the raw archive and proposes `params/rawFileSN.csv` as a pull request for
a person to merge; **Delete published runs** takes runs out of the picker. Each
is followed in the same tray, and each is dispatched into the same copy of this
repository a verification run is. See
[Serial numbers from the raw archive](#serial-numbers-from-the-raw-archive).

## Publishing the generated files

Three products are generated rather than checked. Each is written to disk, and
proposed to **your own fork** when you name one — never to a shared repository.

    publish-metadata history --fork you/deployments
    publish-metadata seasons --year 2026
    publish-metadata positions --fork you/asset-management --node-fork you/deployments

Positions need two forks because instrument sheets live in `asset-management`
and node deployments live in `deployments`; a single combined write would file
half of them into the wrong sheet. A reviewer correcting one position at a time
does it from the dashboard instead; this is for correcting every one the
spreadsheet disagrees with in a single pass.

## In CI

`.github/workflows/verify.yaml` runs the checks on `workflow_dispatch` only.
There is no schedule: a run is an event someone chooses, usually once a season
after the cruise, and occasionally to check a branch before it merges. Inputs
select the asset-management repository and ref, the calibrationFiles ref, an
optional `baseline_ref` to compare against, and whether to publish. The report is
kept as a build artifact either way, so a run that was only a look can still be
read back. Publishing only happens when the workflow was dispatched from the
default branch: dispatched from any other branch, the report would be committed
there, the site rebuilds from the default branch and never shows it, and the run
would go green regardless. Such a run keeps its artifact and says so in a
warning instead.

Publishing **commits the report to this repository** under `reports/`, rather
than uploading it anywhere. Every published run is committed under its own name
and added to `reports/index.json`, which is what the run picker reads. Only a
production run is also copied to `reports/latest.json` — the run the site opens
on, and the baseline later comparisons are measured against. A branch run
therefore publishes without moving anything, which is why publishing one is
offered rather than refused.

The history and the comparison follow the report under both names: per run as
`history_<stamp>.json` and `comparison_<stamp>.json`, and for a production run
as `history-latest.json` and `comparison-latest.json`. The dashboard asks for
the fixed names when it opens on the current run and for the per-run names when
a reviewer picks an earlier one. A production run given no baseline has no
comparison, so publishing it **deletes** `comparison-latest.json` rather than
leaving the previous run's behind. The dashboard refuses one whose
`currentRunAt` is not the report's anyway, because a page of somebody else's
movements is worse than an empty one.

`replace_production` is the one exception, and it applies only to a run that is
not production: it promotes that run to `latest.json`. A production run becomes
that anyway, so the input does nothing there. A 2.1 MB report is roughly 75 KB as a git object, so
a decade of annual runs is under a megabyte — and the history then *is* the
provenance record, with every published run reachable as a baseline.

`.github/workflows/prune-runs.yaml` deletes runs that are no longer worth
keeping, on `workflow_dispatch` or from the dashboard's **Workflows** page. It
takes either a number of newest runs to keep or a list of names, and it **says
what it would do and changes nothing** unless `dry_run` is unticked. The same
thing on the command line:

    prune-runs --keep 10
    prune-runs --before 2026-01-01
    prune-runs --remove report_20260917T153944Z.json --dry-run

A run is its report plus whatever was published beside it — its comparison, and
the deployment history it built — and all of them go together, along with its
line in `reports/index.json`. Size is not the reason: an afternoon of test runs
makes the run picker unreadable long before it makes the repository large.

The run the dashboard opens on is protected. A rule that reaches it spares it
and says so, because deleting it would leave `latest.json` serving a run the
picker no longer lists; naming it outright is refused instead, because then it
is that run somebody asked for. Nothing is lost that git does not still hold —
`git checkout <sha>~1 -- reports/<name>` brings a deleted run back — but the
site stops offering it, which is the point.

`.github/workflows/extract-serials.yaml` reads the raw archive on
`workflow_dispatch`, or from the dashboard's **Workflows** page, and proposes
`params/rawFileSN.csv` as a pull request; it is
kept apart from the verification run so that a run stays a function of the
repositories and the committed parameter files, which is what lets two runs be
compared. It needs **Settings → Actions → General → Allow GitHub Actions to
create and approve pull requests** switched on, once.

`.github/workflows/pages.yaml` builds the site and publishes it to **GitHub
Pages**, with typecheck and tests blocking. It runs on a push that changes the
dashboard, and on the verification or deletion workflow **finishing**, so a
published run redeploys the site that serves it and a deleted one leaves it. A
run that only looked, or a dry-run prune, pushed nothing, and the build first
checks whether the default branch has moved since that run started; if it has
not, there is nothing to deploy and it stops there. A pull request builds but
does not deploy.

Two workflows commit to `reports/`, and they can run at the same time. Neither
uses a concurrency group: GitHub holds one running and one pending run per
group and cancels a third, so a busy afternoon of publishes lost runs. Instead
both commit through `.github/actions/commit-reports`, which rebases over
whatever landed meanwhile and resolves the one file two runs both write, the
index, by rebuilding it from the reports on disk with `index-metadata --rebuild`.
The `-latest` copies go to the run that finished later.

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

`.github/dependabot.yml` proposes updates to the pinned actions and to the
dashboard's dependencies, monthly. The one third-party action is pinned to a
commit, which is safe until it is stale; this is what says so.

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

- [docs/post-cruise-review.md](docs/post-cruise-review.md) — the whole
  post-cruise review, step by step, including how to raise a change upstream
  without a second commit.
- [docs/using-the-dashboard.md](docs/using-the-dashboard.md) — the reviewer's
  walkthrough: token, navigation, sign-offs, corrections, runs, and what to do when GitHub
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

`rawFileSN.csv` also records the attempt: `attemptedAt` and `filesTried`, so a
row holding `-99999` says which files were read to conclude there was nothing,
and a deployment never attempted is told apart from one attempted and empty.

`serialAliases.csv` pairs an asset with the serial its raw data reports where
that is a different number from the one the sensor bulk record carries. The
five-beam ADCPs are one asset with two Teledyne serials -- the record holds the
system's, the data holds the electronics' -- and the same asset reads the same
number season after season. A person writes the pair down once, with the
deployments it was read from, and the deployment check treats the raw serial as
confirming the asset from then on. An asset seen with a number only once is a
finding, not an alias.

## Serial numbers from the raw archive

    extract-serials --clones repos

reads the deployment sheets, finds every deployment whose instrument class writes
a serial number into its raw data and has none on record yet, and reads the
archive for it. The result is written back to `params/rawFileSN.csv`; `--all`
attempts every deployment, `--refdes` limits the run to named instruments, and
`--out` writes elsewhere. `.github/workflows/extract-serials.yaml` runs the same
command and proposes the file as a pull request on a fixed branch, so a second
run before the first merged updates the proposal rather than opening another.

The archive is public Apache directory indexes, and listing is what a run costs:
an instrument folder holds a month folder for every month since 2014. Only the
years a deployment spans are listed, which is a dozen index pages rather than
130, and only files dated within the deployment are read -- an earlier file
holds the previous deployment's instrument, and reading it is how the wrong
serial gets confirmed. A power-on banner is printed once, so the first few
files are read for one. Everything else is read from the **middle** of the
deployment: the sheet's times are approximate, a turnaround day's file opens
with the recovered instrument's records, and a deep profiler went on reporting
the recovered profiler's instruments 27 hours after the recorded start of the
next deployment. Twelve deployments read as a different asset from the sheet
before that rule, five of them in 2026.

Text instruments print the serial in a power-on banner (CTD, SPKIR, NUTNR,
FLORT, PREST, TMPSF) or on every data line (PARAD, and SPKIR and NUTNR again).
The two binary instruments carry it in every record in a fixed place: the ADCP
in bytes 55-58 of the PD0 fixed leader, read from the first ensemble whose
checksum is intact, and the OPTAA in the three bytes after the meter type of an
ac-s packet. Both are a few lines of `struct`; the notebooks shelled out to the
python2 instrument drivers for them, and where that environment was missing
every ADCP and OPTAA silently came back empty. The archive wraps every record
-- in port agent packets since 2018, in `<OOI-TS>` text tags before -- and the
wrapper is stripped before parsing, because an ensemble with a tag inside it
fails its checksum. The VADCPB fitted in 2024 is a Nortek Signature rather than
a Teledyne unit and writes text, with its serial on every `$PNORI` line. A
five-beam ADCP is archived as two folders, `MAIN` and `-5TH`; only the main unit
is read, because the fifth beam's serial belongs to no asset. Deep profiler serials are in the
`sernums_hi-res_` engineering files, which begin in 2020; earlier profiler
deployments cannot be confirmed this way.

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
      instruments.py    which classes write a serial, and how one is matched
      cli.py            the six entry points
    dashboard/          the Nuxt SPA
    params/             instrument list, coefficient map, constants, raw serials and aliases
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

Comparison is exact to the last digit a vendor file publishes, so the library
that reads the csv is part of what produced the numbers. Three files say so, and
they say different things on purpose:

| file | what it pins | why |
|---|---|---|
| `constraints.txt` | pandas and numpy, exactly | what a published run is produced with, so it is reproducible |
| `environment.yml` | the same two, plus the python | a reviewer's laptop reaching the runner's verdicts |
| `pyproject.toml` | a floor, `pandas>=2.1` | what the package can be installed against at all |

`.github/workflows/verify.yaml` installs against the constraints;
`.github/workflows/tests.yaml` deliberately does not. That matrix resolving
freely is the early warning, and it earned its keep: pandas 3.0 removed the
`applymap` this code called, and the python 3.11 entry failed while 3.10, which
resolves pandas 2, still passed. Installing against the constraints there would
have hidden it until a published run hit it. `tests/test_pins.py` fails if the
pip and conda pins drift apart.

The floor is 2.1 because that is where `DataFrame.map` arrived and 3.0 is where
`applymap` left, so below it no single spelling works on both.

Measured before pinning, against 116 real calibration files across 91
instrument directories: pandas 2.3.3 with numpy 1.22 and pandas 3.0.6 with numpy
2.5 parse every coefficient to the same bits. The only divergence in 1,556
parsed values is that `iterrows` turns a `None` into a `NaN` under pandas 3, and
`_unresolved` in `calibrations.py` already tests for both. So the pins are
reproducibility rather than a fix for drifting numbers.

`dashboard/.nvmrc` names the node the dashboard is built with. Every run records
the versions it ran with under `parameters`, and the dashboard's run stamp shows
them, so a number on screen can be traced to the library that read it.

    conda env create -f environment.yml && conda activate rca-metadata
    pip install -e ".[test]"

The dashboard tests cover the code that rewrites the HITL sheets, against the
team's real calibration sheet. A bug there corrupts years of sign-offs, and the
first version of it would have rewritten every line of the file on every commit.
