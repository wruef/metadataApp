import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { identity, siteOf, splitVerdict, toneOf, VERDICTS, yearOf } from '../app/display'

describe('verdict tone', () => {
  it('colours a verdict by the severity the run gives it', () => {
    expect(toneOf('calibrations', 'vendorMatch', 'MISMATCH')).toBe('crit')
    expect(toneOf('calibrations', 'vendorMatch', 'COMPARED')).toBe('ok')
    // A disagreement with a constant is not a disagreement with the vendor.
    expect(toneOf('calibrations', 'vendorMatch', 'CONSTANT_MISMATCH')).toBe('warn')
    expect(toneOf('calibrations', 'vendorMatch', 'PDF_NOTCOMPARED')).toBe('na')
  })

  it('draws the eye to a verdict it does not know, rather than passing it', () => {
    expect(toneOf('calibrations', 'vendorMatch', 'SOMETHING_NEW')).toBe('warn')
  })

  it('leaves a column that holds no verdict as plain text', () => {
    expect(toneOf('calibrations', 'fileName', 'ATAPL-66662-00002__20160303.csv')).toBeNull()
    expect(toneOf('deployments', 'AssetID', 'ATAPL-58320-00002')).toBeNull()
  })

  it('reads the sign-off column, which is a person and not a check', () => {
    expect(toneOf('calibrations', 'HITLstatus', 'Clear')).toBe('ok')
    expect(toneOf('calibrations', 'HITLstatus', 'NotClear')).toBe('crit')
    expect(toneOf('calibrations', 'HITLstatus', 'NA')).toBe('na')
  })

  it('badges the verdict and leaves the detail beside it', () => {
    // rawFile_verify carries the serial numbers behind the verdict in the value.
    expect(splitVerdict('MISMATCH: raw: 379: ATAPL-68020-00002')).toEqual({
      token: 'MISMATCH',
      detail: 'raw: 379: ATAPL-68020-00002',
    })
    expect(toneOf('deployments', 'rawFile_verify', 'MISMATCH: raw: 379: ATAPL-68020-00002')).toBe('crit')
    expect(splitVerdict('MATCH')).toEqual({ token: 'MATCH', detail: '' })
  })
})

/**
 * The dashboard's copy of the severity map only picks a colour, but a colour
 * that disagrees with the run's own judgement is worse than no colour. This
 * fails the moment the two drift.
 */
describe('the mirrored severity map', () => {
  const source = readFileSync(
    new URL('../../src/rca_metadata/report.py', import.meta.url),
    'utf8',
  )

  it('matches SEVERITY in report.py exactly', () => {
    const block = source.slice(source.indexOf('SEVERITY = {') + 'SEVERITY = '.length)
    const literal = block
      .slice(0, block.indexOf('\n}') + 2)
      .split('\n')
      .filter((line) => !line.trim().startsWith('##'))
      .join('\n')
      .replace(/'/g, '"')
      // python closes a dict after a trailing comma; JSON does not.
      .replace(/,(\s*})/g, '$1')
    expect(JSON.parse(literal)).toEqual(VERDICTS)
  })
})

describe('identifiers', () => {
  it('bolds the instrument, which is the part that differs down the column', () => {
    expect(identity('refDes', 'RS01SBPS-SF01A-4A-NUTNRA101')).toEqual({
      dim: 'RS01SBPS-SF01A-4A-',
      strong: 'NUTNRA101',
    })
  })

  it('bolds the asset and dims the calibration date', () => {
    expect(identity('fileName', 'ATAPL-66662-00002__20160303.csv')).toEqual({
      dim: '',
      strong: 'ATAPL-66662-00002',
      tail: '__20160303.csv',
    })
  })

  it('leaves anything else alone', () => {
    expect(identity('AssetID', 'ATAPL-58320-00002')).toBeNull()
    expect(identity('refDes', 'NOTAREFDES')).toBeNull()
  })
})

describe('derived facets', () => {
  it('takes the site from a reference designator', () => {
    expect(siteOf('RS01SBPS-SF01A-4A-NUTNRA101')).toBe('RS01SBPS')
    expect(siteOf(undefined)).toBe('')
  })

  it('takes the year from a deployment date', () => {
    expect(yearOf('2016-07-14T00:00:00')).toBe('2016')
    expect(yearOf(null)).toBe('')
  })
})
