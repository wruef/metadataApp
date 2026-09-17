# The run report

What a verification run emits, and what a comparison between two runs will and
will not accept. The [README](../README.md) covers running one; this is the
contract the dashboard reads and the reason each field is in it.

The shape is named once in [`schema/report.json`](../schema/report.json), which
`tests/test_schema.py` and `dashboard/test/schema.test.ts` both check against the
same committed report — so a renamed field fails on both sides rather than
turning into blank cells in a published table.

## The run report

A run emits one versioned JSON document — `schemaVersion`, when it ran, every
input it read (both repository refs and the parameter-file commit), and the five
checks. It replaces five CSV and TXT files that could not reliably be read back:
the calibration report embedded a python list literal containing commas in its
last column, and the season lists wrote multi-valued serial numbers unquoted, so
27 of 154 rows in the 2022 list had more fields than the header.

Every row carries four things the dashboard should not have to work out itself:

- **`severity`** — the review status: the category the row is in. Shown in the
  dashboard as **Review status**, because that is what it now says — a sign-off
  is a category, not a degree of badness. The field keeps its name so published
  reports stay readable. One of `problem`, `review`, `unchecked`,
  `cleared`, `ok` or `excluded`, taken as the worst of the row's verdicts, so a
  queue can be ranked by consequence rather than by row order. A verdict with no
  mapping counts as `review`, so a new one reaches a person instead of quietly
  passing.

  **`excluded`** is outside what the check can judge: asset-management holds no
  calibration for the instrument at all, so there was nothing to compare and
  nothing was missed. An excluded verdict is skipped when a row's severity is
  taken rather than ranked among the others, so it neither passes the row nor
  holds it back, and a row whose every verdict is excluded is excluded itself.
  It is counted in no other number. `unchecked` would claim a look that was
  never owed, and a proportion measured against the row count would make the
  record look worse every time one of these instruments was deployed. The
  instruments themselves are named in `excludedInstruments`, because a check
  that quietly covers less than you think is worse than one that says what it
  skipped.
- **`cleared`** — whether a reviewer signed the row off. A signed-off row takes
  the `cleared` category whatever its checks found, so it is never a problem and
  never work waiting on somebody.
- **`finding`** — what the checks themselves found, kept whatever the sign-off
  says. A sign-off is a judgement *about* a finding rather than the absence of
  one: three signed-off calibrations turned out to hold real transcription
  errors, so the disagreement stays on the row and on screen beside the badge.
  A cleared row reads **green**, whatever its finding — a reviewer's judgement
  is not a lesser kind of pass than a machine's — and carries a second badge
  naming what was found, in that finding's own colour. So a cleared row over a
  real mismatch shows green beside red.
- **`reason`** — one sentence saying why the row reads as it does, in the words
  someone would use out loud. A queue is worked by people, and
  `MISMATCH: raw: 379: ATAPL-68020-00002` is a verdict, not a reason.

Each check's `summary` counts every category, and beside them `attention` — the
problem and review rows, which a signed-off row is never one of — `verified`,
agreed plus cleared, and `considered`, the rows the check could judge at all,
which is the row count less the excluded ones. `attention` is what *needs attention* means
everywhere: the rail, the segmented control and the overview queue all read it,
so they cannot disagree about how much is left. `verified` is what the headline
tiles count, because a sign-off is how the things a check cannot settle get
settled, and leaving them out would leave the record looking permanently
unfinished.

The reason explains the severity, so the two must never contradict each other —
a row reading *a photograph confirms the asset* above a badge reading *not
checked* helps nobody. A test runs every combination of verdicts each check can
return and asserts that no reason lands on both a settled row and an open one.
It found 442 real deployments doing exactly that: confirmed by one piece of
evidence while another had never been looked at. The two sign-off reasons are
exempt by design, because a sign-off describes what a person did rather than
what a check found.

The report also carries `hitlNotes` — every note already written in each 2i-HITL
sheet, most used first. Those are the reasons offered when a row is signed off,
so a new sign-off reuses the team's wording rather than a fresh synonym for it.
They are read from the sheets rather than from the run's own rows, because the
two do not hold the same set: a note written against a calibration file that
asset-management no longer carries is still a reason worth offering.

Non-finite floats are written as `null`. Python emits `NaN` and `Infinity`
happily and neither is valid JSON, which a browser refuses to parse.

## What confirms a deployment

`verificationStatus` answers one question: is the instrument named on the
deployment sheet the one that was actually in the water? Two things answer it,
and **either alone is enough**:

- the serial number recovered from the first raw file matches the asset's serial
  in the sensor bulk record, or
- a reviewer signed the deployment off.

A pre-deploy photograph is **not** one of them. It is still read, still reported
in `image_verify`, and a photograph that disagrees with the sheet is still a
problem. But a photograph of an instrument is not evidence of which instrument
went in the water, and 127 deployments were reading as confirmed on that alone.

The serial comparison is a containment rather than an equality, and
deliberately so: the two records spell a serial differently — an instrument
reporting `05400030` against a record carrying `5471540-0030` — so the extractor
keeps only a tail of it. 265 deployments are confirmed that way and are sound,
because nothing else of the same model could answer to the number.

Four were not. Their raw serial is a **single digit**, because the PREST
extractor keeps two characters, and the same digit fits the instrument beside
them. Those now report `AMBIGUOUS_SN` and name the rival asset. Nothing
disagrees, so it is not a mismatch; nothing was established either, so it is not
a match. A serial is only evidence while no other instrument of the same model
could answer to it.

Where neither answer is available, the status is `RAW_SN_POSSIBLE` when the
instrument class writes its serial into its raw data — extraction would settle
it — and `NOT_VERIFIED` when nothing could.

