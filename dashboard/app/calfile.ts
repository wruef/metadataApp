/**
 * Correcting a coefficient in an asset-management calibration CSV.
 *
 * The columns are `serial,name,value,notes`, but an OPTAA's `CC_acwo` is a
 * bracketed list of eighty-three numbers written as one quoted field -- so a
 * line cannot be split on commas, and only a coefficient the run read as a
 * single number can be typed over. The CSV primitives are in `csv.ts`, which
 * the deployment sheets share.
 */

import { asField, columnIndex, formatList, holdsValue, matchNotation, scalar,
         splitLine } from '~/csv'

/** Where a calibration file lives in asset-management. */
export function calibrationPath(instrument: string, fileName: string) {
  return `calibration/${instrument}/${fileName}`
}

/** Every scalar coefficient the file records, by name. */
export function valuesByCoefficient(text: string) {
  const values: Record<string, number | null> = {}
  for (const line of text.split('\n').slice(1)) {
    if (!line.trim()) continue
    const fields = splitLine(line)
    if (fields.length < 3) continue
    values[fields[1]!.trim()] = scalar(fields[2]!)
  }
  return values
}

export interface Correction {
  coefficient: string
  /** The value the run read, which the file must still hold. A list where the
   *  coefficient is one: a DOSTA's `CC_conc_coef` is two numbers. */
  from: number | number[]
  to: number | number[]
  /** Replaces the `notes` column when given; the column is left alone when not. */
  note?: string
}

/**
 * The file with each correction applied.
 *
 * Throws rather than guessing. A coefficient the file does not carry, or one
 * whose value is no longer what the run read, means the record has moved on
 * since the report was produced -- and appending a line or overwriting a newer
 * value would silently revert somebody else's work.
 */
export function applyCorrections(text: string, corrections: Correction[]) {
  const wanted = new Map(corrections.map((each) => [each.coefficient, each]))
  const seen = new Set<string>()
  const lines = text.split('\n')
  const column = columnIndex(lines[0] ?? '')
  const valueAt = column.value ?? 2
  const notesAt = column.notes ?? 3

  const rewritten = lines.map((line, index) => {
    if (!index || !line.trim()) return line
    const fields = splitLine(line)
    const correction = wanted.get(fields[1]?.trim() ?? '')
    if (!correction) return line
    const held = fields[valueAt] ?? ''
    if (!holdsValue(held, correction.from)) {
      // The fork is checked against upstream before this runs, so a value that
      // is not the one the run read means upstream itself has moved: the report
      // on screen is older than the file it is reporting on.
      throw new Error(
        `${correction.coefficient} now reads ${held.trim()} in asset-management, not `
        + `${correction.from} as the run read it. Run the checks again before correcting this.`,
      )
    }
    seen.add(correction.coefficient)
    if (Array.isArray(correction.to)) {
      const written = formatList(held, correction.to)
      if (written === null) {
        throw new Error(
          `${correction.coefficient} is ${(correction.from as number[]).length} values in the file `
          + `and ${correction.to.length} were given. A coefficient cannot change length here.`,
        )
      }
      fields[valueAt] = written
    } else {
      fields[valueAt] = matchNotation(held, String(correction.to))
    }
    if (correction.note !== undefined && fields.length > notesAt) {
      fields[notesAt] = asField(correction.note)
    }
    return fields.join(',')
  })

  const missing = corrections.filter((each) => !seen.has(each.coefficient))
  if (missing.length) {
    throw new Error(
      `Your fork's copy of this file carries no ${missing.map((each) => each.coefficient).join(', ')}.`,
    )
  }
  return rewritten.join('\n')
}

/** What the pull request is called: the file, and what changed in it. */
export function correctionTitle(fileName: string, corrections: Correction[]) {
  const named = corrections.length === 1
    ? corrections[0]!.coefficient
    : `${corrections.length} coefficients`
  return `Correct ${named} in ${fileName}`
}

/**
 * One file's worth of review: every value before and after it.
 *
 * A section rather than a whole body, because a batch carries several files and
 * each one still has to be readable on its own. What closes the pull request --
 * who proposed it, and what merging it would change -- is said once by the
 * batch, not once per file.
 */
export function correctionSection(path: string, corrections: Correction[]) {
  const rows = corrections.map(
    (each) => `| \`${each.coefficient}\` | ${each.from} | ${each.to} | ${each.note ?? ''} |`,
  )
  return [
    `\`${path}\``,
    '',
    '| coefficient | was | now | note |',
    '|---|---|---|---|',
    ...rows,
  ].join('\n')
}
