import type { Facet, Row } from '~/store'

/**
 * One predicate for "which rows am I looking at".
 *
 * The check table filters with it, the overview counts with it, and a link from
 * the overview carries it in the URL. That matters: a queue saying *43 rows* has
 * to land on a table showing 43 rows, and it will only keep doing that if both
 * numbers come from the same function.
 */

/** Everything a person still has to deal with. */
export const ATTENTION = 'attention'
export const ALL = 'all'

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
  const severity = where.severity || ALL
  if (severity === ATTENTION) {
    if (row.severity !== 'problem' && row.severity !== 'review') return false
  } else if (severity !== ALL && row.severity !== severity) return false

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
