# Comparing a calibration against the vendor original

Which vendor file each instrument is compared against, why, and what each
verdict means. Every rule here was settled against the full file set rather than
against the one file someone happened to be looking at, and the paragraphs say
which ones cost real findings to get right.

The [README](../README.md) covers running the check; this is why it answers the
way it does.

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
| PCO2W | `.pdf` | typed in from the certificate |
| DOSTAD | `.pdf` | typed in from the certificate |

### A difference carries what the file says about it

Every calibration csv in asset-management has a `notes` column, and 12,810
coefficients across the repository have something written in it: where a value
came from, which vendor file it was read out of, that it is a constant, that a
pressure offset was added deliberately. On a coefficient that disagrees, that is
exactly the context a reviewer would otherwise go and open the file for, so it
travels with the difference and is shown under it.

Of the 86 differences the current run records, **77 carry a note**. Most are the
same sentence the reviewer later wrote into the HITL sheet, which is the point:
the explanation was in the file all along.

### Instruments no vendor publishes a file for

Four instrument families carry fixed values rather than measurements: the same
numbers on every unit of the type, entered into asset-management by hand. No
vendor measures them, so nothing is ever published to compare against, and every
one of these files read as `NAN` — not checked, and taken to be uncheckable.

They are checkable. The numbers are written down in
`params/coefficientConstants.csv`, and a file that disagrees with them is as
much a transcription error as one that disagrees with a vendor.

| instrument | held to |
|---|---|
| ADCP | `CC_scale_factor1` to `CC_scale_factor4`, all 0.45 |
| VADCP | the same four scale factors |
| HYDBB | `CC_gain`, 0 |
| ZPLSC | frequency, sound speed, seawater density, absorption and theoretical target strength |

**46 RCA calibrations now compare, and all 46 agree.**

These files also carry things that are not calibrations at all — an ADCP's bin
size, first-bin distance, orientation and depth, and a VADCP's beam
transformation matrix and its shape. Those change from one deployment to the
next or belong to the individual instrument, so there is no fixed value to hold
them to. They are declared per sensor as configuration, which reads as a stated
limit of the check rather than a silence.

Four VADCP files hold nothing else. Skipping their configuration leaves no
coefficient compared at all, so they report `CONFIGURATION_ONLY` rather than a
pass — a verdict of *compared* set before anything was read is the defect this
whole rewrite exists for, and it was not going to be reintroduced here. A
coefficient with no fixed value written for it reports `MISSING_COEFFICIENT` for
the same reason.

One more thing had to give way. The check reports `NOMATCH` when
calibrationFiles holds nothing under a calibration's name, and that alone is
enough to put a row in front of a person. For a CTD it should: a vendor original
that is missing is a gap. For these it is the normal state of the world, and it
left files that agreed with everything they were checked against reading *needs
a person* under the sentence *no vendor file in calibrationFiles*. They now
report `NOT_EXPECTED`, which is excluded rather than a finding, so a calibration
that agrees with its fixed values reads **agreed**.

These instruments are identified through the RCA instrument list rather than by
an asset-ID code, which is the same path a borrowed instrument takes.

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

Of 110 OPTAA calibrations, **108 now compare and all 108 agree**. The other two
have no vendor file at all.

The 108th is a borrowed instrument. Sensor rules are keyed on the asset-ID field
of the file name, which holds a model code for an RCA-owned asset and a word for
a loaner: `ATSBE-LOANER-00001` spells `LOANER`, which is no model code, so
nothing matched and the calibration reported `NOTCOMPARED` with its vendor
`.dev` sitting beside it. Where that field settles nothing, the asset is now
looked up in `params/RCA-InstrumentList.csv` and identified by the instrument
type recorded there. That list is the record of what every RCA asset is, so the
next oddly-named one needs no code change. The field still has the last word
where it resolves, because keying on it is what fixed the calibration date being
read as an asset ID.

### Certificates that were only ever published as a pdf

DOSTAD, PHSEN, PCO2W and PAR have no machine-readable vendor file, so their
coefficients are typed into asset-management by hand — about 400 RCA
calibrations, none of which anything checked. **Three quarters of those
certificates carry a text layer**, so the numbers can be read exactly rather
than recognised from an image; OCR is only needed for the 95 that are scans, and
is not implemented.

All four are done: **288 calibrations that nothing had ever checked now
compare**, and they found three real transcription errors:

| | in the record | on the certificate |
|---|---|---|
| PHSEN `CC_eb578` | `38676.5` | `38676.0` |
| PCO2W `CC_cal_range` | `[100, 1190]` | `100–1199` |
| DOSTAD `CC_conc_coef` | `-0.9765852` | `-0.9768582` |

