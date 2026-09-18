# Using the dashboard

A walkthrough for anyone reviewing RCA metadata: signing in, working the queue,
recording a decision, and starting a run. No programming required for any of it.

The dashboard is at **https://wruef.github.io/metadataApp/**. It is a web page
with no server behind it. Everything it shows comes from one file that a
verification run produced, and everything you write goes back to GitHub as a
pull request under your own name.

- [Before you start](#before-you-start)
- [Signing in](#signing-in)
- [Finding your way around](#finding-your-way-around)
- [Working the queue](#working-the-queue)
- [Clearing and flagging a row](#clearing-and-flagging-a-row)
- [Submitting your decisions](#submitting-your-decisions)
- [Correcting a file in asset-management](#correcting-a-file-in-asset-management)
- [Publishing the deployment history](#publishing-the-deployment-history)
- [Reading an earlier run](#reading-an-earlier-run)
- [Starting a run](#starting-a-run)
- [Checking a branch before it merges](#checking-a-branch-before-it-merges)
- [What the review statuses mean](#what-the-review-statuses-mean)
- [When something goes wrong](#when-something-goes-wrong)
- [The other guides](#the-other-guides)

## Before you start

You can read the whole dashboard without signing in. You need a GitHub account
and a token only to record decisions or to start a run.

If you are going to do either, fork three repositories to your own GitHub
account first. Open each one and press **Fork**:

- `OOI-CabledArray/metadataApp` — this repository, which holds the sign-off
  sheets and the workflows
- `oceanobservatories/asset-management`
- `OOI-CabledArray/deployments`

Your work goes to your own forks. Nothing the dashboard does can write to a
shared repository.

## Signing in

### 1. Create a token

Go to **https://github.com/settings/personal-access-tokens/new**. This is a
*fine-grained* token, not a classic one.

Fill it in like this:

| field | what to put |
|---|---|
| Token name | anything you will recognise, such as `rca-metadata-dashboard` |
| Expiration | your choice; you will need a new one when it lapses |
| Repository access | **Only select repositories**, then choose your three forks |

Then open **Permissions → Repository permissions** and set:

| permission | level | why |
|---|---|---|
| Contents | Read and write | to write your decisions into the sheets, corrections into calibration files, and the deployment history |
| Pull requests | Read and write | to open the pull request carrying them |
| Actions | Read and write | to start a verification run from the dashboard |

**Actions is only needed on your `metadataApp` fork.** Nothing else needs it.

You do not need organisation access, and you do not need any permission on any
upstream repository. Press **Generate token** and copy it. GitHub shows it once.

### 2. Enter it

In the dashboard, open **Settings** at the bottom of the left-hand rail. Paste
the token and press sign in. The page checks it with GitHub and shows your
avatar when it works.

The token stays in your own browser. It is sent to `api.github.com` and nowhere
else, and it is re-checked rather than trusted when you come back.

### 3. Set your initials

On the same page, enter your initials — `WR`, `KB`. The sign-off sheets have
identified reviewers by initials since 2019, not by GitHub login, so a decision
cannot be recorded without them.

## Finding your way around

The rail on the left has three groups.

**The checks**, in the order they are worth working. Each carries the number of
rows waiting for a person, and a red dot when any of them is a problem.

| check | the question it answers |
|---|---|
| Calibrations | does each repository calibration file match the vendor original? |
| Deployments | is the instrument on the sheet the one that was in the water? |
| Positions | do the deployment sheets agree with the RCA position spreadsheet? |
| Sensor bulk | do serial numbers agree between the RCA list and OOI's record? |
| Duplicate asset deployments | is one asset deployed in two places at once? |

**This run**: the Changes view, which compares two runs; the reference
designators the run covered; the vendor calibrations that have no repository
file; the deployment history the run built; and your queue of sign-offs waiting
to be submitted.

**Settings**, at the foot, showing who you are signed in as.

The home page opens on **what needs a person** — not a count of problems, but
the situations behind them, each with a count and a link that opens the check
already filtered to exactly those rows. Below it, deployments by the year they
went in the water.

Every page carries a **run stamp**: when the run happened, which commit of each
repository it read, and which version of the parameter files. Nothing refreshes
on its own, so this is the first thing to read. A report older than a season is
marked stale.

## Working the queue

Open a check. It opens on **Needs attention** rather than on everything, so a
check with 1,558 agreeing rows does not bury the 105 that do not.

- **The segmented control** at the top switches between attention, each review
  status, and everything. Each carries its own count.
- **The dropdowns** beside it narrow by instrument, site, year, verdict or
  sign-off, depending on the check. Their options come from the rows in front of
  you, and each option's count is measured against the other filters, so
  narrowing one does not leave the other numbers stale.
- **Every column header sorts.** Click once for ascending, again for descending,
  a third time to go back to queue order. Review status sorts by consequence
  rather than alphabetically.
- **The search box** matches any column shown.

A filtered table is a URL. Sending a colleague
`/checks/calibrations?instrument=NUTNRA&vendorMatch=MISMATCH` sends them the
view rather than instructions for reproducing it.

**Click a row to open it.** You get a sentence saying why the row reads as it
does, the coefficients or fields that actually differ, any note the
asset-management file keeps about them, the raw output of every check on the
row, and links to each source file at the commit the run read.

On a calibration that disagrees, **View files side by side** puts the repository
CSV and the vendor original next to each other, with the differing coefficients
marked on both and each pane scrolled to the first one. A vendor calibration
that exists only as a scan is shown as the certificate itself, to read across.

## Clearing and flagging a row

Three checks can be signed off: calibrations, deployments and sensor bulk.

1. Open the row.
2. Press **Clear** if you are satisfied, or **Flag** if it needs someone who
   knows the instrument.
3. Choose a reason from the dropdown, or type your own underneath.

The dropdown offers two groups. **From the asset-management file** is whatever
the file itself says about the coefficients in question — on a row that
disagrees, that is usually the answer. **Written before in 2i-HITL** is every
note the team has already used, most-used first, so a sign-off reuses the
wording everyone else uses.

A decision is queued, not sent. Change your mind and press the button again, or
undo it.

**What a sign-off means.** The row moves to *Cleared in review* and is no longer
work waiting on anyone. It does **not** erase what the check found: the finding
keeps its own badge beside the cleared one, and the coefficients that disagree
are still there. Three signed-off calibrations turned out to hold real
transcription errors, which is exactly why the finding stays visible.

## Submitting your decisions

Open **Sign-offs** in the rail to see everything queued. Press submit.

That opens **one** pull request on **your own fork**, carrying the whole batch.
Review the diff — it should show one changed line per decision, not a rewritten
file — and merge it.

Then raise the onward pull request from your fork to the shared repository
yourself. A person decides when a batch is worth proposing to everyone else.

**Merging does not update the dashboard.** The sign-offs are inputs to a
verification run, and the report on screen was produced before you made them.
Start a production run when the merged decisions are worth folding in; cleared
rows leave the queue on the next run, not before.

## Correcting a file in asset-management

A sign-off records a judgement about a file. This changes the file itself, and
every data product computed from it changes too. It is therefore a separate
thing, with separate rules, and it works the same way on two checks.

| check | the button | what it changes |
|---|---|---|
| Calibrations | **Correct this file** | the coefficients in `calibration/<instrument>/<file>.csv` |
| Positions | **Correct the deployment sheet** | one deployment's row in `deployment/<array>_Deploy.csv` |

Both sit below the sign-off buttons in the expanded row. Both give you one line
per thing that disagrees, with what the file says, what it should say, and a box
to type a value in. Clicking the value on the right takes it. A box left blank
is left alone.

### Rules both of them follow

**Your fork has to be exactly `oceanobservatories/asset-management`.** Not
behind it, not ahead of it. The dashboard checks before the editor opens and
again before it writes, and refuses rather than warns.

| your fork | why it is refused |
|---|---|
| behind upstream | your pull request would revert whatever landed upstream meanwhile |
| ahead of upstream | the onward pull request would carry your other commits along with the correction |

Press **Sync fork** on your fork's GitHub page, then start a run and correct the
file from that run. A correction has to start from the file the finding came
from. For the same reason it refuses if the value no longer reads what the run
read, which means upstream moved and the report on screen is out of date.

**One pull request per record, on your fork only.** One calibration file, or one
deployment. Neither is batched with your sign-offs, and neither is batched with
the other. Raise the onward pull request to
`oceanobservatories/asset-management` by hand, and nothing anyone computes
changes until that one is reviewed and merged.

### Correcting a calibration

Each coefficient also takes a note, which is written into the file's own `notes`
column — the same column the row detail reads back to you. The number is written
in the notation the line already uses, so the diff is a changed digit rather
than a reformatted file.

An array coefficient cannot be corrected here. An OPTAA's `CC_acwo` is
eighty-three numbers in one field, and a single text box would be guessing.
Those are edited on GitHub.

### Correcting a position

The RCA position spreadsheet is the authority on where anything was put, so
**Take every spreadsheet value** is usually the whole answer. The four fields a
position governs are latitude, longitude, water depth and deployment depth.

A deployment sheet holds every deployment on its array, around two hundred rows,
so what identifies the row is the reference designator *and* the deployment
number. An instrument deployed twice in one season has two rows, and only the
one you opened is touched.

If the row's notes say the parameters are preliminary, correcting the position
clears that note as well. Once the position comes from the spreadsheet it is no
longer provisional, and a sheet that kept the claim would contradict itself.
The pull request says when it did this.

## Publishing the deployment history

Everything else in the dashboard answers "what is wrong". This answers "what was
where, and when", and its output is a product rather than a queue: one CSV per
instrument type, each row a deployment with the calibration that was in force
for it. It is what `OOI-CabledArray/deployments` holds.

Open **Deployment history** in the rail. Every run builds it, so what you see
was built by the run you are reading, and choosing a different run in the picker
shows that run's version. The page says how many deployments and instrument
types it covers, and lists every file it would commit. Click a file to see its
first few lines.

**Propose this history** opens one pull request on your own fork of the
deployments repository, carrying all the files at once. The history describes one
state of the deployment sheets, so half of it from one run and half from another
would describe no state at all.

Anything the repository holds that the history does not name is left alone. The
node deployments are the case that matters: they come from a different source and
are not rebuilt here.

The fork rule is the same as for a correction. Your `deployments` fork has to be
exactly `OOI-CabledArray/deployments`, and the page refuses rather than warns.
Press **Sync fork** on GitHub and check again.

You are not expected to do this often. Between cruises nothing changes, and a
pull request with no changes in it is not created at all — the page says your
fork already matches.

## Reading an earlier run

The **Run** dropdown in the stamp lists every published run, newest first. A run
that was not against production is labelled with the fork or branch it read, so
a colleague's branch check is not mistaken for what is merged.

Choosing one reloads the whole dashboard against it, including its comparison in
the Changes view.

## Starting a run

The bar across the top of every page says what a run *would* verify. It is a
control for starting runs, **not** a switch for what is on screen. Changing it
moves no number on the page.

**Production** is what has been merged: `oceanobservatories/asset-management` at
`master`. That is what you want after a cruise, or after merging sign-offs.

**Testing** takes a repository and a ref of your own. The bar turns amber the
moment it points anywhere other than production.

Tick **Publish** (or **Publish for review** on a testing run) if you want the
result kept. Then press **Run all checks**.

The run is followed in a tray, step by step. Closing the tray stops following
it; it does not stop the run. A run takes a few minutes.

**What publishing does depends on what you ran.** A production run becomes the
report the site opens on. A testing run is committed under its own name and
appears in the run dropdown, and the production figures do not move. Either way
the site rebuilds itself a couple of minutes later; choose the run in the
dropdown to read it.

If you start a run from the Actions tab rather than the dashboard you will see a
third box, `replace_production`. Leave it off. It applies only to a run that is
*not* production, where it promotes that run to the report everyone opens on —
useful when a branch result should stand in before the branch is merged, and
wrong every other time. A production run becomes that report anyway.

Serial extraction is deliberately not here. It cannot finish without a person in
the middle, so a button implying otherwise would be a lie.

## Checking a branch before it merges

This is what the testing mode exists for.

1. Push your pending asset-management changes to a branch on your fork.
2. Set the bar to **Testing**, and enter `yourname/asset-management` and the
   branch name.
3. Set **Compare with** to production `master`.
4. Tick **Publish for review** and run.
5. When it finishes, pick the run from the Run dropdown.
6. Open **Changes**. Newly failing rows are what the branch broke; newly passing
   rows are what it fixed.
7. Merge, or send it back — with the specific rows as the reason.

A comparison states whether it can be trusted and refuses itself when it cannot:
when the two runs used different versions of the checks, when either cannot name
the commit it read, or when either ran from a modified working tree.

## What the review statuses mean

| status | meaning |
|---|---|
| **Problem** | something disagrees and nobody has looked at it |
| **Needs a person** | something needs a judgement rather than a fix |
| **Not checked** | nothing settled this, and something could have |
| **Cleared in review** | a reviewer has been; the finding is still shown beside it |
| **Agreed** | the records agree |
| **Excluded** | there was nothing to check, and nothing was missed |

Every verdict each check can return, and which status it carries, is in
[what-each-check-decides.md](what-each-check-decides.md).

*Excluded* is counted in no other number. An instrument that asset-management
holds no calibration for cannot have one compared, so it is not a gap.

Two things are noted without holding a row open: a calibration more than fifteen
months older than its deployment, and a pre-deploy photograph showing a
different asset. Both colour their cell amber and are said in the row's
sentence. A photograph does not confirm a deployment, so it does not condemn one
either.

## When something goes wrong

**It says my fork is not in sync.** It is refusing on purpose. Open your
`asset-management` fork on GitHub, press **Sync fork**, and if it says your
branch is ahead as well, delete the extra commits or re-fork. Then run the
checks again and correct the file from that run.

**GitHub refused the sign-off.** Your token is missing a permission. The reads
before the write all succeed, so a failure at the first write means **Contents**
is read-only. Edit the token, set Contents to read and write, then sign out and
back in on the Settings page.

**GitHub refused to start a run.** The same, for **Actions**, on your
`metadataApp` fork.

**The dashboard says there is no report.** No run has published yet, or the last
one did not finish. Check the Actions tab of your fork.

**The numbers did not change after my run.** Three possibilities. The bar is not
a view switcher, so changing it never moves a number. A testing run does not
replace the production figures, so pick it from the Run dropdown. And a run with
publish unticked keeps its report as a build artifact only.

**A row I signed off is still in the queue.** Sign-offs are read at the start of
a run. Merge the pull request, then run again.

## The other guides

| guide | what it covers |
|---|---|
| [What each check decides](what-each-check-decides.md) | every verdict a check can return, what it means, and whether it passes |
| [Calibration comparison](calibration-comparison.md) | which vendor format each instrument is compared against, and why |
| [The report contract](report-contract.md) | the shape of the file a run produces, for anyone reading it directly |
| [README](../README.md) | running the checks yourself, and how the pieces fit together |
