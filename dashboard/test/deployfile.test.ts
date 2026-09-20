import { describe, expect, it } from 'vitest'

import {
  applyDeploymentCorrections,
  ASSET_FIELD,
  deploymentPath,
  deploymentSection,
  deploymentTitle,
  isNodeRefDes,
  NODE_PATH,
  PRELIMINARY_NOTE,
  sheetPathFor,
} from '../app/deployfile'

/**
 * Four lines of a real `RS03AXPS_Deploy.csv`, header and all twenty columns.
 *
 * Every row shares a position, which is what makes the sheet dangerous to edit:
 * the correction has to land on one deployment and leave its neighbours alone.
 */
const HEAD = 'CUID_Deploy,deployedBy,CUID_Recover,recoveredBy,Reference Designator,'
  + 'deploymentNumber,versionNumber,startDateTime,stopDateTime,mooring.uid,node.uid,'
  + 'sensor.uid,lat,lon,orbit,deployment_depth,water_depth,notes,electrical.uid,'
  + 'assembly_template_revision'

const row = (refDes: string, deployNum: number, lat: string, notes = '') =>
  `TN313,,,,${refDes},${deployNum},1,2014-09-27T13:29:00,2015-07-09T00:00:00,`
  + `ATAPL-67762-30001,ATAPL-69839-00103,ATAPL-58315-00002,${lat},-129.753284,,187,2611,`
  + `${notes},,`

const SHEET = [
  HEAD,
  row('RS03AXPS-PC03A-05-ADCPTD302', 1, '45.830481'),
  row('RS03AXPS-PC03A-06-VADCPA301', 1, '45.830481'),
  row('RS03AXPS-PC03A-05-ADCPTD302', 2, '45.830481'),
  '',
].join('\n')

describe('which sheet a deployment is on', () => {
  it('is its array', () => {
    expect(deploymentPath('CE02SHBP-LJ01D-05-ADCPTB104')).toBe('deployment/CE02SHBP_Deploy.csv')
  })
})

describe('correcting one deployment', () => {
  const lat = { field: 'lat', from: '45.830481', to: '45.830512' }

  it('changes one line and leaves the rest of the sheet alone', () => {
    const { text } = applyDeploymentCorrections(SHEET, 'RS03AXPS-PC03A-05-ADCPTD302', 1, [lat])
    const before = SHEET.split('\n')
    const after = text.split('\n')
    expect(after.filter((line, index) => line !== before[index])).toHaveLength(1)
    expect(after[1]).toContain('45.830512')
  })

  /** Every row in this sheet carries the same latitude, so matching on the
   *  value rather than on the deployment would rewrite all of them. */
  it('leaves the other instrument at the same position alone', () => {
    const { text } = applyDeploymentCorrections(SHEET, 'RS03AXPS-PC03A-05-ADCPTD302', 1, [lat])
    expect(text.split('\n')[2]).toBe(SHEET.split('\n')[2])
  })

  /** An instrument can be deployed more than once, so the designator alone does
   *  not identify a row. */
  it('tells two deployments of one instrument apart', () => {
    const { text } = applyDeploymentCorrections(SHEET, 'RS03AXPS-PC03A-05-ADCPTD302', 2, [lat])
    expect(text.split('\n')[1]).toBe(SHEET.split('\n')[1])
    expect(text.split('\n')[3]).toContain('45.830512')
  })

  it('keeps all twenty columns', () => {
    const { text } = applyDeploymentCorrections(SHEET, 'RS03AXPS-PC03A-05-ADCPTD302', 1, [lat])
    expect(text.split('\n')[1]!.split(',')).toHaveLength(20)
  })

  it('corrects several fields at once', () => {
    const { text } = applyDeploymentCorrections(SHEET, 'RS03AXPS-PC03A-05-ADCPTD302', 1, [
      lat,
      { field: 'lon', from: '-129.753284', to: '-129.753300' },
      { field: 'water_depth', from: '2611', to: '2609' },
    ])
    expect(text.split('\n')[1]).toContain('45.830512,-129.753300,,187,2609,')
  })

  /** A profiler holds no fixed depth, so N/A is the value rather than a gap. */
  it('writes N/A as the value it is', () => {
    const profiler = SHEET.replace(',187,2611,', ',N/A,2611,')
    const { text } = applyDeploymentCorrections(profiler, 'RS03AXPS-PC03A-05-ADCPTD302', 1, [
      { field: 'deployment_depth', from: 'N/A', to: 'N/A' },
    ])
    expect(text).toBe(profiler)
  })
})

