import type { Row } from '~/store'

/**
 * Which reference designators a run covered, and when.
 *
 * The report lists every designator with a deployment, and the deployments
 * check carries a row per deployment with the year it went in the water. That
 * is enough to answer the question the list could not: not only what the array
 * holds, but what went in the water in a given season — and, more useful when
 * reading a cruise back, what did **not**.
 *
 * A designator absent from a year is the interesting half. It is either an
 * instrument nobody turned around that season, which is expected and worth
 * confirming, or one whose deployment never reached the sheets, which is not.
 */

export type Scope = 'all' | 'year' | 'absent' | 'now' | 'notNow'

/** A deployment with no end date is the one in the water. The report writes an
 *  absent date as the string `None`, which is not a date and is not nothing. */
const ENDED = new Set(['', 'none', 'nan', 'nat', 'null', 'undefined'])
export const isInTheWater = (row: Row) =>
  ENDED.has(String(row.deployEnd ?? '').trim().toLowerCase())

/** The open deployments of each designator, which is what it has in the water.
 *  More than one is a sheet error rather than two instruments — see the
 *  duplicate-asset check — and showing both is how a reader sees it. */
export function inTheWater(rows: Row[]) {
  const held = new Map<string, Row[]>()
  for (const row of rows) {
    if (!isInTheWater(row)) continue
    const name = String(row.refDes ?? '')
    if (!name) continue
    held.set(name, [...(held.get(name) ?? []), row])
  }
  return held
}

/** Designator -> the years it has a deployment in. */
export function yearsByDesignator(rows: Row[]) {
  const years = new Map<string, Set<string>>()
  for (const row of rows) {
    const name = String(row.refDes ?? '')
    const year = String(row.deployYear ?? '')
    if (!name || !year) continue
    const held = years.get(name) ?? new Set<string>()
    held.add(year)
    years.set(name, held)
  }
  return years
}

/** Every year the run saw a deployment in, newest first. */
export function deployYears(rows: Row[]) {
  const years = new Set<string>()
  for (const row of rows) {
    const year = String(row.deployYear ?? '')
    if (year) years.add(year)
  }
  return [...years].sort().reverse()
}

/** How many deployments a designator has in one year, for the count beside it. */
export function countsIn(rows: Row[], year: string) {
  const counts = new Map<string, number>()
  for (const row of rows) {
    if (String(row.deployYear ?? '') !== year) continue
    const name = String(row.refDes ?? '')
    if (name) counts.set(name, (counts.get(name) ?? 0) + 1)
  }
  return counts
}

/**
 * The designators one view shows.
 *
 * `all` is what the run covered, which is the list the report carries. Every
 * other view is measured against that same list, so each pair partitions it: a
 * designator is deployed in the year or it is not, is in the water now or it is
 * not.
 */
export function designatorsFor(all: string[], rows: Row[], scope: Scope, year: string) {
  if (scope === 'now' || scope === 'notNow') {
    const deployed = inTheWater(rows)
    return all.filter((name) => deployed.has(name) === (scope === 'now'))
  }
  if (scope === 'all' || !year) return [...all]
  const years = yearsByDesignator(rows)
  const inYear = (name: string) => years.get(name)?.has(year) ?? false
  return all.filter((name) => (scope === 'year' ? inYear(name) : !inYear(name)))
}
