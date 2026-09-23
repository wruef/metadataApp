import { describe, expect, it } from 'vitest'

import { countsIn, deployYears, designatorsFor, inTheWater, isInTheWater, yearsByDesignator }
  from '../app/designators'
import type { Row } from '../app/store'

/**
 * Which designators a run covered, and when.
 *
 * The half that earns this is the absent list: a designator with no deployment
 * in a season is either an instrument nobody turned around, which is expected,
 * or one whose deployment never reached the sheets, which is not. Reading a
 * cruise back is exactly when you want to know which.
 */
const row = (refDes: string, deployYear: number): Row =>
  ({ refDes, deployYear, severity: 'ok', cleared: false })

const ROWS = [
  row('CE02SHBP-LJ01D-06-CTDBPN106', 2025),
  row('CE02SHBP-LJ01D-06-CTDBPN106', 2026),
  row('CE02SHBP-LJ01D-06-CTDBPN106', 2026),
  row('RS01SBPS-PC01A-4B-PHSENA102', 2025),
  row('RS03AXPS-SF03A-2D-PHSENA301', 2024),
]

const ALL = [
  'CE02SHBP-LJ01D-06-CTDBPN106',
  'RS01SBPS-PC01A-4B-PHSENA102',
  'RS03AXPS-SF03A-2D-PHSENA301',
  'RS03INT1-MJ03C-09-TRHPHA302',
]

describe('the years a run saw', () => {
  it('lists them newest first', () => {
    expect(deployYears(ROWS)).toEqual(['2026', '2025', '2024'])
  })

  it('gathers the years each designator went in the water', () => {
    expect(yearsByDesignator(ROWS).get('CE02SHBP-LJ01D-06-CTDBPN106'))
      .toEqual(new Set(['2025', '2026']))
  })

  it('leaves out a row with no year rather than inventing one', () => {
    expect(deployYears([{ refDes: 'X', severity: 'ok', cleared: false } as Row])).toEqual([])
  })
})

describe('which designators a view shows', () => {
  it('shows everything the run covered for all time', () => {
    expect(designatorsFor(ALL, ROWS, 'all', '2026')).toEqual(ALL)
  })

  it('shows what went in the water that year', () => {
    expect(designatorsFor(ALL, ROWS, 'year', '2026'))
      .toEqual(['CE02SHBP-LJ01D-06-CTDBPN106'])
  })

  it('shows what did not', () => {
    expect(designatorsFor(ALL, ROWS, 'absent', '2026')).toEqual([
      'RS01SBPS-PC01A-4B-PHSENA102',
      'RS03AXPS-SF03A-2D-PHSENA301',
      // Covered by the run and deployed in no year at all, which is the case
      // most worth seeing: it has rows somewhere but none that start.
      'RS03INT1-MJ03C-09-TRHPHA302',
    ])
  })

  it('puts every designator in one of the two, and never both', () => {
    for (const year of deployYears(ROWS)) {
      const inYear = designatorsFor(ALL, ROWS, 'year', year)
      const absent = designatorsFor(ALL, ROWS, 'absent', year)
      expect([...inYear, ...absent].sort()).toEqual([...ALL].sort())
      expect(inYear.filter((name) => absent.includes(name))).toEqual([])
    }
  })

  it('falls back to everything when no year is chosen yet', () => {
    expect(designatorsFor(ALL, ROWS, 'year', '')).toEqual(ALL)
  })
})

describe('how many deployments a designator had that year', () => {
  it('counts a turnaround as two', () => {
    expect(countsIn(ROWS, '2026').get('CE02SHBP-LJ01D-06-CTDBPN106')).toBe(2)
    expect(countsIn(ROWS, '2025').get('CE02SHBP-LJ01D-06-CTDBPN106')).toBe(1)
  })

  it('has nothing for a designator absent that year', () => {
    expect(countsIn(ROWS, '2026').get('RS01SBPS-PC01A-4B-PHSENA102')).toBeUndefined()
  })
})

describe('what the sheets say is in the water', () => {
  const water = (refDes: string, deployNum: number, deployEnd: string | null): Row =>
    ({ refDes, deployNum, deployYear: 2026, deployEnd, deployDate: '2026-08-09T00:00:00',
       AssetID: `ATAPL-${deployNum}`, severity: 'ok', cleared: false }) as Row

  const ROWS = [
    water('CE02SHBP-LJ01D-06-CTDBPN106', 12, '2026-08-09T00:00:00'),
    water('CE02SHBP-LJ01D-06-CTDBPN106', 13, 'None'),
    water('RS01SBPS-PC01A-4B-PHSENA102', 9, '2025-07-01T00:00:00'),
  ]
  const ALL = ['CE02SHBP-LJ01D-06-CTDBPN106', 'RS01SBPS-PC01A-4B-PHSENA102']

  it('reads an absent end date however the report spells it', () => {
    // The report writes it as the string `None`, which is not a date and is not
    // nothing. Treating that as an end date put everything on the seafloor.
    for (const value of ['None', '', 'nan', 'NaT', null, undefined]) {
      expect(isInTheWater({ deployEnd: value } as Row)).toBe(true)
    }
    expect(isInTheWater({ deployEnd: '2026-08-09T00:00:00' } as Row)).toBe(false)
  })

  it('shows only what has a deployment still open', () => {
    expect(designatorsFor(ALL, ROWS, 'now', '')).toEqual(['CE02SHBP-LJ01D-06-CTDBPN106'])
  })

  it('shows the rest as not in the water', () => {
    expect(designatorsFor(ALL, ROWS, 'notNow', '')).toEqual(['RS01SBPS-PC01A-4B-PHSENA102'])
  })

  it('puts every designator in one of the two, and never both', () => {
    const now = designatorsFor(ALL, ROWS, 'now', '')
    const notNow = designatorsFor(ALL, ROWS, 'notNow', '')
    expect([...now, ...notNow].sort()).toEqual([...ALL].sort())
    expect(now.filter((name) => notNow.includes(name))).toEqual([])
  })

  it('names the deployment down there, and both when a designator has two', () => {
    // Two open deployments of one designator is a sheet error rather than two
    // instruments, and the reader has to see both to fix it.
    const twice = [...ROWS, water('CE02SHBP-LJ01D-06-CTDBPN106', 14, 'None')]
    expect(inTheWater(twice).get('CE02SHBP-LJ01D-06-CTDBPN106')?.map((r) => r.deployNum))
      .toEqual([13, 14])
  })

  it('ignores the year when asked what is in the water', () => {
    expect(designatorsFor(ALL, ROWS, 'now', '2019')).toEqual(['CE02SHBP-LJ01D-06-CTDBPN106'])
  })
})
