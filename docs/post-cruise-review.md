# The post-cruise metadata review, step by step

The whole review after a cruise, in order, from the deployment sheets landing to
the season's record being published. Each step says where it happens, what you
press, and what you should have when it is done. The other guides explain why
things work the way they do; this one is the checklist.

Read it once end to end before the first cruise you run it for. After that,
the [checklist at the bottom](#the-checklist) is enough.

This file is the source. A copy is published as a Claude page, which is easier
to read on a ship's laptop, and the dashboard's rail links to this one. Anything
written on the page has to be copied back here to survive, because the page is
regenerated from this file.

- [What you end up with](#what-you-end-up-with)
- [The sequence at a glance](#the-sequence-at-a-glance)
- [0. Once, before your first review](#0-once-before-your-first-review)
- [1. Bring your forks up to date](#1-bring-your-forks-up-to-date)
- [2. Make sure the season's inputs have landed](#2-make-sure-the-seasons-inputs-have-landed)
- [3. Read the serial numbers out of the raw archive](#3-read-the-serial-numbers-out-of-the-raw-archive)
- [4. Publish a production run](#4-publish-a-production-run)
- [5. Work the queue, check by check](#5-work-the-queue-check-by-check)
- [6. Propose your batches](#6-propose-your-batches)
- [7. Raise each pull request upstream — without a second commit](#7-raise-each-pull-request-upstream--without-a-second-commit)
- [8. Run again and confirm](#8-run-again-and-confirm)
- [9. Publish the deployment history](#9-publish-the-deployment-history)
- [10. Positions and season lists from the command line](#10-positions-and-season-lists-from-the-command-line)
- [11. Tidy the run picker](#11-tidy-the-run-picker)
- [If you already merged into your own master](#if-you-already-merged-into-your-own-master)
- [The checklist](#the-checklist)

## What you end up with

- Every deployment on this season's sheets either **confirmed** by the serial
  number in its raw data, or **signed off** by a person, or **corrected** on the
  sheet.
- Every new calibration file either **agreeing** with its vendor original, or
  signed off, or corrected.
- Every disagreement between the deployment sheets and the position spreadsheet
  either corrected or signed off.
- The **deployment history** in the `deployments` repository regenerated from
  the sheets as they now stand.
- One **published production run** that is the record of all of that, which
  next season's review will be compared against.

Nothing you do in the dashboard reaches a shared repository on its own. Every
change goes to **your own fork** as a pull request, and you raise it to the
shared repository yourself. Step 7 is how to do that without leaving your fork
in a state that blocks your next correction.

## The sequence at a glance

| step | where | you end with |
|---|---|---|
| 1 | GitHub, your three forks | forks identical to upstream |
| 2 | asset-management upstream | the season's sheets and calibration files merged |
| 3 | dashboard → **Workflows** → Run the extraction | `params/rawFileSN.csv` updated and merged |
| 4 | dashboard bar → **Production**, **Publish**, **Run all checks** | a new run the site opens on |
| 5 | dashboard, each check | every open row decided: cleared, flagged, or corrected |
| 6 | dashboard → **Queued changes** | one pull request per batch, on your forks |
| 7 | GitHub compare pages | the same changes as pull requests on the shared repositories |
| 8 | dashboard, another production run | the rows you decided have left the queue |
| 9 | dashboard → **Deployment history** | the history proposed to the deployments repository |
| 10 | command line | the season lists |
| 11 | dashboard → **Workflows** → Delete published runs | a run picker you can read |

## 0. Once, before your first review

Do these once. They are spelled out field by field in
[using-the-dashboard.md](using-the-dashboard.md#before-you-start).

1. Fork the three repositories to your own account: `wruef/metadataApp`,
   `oceanobservatories/asset-management`, `OOI-CabledArray/deployments`.
2. Create a fine-grained token scoped to those three forks, with **Contents**
   and **Pull requests** read and write, and **Actions** read and write on the
   `metadataApp` fork.
3. In the dashboard's **Settings**, paste the token and enter your initials.
4. On `wruef/metadataApp`, once: **Settings → Actions → General → Allow GitHub
   Actions to create and approve pull requests**. Step 3 needs it.

## 1. Bring your forks up to date

The dashboard refuses to write to a fork that is not exactly upstream. Not
behind it, not ahead of it. So the review starts by making all three identical.

1. Open each fork on GitHub: your `asset-management`, your `deployments`, your
   `metadataApp`.
2. Above the file list, GitHub says whether the branch is *behind*, *ahead*, or
   *up to date* with upstream.
3. **Behind** → press **Sync fork** → **Update branch**. Done.
4. **Up to date** → nothing to do.
5. **Ahead** → **stop.** Do not press Sync fork; on a fork that is ahead it
   offers to *discard* your commits. Read
   [If you already merged into your own master](#if-you-already-merged-into-your-own-master)
   first.

You should have: three forks all reading *up to date with upstream*.

## 2. Make sure the season's inputs have landed

The review verifies what is in `oceanobservatories/asset-management` at
`master`. It cannot verify sheets that are not there yet.

1. Confirm the cruise's deployment rows are in `deployment/<array>_Deploy.csv`
   upstream, for every array the cruise touched.
2. Confirm the season's new calibration files are in `calibration/<instrument>/`
   upstream, and the vendor originals in `OOI-CabledArray/calibrationFiles`.
3. If either is still in a branch, that is the pre-cruise check, not this one:
   see [Checking a branch before it merges](using-the-dashboard.md#checking-a-branch-before-it-merges).
4. Pre-deploy photographs are a separate, hand-curated input,
   `params/imageSN.csv`. Add the season's rows if you have them. A photograph
   never confirms a deployment on its own, so the review works without them.
5. If step 1 changed anything, sync your `asset-management` fork again.

You should have: upstream `master` holding the season, and your fork matching it.

## 3. Read the serial numbers out of the raw archive

Most deployments are confirmed by the serial number the instrument wrote into
its own raw data. This step reads those out for every deployment that has none
on record yet.

1. Open **Workflows** in the dashboard rail and press **Run the extraction**.
   Leave both boxes as they are; the page says how many deployments in this run
   one would settle. (The same job is in the Actions tab as **Extract serial
   numbers**, if you would rather start it there.)
2. Wait. An incremental run is a few minutes; the log lists each instrument and
   what it found.
3. When it finishes, a pull request named **Serial numbers from the raw
   archive** appears on `wruef/metadataApp`. Open it.
4. Read the diff of `params/rawFileSN.csv`. New rows are this season's
   deployments. A row ending `-99999` was attempted and found nothing; its
   `filesTried` column says which files were read.
5. Look at the `serialAliases.csv` question if a five-beam ADCP is new this
   season: a raw serial that consistently disagrees with the record on the same
   asset, season after season, is an alias for a person to write down there. A
   number seen once is a finding, not an alias.
6. Merge the pull request into `main`.

Run it a second time later in the review if a deployment still reads
*deployments an extraction would settle* on the overview; the workflow only
attempts rows without a serial, so a second run is cheap.

You should have: `params/rawFileSN.csv` on `main` carrying a row for every
deployment the archive could settle.

## 4. Publish a production run

1. In the dashboard, the bar across the top: **Production**.
2. Tick **Publish**.
3. Press **Run all checks**. The tray follows the run; closing it does not stop
   the run.
4. Wait for the run to finish, then a couple of minutes more for the site to
   rebuild. Nothing on screen changes on its own.
5. Reload. The run stamp at the top now shows the new run's time, and the
   **Run** dropdown lists it.

If you run from the Actions tab instead, dispatch **Verify metadata** from
`main`. A run dispatched from any other branch keeps its report as an artifact
and does not publish, and it says so in a warning.

You should have: the dashboard opening on this season's run.

## 5. Work the queue, check by check

The home page opens on **what needs verification**: each situation with its count,
and a link that opens the check filtered to exactly those rows. Work them in
the order the rail lists the checks. Every row you open shows a sentence saying
why it is open, the values that disagree, the check's raw output, and links to
the files at the commit the run read.

For every open row there are three possible decisions:

- **Correct the file**, when the record is wrong and you know what it should
  say. The correction is queued, not sent.
- **Clear**, when the record is right and the finding is explained. Write down
  what convinced you; the dropdown offers what the team has written before.
- **Flag**, when it needs someone who knows the instrument.

### Calibrations

1. Open **Calibrations**. It opens on *Needs verification*.
2. For a `MISMATCH`, press **View files side by side**. The coefficients that
   disagree are marked in both files.
3. If the repository file is wrong: type the vendor's value in **Correct to**,
   or click the vendor's number to take it, add a note for the file if the
   reason is worth recording, then **Add to batch**.
4. If the repository file is right on purpose (a pressure offset added
   deliberately, a value read from a different vendor sheet): **Clear**, with
   the reason. Where the file's own `notes` column already says why, that note
   is the first thing the dropdown offers.
5. A `PDF_NOTCOMPARED` is a scanned certificate. The side-by-side view shows
   the certificate itself beside the file's values. Read across, then clear or
   flag.
6. `NO_VENDOR_FILE` means the vendor original is not in `calibrationFiles`.
   That is a file to add there, not a dashboard decision; flag it with a note.

### Deployments

1. Open **Deployments**.
2. A `MISMATCH` on the raw file names the asset the serial actually belongs to.
   Under the row, **The instrument on the sheet** shows that asset beside the
   one on the sheet. If the sheet is wrong, click the asset to take it, then
   **Add to batch**. If the sheet is right and the raw data is not (a serial
   from a swapped cable, an instrument that was changed mid-deployment), clear
   or flag with the reason.
3. `RAW_SN_POSSIBLE` rows are the ones step 3 could not settle. Read
   `filesTried` in `params/rawFileSN.csv` if you want to know why. Confirm
   them by other evidence and **Clear**, or leave them for the next extraction
   run.
4. A calibration verdict of `none` or `NO_VALID_FILE` means the instrument has
   no calibration covering the deployment. That is a file to add to
   asset-management; flag it.
5. A photograph that disagrees is amber, not red. It is a prompt to go and
   look, not a verdict; it does not hold the row open.

### Positions

1. Open **Positions**.
2. For a `MISMATCH`, the table shows the sheet's value beside the spreadsheet's.
   The RCA position spreadsheet is the authority, so **Take every spreadsheet
   value** is usually the whole answer. Then **Add to batch**.
3. A row whose reference designator has no instrument code is a **node**. Its
   position lives in `NODE_deployments.csv` in the deployments repository rather
   than on an array's sheet, so it corrects exactly the same way and joins a
   group of its own, on your `deployments` fork. That fork has to be in sync for
   it, the way your `asset-management` fork does for the others.
4. `NEEDS_HITL` means more than one spreadsheet row could be this deployment.
   Pin the right one in `params/HITLpositionList.csv` and run again.

### Sensor bulk

1. Open **Sensor bulk**.
2. A `MISMATCH` is two records naming different serials for one asset. Decide
   which record is right. If the RCA list is right, this is a correction to
   OOI's bulk record and is raised with them; **Flag** it with a note saying
   so. If the bulk record is right, fix `params/RCA-InstrumentList.csv` and
   **Clear**.
3. `MISSING_FROM_SENSOR_BULK` is an asset OOI has never heard of. Same route.

### Duplicate asset deployments

1. Open **Duplicate asset deployments**. It is usually empty.
2. The same asset in two places at once is a sheet error: correct the wrong
   row's asset from the Deployments check, or flag it.

You should have: every row on the overview either decided or deliberately left
for a named reason.

## 6. Propose your batches

Everything you decided is waiting under **Queued changes** in the rail, grouped
by the repository it writes to and by what kind of change it is:

| group | goes to | carries |
|---|---|---|
| Sign-offs | your `metadataApp` fork | all three 2i-HITL sheets |
| Calibration coefficients | your `asset-management` fork | every calibration file you corrected |
| Deployment sheets | your `asset-management` fork | every deployment you repositioned or reassigned |

1. Open **Queued changes**. Read the list: every record you queued, with what
   it would change.
2. Press **Open pull request** under each group, or **Open all** to send every
   group one after another.
3. Each group becomes **one pull request on your own fork**, on a branch named
   for what it is and when: `hitl-<stamp>Z`, `calibration-<stamp>Z`,
   `deployment-<stamp>Z`. The link appears under the group.
4. If a group is refused, nothing in it was sent. The message names the record
   that no longer reads what the run read: the file moved since the run on
   screen. Sync the fork, publish a new run, and queue from that.

You should have: up to three pull requests, each on one of your forks, none of
them merged.

## 7. Raise each pull request upstream — without a second commit

This is the step that is easy to get wrong, and getting it wrong costs you the
rest of the review. Read the whole section before doing it.

### Why there is a trap

The dashboard opens its pull request **on your fork**, from a branch to your
fork's `master`. That request is for you to read. It is not the route to the
shared repository, and **merging it is the mistake**:

1. Merging it adds a **merge commit** to your fork's `master`. One change is
   now two commits.
2. Your fork's `master` is now **ahead of upstream**. The dashboard refuses to
   write to a fork that is ahead, so you cannot correct anything else until
   upstream has taken your change and your fork is identical again.
3. Pressing **Sync fork** on a fork that is ahead offers to **discard** the
   commits it is ahead by. That is your correction.
4. Raising a pull request from your `master` to upstream then carries both
   commits, and anything else that has landed on your `master` since.

So: the change travels **on the branch the dashboard wrote it on**, straight
from your fork to the shared repository, and your `master` is never touched.

### Step by step

Do this for each of the pull requests step 6 opened. The example is a
calibration batch; the deployment-sheet and sign-off batches are the same with
their own branch and repository.

1. Open the pull request on your fork. Note its **branch name** in the
   header: something like `calibration-20260918T153944Z`.
2. Read the diff. It should show one changed value per correction and nothing
   else. If the whole file has been rewritten, do not go on; something is
   wrong.
3. **Do not press Merge.** Leave this pull request open for now.
4. Open the shared repository's compare page, base first, your branch second.
   Replace `YOU` with your GitHub login:

       https://github.com/oceanobservatories/asset-management/compare/master...YOU:asset-management:calibration-20260918T153944Z?expand=1

   For the other two repositories:

       https://github.com/OOI-CabledArray/deployments/compare/main...YOU:deployments:history-20260918T153944Z?expand=1
       https://github.com/wruef/metadataApp/compare/main...YOU:metadataApp:hitl-20260918T153944Z?expand=1

   Or by hand: on the shared repository press **Pull requests → New pull
   request → compare across forks**, set *base repository* to the shared one
   and *base* to its default branch, set *head repository* to your fork and
   *compare* to your branch.
5. Check the page shows **exactly the same diff** as step 2, and **1 commit**.
   If it shows more than one commit, your branch was cut from a `master` that
   was ahead; go to [the recovery section](#if-you-already-merged-into-your-own-master).
6. Press **Create pull request**. The dashboard's title and body come with the
   branch, so the request already says what it changes and why. Add a line if
   there is anything the reviewer upstream should know.
7. Wait for the shared repository to merge it. That is their decision and
   their timetable.
8. **After** it merges upstream: your fork's `master` is now *behind* by that
   change. Open your fork and press **Sync fork → Update branch**. Your fork
   is identical to upstream again, and holds the change.
9. Now close the pull request on your fork from step 3 without merging, and
   delete its branch. The change is upstream; the copy has done its job.

You should have: your change upstream as one commit, your fork identical to
upstream, and no pull request left open on your fork.

### If you own the shared repository

`wruef/metadataApp` is the shared repository for the sign-off sheets. If you
are its owner you have no fork of it: the dashboard's sign-off pull request is
already on the shared repository, and you merge it there directly. Steps 4 to
9 do not apply to that one batch. The other two repositories are not yours,
and the steps above apply in full.

*Note: the plan is to move this repository to the OOI-CabledArray shared org as
the last step of this build. Once that happens, `wruef/metadataApp` becomes a
fork rather than the shared repository, and steps 4–9 (the fork workflow) will
apply to it too, same as the other two repositories. Update this section once
the move is done.*

### Doing several batches

Each batch is its own branch cut from your `master` at the moment you opened
it. Because you never merge into your `master`, every branch is cut from a
`master` identical to upstream, and every pull request upstream shows exactly
one commit. You can have the calibration batch and the deployment-sheet batch
open upstream at the same time; they touch different files.

## 8. Run again and confirm

Sign-offs and corrections are inputs to a run. The report on screen was
produced before you made them, so nothing on it moves until a new run reads
them.

1. When the sign-off pull request has merged into `wruef/metadataApp`, and the
   asset-management corrections have merged upstream, sync your forks (step 1).
2. Publish another production run (step 4).
3. Reload. On the overview, the situations you decided have gone or shrunk.
   A row you cleared reads **Cleared in review** with the finding still shown
   beside it. A file you corrected reads **Agreed**.
4. Anything still open is either waiting on a merge or a decision you left for
   a named reason. Both are fine. Write down which.
5. Open **Changes** if you gave the run a baseline. It lists what moved between
   the two runs, and whether the two can be trusted against each other.

You should have: a published run whose open rows you can account for.

## 9. Publish the deployment history

The history is a product, not a finding: one file per instrument type saying
what was where and when, with the calibration in force. The run builds it; you
propose it.

1. Open **Deployment history** in the rail. It shows the history the run on
   screen built, the deployments and instrument types it covers, and every file
   it would commit.
2. Press **Propose this history**. One pull request opens on your `deployments`
   fork carrying every file, on a branch `history-<stamp>Z`.
3. Read its diff before going on. A history that has not been rebuilt in a
   while moves rows for three known reasons, listed in
   [using-the-dashboard.md](using-the-dashboard.md#publishing-the-deployment-history).
   Anything you cannot place there is worth asking about first.
4. Raise it to `OOI-CabledArray/deployments` exactly as in step 7. Do not merge
   it into your fork's `main`.
5. After it merges upstream, sync your `deployments` fork.

You should have: the deployments repository describing the sheets as they now
stand.

## 10. Positions and season lists from the command line

Two products the dashboard does not write. Both need the package installed and
clones of the repositories on disk; the README's *Running a verification*
section covers that.

**Every position at once.** The dashboard corrects a position a row at a time,
instruments and nodes alike, which is what step 5 covers. This corrects every
position the spreadsheet disagrees with in one pass, across both repositories,
which is worth it after a cruise has moved a great many:

    publish-metadata positions --fork YOU/asset-management --node-fork YOU/deployments

It writes the corrected sheets to `out/`, then opens one pull request on each
fork named. Raise each upstream as in step 7.

**Season lists.** The deployed, recovered and current instrument lists for the
year, written to `out/` for whoever needs them:

    publish-metadata seasons --year 2026

## 11. Tidy the run picker

Every published run stays in the **Run** dropdown until somebody removes it,
and a review leaves several behind. Keep the ones worth comparing against.

1. Open **Workflows** in the rail. Under **Delete published runs**, set how
   many of the newest to keep; the page says how many that would delete.
2. Press **Show what would go** and read the run summary. It lists exactly what
   would be deleted and changes nothing.
3. Untick the dry run and press it again. The site rebuilds without them.

Deleting specific runs by name is the Actions tab's **Delete published runs**,
which takes a `remove` list.

The run the dashboard opens on is never deleted, and a deleted run is still in
the repository's history if it turns out to have been needed.

## If you already merged into your own master

Your fork reads *ahead of upstream*, and the dashboard refuses to write to it.
Do not press Sync fork yet. The fix depends on whether upstream already has the
change.

**Upstream does not have it yet.**

1. On your fork, find the branch the dashboard wrote: it is still there, under
   **Branches**, named `calibration-…`, `deployment-…` or `hitl-…`.
2. Raise **that branch** upstream by step 7. The compare page will show one
   commit, because the branch itself never gained a merge commit; only your
   `master` did.
3. Wait for upstream to merge it.
4. Now your `master` is ahead only by a merge commit whose content upstream
   already holds. Press **Sync fork**. It will say it has to discard commits;
   that is now true and harmless, because the change is upstream. Confirm.
5. Your fork reads *up to date*. Delete the branch.

**Upstream already has it** (you raised it from `master` and it was merged).

1. Your `master` is ahead by commits whose content upstream now holds.
2. Press **Sync fork** and confirm the discard. Nothing is lost that upstream
   does not have.
3. Your fork reads *up to date*.

**If you are not sure** whether upstream has the change, open the file on
`oceanobservatories/asset-management` at `master` and look at the value. If the
corrected value is there, upstream has it.

## The checklist

Copy this into wherever you keep the season's notes and tick it off.

    Before
    [ ] Three forks read "up to date with upstream"
    [ ] The cruise's deployment sheets and calibration files are merged upstream
    [ ] params/imageSN.csv has the season's photographs, if any

    Inputs
    [ ] Extract serial numbers run; its pull request read and merged

    Run
    [ ] Production run published; the site opens on it

    Review
    [ ] Calibrations: every open row corrected, cleared or flagged
    [ ] Deployments: every open row corrected, cleared, flagged, or left for extraction
    [ ] Positions: every mismatch corrected or cleared, nodes included
    [ ] Sensor bulk: every mismatch decided
    [ ] Duplicate asset deployments: empty, or decided

    Propose
    [ ] Queued changes: every batch opened as a pull request on my fork
    [ ] Each one raised upstream FROM ITS BRANCH via the compare page
    [ ] Nothing merged into my own master
    [ ] After upstream merged: Sync fork, close the fork copy, delete the branch

    Confirm
    [ ] Forks synced, second production run published
    [ ] Every row still open is accounted for in the notes

    Products
    [ ] Deployment history proposed and raised upstream
    [ ] Season lists produced from the command line

    After
    [ ] Old runs deleted from the picker

For the pre-cruise check of a branch before it merges, the sequence is the
same from step 4 with the bar set to **Testing** and a baseline chosen; see
[Checking a branch before it merges](using-the-dashboard.md#checking-a-branch-before-it-merges).
