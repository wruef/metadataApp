import type { Severity } from '~/store'

/**
 * How a cell reads at a glance.
 *
 * Every verdict in a check table is coloured by the severity the run itself
 * would give it, so the colour of a cell and the severity of its row are the
 * same judgement rather than two that can disagree.
 */
export type Tone = 'ok' | 'warn' | 'crit' | 'na'

export const SEVERITY_TONE: Record<Severity, Tone> = {
  verification: 'warn',
  unchecked: 'na',
  // Green, whatever the checks found. A sign-off is a person saying they have
  // been and this row is settled, and that is as settled as a row gets — a
  // reviewer's judgement is not a lesser kind of pass than a machine's. What
  // they judged is not hidden: the finding keeps its own badge beside this one,
  // in its own colour, so a cleared row over a real mismatch still shows the
  // mismatch in red. Three signed-off calibrations turned out to hold real
  // transcription errors, and that is what the second badge is for.
  cleared: 'ok',
  ok: 'ok',
  excluded: 'na',
}

/**
 * verdict -> severity, per check and field.
 *
 * This mirrors `SEVERITY` in `src/rca_metadata/report.py`, which is the source
 * of truth: the run uses it to rank rows, and this copy only decides a colour.
 * A verdict missing here reads as `warn`, the same way the run counts an
 * unmapped verdict as `verification` — a new verdict draws the eye rather than
 * quietly passing.
 */
export const VERDICTS: Record<string, Record<string, Record<string, Severity | 'warning'>>> = {
  sensorBulk: {
    verdict: {
      MATCH: 'ok',
      FORMAT_MATCH: 'ok',
      MISMATCH: 'verification',
      MISSING_FROM_RCA_LIST: 'verification',
      MISSING_FROM_SENSOR_BULK: 'verification',
      NO_BULK_SERIAL: 'unchecked',
    },
  },
  calibrations: {
    vendorMatch: {
      COMPARED: 'ok',
      COMPARED_XML: 'ok',
      MISMATCH: 'verification',
      MISSING_COEFFICIENT: 'verification',
      NO_VENDOR_FILE: 'verification',
      VENDOR_DATE_NEAR_MISS: 'verification',
      VENDOR_DATE_MISNAMED: 'verification',
      CONSTANT_MISMATCH: 'verification',
      COMPARED_CONSTANTS: 'ok',
      NO_CONSTANTS: 'verification',
      CONFIGURATION_ONLY: 'unchecked',
      PDF_NOTCOMPARED: 'unchecked',
      FORMAT_NOTCOMPARED: 'unchecked',
      NOTCOMPARED: 'unchecked',
      NAN: 'unchecked',
    },
    calRepo_check: { MATCH: 'ok', NOMATCH: 'verification', NOT_EXPECTED: 'excluded' },
    fileParse: { SUCCESS_TYPE1: 'ok', SUCCESS_TYPE2: 'ok', FAIL: 'verification' },
    serialNumber: {
      MATCH_SENSORBULK: 'ok',
      MISMATCH_SENSORBULK: 'verification',
      MULTIPLE: 'verification',
      PARSING_ERROR: 'verification',
      NOTFOUND_FILE: 'unchecked',
      NOTFOUND_SENSORBULK: 'unchecked',
    },
    duplicateCoeff: {
      NONE: 'ok',
      DUPLICATES_IDENTICAL: 'ok',
      DUPLICATES_NOTIDENTICAL: 'verification',
    },
  },
  deploymentSheets: {
    verdict: {
      SENSOR_NOT_IN_BULK: 'verification',
      MOORING_NOT_IN_PLATFORM_BULK: 'verification',
      NODE_NOT_IN_NODE_BULK: 'verification',
      ELECTRICAL_NOT_IN_ENG_BULK: 'verification',
      ASSET_IN_WRONG_BULK_RECORD: 'verification',
      CRUISE_NOT_IN_CRUISE_LIST: 'verification',
      DUPLICATE_ASSET_IN_DEPLOYMENT: 'verification',
      DUPLICATE_NODE_IN_DEPLOYMENT: 'verification',
      DUPLICATE_MOORING_IN_DEPLOYMENT: 'verification',
      DEPLOYMENT_MISSING_END_DATE: 'verification',
    },
  },
  deployments: {
    verificationStatus: { VERIFIED: 'ok', RAW_SN_POSSIBLE: 'verification', NOT_VERIFIED: 'verification' },
    rawFile_verify: {
      MATCH: 'ok',
      MISMATCH: 'verification',
      NO_FILE: 'verification',
      AMBIGUOUS_SN: 'unchecked',
      NO_SN: 'unchecked',
      NAN: 'excluded',
    },
    image_verify: { MATCH: 'ok', MISMATCH: 'warning', NAN: 'excluded', NO_IMAGE_ASSET: 'excluded' },
    calFile_verify: {
      VALID_FILE: 'ok',
      NO_VALID_FILE: 'verification',
      EXCLUDED: 'excluded',
      VALID_FILE_CAL_OLDER_THAN_15MONTHS: 'warning',
      none: 'verification',
      NAN: 'unchecked',
    },
  },
  positions: {
    verdict: {
      MATCH: 'ok',
      MISMATCH: 'verification',
      NEEDS_HITL: 'verification',
      NO_POSITION: 'verification',
      NO_POSITION_NAME: 'verification',
      BAD_POSITION_RECORD: 'verification',
      HITL_PIN_NOT_FOUND: 'verification',
    },
  },
}