describe('the preliminary note', () => {
  /** The note claims the position is provisional. Correcting it to the
   *  spreadsheet is what makes it not, so the claim goes with it -- which is
   *  what applyPositions in positions.py does to the same column. */
  it('is cleared along with the position', () => {
    const sheet = [HEAD, row('RS03AXPS-PC03A-05-ADCPTD302', 1, '45.830481', PRELIMINARY_NOTE), '']
      .join('\n')
    const { text, clearedNote } = applyDeploymentCorrections(
      sheet, 'RS03AXPS-PC03A-05-ADCPTD302', 1,
      [{ field: 'lat', from: '45.830481', to: '45.830512' }])
    expect(clearedNote).toBe(true)
    expect(text).not.toContain(PRELIMINARY_NOTE)
  })

  it('is not invented where the sheet says something else', () => {
    const sheet = [HEAD, row('RS03AXPS-PC03A-05-ADCPTD302', 1, '45.830481', 'moved in 2019'), '']
      .join('\n')
    const { text, clearedNote } = applyDeploymentCorrections(
      sheet, 'RS03AXPS-PC03A-05-ADCPTD302', 1,
      [{ field: 'lat', from: '45.830481', to: '45.830512' }])
    expect(clearedNote).toBe(false)
    expect(text).toContain('moved in 2019')
  })
})

describe('what it refuses', () => {
  it('refuses a deployment the sheet does not carry', () => {
    expect(() => applyDeploymentCorrections(SHEET, 'RS03AXPS-PC03A-05-ADCPTD302', 9, [
      { field: 'lat', from: '45.830481', to: '45.830512' },
    ])).toThrow(/has no RS03AXPS-PC03A-05-ADCPTD302 deployment 9/)
  })

  it('refuses a value the sheet no longer holds', () => {
    expect(() => applyDeploymentCorrections(SHEET, 'RS03AXPS-PC03A-05-ADCPTD302', 1, [
      { field: 'lat', from: '44.0', to: '45.830512' },
    ])).toThrow(/now reads 45.830481 on this deployment/)
  })

  it('refuses a column the sheet does not carry', () => {
    expect(() => applyDeploymentCorrections(SHEET, 'RS03AXPS-PC03A-05-ADCPTD302', 1, [
      { field: 'elevation', from: '1', to: '2' },
    ])).toThrow(/no elevation column/)
  })

  /** All-or-nothing: a sheet half corrected is worse than one not corrected. */
  it('writes nothing when one of several fields is refused', () => {
    expect(() => applyDeploymentCorrections(SHEET, 'RS03AXPS-PC03A-05-ADCPTD302', 1, [
      { field: 'lat', from: '45.830481', to: '45.830512' },
      { field: 'water_depth', from: '9999', to: '2609' },
    ])).toThrow(/water_depth now reads 2611/)
  })
})

describe('what the pull request says', () => {
  it('names the deployment, not just the sheet', () => {
    expect(deploymentTitle('CE02SHBP-LJ01D-05-ADCPTB104', 13, [
      { field: 'lat', from: '44.637213', to: '44.637184' },
    ])).toBe('Correct lat for CE02SHBP-LJ01D-05-ADCPTB104 deployment 13')
  })

  it('counts the fields when there are several', () => {
    expect(deploymentTitle('CE02SHBP-LJ01D-05-ADCPTB104', 13, [
      { field: 'lat', from: '1', to: '2' },
      { field: 'lon', from: '3', to: '4' },
    ])).toBe('Correct 2 fields for CE02SHBP-LJ01D-05-ADCPTB104 deployment 13')
  })

  it('puts every value before and after it in the section, and says where they came from', () => {
    const section = deploymentSection('deployment/CE02SHBP_Deploy.csv', 'CE02SHBP-LJ01D-05-ADCPTB104', 13,
      'Taken from the RCA position spreadsheet, position `LJ01D`.', [
        { field: 'lat', from: '44.637213', to: '44.637184' },
      ], false)
    expect(section).toContain('`deployment/CE02SHBP_Deploy.csv`')
    expect(section).toContain('deployment **13**')
    expect(section).toContain('| `lat` | 44.637213 | 44.637184 |')
    expect(section).toContain('position `LJ01D`')
    expect(section).not.toContain(PRELIMINARY_NOTE)
  })

  it('says so when it cleared the preliminary note', () => {
    const section = deploymentSection('deployment/CE02SHBP_Deploy.csv', 'CE02SHBP-LJ01D-05-ADCPTB104', 13,
      'from the spreadsheet', [
      { field: 'lat', from: '44.637213', to: '44.637184' },
    ], true)
    expect(section).toContain(PRELIMINARY_NOTE)
    expect(section).toContain('has been cleared')
  })

  it('names the deployment, so two on one sheet stay apart in a batch', () => {
    const corrections = [{ field: 'lat', from: '1', to: '2' }]
    const sheet = 'deployment/RS03AXPS_Deploy.csv'
    const first = deploymentSection(sheet, 'RS03AXPS-SF03A-2A-CTDPFA302', 10, '', corrections, false)
    const second = deploymentSection(sheet, 'RS03AXPS-PC03A-05-ADCPTD302', 12, '', corrections, false)
    expect(first).toContain('**RS03AXPS-SF03A-2A-CTDPFA302** deployment **10**')
    expect(second).toContain('**RS03AXPS-PC03A-05-ADCPTD302** deployment **12**')
  })
})


