import Papa from 'papaparse'

/**
 * Folding sign-offs into the 2i-HITL sheets.
 *
 * Kept free of anything Nuxt so it can be tested on its own: this is the code
 * that rewrites the team's record of who checked what, and getting it wrong
 * would corrupt years of sign-offs.
 */

export const COLUMNS = ['Reviewers', 'DateReviewed', 'Status', 'HITLnotes'] as const

export interface Decision {
  key: string
  status: 'Clear' | 'NotClear'
  notes: string
}

/** The sheets have recorded dates as M/D/YY since 2019; a new row matches. */
export function hitlDate(when = new Date()) {
  return `${when.getMonth() + 1}/${when.getDate()}/${String(when.getFullYear()).slice(2)}`
}

/** Reviewers accumulate on a row rather than replace one another — a second
 *  person signing off is the point of the column. */
export function withReviewer(existing: string, initials: string) {
  const people = String(existing || '')
    .split(',')
    .map((person) => person.trim())
    .filter(Boolean)
  return people.includes(initials) ? people.join(',') : [...people, initials].join(',')
}

/** The sheet with these decisions folded in: an existing row is updated in
 *  place, a new one is appended, and every other row is left exactly as it was. */
export function applyDecisions(
  csv: string | null,
  keyColumn: string,
  decisions: Decision[],
  initials: string,
  when = new Date(),
) {
  const parsed = csv
    ? Papa.parse<Record<string, string>>(csv.trim(), { header: true, skipEmptyLines: true })
    : { data: [] as Record<string, string>[], meta: { fields: undefined } }
  const columns = parsed.meta?.fields?.length ? parsed.meta.fields : [keyColumn, ...COLUMNS]
  const rows = parsed.data

  for (const decision of decisions) {
    const existing = rows.find((row) => row[keyColumn] === decision.key)
    const target = existing ?? { [keyColumn]: decision.key }
    target.Reviewers = withReviewer(target.Reviewers ?? '', initials)
    target.DateReviewed = hitlDate(when)
    target.Status = decision.status
    target.HITLnotes = decision.notes
    if (!existing) rows.push(target)
  }

  // Surrounding whitespace in a note carries no meaning, and papaparse quotes
  // any field that has it — which would rewrite a row nobody touched. One row
  // in the sheet today has a note that is a single space.
  for (const row of rows) {
    if (typeof row.HITLnotes === 'string') row.HITLnotes = row.HITLnotes.trim()
  }

  // The sheets are LF; papaparse writes CRLF unless told otherwise, and a
  // changed line ending on every row would bury one sign-off in a 400-line diff.
  return Papa.unparse(rows, { columns, newline: '\n' }) + '\n'
}