/** The sign-off column, which is a person's word rather than a check's. */
const HITL: Record<string, Tone> = { Clear: 'ok', NotClear: 'crit', NA: 'na' }

/**
 * A verdict and the detail appended to it.
 *
 * `rawFile_verify` reads `MISMATCH: raw: 379: ATAPL-68020-00002` — the verdict
 * and the serial numbers behind it in one string. The verdict is what the
 * column is scanned for, so it is badged and the rest is left as text.
 */
/**
 * What a column is called on screen, where its field name is not what a reader
 * would call it.
 *
 * The field names are the report's, and they stay the report's: renaming one
 * would break every published run and every link somebody sent. Anything not
 * named here is the field with its underscores and camel humps opened out.
 */
export const COLUMN_LABEL: Record<string, string> = {
  /** It answers whether the vendor original is on file, not what a repository
   *  check concluded. */
  calRepo_check: 'Vendor file',
  /** The comparison is between the file in asset-management and that original,
   *  and calling it the vendor's made the two columns read as one question
   *  asked twice. */
  vendorMatch: 'Github comparison',
  HITLstatus: 'HITL status',
  /** On the deployments table: what each column is evidence *from*, rather than
   *  the name of the check that read it. A reader working the queue is asking
   *  what the archive said and what the cruise photograph said, not which
   *  verify step produced the string. */
  rawFile_verify: 'Raw archive',
  image_verify: 'Cruise image',
  calFile_verify: 'Calibration',
}

/**
 * What a verdict is called on screen, per column.
 *
 * Same rule: the value in the report is unchanged, because a filter someone
 * saved reads `?vendorMatch=MISMATCH` and a run published last season still has
 * to open. `MATCH` under *Vendor file* answers a different question from
 * `MATCH` under a comparison, and reading the same word twice on one row
 * suggested the two agreed about something when only one of them had looked.
 */
export const VERDICT_LABEL: Record<string, Record<string, string>> = {
  calRepo_check: { MATCH: 'On file', NOMATCH: 'Missing', NOT_EXPECTED: 'Not expected' },
}

export const columnLabel = (column: string) =>
  COLUMN_LABEL[column] ?? column.replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2')

export const verdictLabel = (column: string, token: string) =>
  VERDICT_LABEL[column]?.[token] ?? token

export function splitVerdict(value: string) {
  const [token, ...rest] = value.split(':')
  return { token: (token ?? '').trim(), detail: rest.join(':').trim() }
}

/**
 * The asset a raw serial number turned out to belong to, or null.
 *
 * `rawFile_verify` reads `MISMATCH: raw: 23443: ATAPL-68073-00005` when the
 * serial in the raw file belongs to a different asset of the same model, and
 * ends `: unknown` when the run could not place it at all.
 *
 * Only a MISMATCH names one. `AMBIGUOUS_SN` names an asset the serial *also*
 * fits, which is the opposite of evidence — it is the reason that row cannot be
 * settled — so nothing is offered from it.
 */
