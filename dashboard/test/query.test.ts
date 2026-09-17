import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { ALL, ATTENTION, matchesWhere } from '../app/query'
import type { Row } from '../app/store'

/** Only the two fields the severity filter reads. */
const row = (severity: Row['severity'], cleared: boolean): Row => ({ severity, cleared })

const attention = (candidate: Row) => matchesWhere(candidate, [], { severity: ATTENTION })

describe('what still needs a person', () => {
  it('leaves out a failing row a reviewer has cleared', () => {
    expect(attention(row('problem', true))).toBe(false)
  })

  it('leaves out a row that needs a person once a person has been', () => {
    expect(attention(row('review', true))).toBe(false)
  })

  it('keeps a failing row nobody has signed off', () => {
    expect(attention(row('problem', false))).toBe(true)
  })

  it('keeps a row waiting on a person', () => {
    expect(attention(row('review', false))).toBe(true)
  })

  it('leaves out rows that agree, or that nothing checked', () => {
    expect(attention(row('ok', false))).toBe(false)
    expect(attention(row('unchecked', false))).toBe(false)
  })

  /** The sign-off takes the row out of the queue; it does not erase what the
   *  check found. Every other view of the row still shows it. */
  it('still shows a cleared row under its own severity', () => {
    const cleared = row('problem', true)
    expect(matchesWhere(cleared, [], { severity: 'problem' })).toBe(true)
    expect(matchesWhere(cleared, [], { severity: ALL })).toBe(true)
    expect(matchesWhere(cleared, [], { cleared: 'cleared' })).toBe(true)
  })
})

describe('against the rows of a real run', () => {
  const REPORT = JSON.parse(
    readFileSync(new URL('./fixtures/report.json', import.meta.url), 'utf8'),
  ) as { checks: Record<string, { rows: Row[]; summary: Record<string, number> }> }

  /** The rail reads the report's count and the table filters the rows. They are
   *  the same number or the dashboard contradicts itself on one screen. */
  it('matches exactly the rows the report counted', () => {
    for (const check of Object.values(REPORT.checks)) {
      const matched = check.rows.filter((candidate) => attention(candidate))
      expect(matched.length).toBe(check.summary.attention)
    }
  })

  it('is smaller than the severities alone, because sign-offs have happened', () => {
    const calibrations = REPORT.checks.calibrations!
    const open = calibrations.rows.filter(
      (candidate) => candidate.severity === 'problem' || candidate.severity === 'review',
    )
    const waiting = calibrations.rows.filter((candidate) => attention(candidate))
    expect(waiting.length).toBeLessThan(open.length)
  })
})
