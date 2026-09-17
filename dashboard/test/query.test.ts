import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { rowTone } from '../app/display'
import { ALL, ATTENTION, matchesWhere } from '../app/query'
import type { Row, Severity } from '../app/store'

/** Only the fields the severity filter and the tone rule read. */
const row = (severity: Severity, finding?: Severity): Row => ({
  severity,
  finding,
  cleared: severity === 'cleared',
})

const attention = (candidate: Row) => matchesWhere(candidate, [], { severity: ATTENTION })

describe('what still needs a person', () => {
  it('leaves out a signed-off row, whatever its checks found', () => {
    expect(attention(row('cleared', 'problem'))).toBe(false)
    expect(attention(row('cleared', 'review'))).toBe(false)
    expect(attention(row('cleared', 'ok'))).toBe(false)
  })

  it('keeps a failing row nobody has signed off', () => {
    expect(attention(row('problem'))).toBe(true)
  })

  it('keeps a row waiting on a person', () => {
    expect(attention(row('review'))).toBe(true)
  })

  it('leaves out rows that agree, or that nothing checked', () => {
    expect(attention(row('ok'))).toBe(false)
    expect(attention(row('unchecked'))).toBe(false)
  })

  /** A report published before sign-offs became a category of their own still
   *  carries them as problems. The filter has to drop those too, or an old run
   *  reads as having work that somebody already did. */
  it('leaves out a cleared row in a report that predates the category', () => {
    expect(matchesWhere({ severity: 'problem', cleared: true }, [], { severity: ATTENTION })).toBe(
      false,
    )
  })

  it('still shows a signed-off row under its own category', () => {
    const cleared = row('cleared', 'problem')
    expect(matchesWhere(cleared, [], { severity: 'cleared' })).toBe(true)
    expect(matchesWhere(cleared, [], { severity: ALL })).toBe(true)
    expect(matchesWhere(cleared, [], { cleared: 'cleared' })).toBe(true)
  })
})

describe('how a signed-off row reads', () => {
  /** A reviewer clearing a row that also agrees has confirmed a pass. One
   *  clearing a row that disagrees has judged the disagreement acceptable, and
   *  the disagreement is still there — three of them turned out to be real
   *  transcription errors. */
  it('is green over an agreement and amber over a disagreement', () => {
    expect(rowTone('cleared', 'ok')).toBe('ok')
    expect(rowTone('cleared', 'problem')).toBe('warn')
    expect(rowTone('cleared', 'review')).toBe('warn')
    expect(rowTone('cleared', 'unchecked')).toBe('warn')
  })

  it('leaves every other category coloured by itself', () => {
    expect(rowTone('problem')).toBe('crit')
    expect(rowTone('review')).toBe('warn')
    expect(rowTone('ok')).toBe('ok')
    expect(rowTone('unchecked')).toBe('na')
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

  it('puts every signed-off row in the cleared category and nowhere else', () => {
    for (const check of Object.values(REPORT.checks)) {
      for (const candidate of check.rows) {
        expect(candidate.cleared).toBe(candidate.severity === 'cleared')
      }
    }
  })

  it('counts a signed-off row as verified', () => {
    for (const check of Object.values(REPORT.checks)) {
      const verified = check.rows.filter(
        (candidate) => candidate.severity === 'ok' || candidate.severity === 'cleared',
      )
      expect(verified.length).toBe(check.summary.verified)
    }
  })
})
