import { describe, expect, it } from 'vitest'

import {
  BATCHES,
  batchTitle,
  batchesFor,
  buildBatch,
  describe as describeEntry,
  deploymentKey,
  pathOf,
  signoffKey,
  type CalibrationEntry,
  type Entry,
  type PositionEntry,
  type SignoffEntry,
} from '../app/batch'
import { PRELIMINARY_NOTE } from '../app/deployfile'

/** A real DOFSTA file, and a second one on another instrument. */
const DOFSTA = [
  'serial,name,value,notes',
  '43-3136,CC_frequency_offset,-5.064574e-001,',
  '43-3136,CC_oxygen_signal_slope,5.022414e-001,',
  '',
].join('\n')

const CTDBP = [
  'serial,name,value,notes',
  '16-50325,CC_a0,1.234000e+000,',
  '',
].join('\n')

const HEAD = 'CUID_Deploy,deployedBy,CUID_Recover,recoveredBy,Reference Designator,'
  + 'deploymentNumber,versionNumber,startDateTime,stopDateTime,mooring.uid,node.uid,'
  + 'sensor.uid,lat,lon,orbit,deployment_depth,water_depth,notes,electrical.uid,'
  + 'assembly_template_revision'

const row = (refDes: string, deployNum: number, lat: string, notes = '') =>
  `TN313,,,,${refDes},${deployNum},1,2014-09-27T13:29:00,2015-07-09T00:00:00,`
  + `ATAPL-67762-30001,ATAPL-69839-00103,ATAPL-58315-00002,${lat},-129.753284,,187,2611,`
  + `${notes},,`

/** Two deployments that share one sheet, which is what a batch has to fold. */
const SHEET = [
  HEAD,
  row('RS03AXPS-PC03A-05-ADCPTD302', 1, '45.830481'),
  row('RS03AXPS-PC03A-06-VADCPA301', 1, '45.830481', PRELIMINARY_NOTE),
  '',
].join('\n')

const CAL_PATH = 'calibration/DOFSTA/one.csv'
const CAL_PATH_2 = 'calibration/CTDBP/two.csv'
const SHEET_PATH = 'deployment/RS03AXPS_Deploy.csv'

const calibration = (instrument: string, fileName: string, coefficient: string,
                     from: number, to: number): CalibrationEntry => ({
  batch: 'calibrations',
  key: `calibration/${instrument}/${fileName}`,
  instrument,
  fileName,
  corrections: [{ coefficient, from, to }],
})

const position = (refDes: string, deployNum: number, to: string): PositionEntry => ({
  batch: 'positions',
  key: deploymentKey(refDes, deployNum),
  refDes,
  deployNum,
  positionName: 'PC03A',
  corrections: [{ field: 'lat', from: '45.830481', to }],
})

const signoff = (sheet: SignoffEntry['sheet'], line: string, notes = 'checked'): SignoffEntry => ({
  batch: 'signoffs',
  key: signoffKey(sheet, line),
  sheet,
  row: line,
  status: 'Clear',
  notes,
})

const WHEN = new Date('2026-09-18T12:00:00')
const BY = 'WR (wruef)'

describe('which pull request a change belongs to', () => {
  it('keys a batch by the repository and by what the change is', () => {
    // Both land in asset-management and still travel separately: approving a
    // page of coefficients is not agreeing to move an instrument on the seabed.
    const forAssetManagement = batchesFor('assetManagement').map((batch) => batch.key)
    expect(forAssetManagement).toEqual(['calibrations', 'positions'])
    expect(batchesFor('hitl').map((batch) => batch.key)).toEqual(['signoffs'])
  })

  it('never puts two repositories in one request', () => {
    const forks = new Set(BATCHES.map((batch) => batch.fork))
    for (const fork of forks) {
      for (const batch of batchesFor(fork)) expect(batch.fork).toBe(fork)
    }
  })

  it('guards the batches that change a file, and not the one that records a judgement', () => {
    expect(BATCHES.filter((batch) => batch.guarded).map((batch) => batch.key))
      .toEqual(['calibrations', 'positions'])
  })

  it('sends each entry to the file it writes', () => {
    expect(pathOf(calibration('DOFSTA', 'one.csv', 'a', 1, 2))).toBe(CAL_PATH)
    expect(pathOf(position('RS03AXPS-PC03A-05-ADCPTD302', 1, '45.8'))).toBe(SHEET_PATH)
    expect(pathOf(signoff('calibrations', 'x.csv')))
      .toBe('2i_HITL/2i_HITL_calibrationVerification.csv')
  })

  it('tells the same identifier in two sheets apart', () => {
    expect(signoffKey('calibrations', 'ATAPL-1')).not.toBe(signoffKey('sensorBulk', 'ATAPL-1'))
  })
})

describe('gathering calibration corrections', () => {
  const entries: Entry[] = [
    calibration('DOFSTA', 'one.csv', 'CC_frequency_offset', -0.5064574, -0.4839777),
    calibration('CTDBP', 'two.csv', 'CC_a0', 1.234, 1.235),
  ]
  const current = { [CAL_PATH]: DOFSTA, [CAL_PATH_2]: CTDBP }

  it('carries every file in one request', () => {
    const built = buildBatch('calibrations', entries, current, BY, 'WR', WHEN)
    expect(Object.keys(built.files).sort()).toEqual([CAL_PATH_2, CAL_PATH])
    expect(built.files[CAL_PATH]).toContain('-4.839777e-001')
    expect(built.files[CAL_PATH_2]).toContain('1.235000e+000')
  })

  it('gives each file its own section, so the unit of review survives the batch', () => {
    const { body } = buildBatch('calibrations', entries, current, BY, 'WR', WHEN)
    expect(body).toContain(`\`${CAL_PATH}\``)
    expect(body).toContain(`\`${CAL_PATH_2}\``)
    expect(body).toContain('| `CC_frequency_offset` | -0.5064574 | -0.4839777 |')
    expect(body).toContain('| `CC_a0` | 1.234 | 1.235 |')
    // Who proposed it and what merging it means are said once, not per file.
    expect(body.match(/Proposed from the metadata dashboard/g)).toHaveLength(1)
    expect(body).toContain(BY)
    expect(body).toContain('raise the pull request to the upstream repository by hand')
  })

  it('counts the files in the title, and keeps a single one reading as it always did', () => {
    expect(batchTitle('calibrations', entries)).toBe('Correct coefficients in 2 calibration files')
    expect(batchTitle('calibrations', [entries[0]!]))
      .toBe('Correct CC_frequency_offset in one.csv')
  })
})

