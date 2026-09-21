# What each check decides

Every verdict each check can return, what it means, and whether it counts as
passing. Written for anyone reading a row in the dashboard and asking why it
says what it says.

The authoritative table is `SEVERITY` in
[`src/rca_metadata/report.py`](../src/rca_metadata/report.py); this page is that
table in words.

- [How a row's status is decided](#how-a-rows-status-is-decided)
- [Calibrations](#calibrations)
- [Deployments](#deployments)
- [Positions](#positions)
- [Sensor bulk](#sensor-bulk)
- [Duplicate asset deployments](#duplicate-asset-deployments)

## How a row's status is decided

A row carries several verdicts, one per thing that was checked. Its status is
the **worst** of them, so a deployment confirmed by its serial number but
missing a calibration is not a pass.

Six statuses, worst first:

| status | meaning |
|---|---|
| **Needs verification** | something disagrees, or nothing has established the row, and nobody has looked at it |
| **Not checked** | nothing settled this, and something could have |
| **Cleared in review** | a reviewer signed it off |
| **Agreed** | the records agree |
| **Excluded** | there was nothing to check |

Two kinds of verdict describe a row without ranking it:

- **excluded** — nothing to check, and nothing missed. It is counted in no other
  number. A row whose every verdict is excluded is excluded itself.
- **warning** — worth noticing, nobody has to act. It colours its cell amber and
  is said in the row's sentence.

**A sign-off overrides the lot.** A signed-off row reads *Cleared in review*
whatever its verdicts, and is never work waiting on anyone. What the checks
found is kept beside it and still shown, because three signed-off calibrations
turned out to hold real transcription errors.

**A verdict nobody has ranked counts as *needs verification*.** Adding one without
adding it to the table puts rows in front of somebody rather than quietly
passing them.

## Calibrations

Does each calibration file in `asset-management` match the vendor original in
`calibrationFiles`? Five things are judged per file.

### The comparison itself — `vendorMatch`

| verdict | status | meaning |
|---|---|---|
| `COMPARED` | Agreed | read against the vendor file, and every coefficient matches |
| `COMPARED_CONSTANTS` | Agreed | no vendor measures these; every value matches the fixed ones in `coefficientConstants.csv` |
| `MISMATCH` | Needs verification | a coefficient disagrees with the vendor |
| `MISSING_COEFFICIENT` | Needs verification | the vendor file does not carry a coefficient this file claims, so it could not be checked |
| `NO_VENDOR_FILE` | Needs verification | the instrument has a comparison rule and nothing is on record |
| `VENDOR_DATE_NEAR_MISS` | Needs verification | a vendor file exists days away and its coefficients differ, so it is a different calibration |
| `VENDOR_DATE_MISNAMED` | Needs verification | a vendor file days away holds *exactly* these coefficients — one of the two file names has the wrong date |
| `CONSTANT_MISMATCH` | Needs verification | the only disagreements are with the constants file, where no vendor value is involved |
| `NO_CONSTANTS` | Needs verification | the instrument is held to fixed values and none are written |
| `PDF_NOTCOMPARED` | Not checked | the vendor calibration is a scan, so a person has to read it |
| `FORMAT_NOTCOMPARED` | Not checked | a vendor file is on record, but not in the format this instrument is compared against |
| `CONFIGURATION_ONLY` | Not checked | the file holds only deployment configuration, so there was no coefficient to compare |
| `NOTCOMPARED`, `NAN` | Not checked | no comparison is written for this instrument yet |

Runs published before DOFSTA moved to its `.cal` also carry `COMPARED_XML`, which
ranks as agreed. Nothing produces it now.

A coefficient that disagrees can be corrected from the row. It joins the
calibration batch, which goes to your own `asset-management` fork as one pull
request. See
[using-the-dashboard.md](using-the-dashboard.md#correcting-a-file-in-asset-management).

**Comparison is exact.** There is no tolerance. Where a vendor publishes fewer
significant figures than the repository file carries, that gap is a
transcription to fix in the data rather than noise to absorb in code.

**One vendor format per instrument, with no falling back to another.** Where a
vendor publishes the same calibration twice the two files do not carry the same
numbers at the same precision, so comparing against whichever happens to be
present manufactures disagreements. Which format each instrument uses is in
[calibration-comparison.md](calibration-comparison.md).

### Whether a vendor original is on record — `calRepo_check`

| verdict | status | meaning |
|---|---|---|
| `MATCH` | Agreed | calibrationFiles holds a file under this name |
| `NOMATCH` | Needs verification | it does not |
| `NOT_EXPECTED` | Excluded | no vendor publishes one for this instrument and none ever will |

### Whether the file could be read — `fileParse`

| verdict | status | meaning |
|---|---|---|
| `SUCCESS_TYPE1` | Agreed | read with the strict number parser |
| `SUCCESS_TYPE2` | Agreed | read with the looser one, which is what an OPTAA sheet reference needs |
| `FAIL` | Needs verification | the file could not be read at all |

### The serial number inside the file — `serialNumber`

| verdict | status | meaning |
|---|---|---|
| `MATCH_SENSORBULK` | Agreed | the serial in the file agrees with OOI's record for the asset in its name |
| `MISMATCH_SENSORBULK` | Needs verification | it disagrees |
| `MULTIPLE` | Needs verification | the file carries more than one serial number |
| `PARSING_ERROR` | Needs verification | the asset in the file name is not in OOI's record |
| `NOTFOUND_FILE` | Not checked | the file carries no serial column |
| `NOTFOUND_SENSORBULK` | Not checked | OOI's record carries no serial for the asset |

### Repeated coefficient names — `duplicateCoeff`

| verdict | status | meaning |
|---|---|---|
| `NONE` | Agreed | no name appears twice |
| `DUPLICATES_IDENTICAL` | Agreed | a name appears twice with the same value, which changes nothing |
| `DUPLICATES_NOTIDENTICAL` | Needs verification | a name appears twice with conflicting values |

## Deployments

Is the instrument named on the sheet the one that was actually in the water, and
did it have a calibration?

### Confirmation — `verificationStatus`

**Two things confirm a deployment, and either alone is enough:** the serial
number read out of the deployment's raw data, or a reviewer's sign-off.

| verdict | status | meaning |
|---|---|---|
| `VERIFIED` | Agreed | the raw serial matches, or a reviewer signed it off |
| `RAW_SN_POSSIBLE` | Needs verification | nothing confirms it yet, but this instrument class writes its serial into its raw data, so extraction would settle it |
| `NOT_VERIFIED` | Needs verification | nothing could confirm it |

A pre-deploy photograph is **not** one of the two. It is still read and still
reported, and one that disagrees is still shown, but a photograph of an
instrument is not evidence of which instrument went in the water.

### The serial in the raw archive — `rawFile_verify`

| verdict | status | meaning |
|---|---|---|
| `MATCH` | Agreed | the serial identifies the deployed asset |
| `MISMATCH` | Needs verification | the serial belongs to a different asset, which is named in the verdict |
| `NO_FILE` | Needs verification | this class writes a serial and no raw file was found |
| `AMBIGUOUS_SN` | Not checked | the serial is too short to tell this instrument from another of the same model |
| `NO_SN` | Not checked | a raw file exists and no serial has been extracted from it |
| `NAN` | Excluded | this instrument class writes no serial into its data |

The comparison is not an equality, because the two records often spell a serial
differently — an instrument reporting `05400030` against a record carrying
`5471540-0030`, the same number in vendor part-number dress. Stripped to digits,
and of the leading zero, the raw serial is the last seven of the recorded one.
For most classes the extractor keeps a tail of the serial instead and the
comparison is containment. Either way it is sound only while no other instrument
of the same model could answer to the number, which is what `AMBIGUOUS_SN`
catches: every match is put to the rest of the platform before it is called one.

The Sea-Bird pH sensor spells it a third way, and the same rule settles it. It
prints `SerialNumber='0002085'` at power-on where both records carry
`721-2085`: the same number under a product prefix. Only `PHSENH` is read this
way. `PHSEND` and `PHSENA` are Sunburst SAMI2-pH, whose records carry a one-byte
device id that is not the serial and changes between deployments, so nothing in
their raw data says which instrument wrote them and they stay `NAN`.

A five-beam ADCP is the other way round: its raw data reports a serial that
shares nothing with the record's, because the record holds the system serial
and the PD0 ensembles hold the electronics'. `params/serialAliases.csv` pairs
the two for each asset, once a person has seen the same asset read the same
number season after season, and a raw serial equal to an asset's alias is a
`MATCH`. A raw serial equal to *another* asset's alias names that asset in the
`MISMATCH`, the same as a bulk serial would.

The asset a `MISMATCH` names can be taken as a correction from the row, which
rewrites `sensor.uid` on that deployment's line of its array's sheet. See
[using-the-dashboard.md](using-the-dashboard.md#correcting-the-instrument-a-deployment-names).

### The pre-deploy photograph — `image_verify`

| verdict | status | meaning |
|---|---|---|
| `MATCH` | Agreed | the asset read from the photograph is the one on the sheet |
| `MISMATCH` | *warning* | it is not — noted on the row, but it does not hold the row open |
| `NO_IMAGE_ASSET` | Excluded | a photograph is on record and no asset could be read from it, so there is nothing to compare |
| `NAN` | Excluded | no photograph is on record |

### The calibration in force — `calFile_verify`

| verdict | status | meaning |
|---|---|---|
| `VALID_FILE` | Agreed | a calibration dated before the deployment is on file |
| `NO_VALID_FILE` | Needs verification | calibrations exist but all are dated after the deployment |
| `none` | Needs verification | the instrument needs a calibration and asset-management holds none at all |
| `VALID_FILE_CAL_OLDER_THAN_15MONTHS` | *warning* | one is on file and predates the deployment by more than fifteen months |
| `EXCLUDED` | Excluded | asset-management holds no calibration directory for this instrument, so none was ever owed |
| `NAN` | Not checked | — |

## Positions

Do the deployment sheets agree with the RCA position spreadsheet? Latitude,
longitude and depth are compared for each deployment.

| verdict | status | meaning |
|---|---|---|
| `MATCH` | Agreed | all three agree with the spreadsheet |
| `MISMATCH` | Needs verification | one or more differ |
| `NEEDS_HITL` | Needs verification | more than one spreadsheet row could be this deployment |
| `NO_POSITION` | Needs verification | the spreadsheet holds no position for it |
| `NO_POSITION_NAME` | Needs verification | no position name maps to this reference designator |
| `BAD_POSITION_RECORD` | Needs verification | the spreadsheet row could not be read as a position |
| `HITL_PIN_NOT_FOUND` | Needs verification | a reviewer pinned this deployment to a spreadsheet row that is no longer there |

A `MISMATCH` can be corrected from the row, which rewrites that one deployment's
line. An instrument's line is on its array's sheet in `asset-management`; a
node's is in `NODE_deployments.csv` in the `deployments` repository, so the two
go to different forks in different batches. See
[using-the-dashboard.md](using-the-dashboard.md#correcting-a-position).

A profiler's deployment depth is the literal `N/A`, which is the value rather
than a missing one. Reading it as missing once made 644 already-correct rows
look like they needed correcting.

## Sensor bulk

Do serial numbers agree between `params/RCA-InstrumentList.csv` and OOI's sensor
bulk record?

| verdict | status | meaning |
|---|---|---|
| `MATCH` | Agreed | the two records carry the same serial |
| `FORMAT_MATCH` | Agreed | the same number written two ways — a prefix one record carries and the other does not |
| `MISMATCH` | Needs verification | the two records name different instruments |
| `MISSING_FROM_SENSOR_BULK` | Needs verification | the RCA list carries an asset OOI's record has never heard of |
| `MISSING_FROM_RCA_LIST` | Needs verification | OOI's record carries an RCA asset the RCA list does not |
| `NO_BULK_SERIAL` | Not checked | OOI's record carries no serial for the asset |

A format match agrees because the records agree about *which instrument it is*,
which is what this check asks. The instrument type column is empty on exactly
the rows that say `MISSING_FROM_RCA_LIST`, because only the RCA list names one.

## Duplicate asset deployments

Is one asset in the water twice at the same time, is one node or mooring in two
places at once, and does every asset a deployment sheet names exist in the bulk
record it belongs to?

| verdict | status | meaning |
|---|---|---|
| `DUPLICATE_ASSET_IN_DEPLOYMENT` | Needs verification | the same sensor asset was in the water twice at the same time; the verdict names the deployment it overlaps |
| `DUPLICATE_NODE_IN_DEPLOYMENT` | Needs verification | one node asset is recorded at two places over the same days; the verdict names the others |
| `DUPLICATE_MOORING_IN_DEPLOYMENT` | Needs verification | one mooring asset is recorded at two sites over the same days |
| `SENSOR_NOT_IN_BULK` | Needs verification | `sensor.uid` is not in the sensor record |
| `MOORING_NOT_IN_PLATFORM_BULK` | Needs verification | `mooring.uid` is not in the platform record |
| `NODE_NOT_IN_NODE_BULK` | Needs verification | `node.uid` is not in the node record |
| `ELECTRICAL_NOT_IN_ENG_BULK` | Needs verification | `electrical.uid` is not in the eng record |
| `ASSET_IN_WRONG_BULK_RECORD` | Needs verification | the asset is in the bulk records, but under a different one than its column calls for |
| `CRUISE_NOT_IN_CRUISE_LIST` | Needs verification | the cruise is not in the cruise list |

**Overlapping dates are the whole test.** Asset IDs are unique across every
instrument class, so the asset alone identifies the instrument, and two rows
carrying one asset over the same days are two claims about where it was.

Deployment numbers cannot find this. They count per reference designator, so one
asset can be deployment 3 on one designator and 7 on another in the same season,
and two unrelated designators can share a number. Neither does the designator
matter: two overlapping deployments of one asset on the **same** designator used
to be waved through as a redeployment, and that is where the error actually
lives. A velocity meter's deployment 4 was never given a stop date, deployment 5
started a year later, and the sheet has said ever since that one instrument is in
the water twice. Both VEL3D findings today are that shape.

A deployment with no stop date runs until now, which is what makes an unclosed
one visible. One ending the day the next begins is a turnaround, not an overlap:
the comparison is strict at both ends.

### Nodes and moorings

A node is in one place at a time too, and it is checked differently because it
does a different job. A node hosts many instruments at once, so its asset is on
a deployment row per instrument hanging off it, all at the same time. Those rows
are not the comparison — the **places** are. The place a node occupies is the
site and the node, `RS03AXBS-MJ03A`; for a mooring it is the site alone.

A node recorded at two places over the same days is one box on two parts of the
seafloor, and it is reported once per place, naming the others. Nineteen rows
across nine junction boxes read that way today. Most are an earlier site never
given a stop date; one is a box claimed at two platforms for nine overlapping
days in 2018. No mooring is in two places.

`electrical.uid` is not checked this way. It is empty in every sheet today, and
what a place would mean for one is not worth guessing at before there is a row
to look at.

**One pair is exempt from the duplicate rule.** `RASFLA301` and `D1000A301`
share an asset ID because they are the same hardware; two reference designators
exist because two data streams are required of it. That pair accounted for 24 of
the 26 rows this check used to report. The exemption is on the pair — a RAS
sharing an asset with anything else is still reported.
