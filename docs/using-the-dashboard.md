# Using the dashboard

A walkthrough for anyone reviewing RCA metadata: signing in, working the queue,
recording a decision, and starting a run. No programming required for any of it.
For the whole post-cruise review in order, step by step, read
[post-cruise-review.md](post-cruise-review.md) and come back here for the
detail of any one step.

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

- `wruef/metadataApp` — this repository, which holds the sign-off sheets and
  the workflows
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
| Contents | Read and write | to write your decisions into the sheets, corrections into calibration files and deployment sheets, and the deployment history |
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
| Duplicate asset deployments | is one asset in the water twice at once, one node in two places, or a deployment never closed out? Correctable inline. |

**This run**: the Changes view, which compares two runs; the reference
designators the run covered; the vendor calibrations that have no repository
file; the sign-offs that match no row; the deployment history the run built; and
your queue of changes waiting to be proposed.

*Sign-offs with nothing to sign* appears only when there are some. A sign-off is
written against a key — a calibration file name, a reference designator with its
year and deployment number, an asset ID — and when the thing behind that key
stops existing, the line stays in the sheet and matches nothing. It is a list to
fix rather than a queue to work: open a row and it names the sheet to correct
the key in or delete the line from.

**Settings**, at the foot, showing who you are signed in as.

The home page opens on **what needs verification** — not one number, but the
situations behind it, each with a count and a link that opens the check already
filtered to exactly those rows. Below it, deployments by the year they
went in the water.

Every page carries a **run stamp**: when the run happened, which commit of each
repository it read, which version of the parameter files, and which python and
pandas read the numbers. Nothing refreshes
on its own, so this is the first thing to read. A report older than a season is
marked stale.

## Working the queue

Open a check. It opens on **Needs verification** rather than on everything, so
a check with 1,558 agreeing rows does not bury the 105 that do not.

- **The segmented control** at the top switches between each review status and
  everything. Each carries its own count.
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

Open **Queued changes** in the rail to see everything waiting. Sign-offs and
corrections both gather there, in groups.

Each group is **one pull request** on **one of your own forks**. The groups are:

| group | fork | what it carries |
|---|---|---|
| Sign-offs | your `metadataApp` | all three 2i-HITL sheets |
| Calibration coefficients | your `asset-management` | every calibration file you corrected |
| Deployment sheets | your `asset-management` | every deployment you repositioned or reassigned |
| Node positions | your `deployments` | every node you repositioned |

Coefficients and deployment sheets go to the same fork and still travel
separately. Somebody approving a page of numbers has not agreed to move an
instrument on the seabed, so the two are never in the same request. Positions
and asset IDs *do* share a request, because they share a file: two requests
editing one array's sheet would conflict the moment the first was merged.

Press **Open pull request** under a group to send that one, or **Open all** to
send every group. Opening all does them one after another rather than at once:
two branches cut from the same base at the same time is how the second one lands
empty.

Review each diff — it should show one changed line per decision, not a rewritten
file — and merge it. Then raise the onward pull request from your fork to the
shared repository yourself. A person decides when a batch is worth proposing to
everyone else.

**If a group is refused, nothing in it was sent.** A record that no longer reads
what the run read means the files have moved since the report on screen, so the
whole group is held rather than written in part. The message names the records
that failed. Start a run against the files as they are now and work from that.

**Merging does not update the dashboard.** The sign-offs are inputs to a
verification run, and the report on screen was produced before you made them.
Start a production run when the merged decisions are worth folding in; cleared
rows leave the queue on the next run, not before.

## Correcting a file in asset-management

A sign-off records a judgement about a file. This changes the file itself, and
every data product computed from it changes too. It is therefore a separate
thing, with separate rules, and it works the same way on three checks.

| check | the button | what it changes |
|---|---|---|
| Calibrations | **Add to batch** | the coefficients in `calibration/<instrument>/<file>.csv` |
| Positions | **Add to batch** | the position on one deployment's row in `deployment/<array>_Deploy.csv`, or in `NODE_deployments.csv` for a node |
| Deployments | **Add to batch** | `sensor.uid` on that row — which instrument the sheet says was deployed |

Adding does not open anything. The correction joins the batch for its kind and
waits under **Queued changes** with the rest. Correct as many files as a sitting
is worth, then send them together.

You correct it on the line. The table of what disagrees gains two columns when
you are signed in and your fork is in sync: **Correct to**, and for a
calibration **Note for the file**. Each line already shows what the file says
and what it should say, so the number you are copying and the box you type it
into are side by side.

- **Click the value on the right to take it.** That is the vendor's coefficient,
  or the spreadsheet's position, and on most rows it is the whole answer.
- **Or type your own** in the box.
- **A box left blank is left alone.** Only lines you changed are proposed.
- **Take every vendor value** fills the column in one go.
- **Edit the whole file on GitHub** opens your fork's editor, for the cases a
  text box cannot do.

### Correcting the instrument a deployment names

On a deployment row the panel is called **The instrument on the sheet**, and it
has one box. The finding it answers is the check's commonest: the serial number
read out of the raw archive belongs to a different asset of the same model, so
the sheet names the wrong instrument.

Where the run could say which asset that serial belongs to, it is shown beside
the current one and clicking it takes it. Where it could not, type the asset ID
yourself.

The pre-deploy photograph names an asset too, and is deliberately not offered
here. A photograph of an instrument is not evidence of which instrument went in
the water, which is why it does not confirm a deployment either. Use it as a
prompt to go and find out, not as the answer.

Correcting the asset does **not** clear the preliminary-parameters note the way
correcting a position does. That note is about where the instrument sat, and
this says nothing about that.

### Rules all of them follow

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

