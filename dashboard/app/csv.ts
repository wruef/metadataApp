/**
 * Reading and rewriting one field of a CSV that somebody else owns.
 *
 * Shared by the two files this dashboard proposes changes to: an
 * asset-management calibration file and an asset-management deployment sheet.
 * Both are hand-maintained records, so the rule for both is that everything the
 * edit did not touch comes back byte for byte -- reformatting a file while
 * correcting a digit in it buries the correction in a diff nobody can review.
 *
 * Nuxt-free so it can be tested against the real formats.
 */

/** Comma-separated, honouring double quotes, keeping the quotes in the field so
 *  that rejoining reproduces the line exactly. */
export function splitLine(line: string) {
  const fields: string[] = []
  let field = ''
  let quoted = false
  for (const character of line) {
    if (character === '"') {
      quoted = !quoted
      field += character
    } else if (character === ',' && !quoted) {
      fields.push(field)
      field = ''
    } else {
      field += character
    }
  }
  fields.push(field)
  return fields
}

/** A value needs quoting once it carries a comma, a quote or a newline. */
export function asField(value: string) {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value
}

/**
 * The value as a number, or null when it is not one number.
 *
 * Null for an OPTAA's bracketed list of eighty-three coefficients, for a
 * `SheetRef:` pointer, and for the literal `N/A` a profiler carries as its
 * deployment depth. A text box is not a way to edit any of those.
 */
export function scalar(value: string) {
  const text = value.trim()
  if (!text || text.startsWith('"') || text.startsWith('[')) return null
  const parsed = Number(text)
  return Number.isFinite(parsed) ? parsed : null
}

/**
 * Whether the file still holds the value a run read.
 *
 * Numeric where both sides are numbers, because the two spell the same value
 * differently -- a file writing `-5.064574e-001` against a report carrying
 * `-0.5064574`. Exact text otherwise, which is what compares a profiler's
 * literal `N/A`.
 */
export function holdsValue(inFile: string, asRead: string | number) {
  const held = scalar(inFile)
  const wanted = scalar(String(asRead))
  if (held !== null && wanted !== null) return held === wanted
  return inFile.trim() === String(asRead).trim()
}

const EXPONENT = /^[-+]?\d*\.?(\d*)[eE][-+](\d+)$/

/**
 * A new value written the way the line already writes its numbers.
 *
 * The calibration files write `-5.064574e-001` where a vendor publishes
 * `-0.4839777`. Both are the same number, and either would load, but a
 * correction that also switches notation reads as a rewritten line rather than
 * a changed digit. Anything not in exponential form is left as it was typed.
 */
export function matchNotation(existing: string, value: string) {
  const shape = EXPONENT.exec(existing.trim())
  const parsed = scalar(value)
  if (!shape || parsed === null) return value
  const [digits, power] = parsed.toExponential(shape[1]!.length).split('e')
  const sign = power!.startsWith('-') ? '-' : '+'
  return `${digits}e${sign}${power!.replace(/^[-+]/, '').padStart(shape[2]!.length, '0')}`
}

/** Where a column sits, by name, from the header line. */
export function columnIndex(header: string) {
  const index: Record<string, number> = {}
  splitLine(header).forEach((name, position) => { index[name.trim()] = position })
  return index
}
