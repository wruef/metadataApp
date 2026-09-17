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
  problem: 'crit',
  review: 'warn',
  unchecked: 'na',
  cleared: 'warn',
  ok: 'ok',
}

/**
 * How a whole row reads, which a sign-off splits in two.
 *
 * A reviewer clearing a row that also agrees with the record has confirmed a
 * pass: green, like any other agreement. A reviewer clearing a row that
 * disagrees has judged the disagreement acceptable — amber, because the
 * disagreement is still there. Three signed-off calibrations turned out to hold
 * real transcription errors, so this never goes green over a finding.
 */
export function rowTone(severity: Severity, finding?: Severity): Tone {
  if (severity !== 'cleared') return SEVERITY_TONE[severity]
  return !finding || finding === 'ok' ? 'ok' : 'warn'
}

/**
 * verdict -> severity, per check and field.
 *
 * This mirrors `SEVERITY` in `src/rca_metadata/report.py`, which is the source
 * of truth: the run uses it to rank rows, and this copy only decides a colour.
 * A verdict missing here reads as `warn`, the same way the run counts an
 * unmapped verdict as `review` — a new verdict draws the eye rather than
 * quietly passing.
 */
export const VERDICTS: Record<string, Record<string, Record<string, Severity>>> = {
  sensorBulk: {
    verdict: {
      MATCH: 'ok',
      FORMAT_MATCH: 'review',
      MISMATCH: 'problem',
      MISSING_FROM_RCA_LIST: 'review',
      MISSING_FROM_SENSOR_BULK: 'problem',
      NO_BULK_SERIAL: 'unchecked',
    },
  },
  calibrations: {
    vendorMatch: {
      COMPARED: 'ok',
      COMPARED_XML: 'ok',
      MISMATCH: 'problem',
      MISSING_COEFFICIENT: 'problem',
      NO_VENDOR_FILE: 'problem',
      CONSTANT_MISMATCH: 'review',
      PDF_NOTCOMPARED: 'unchecked',
      FORMAT_NOTCOMPARED: 'unchecked',
      NOTCOMPARED: 'unchecked',
      NAN: 'unchecked',
    },
    calRepo_check: { MATCH: 'ok', NOMATCH: 'review' },
    fileParse: { SUCCESS_TYPE1: 'ok', SUCCESS_TYPE2: 'ok', FAIL: 'problem' },
    serialNumber: {
      MATCH_SENSORBULK: 'ok',
      MISMATCH_SENSORBULK: 'problem',
      MULTIPLE: 'problem',
      PARSING_ERROR: 'problem',
      NOTFOUND_FILE: 'unchecked',
      NOTFOUND_SENSORBULK: 'unchecked',
    },
    duplicateCoeff: {
      NONE: 'ok',
      DUPLICATES_IDENTICAL: 'ok',
      DUPLICATES_NOTIDENTICAL: 'problem',
    },
  },
  deploymentSheets: {
    verdict: {
      SENSOR_NOT_IN_BULK: 'problem',
      MOORING_NOT_IN_PLATFORM_BULK: 'problem',
      CRUISE_NOT_IN_CRUISE_LIST: 'problem',
      DUPLICATE_ASSET_IN_DEPLOYMENT: 'problem',
    },
  },
  deployments: {
    verificationStatus: { VERIFIED: 'ok', RAW_SN_POSSIBLE: 'review', NOT_VERIFIED: 'review' },
    rawFile_verify: {
      MATCH: 'ok',
      MISMATCH: 'problem',
      NO_FILE: 'review',
      NO_SN: 'unchecked',
      NAN: 'unchecked',
    },
    image_verify: { MATCH: 'ok', MISMATCH: 'problem', NAN: 'unchecked' },
    calFile_verify: {
      VALID_FILE: 'ok',
      NO_VALID_FILE: 'problem',
      VALID_FILE_CAL_OLDER_THAN_15MONTHS: 'review',
      none: 'unchecked',
      NAN: 'unchecked',
    },
  },
  positions: {
    verdict: {
      MATCH: 'ok',
      MISMATCH: 'problem',
      NEEDS_HITL: 'review',
      NO_POSITION: 'review',
      NO_POSITION_NAME: 'review',
      BAD_POSITION_RECORD: 'review',
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
export function splitVerdict(value: string) {
  const [token, ...rest] = value.split(':')
  return { token: (token ?? '').trim(), detail: rest.join(':').trim() }
}

/**
 * The tone for a cell, or null when the column does not hold a verdict and the
 * value should be left as plain text.
 */
export function toneOf(check: string, column: string, value: string): Tone | null {
  if (column === 'HITLstatus') return HITL[value] ?? 'na'
  const mapped = VERDICTS[check]?.[column]
  if (!mapped) return null
  const severity = mapped[splitVerdict(value).token]
  return severity ? SEVERITY_TONE[severity] : 'warn'
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