**One pull request per kind, on your fork only.** Every calibration file you
corrected in one request, every deployment you repositioned or reassigned in
another, and your sign-offs in a third on a different fork entirely. Each record has its own
section of the body, with every value before and after it, so a batch is no
harder to read than a single correction was — there are simply fewer requests to
raise. Nothing anyone computes changes until it reaches
`oceanobservatories/asset-management`, which you do by hand.

**Do not merge it into your fork's `master`.** The pull request on your fork is
for you to read. The route upstream is a *new* pull request from the same
branch, opened on the shared repository's compare page with your fork's branch
as the head. That sends the one commit the dashboard wrote, straight from the
branch it wrote it on. A pull request cannot be moved to another repository once
opened, so editing the fork's request will not do it.

Merging into your own `master` instead costs you twice. GitHub adds a merge
commit, so what should be one commit becomes two. And your fork is then ahead of
upstream, which is exactly what the sync rule refuses, so you cannot correct
anything else until upstream merges your work. Leaving `master` alone keeps it
identical to upstream and keeps you able to correct the next batch. The exact
clicks, and how to recover if you have already merged, are in
[post-cruise-review.md](post-cruise-review.md#7-raise-each-pull-request-upstream--without-a-second-commit).

### Correcting a calibration

The note goes into the file's own `notes` column, the same column the table
reads back to you as *asset-management note*. The number is written in the
notation the line already uses, so the diff is a changed digit rather than a
reformatted file.

A coefficient that holds several numbers is shown and edited as the file writes
it, `[-0.9765852, 1.081678]`. Clicking the vendor's value takes the whole list,
and each number is written back in the notation its own element already used. A
replacement has to have the same number of values, because a coefficient cannot
change length through a text box.

Above eight values there is no box, and the line says *too many values to type*.
An OPTAA's `CC_acwo` is eighty-three numbers, where typing the array back is
guessing rather than correcting. The GitHub link is how you edit those.

### Correcting a position

The RCA position spreadsheet is the authority on where anything was put, so
**Take every spreadsheet value** is usually the whole answer. The four fields a
position governs are latitude, longitude, water depth and deployment depth.

A profiler's deployment depth is the literal `N/A`, which is the value rather
than a missing one, so a position field is not required to be a number.

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
for it, plus `refDesList.csv` naming every reference designator that has a
deployment. It is what `OOI-CabledArray/deployments` holds.

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

**Read the diff rather than trusting its size.** A history that has not been
rebuilt in a while moves rows for reasons other than new deployments, and three
of them are known:

| what you will see | why |
|---|---|
| an end time changing from `nan` to empty | the instrument is still in the water, and an empty cell says that where the word `nan` did not |
| a vendor calibration link pointing at a different file | it now names the file the comparison actually reads, which moved every OPTAA from its air calibration to its pure-water one |
| rows disappearing from `CAMDS_deployments.csv` | 30 of its rows say `CAMDSB_CAMDSC` in their own sensor type column, and `CAMDSB_CAMDSC_deployments.csv` already holds all 30 — they move to the file named for them, and none is lost |

Anything you cannot place in one of those three is worth asking about before you
merge it.

## Reading an earlier run

The **Run** dropdown in the stamp lists every published run, newest first. A run
that was not against production is labelled with the fork or branch it read, so
a colleague's branch check is not mistaken for what is merged.

Choosing one reloads the whole dashboard against it, including its comparison in
the Changes view.

**When the list gets long.** Every published run stays in the dropdown until
somebody removes it, and an afternoon of test runs will bury the ones worth
reading. Run **Delete published runs** from the Actions tab: give it the number
of newest runs to keep, or the names of the ones to remove. It reports what it
would do and changes nothing until you untick `dry_run`. The run the dashboard
opens on is never deleted. A deleted run is still in the repository's history if
it turns out to have been needed, but it leaves the dropdown.

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

Serial extraction is not started from here. It has its own workflow in the
Actions tab, **Extract serial numbers**, and what it produces is a pull request
against `params/rawFileSN.csv` rather than a report. Merge it, and the next run
reads the serial numbers it found; the count under *deployments an extraction
would settle* on the overview is what it works from.

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
| **Needs verification** | something disagrees, or nothing has established the row, and nobody has looked at it |
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

**It says my fork is not in sync.** It is refusing on purpose, and what to do
depends on which way it has moved. The message says which.

*Behind* means upstream has moved on. Press **Sync fork** on GitHub, run the
checks again, and correct the file from that run.

*Ahead* means your fork carries work upstream does not, usually a correction you
merged into your own `master` rather than sending upstream. **Do not press Sync
fork:** on a fork that is ahead it offers to discard those commits, which would
throw the correction away. Get them merged upstream instead, and the fork
becomes identical again on its own.

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

**I published a run and it is not in the dropdown.** A run publishes only when it
was started from the repository's default branch. Started from the Actions tab
on another branch, it keeps its report as a build artifact and prints a warning
saying so. The dashboard always starts runs from the default branch.

**A run in the dropdown will not open.** It was probably deleted from the
repository after your browser last fetched the list. The report you were reading
stays on screen and the message under the dropdown says what happened; reload
the page to refresh the list.

## The other guides

| guide | what it covers |
|---|---|
| [The post-cruise review, step by step](post-cruise-review.md) | the whole season's review in order, and how to raise a change upstream without a second commit |
| [What each check decides](what-each-check-decides.md) | every verdict a check can return, what it means, and whether it passes |
| [Calibration comparison](calibration-comparison.md) | which vendor format each instrument is compared against, and why |
| [The report contract](report-contract.md) | the shape of the file a run produces, for anyone reading it directly |
| [README](../README.md) | running the checks yourself, and how the pieces fit together |