A confirmed deployment reads as **agreed**, the same way a calibration that
matches its vendor file does, unless something else on the row objects. What
counts as an objection is the point. A verdict can describe a row without
ranking it, and two kinds do:

- **`excluded`** — there was nothing to check. `NAN` on the raw file means the
  instrument class writes no serial into its data; `NAN` on the photograph means
  nobody took one. Neither is a check that was skipped, and counting them as
  unchecked held 459 confirmed deployments back from reading as confirmed.
- **`warning`** — something worth noticing that nobody has to act on. Two
  today: a calibration more than fifteen months older than its deployment, and a
  pre-deploy photograph showing a different asset. Neither changes what the raw
  archive or a reviewer established about which instrument went in the water, so
  both colour their cell amber and are said in the row's sentence rather than
  holding the row open. A photograph that does not confirm a deployment cannot
  condemn one either: it shows an instrument, not which instrument went in the
  water. The disagreement is still worth reconciling, and it is still on the
  row.

A required calibration that is missing still holds a row back. Those are findings rather than absences. A
calibration verdict of `none` is one of them: by the time the severity is read
it can only mean a calibration was required and asset-management holds none at
all, because the check rewrites it to `excluded` wherever none was expected.
That is worse than a calibration dated after the deployment, which is already a
problem, so 32 deployments that read as merely unchecked now read as findings.

There is no `verificationStatus` column in the dashboard. It is the raw serial
and the sign-off read together, both of which are columns of their own, and the
review status badge already says what it concluded. The value stays on the row,
under *Raw check output*, and remains a filter — it is the only way to ask for
the deployments nothing confirms, which the review status cannot isolate because
it folds in the calibration findings too.

## Vendor calibrations with no repository file

146 calibrations are on file in calibrationFiles with nothing in
asset-management to compare them to. They are not rows in the calibration check,
because there is no repository file to be a row, and they used to sit in an
amber panel above the table — 146 names in a scrolling box on top of the queue
someone was trying to work.

They now have their own view, listing each with the directory the vendor filed
it under, which is the only thing on record that says what kind of instrument it
is. Half of them are hydrophones and optical absorption sensors.

Each can be cleared or flagged, and the decision is written into the existing
calibration sheet under the name the repository file **would** have if it were
ingested — `<asset>__<date>.csv`. So a note taken now is already attached to the
file on the day it arrives.

## Asset IDs, against every record that could hold one

A deployment sheet names four assets per row, and two of them were never
checked. `sensor.uid` went to the sensor record and `mooring.uid` to the
platform record; `node.uid` went nowhere — 46 node assets across every
deployment in the archive, against a record nothing compared them to — and
`electrical.uid` is empty in every sheet today and is checked anyway, because
the day it is filled in is not the day to notice.

All six bulk records are now read: sensor, platform, node, eng, array and
unclassified. An asset that is in one of them but not the one its column calls
for is **misfiled rather than missing**, and the verdict says which record holds
it. That is a different answer from an asset nobody has ever heard of, and
naming the record is most of the fix.

Every column resolves today, so this is coverage rather than a correction.

## A serial number is a judgement, so it can be signed off

The sensor bulk check compares the RCA instrument list against OOI's record, and
131 of its rows needed a person every single run. Most of them are not errors to
fix but judgements about which record is right, and there was nowhere to write
that judgement down. There is now: `2i_HITL/2i_HITL_sensorVerification.csv`, keyed on
the asset ID, signed off from the dashboard like any other row.

The view carries the instrument type too, taken from the RCA instrument list.
Only that list names one — the bulk record describes equipment, `SENSOR CTD`,
rather than naming an instrument — so the column is empty on exactly the 32 rows
that say `MISSING_FROM_RCA_LIST`. That is not a gap in the column. It is the
finding itself.

The same change made `FORMAT_MATCH` agree rather than needing a person. It means
the same serial number written two ways — a prefix one record carries and the
other does not. The records agree about which instrument it is, which is what
this check asks, so 69 rows that were never going to be anything else left the
queue. **Sensor bulk drops from 131 rows needing a person to 62.**

## One instrument, two data streams

The deployment sheets are checked for the same asset appearing twice in one
deployment, because an instrument cannot be in two places at once. One pair is
exempt: **RASFLA301 and D1000A301 share an asset ID because they are the same
hardware.** Two reference designators exist because two data streams are
required of it, and the sheets name the asset once under each.

That pair accounted for 24 of the 26 rows this check reported. What is left is
one real finding — a DOSTA deployed on a deep profiler and a shallow profiler
in the same 2014 deployment.

The exemption is on the pair, not on either name alone: a RAS sharing an asset
with anything else is still reported.

## Comparing two runs

    compare-metadata reports/baseline.json reports/report.json

Every comparison says whether it can be trusted. A row can move because the data
changed or because the *check* changed — fixing the silent-pass bug moved 114
rows with nothing in the repositories moving at all — so two runs produced by
different versions of the checks are refused rather than diffed.

A run must also record the commit of every repository it read, and a comparison
is refused when one does not. The ref is not enough: `master` today and `master`
next season are different data, so a moved row could not be attributed to
either. A directory copied rather than cloned has no `.git` to ask, which is
exactly how two runs came to be diffed while neither recorded which
asset-management it had seen — the commit now reads `UNKNOWN` rather than coming
back empty.

## Reports predating the correctness fixes are not a baseline

Two defects made the calibration check report success without checking: the
verdict was set to `COMPARED` before any vendor file was opened, and in the CTD
and DOFSTA `.cal` paths the difference was computed outside the coefficient loop
so only the last coefficient was compared. Both are fixed here, and
`tests/test_calibrations.py` covers exactly those failure modes.

Anything in the old `reportOuts/` predating `metadataVerification@0ac8bd8` was
produced by the buggy path. Baselines start at the first post-fix run.
