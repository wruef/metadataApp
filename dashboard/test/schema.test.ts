import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { CHECKS, SEVERITIES, type Check, type Report, type Row } from '../app/store'
import { HITL_SHEETS, hitlKeyOf, type SheetKey } from '../app/signoff'

/**
 * The report contract, checked from the dashboard's side.
 *
 * `schema/report.json` names what a run report contains, and `tests/
 * test_schema.py` checks the same file against the same committed report. Until
 * they existed the emitter and these types could drift in silence: a renamed
 * field became blank cells in a published table with nothing failing anywhere.
 */
const read = (path: string) => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'))

const SCHEMA = read('../../schema/report.json') as {
  schemaVersion: number
  severities: string[]
  report: string[]
  parameters: string[]
  source: string[]
  check: string[]
  summary: string[]
  row: string[]
  rows: Record<string, string[]>
  unmatchedSignOff: string[]
}

const REPORT = read('./fixtures/report.json') as Report

const missing = (required: string[], present: object) =>
  required.filter((field) => !(field in present))

describe('the contract both sides read', () => {
  it('lists the same categories the store does, in the same order', () => {
    // The order is the ranking: a queue is sorted by a severity's index in it.
    expect(SCHEMA.severities).toEqual([...SEVERITIES])
  })

  it('is the version the committed report was written at', () => {
    expect(REPORT.schemaVersion).toBe(SCHEMA.schemaVersion)
  })
})

describe('the committed report', () => {
  it('carries every field the contract names', () => {
    expect(missing(SCHEMA.report, REPORT)).toEqual([])
    expect(missing(SCHEMA.parameters, REPORT.parameters)).toEqual([])
  })

  it('names every sign-off that matches no row, with what was decided', () => {
    // These are the judgements no check can show, because the calibration file
    // or the deployment they were written against is gone from the records.
    // Nothing else in the report carries them, so the shape is the only thing
    // standing between them and a blank page.
    const orphaned = REPORT.unmatchedSignOffs ?? {}
    expect(Object.keys(orphaned).length).toBeGreaterThan(0)
    for (const rows of Object.values(orphaned)) {
      for (const row of rows) {
        expect(missing(SCHEMA.unmatchedSignOff, row)).toEqual([])
        // A line with nothing written against it is a key somebody added and
        // never came back to; listing those buries the decisions that matter.
        expect(row.status.trim()).not.toBe('')
      }
    }
  })

  it('has a sheet for every check its orphaned sign-offs name', () => {
    for (const check of Object.keys(REPORT.unmatchedSignOffs ?? {})) {
      expect(HITL_SHEETS[check as SheetKey]?.path).toBeTruthy()
    }
  })

  it('says which commit each repository was read at', () => {
    for (const source of Object.values(REPORT.sources)) {
      if (source && typeof source === 'object') {
        expect(missing(SCHEMA.source, source)).toEqual([])
        // The clone's path describes a machine, not the data it read.
        expect('local' in source).toBe(false)
      }
    }
  })

  /** A naive stamp is read as local time here and sorts against the UTC file
   *  stamp in the run index, so a laptop run and a runner run could order
   *  wrongly against each other. */
  it('stamps the run unambiguously', () => {
    expect(REPORT.runAt).toMatch(/(Z|[+-]\d\d:\d\d)$/)
  })

  it('summarises every check', () => {
    for (const check of Object.values(REPORT.checks)) {
      expect(missing(SCHEMA.check, check)).toEqual([])
      expect(missing(SCHEMA.summary, check.summary)).toEqual([])
    }
  })

  it('says what every row is, and why', () => {
    for (const check of Object.values(REPORT.checks)) {
      for (const row of check.rows) {
        expect(missing(SCHEMA.row, row)).toEqual([])
        expect(SCHEMA.severities).toContain(row.severity)
        expect(SCHEMA.severities).toContain(row.finding)
      }
    }
  })

  it('carries the identifying fields of each check', () => {
    for (const [name, required] of Object.entries(SCHEMA.rows)) {
      const rows = REPORT.checks[name]?.rows ?? []
      expect(rows.length).toBeGreaterThan(0)
      for (const row of rows) expect(missing(required, row)).toEqual([])
    }
  })
})

describe('what the dashboard reads off a row', () => {
  /** Every column the app declares has to exist somewhere in the check it
   *  belongs to, or the table renders a column of dashes and nothing says so. */
  it('finds every declared column in the rows it will render', () => {
    for (const check of CHECKS) {
      const rows = REPORT.checks[check.key]?.rows ?? []
      if (!rows.length) continue
      for (const column of check.columns) {
        expect(rows.some((row: Row) => column in row)).toBe(true)
      }
    }
  })

  /** A sign-off writes to the line the run named. Rebuilding it here read the
   *  year in the viewer's own timezone, which appends a second line to the
   *  sheet for a deployment that already has one. */
  it('takes the sign-off key from the row rather than rebuilding it', () => {
    for (const sheet of Object.keys(HITL_SHEETS) as SheetKey[]) {
      const rows = REPORT.checks[sheet]?.rows ?? []
      expect(rows.length).toBeGreaterThan(0)
      for (const row of rows) {
        expect(hitlKeyOf(sheet, row)).toBe(row.hitlKey)
      }
    }
  })

  it('offers the reasons a sign-off picks from', () => {
    for (const sheet of Object.keys(HITL_SHEETS)) {
      expect(Array.isArray(REPORT.hitlNotes?.[sheet])).toBe(true)
    }
  })
})

describe('the counts the report settles', () => {
  const count = (check: Check, of: (row: Row) => boolean) => check.rows.filter(of).length

  it('counts what is waiting on a person, and leaves sign-offs out of it', () => {
    for (const check of Object.values(REPORT.checks)) {
      const waiting = count(check, (row) => row.severity === 'problem' || row.severity === 'review')
      expect(check.summary.attention).toBe(waiting)
    }
  })

  it('counts a sign-off as verified', () => {
    for (const check of Object.values(REPORT.checks)) {
      const settled = count(check, (row) => row.severity === 'ok' || row.severity === 'cleared')
      expect(check.summary.verified).toBe(settled)
    }
  })

  /** An excluded row is in no other number, so a proportion measured against the
   *  row count would shrink every time an instrument with no calibration was
   *  deployed. */
  it('leaves excluded rows out of what the check could judge', () => {
    for (const check of Object.values(REPORT.checks)) {
      const excluded = count(check, (row) => row.severity === 'excluded')
      expect(check.summary.excluded).toBe(excluded)
      expect(check.summary.considered).toBe(check.summary.total - excluded)
    }
  })

  it('names the instruments nothing could be compared for', () => {
    expect(Array.isArray(REPORT.excludedInstruments)).toBe(true)
  })
})
