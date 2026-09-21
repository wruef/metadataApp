import type { Facet, Row } from '~/store'

/**
 * One predicate for "which rows am I looking at".
 *
 * The check table filters with it, the overview counts with it, and a link from
 * the overview carries it in the URL. That matters: a queue saying *43 rows* has
 * to land on a table showing 43 rows, and it will only keep doing that if both
 * numbers come from the same function.
 */

export const ALL = 'all'

/** What schema 2 called the pair of severities that are now one. A filtered
 *  view is a URL someone sent to whoever owns the instrument, and links written
 *  before the merge should still land on the rows they were about. */
const LEGACY_ATTENTION = 'attention'

/**
 * `severity`, `cleared` and `q`, plus one entry per facet key.
 *
 * Written as a flat map because it is also the page's query string: a filtered
 * view is a URL someone can send to whoever owns the instrument.
 */
export type Where = Record<string, string | undefined>

export function matchesWhere(
  row: Row,
  facets: readonly Facet[],
  where: Where,
  columns: readonly string[] = [],
) {
  const asked = where.severity || ALL
  const severity = asked === LEGACY_ATTENTION ? 'verification' : asked
  if (severity === 'verification') {
    // A sign-off is a person having dealt with the row, so a cleared row is not
    // waiting on anyone — even though the failing check stays on it, and the
    // 'Cleared only' filter and the badge both still show it. A current run
    // puts such a row in the cleared category itself, but one published before
    // that category existed still carries it as work, and an old run must not
    // read as having work somebody already did.
    if (row.cleared) return false
  }
  if (severity !== ALL && row.severity !== severity) return false

  if (where.cleared === 'cleared' && !row.cleared) return false
  if (where.cleared === 'open' && row.cleared) return false

  for (const facet of facets) {
    const wanted = where[facet.key]
    if (wanted && facet.of(row) !== wanted) return false
  }

  const term = (where.q ?? '').trim().toLowerCase()
  if (term && !columns.some((column) => String(row[column] ?? '').toLowerCase().includes(term))) {
    return false
  }
  return true
}
