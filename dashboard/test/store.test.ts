import { describe, expect, it } from 'vitest'

import { comparisonFor, type Comparison, type Report } from '../app/store'

const report = { runAt: '2026-09-18T15:50:55+00:00' } as Report

const comparison = (currentRunAt: string) =>
  ({ currentRunAt, baselineRunAt: '2026-09-17T00:00:00+00:00' } as Comparison)

describe('which comparison belongs to a run', () => {
  it('is the one produced for that run', () => {
    const mine = comparison('2026-09-18T15:50:55+00:00')
    expect(comparisonFor(report, mine)).toBe(mine)
  })

  it('refuses one produced for a different run', () => {
    // A production run given no baseline leaves the previous run's comparison
    // in place. Shown, it would read as this run's changes.
    expect(comparisonFor(report, comparison('2026-09-17T15:36:23+00:00'))).toBeNull()
  })

  it('is nothing when either side is missing', () => {
    expect(comparisonFor(report, null)).toBeNull()
    expect(comparisonFor(null, comparison('2026-09-18T15:50:55+00:00'))).toBeNull()
  })
})
