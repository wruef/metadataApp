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
 * The value as a single number, or null when it is not one.
 *
 * Null for a bracketed list, for a `SheetRef:` pointer, and for the literal
 * `N/A` a profiler carries as its deployment depth.
 */
export function scalar(value: string) {
  const text = value.trim()
  if (!text || text.startsWith('"') || text.startsWith('[')) return null
  const parsed = Number(text)
  return Number.isFinite(parsed) ? parsed : null
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

/**
 * A bracketed list field, split into its raw elements.
 *
 * Raw rather than parsed, because writing one back has to keep each element in
 * the notation it already used: a DOSTA writes `"[-9.765852e-01, 1.081678]"`,
 * one element in exponential form and one not.
 */
export function listParts(value: string) {
  const text = value.trim()
  const quoted = text.startsWith('"') && text.endsWith('"')
  const bare = (quoted ? text.slice(1, -1) : text).trim()
  if (!bare.startsWith('[') || !bare.endsWith(']')) return null
  const body = bare.slice(1, -1)
  return { quoted, parts: body.trim() ? body.split(',') : [] }
}

/** The numbers in a bracketed list, or null when it is not one. */
export function parseList(value: string) {
  const held = listParts(value)
  if (!held) return null
  const numbers = held.parts.map((part) => Number(part.trim()))
  return numbers.every((number) => Number.isFinite(number)) ? numbers : null
}

/**
 * A corrected list written the way the field already writes it.
 *
 * Same brackets, same quoting, same spacing, and each element in the notation
 * its predecessor used. Null when the replacement is a different length,
 * because a coefficient that is two numbers cannot become three by way of a
 * text box.
 */
export function formatList(existing: string, values: number[]) {
  const held = listParts(existing)
  if (!held || held.parts.length !== values.length) return null
  const written = held.parts.map((part, index) => {
    const lead = /^\s*/.exec(part)![0]
    return lead + matchNotation(part.trim(), String(values[index]))
  })
  const body = `[${written.join(',')}]`
  return held.quoted ? `"${body}"` : body
}

/**
 * Whether the file still holds the value a run read.
 *
 * Numeric where both sides are numbers, because the two spell the same value
 * differently -- a file writing `-5.064574e-001` against a report carrying
 * `-0.5064574`. Element by element for a list. Exact text otherwise, which is
 * what compares a profiler's literal `N/A`.
 */
export function holdsValue(inFile: string, asRead: string | number | number[]) {
  if (Array.isArray(asRead)) {
    const held = parseList(inFile)
    return held !== null && held.length === asRead.length
      && held.every((value, index) => value === asRead[index])
  }
  const held = scalar(inFile)
  const wanted = scalar(String(asRead))
  if (held !== null && wanted !== null) return held === wanted
  return inFile.trim() === String(asRead).trim()
}

/** Where a column sits, by name, from the header line. */
export function columnIndex(header: string) {
  const index: Record<string, number> = {}
  splitLine(header).forEach((name, position) => { index[name.trim()] = position })
  return index
}