export function assetNamedByRawSerial(verdict: string) {
  const named = /^MISMATCH: raw: [^:]*: *(\S+)$/.exec(verdict.trim())?.[1]
  return named && named !== 'unknown' ? named : null
}

/**
 * The tone for a cell, or null when the column does not hold a verdict and the
 * value should be left as plain text.
 */
/** A verdict can describe a row without ranking it. `excluded` says there was
 *  nothing to check, and reads as grey; `warning` says there is something worth
 *  noticing that nobody has to act on, and reads amber. Neither is ever a row's
 *  own status, so neither belongs in SEVERITY_TONE — they colour a cell. */
const VERDICT_TONE: Record<string, Tone> = { ...SEVERITY_TONE, warning: 'warn' }

export function toneOf(check: string, column: string, value: string): Tone | null {
  if (column === 'HITLstatus') return HITL[value] ?? 'na'
  const mapped = VERDICTS[check]?.[column]
  if (!mapped) return null
  const severity = mapped[splitVerdict(value).token]
  return severity ? VERDICT_TONE[severity] ?? 'warn' : 'warn'
}

/**
 * Two cell values, ordered the way a person reading the column would.
 *
 * Almost every column here is an identifier with digits in it — `deployNum`,
 * `ATAPL-58320-00003`, `CTDBPN106` — and plain string order puts 10 before 9
 * in all of them. Collation with `numeric` reads the digit runs as numbers, so
 * a column of reference designators sorts the way the eye expects.
 *
 * Empty goes last whichever way the column is pointed: a row with nothing in it
 * is not the smallest value, it is the absence of one, and burying it under the
 * rows that do have values is the useful behaviour in both directions.
 */
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

/** `direction` is 1 ascending, -1 descending. It is taken here rather than by
 *  negating the result, because negating would drag the empty rows to the top
 *  the moment a column is reversed. */
export function compareValues(a: unknown, b: unknown, direction: 1 | -1 = 1) {
  const left = a === null || a === undefined || a === '' ? null : a
  const right = b === null || b === undefined || b === '' ? null : b
  if (left === null || right === null) return left === right ? 0 : left === null ? 1 : -1
  if (typeof left === 'number' && typeof right === 'number') return direction * (left - right)
  if (typeof left === 'boolean' && typeof right === 'boolean') {
    return direction * (Number(left) - Number(right))
  }
  return direction * collator.compare(String(left), String(right))
}

/**
 * A difference, without the noise that subtracting two floats leaves behind.
 *
 * −0.5064574 less −0.4839777 is −0.0224797, which a machine writes as
 * −0.022479699999999936: seventeen digits, the last ten an artifact of binary
 * arithmetic rather than anything in either file. Printed in full they claim a
 * precision the vendor never published, and they made the table wide enough to
 * run over the panel beside it.
 *
 * Six significant figures, and here only — the recorded values either side of
 * it are what the two files hold and are shown exactly as they were read. A
 * spectrum reports its difference as a sentence rather than a number, so
 * anything that is not a number passes through untouched.
 */
export function readDifference(value: unknown): string {
  if (typeof value !== 'number') return value === null || value === undefined ? '—' : String(value)
  return Number.isFinite(value) ? Number(value.toPrecision(6)).toString() : String(value)
}

/**
 * An identifier split into the part every row shares and the part that picks
 * this one out. Bolding only the distinguishing half is what makes a column of
 * near-identical reference designators scannable.
 */
export function identity(column: string, value: string) {
  if (column === 'refDes') {
    // RS01SBPS-SF01A-4A-NUTNRA101 — the instrument is the last field.
    const cut = value.lastIndexOf('-')
    if (cut > 0) return { dim: value.slice(0, cut + 1), strong: value.slice(cut + 1) }
  }
  if (column === 'fileName') {
    // ATAPL-66662-00002__20160303.csv — the asset, then the calibration date.
    const cut = value.indexOf('__')
    if (cut > 0) return { dim: '', strong: value.slice(0, cut), tail: value.slice(cut) }
  }
  return null
}

/** The site a reference designator belongs to — its first field. */
export function siteOf(refDes: unknown) {
  return String(refDes ?? '').split('-')[0] ?? ''
}

/** The year a deployment began, from its ISO date. */
export function yearOf(date: unknown) {
  return String(date ?? '').slice(0, 4)
}