/**
 * The commonest thing the deployments check finds is a serial number that
 * belongs to a different asset, which is a claim about one column of one row.
 */
describe('correcting which instrument was deployed', () => {
  const asset = (from: string, to: string) => [{ field: ASSET_FIELD, from, to }]

  it('rewrites the asset on that row and nothing else', () => {
    const { text } = applyDeploymentCorrections(
      SHEET, 'RS03AXPS-PC03A-05-ADCPTD302', 1, asset('ATAPL-58315-00002', 'ATAPL-58315-00005'))
    const lines = text.split('\n')
    expect(lines[1]).toContain('ATAPL-58315-00005')
    // the other two rows keep the asset they had
    expect(lines[2]).toContain('ATAPL-58315-00002')
    expect(lines[3]).toContain('ATAPL-58315-00002')
  })

  it('leaves the preliminary note alone', () => {
    // A note about the position says nothing about which instrument was there,
    // so correcting the asset must not clear it.
    const sheet = [
      HEAD,
      row('RS03AXPS-PC03A-05-ADCPTD302', 1, '45.830481', PRELIMINARY_NOTE),
      '',
    ].join('\n')
    const { text, clearedNote } = applyDeploymentCorrections(
      sheet, 'RS03AXPS-PC03A-05-ADCPTD302', 1, asset('ATAPL-58315-00002', 'ATAPL-58315-00005'))
    expect(clearedNote).toBe(false)
    expect(text).toContain(PRELIMINARY_NOTE)
  })

  it('refuses an asset the sheet no longer names', () => {
    expect(() => applyDeploymentCorrections(
      SHEET, 'RS03AXPS-PC03A-05-ADCPTD302', 1, asset('ATAPL-58315-00009', 'ATAPL-58315-00005')))
      .toThrow(/sensor\.uid now reads ATAPL-58315-00002/)
  })

  it('is titled for the column it changes', () => {
    expect(deploymentTitle('RS03AXPS-PC03A-05-ADCPTD302', 1,
                           asset('ATAPL-58315-00002', 'ATAPL-58315-00005')))
      .toBe('Correct sensor.uid for RS03AXPS-PC03A-05-ADCPTD302 deployment 1')
  })
})


describe('where a deployment row lives', () => {
  it('is its array sheet for an instrument and the node file for a node', () => {
    expect(sheetPathFor('CE02SHBP-LJ01D-05-ADCPTB104')).toBe('deployment/CE02SHBP_Deploy.csv')
    // Fourteen characters is a node: site and node, no port or instrument code.
    // It lives in the deployments repository, not on an array sheet.
    expect(sheetPathFor('CE02SHBP-LJ01D')).toBe(NODE_PATH)
    expect(isNodeRefDes('CE02SHBP-LJ01D')).toBe(true)
    expect(isNodeRefDes('CE02SHBP-LJ01D-05-ADCPTB104')).toBe(false)
  })

  it('names that file in the section, so a batch of both stays readable', () => {
    const corrections = [{ field: 'lat', from: '1', to: '2' }]
    expect(deploymentSection(NODE_PATH, 'CE02SHBP-LJ01D', 1, '', corrections, false))
      .toContain('`NODE_deployments.csv`')
  })
})
