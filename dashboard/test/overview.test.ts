import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { byYear, niceMax, QUEUE, queueCounts } from '../app/overview'
import { matchesWhere } from '../app/query'
import { CHECKS, type Row } from '../app/store'

/** Real rows, sampled from a run to cover every verdict each check produces.
 *  Committed, because the published reports are not: a test that silently skips
 *  wherever the report is missing is a test that never runs in CI. */
const REPORT = JSON.parse(
  readFileSync(new URL('./fixtures/report.json', import.meta.url), 'utf8'),
) as { checks: Record<string, { rows: Row[] }> }

/** The facets the app itself declares — not a copy. A queue item that filters on
 *  a facet the store does not have would otherwise pass here and match nothing
 *  in the browser. */
const facetsOf = (check: string) => CHECKS.find((each) => each.key === check)?.facets ?? []

describe('what needs a person', () => {
  const queue = queueCounts(REPORT.checks, facetsOf)

  it('finds real work in real rows', () => {
    expect(queue.length).toBeGreaterThan(3)
    for (const item of queue) expect(item.count).toBeGreaterThan(0)
  })

  it('leaves out anything matching nothing', () => {
    expect(queueCounts({ calibrations: { rows: [] } }, facetsOf)).toEqual([])
  })

  it('ranks problems above rows that only need a person', () => {
    const worst = queue.map((item) => item.worst)
    const ranked = [...worst].sort(
      (a, b) =>
        ['problem', 'review', 'unchecked', 'ok'].indexOf(a) -
        ['problem', 'review', 'unchecked', 'ok'].indexOf(b),
    )
    expect(worst).toEqual(ranked)
  })

  it('never counts a row a reviewer already signed off', () => {
    for (const item of queue) {
      const rows = REPORT.checks[item.check]!.rows.filter((row) =>
        matchesWhere(row, facetsOf(item.check), item.where),
      )
      expect(rows.every((row) => !row.cleared)).toBe(true)
    }
  })

  /** The count beside a queue item and the table its link opens are the same
   *  clause, so this is the thing that would break if they ever diverged. */
  it('counts exactly the rows its link would show', () => {
    for (const item of queue) {
      const shown = REPORT.checks[item.check]!.rows.filter((row) =>
        matchesWhere(row, facetsOf(item.check), item.where),
      ).length
      expect(shown).toBe(item.count)
    }
  })

  it('names a check that exists in the report', () => {
    for (const item of QUEUE) expect(Object.keys(REPORT.checks)).toContain(item.check)
  })
})

describe('deployments by year', () => {
  const rows = [
    { severity: 'ok', cleared: false, deployDate: '2014-06-01T00:00:00' },
    { severity: 'problem', cleared: false, deployDate: '2014-08-01T00:00:00' },
    { severity: 'ok', cleared: false, deployDate: '2016-06-01T00:00:00' },
    { severity: 'ok', cleared: false, deployDate: '' },
  ] as Row[]
  const bars = byYear(rows, (row) => String(row.deployDate ?? '').slice(0, 4))

  it('groups by deploy year, oldest first', () => {
    expect(bars.map((bar) => bar.year)).toEqual(['2014', '2016'])
  })

  it('splits each year by severity', () => {
    expect(bars[0]).toMatchObject({
      total: 2,
      counts: { ok: 1, problem: 1, review: 0, unchecked: 0 },
    })
  })

  it('drops a row with no date rather than inventing a year for it', () => {
    expect(bars.reduce((total, bar) => total + bar.total, 0)).toBe(3)
  })
})

describe('the top gridline', () => {
  it('rounds up to something readable', () => {
    expect(niceMax(145)).toBe(200)
    expect(niceMax(96)).toBe(100)
    expect(niceMax(21)).toBe(25)
    expect(niceMax(1000)).toBe(1000)
  })

  it('never returns zero, which would divide the whole chart by nothing', () => {
    expect(niceMax(0)).toBe(1)
    expect(niceMax(-5)).toBe(1)
  })
})
