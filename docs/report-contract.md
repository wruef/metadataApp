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

- **`severity`** — the category the row is in: `problem`, `review`, `unchecked`,
  `cleared` or `ok`, taken as the worst of the row's verdicts, so a queue can be
  ranked by consequence rather than by row order. A verdict with no mapping
  counts as `review`, so a new one reaches a person instead of quietly passing.
- **`cleared`** — whether a reviewer signed the row off. A signed-off row takes
  the `cleared` category whatever its checks found, so it is never a problem and
  never work waiting on somebody.
- **`finding`** — what the checks themselves found, kept whatever the sign-off
  says. A sign-off is a judgement *about* a finding rather than the absence of
  one: three signed-off calibrations turned out to hold real transcription
  errors, so the disagreement stays on the row and on screen beside the badge.
  A cleared row reads green where its finding agrees and amber where it does
  not, and carries a second badge naming what was found.
- **`reason`** — one sentence saying why the row reads as it does, in the words
  someone would use out loud. A queue is worked by people, and
  `MISMATCH: raw: 379: ATAPL-68020-00002` is a verdict, not a reason.

Each check's `summary` counts every category, and beside them `attention` — the
problem and review rows, which a signed-off row is never one of — and
`verified`, agreed plus cleared. `attention` is what *needs attention* means
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
