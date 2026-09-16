import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { applyDecisions, hitlDate, withReviewer } from '../app/hitl'

/** The real sheet, so the tests are against the format the team actually keeps. */
const REAL = readFileSync(
  new URL('../../2i_HITL/2i_HITL_calibrationVerification.csv', import.meta.url),
  'utf8',
)
const KEY = 'githubFile'
const WHEN = new Date('2026-09-15T12:00:00')

function rows(csv: string) {
  return csv.trim().split('\n')
}

describe('reviewers', () => {
  it('adds a reviewer alongside the people already there', () => {
    expect(withReviewer('KB,WR', 'JD')).toBe('KB,WR,JD')
  })

  it('does not record the same person twice', () => {
    expect(withReviewer('KB,WR', 'WR')).toBe('KB,WR')
  })

  it('handles a row nobody has signed yet', () => {
    expect(withReviewer('', 'WR')).toBe('WR')
  })
})

describe('dates', () => {
  it('matches the M/D/YY the sheets have used since 2019', () => {
    expect(hitlDate(new Date('2026-05-02T00:00:00'))).toBe('5/2/26')
  })
})

describe('applying decisions to the real sheet', () => {
  it('leaves every other row untouched', () => {
    const before = rows(REAL)
    const after = rows(applyDecisions(REAL, KEY, [
      { key: 'a-file-that-is-not-there.csv', status: 'Clear', notes: 'new' },
    ], 'WR', WHEN))
    expect(after.length).toBe(before.length + 1)
    // Three legacy rows carry notes with surrounding whitespace. They normalise
    // once, on the first sign-off, and are stable afterwards — the alternative
    // is papaparse quoting them, which churns the same rows and reads worse.
    const changed = before.filter((line, index) => line !== after[index])
    expect(changed).toHaveLength(3)
    expect(changed.every((line) => line.includes('Clear, '))).toBe(true)
  })

  it('normalises notes with surrounding whitespace rather than quoting them', () => {
    const after = applyDecisions(REAL, KEY, [], 'WR', WHEN)
    expect(after).toContain('ATAPL-58337-00004__20231102.csv,"JD,WR",7/1/24,Clear,\n')
    expect(after).toContain('Clear,values manually added from seabird correction matrix')
    expect(after).not.toContain('Clear," "')
  })

  it('is stable once those rows have normalised', () => {
    const once = applyDecisions(REAL, KEY, [], 'WR', WHEN)
    expect(applyDecisions(once, KEY, [], 'WR', WHEN)).toBe(once)
  })

  it('writes the same line endings the sheets use', () => {
    expect(applyDecisions(REAL, KEY, [], 'WR', WHEN)).not.toContain('\r')
  })

  it('appends a row for a file with no sign-off yet', () => {
    const after = applyDecisions(REAL, KEY, [
      { key: 'ATAPL-67627-00001__20150423.csv', status: 'NotClear', notes: 'nine coefficients differ' },
    ], 'WR', WHEN)
    const line = rows(after).at(-1)!
    expect(line).toContain('ATAPL-67627-00001__20150423.csv')
    expect(line).toContain('NotClear')
    expect(line).toContain('9/15/26')
  })

  it('updates an existing row in place rather than duplicating it', () => {
    const existing = REAL.split('\n')[1]!.split(',')[0]!
    const after = applyDecisions(REAL, KEY, [
      { key: existing, status: 'Clear', notes: 'rechecked' },
    ], 'JD', WHEN)
    expect(rows(after).length).toBe(rows(REAL).length)
    expect(rows(after).filter((line) => line.startsWith(existing)).length).toBe(1)
    expect(after).toContain('rechecked')
  })

  it('adds the new reviewer to the people already on an existing row', () => {
    const existing = REAL.split('\n')[1]!.split(',')[0]!
    const after = applyDecisions(REAL, KEY, [{ key: existing, status: 'Clear', notes: '' }], 'JD', WHEN)
    const line = rows(after).find((row) => row.startsWith(existing))!
    expect(line).toContain('"KB,WR,JD"')
  })

  it('keeps the header and column order', () => {
    const after = applyDecisions(REAL, KEY, [{ key: 'x.csv', status: 'Clear', notes: '' }], 'WR', WHEN)
    expect(rows(after)[0]).toBe(rows(REAL)[0])
  })

  it('quotes a note containing commas so the row still parses', () => {
    const after = applyDecisions(REAL, KEY, [
      { key: 'x.csv', status: 'Clear', notes: 'checked serial, and the cal date' },
    ], 'WR', WHEN)
    const line = rows(after).at(-1)!
    expect(line).toContain('"checked serial, and the cal date"')
    expect(line.split(',').length).toBeGreaterThan(4)
  })

  it('starts a sheet from nothing when the fork has none', () => {
    const after = applyDecisions(null, KEY, [{ key: 'x.csv', status: 'Clear', notes: '' }], 'WR', WHEN)
    expect(rows(after)[0]).toBe('githubFile,Reviewers,DateReviewed,Status,HITLnotes')
    expect(rows(after).length).toBe(2)
  })
})