The last is a digit transposition — `8582` typed as `5852`. In every case the
other values on the same page are correct, which is what makes them typing slips
rather than a parse going wrong.

### The 95 scans are read by a person, not by OCR

The remaining certificates have no text layer. They are good scans — 600 dpi,
clean, entirely legible — so text recognition was measured rather than assumed.
On the first one tried, against a record whose values are known, tesseract read
three of seven coefficients wrongly and **invented a minus sign** on a fourth:

| on the certificate | recognised as |
|---|---|
| `1.14611E-04` | `LA4611E- 04` |
| `-2.94251E-01` | `"2.942516. o1` |
| `-5.33864E01` | `--S.33864E01` |
| `2.61210E01` | `-2.61210E01` |

The confusions are exactly the ones that matter here — `1`/`L`, `5`/`S`, `0`/`O`,
and a dropped leading digit that turns `2.21e-06` into `.21e-06`, a tenth of the
value and a perfectly plausible number. In a check whose whole premise is exact
comparison, that manufactures findings at best and agrees wrongly at worst.

So the scan is put in front of a person instead. Opening a scan-only calibration
shows the values asset-management holds beside the certificate itself, rendered
in the page: read across, then clear or flag. The verdict stays
`PDF_NOTCOMPARED` — nothing claims to have checked it — but the reading takes
seconds rather than a hunt through the vendor repository.

GitHub serves a raw pdf as `application/octet-stream` with `nosniff`, which a
browser downloads rather than renders, so the bytes are fetched and given their
real type before being shown.

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
  rule runs columns together.
- A PCO2W calibration range arrives four ways: `206–1197` with a real en-dash,
  `200-600` with a hyphen, `202(cid:21)1191` where the dash is a glyph with no
  Unicode mapping, and split across two cells as `200` then `-1500`. A fifth
  way — `2021191`, the dash dropped entirely — is **not** read as a range at
  all. There is no way to know where to split it, and a guess would invent a
  number, so it reports as missing instead.
- Two vendors misspell their own coefficient names — `SUVFoilCoef` for
  `SVUFoilCoef` on ten certificates, and `Conentration Coef` on another
  template. Both spellings are matched rather than corrected: the file on record
  is the file on record.
- One optode template prints the seven SVU coefficients as `C0-C3` on one line
  and `C4-C6` on the next. The index *is* the coefficient, so the halves have to
  go back together the right way round, and a half-read set is reported as
  nothing at all rather than as four values disagreeing with seven.
- The range is taken only from where the page labels it. Searched for freely, a
  part number three lines up (`4830-58336`) reads as a perfectly good range. And
  one certificate prints its range backwards, `1388-200`; those are the ends of
  an interval, so both sides are sorted before they are compared.

Not every coefficient on the page comes from the vendor, and the three cases are
kept apart:

- **Constant.** PCO2W's `ea434`, `eb434`, `ea620` and `eb620` are identical on
  all 89 RCA calibrations, which is why they are not printed on the certificate.
  They live in `params/coefficientConstants.csv`, as does the ADC bit depth —
  12 for both instruments, and a deviation is then a finding rather than a gap.
  It already is one: two calibrations of `ATAPL-58337-00013` run at 16, noted as
  a Rev K circuit board.
- **Absent on purpose.** A DOSTAD certificate with no 2-point recalibration
  prints no concentration coefficient at all, and the record then carries the
  identity — no correction. That is declared per sensor in `defaults`, so the
  record is held to it: 14 calibrations pass *because* they say `[0.0, 1.0]`,
  and one claiming a correction its certificate never made would not.
- **Measured.** PHSEN's salinity is a real measurement on four deployments and
  the default 35 on the rest, and nothing on the vendor's page could check it
  either way. Declared per sensor in `notVendor`, so it reads as a stated limit
  of the check rather than as silence. Asset-management's own note agrees:
  *"no sal listed on cal sheet; using default 35"*.
- **Vendor.** Everything else, including PHSEN's four E values — those vary
  across the archive and are printed on the certificate, which is how the
  transcription error above was found.

A constant is only checked when the vendor file could be read, because a file
whose only evidence is a scan must not report `COMPARED` on the strength of
three constants. That leaves the second Rev K calibration unverified — it is one
of the 36 PHSEN scans.

### A calibration date is not an asset ID

Sensors used to be identified by searching the whole file path for an asset ID.
A calibration dated 2017-01-10 spells `70110` inside its own date, which is
FLNTUA's asset ID, and 2017-01-11 spells `70111`, which is FLCDRA's. A NUTNR and
a SPKIR calibration were checked against the wrong instrument's rules for years
and reported as having no vendor file, while their `.cal` sat in the directory
beside them. Both compare and agree now. The asset ID is read from its own field
in the file name.
