import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { SEVERITY_TONE } from '../app/display'
import { ALL, matchesWhere } from '../app/query'
import type { Row, Severity } from '../app/store'

/** Only the fields the severity filter and the tone rule read. */
const row = (severity: Severity, finding?: Severity): Row => ({
  severity,
  finding,
  cleared: severity === 'cleared',
})

const needsVerifying = (candidate: Row) =>
  matchesWhere(candidate, [], { severity: 'verification' })

describe('what still needs verifying', () => {
  it('leaves out a signed-off row, whatever its checks found', () => {
    expect(needsVerifying(row('cleared', 'verification'))).toBe(false)
    expect(needsVerifying(row('cleared', 'ok'))).toBe(false)
  })

  it('keeps a row nobody has signed off', () => {
    expect(needsVerifying(row('verification'))).toBe(true)
  })

  it('leaves out rows that agree, or that nothing checked', () => {
    expect(needsVerifying(row('ok'))).toBe(false)
    expect(needsVerifying(row('unchecked'))).toBe(false)
  })

  /** A report published before sign-offs became a category of their own still
   *  carries them as work. The filter has to drop those too, or an old run
   *  reads as having work that somebody already did. */
  it('leaves out a cleared row in a report that predates the category', () => {
    expect(
      matchesWhere({ severity: 'verification', cleared: true }, [], { severity: 'verification' }),
    ).toBe(false)
  })

  /** A filtered view is a URL somebody sent to whoever owns the instrument.
   *  Links written before the two categories became one should still land on
   *  the rows they were about. */
  it('still answers to the name the two categories had together', () => {
    expect(matchesWhere(row('verification'), [], { severity: 'attention' })).toBe(true)
    expect(matchesWhere(row('ok'), [], { severity: 'attention' })).toBe(false)
  })

  it('still shows a signed-off row under its own category', () => {
    const cleared = row('cleared', 'verification')
    expect(matchesWhere(cleared, [], { severity: 'cleared' })).toBe(true)
    expect(matchesWhere(cleared, [], { severity: ALL })).toBe(true)
    expect(matchesWhere(cleared, [], { cleared: 'cleared' })).toBe(true)
  })
})

describe('how a signed-off row reads', () => {
  /** A sign-off is a person saying they have been and this row is settled, and
   *  that is as settled as a row gets. What they judged is not hidden: the
   *  finding keeps its own badge beside it, in its own colour. */
  it('is green, whatever the checks found', () => {
    expect(SEVERITY_TONE.cleared).toBe('ok')
  })

  it('leaves every other category coloured by itself', () => {
    expect(SEVERITY_TONE.verification).toBe('warn')
    expect(SEVERITY_TONE.ok).toBe('ok')
    expect(SEVERITY_TONE.unchecked).toBe('na')
    expect(SEVERITY_TONE.excluded).toBe('na')
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
      const matched = check.rows.filter((candidate) => needsVerifying(candidate))
      expect(matched.length).toBe(check.summary.verification)
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