describe('gathering position corrections', () => {
  const two: Entry[] = [
    position('RS03AXPS-PC03A-05-ADCPTD302', 1, '45.830512'),
    position('RS03AXPS-PC03A-06-VADCPA301', 1, '45.830599'),
  ]

  it('folds two deployments of one sheet into a single file', () => {
    const built = buildBatch('positions', two, { [SHEET_PATH]: SHEET }, BY, 'WR', WHEN)
    expect(Object.keys(built.files)).toEqual([SHEET_PATH])
    // Both corrections are in it — the second was applied to the first's output
    // rather than to the file as the fork holds it.
    expect(built.files[SHEET_PATH]).toContain('45.830512')
    expect(built.files[SHEET_PATH]).toContain('45.830599')
  })

  it('names each deployment in the body and says which note it cleared', () => {
    const { body } = buildBatch('positions', two, { [SHEET_PATH]: SHEET }, BY, 'WR', WHEN)
    expect(body).toContain('**RS03AXPS-PC03A-05-ADCPTD302** deployment **1**')
    expect(body).toContain('**RS03AXPS-PC03A-06-VADCPA301** deployment **1**')
    // Only the second row carried the preliminary note.
    expect(body.match(/has been cleared/g)).toHaveLength(1)
  })

  it('counts the deployments in the title', () => {
    expect(batchTitle('positions', two)).toBe('Correct positions for 2 deployments')
    expect(batchTitle('positions', [two[0]!]))
      .toBe('Correct lat for RS03AXPS-PC03A-05-ADCPTD302 deployment 1')
  })
})

describe('a batch that cannot be applied', () => {
  it('refuses the whole batch rather than proposing the part that still fits', () => {
    // A value that no longer reads what the run read means the file has moved
    // since the report on screen, which casts the same doubt over every other
    // record in the batch.
    const stale: PositionEntry = {
      ...position('RS03AXPS-PC03A-05-ADCPTD302', 1, '45.9'),
      corrections: [{ field: 'lat', from: '0.000000', to: '45.9' }],
    }
    const entries: Entry[] = [position('RS03AXPS-PC03A-06-VADCPA301', 1, '45.830599'), stale]
    expect(() => buildBatch('positions', entries, { [SHEET_PATH]: SHEET }, BY, 'WR', WHEN))
      .toThrow(/1 of 2 could not be applied, so nothing was proposed/)
  })

  it('names the record that could not be applied, not just the file', () => {
    const stale: CalibrationEntry = {
      ...calibration('DOFSTA', 'one.csv', 'CC_frequency_offset', -99, -0.48),
    }
    expect(() => buildBatch('calibrations', [stale], { [CAL_PATH]: DOFSTA }, BY, 'WR', WHEN))
      .toThrow(/one\.csv/)
  })

  it('says so when the fork holds no such file', () => {
    const entry = calibration('DOFSTA', 'one.csv', 'CC_frequency_offset', -0.5064574, -0.48)
    expect(() => buildBatch('calibrations', [entry], { [CAL_PATH]: null }, BY, 'WR', WHEN))
      .toThrow(/has no such file/)
  })
})

describe('gathering sign-offs', () => {
  const entries: Entry[] = [
    signoff('calibrations', 'ATAPL-1__20140101.csv', 'ingested by hand in 2019'),
    signoff('sensorBulk', 'ATAPL-58345-00004', 'the RCA list is right'),
  ]

  it('writes each sheet the decisions belong to, and no others', () => {
    const built = buildBatch('signoffs', entries, {}, BY, 'WR', WHEN)
    expect(Object.keys(built.files).sort()).toEqual([
      '2i_HITL/2i_HITL_calibrationVerification.csv',
      '2i_HITL/2i_HITL_sensorVerification.csv',
    ])
    expect(built.files['2i_HITL/2i_HITL_sensorVerification.csv']).toContain('ATAPL-58345-00004')
    expect(built.files['2i_HITL/2i_HITL_sensorVerification.csv']).toContain('WR')
  })

  it('keeps the title and the count it has always had', () => {
    const built = buildBatch('signoffs', entries, {}, BY, 'WR', WHEN)
    expect(built.title).toBe('HITL sign-offs, 9/18/26')
    expect(built.body).toContain('2 row(s) signed off by WR (wruef)')
  })
})

describe('what the queue shows for an entry', () => {
  it('names the record and what it would do', () => {
    expect(describeEntry(calibration('DOFSTA', 'one.csv', 'CC_a0', 1, 2)))
      .toEqual({ name: 'one.csv', summary: 'CC_a0: 1 → 2' })
    expect(describeEntry(position('RS03AXPS-PC03A-05-ADCPTD302', 1, '45.9')).name)
      .toBe('RS03AXPS-PC03A-05-ADCPTD302 deployment 1')
    expect(describeEntry(signoff('calibrations', 'x.csv', '')).summary)
      .toMatch(/worth saying what convinced you/)
  })
})
