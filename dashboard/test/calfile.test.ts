import { describe, expect, it } from 'vitest'

import {
  applyCorrections,
  calibrationPath,
  correctionBody,
  correctionTitle,
  valuesByCoefficient,
} from '../app/calfile'
import { splitLine } from '../app/csv'

/** A real DOFSTA file, which is where the 74 mismatches live. */
const DOFSTA = [
  'serial,name,value,notes',
  '43-3136,CC_frequency_offset,-5.064574e-001,',
  '43-3136,CC_oxygen_signal_slope,5.022414e-001,',
  '43-3136,CC_voltage_offset,-5.064574e-001,',
  '',
].join('\n')

/** A real OPTAA file: the values are bracketed lists, quoted, full of commas. */
const OPTAA = [
  'serial,name,value,notes',
  'ACS-134,CC_acwo,"[-0.84614, -0.579381, -0.3752]",',
  'ACS-134,CC_taarray,SheetRef:CC_taarray,',
  'ACS-134,CC_tcal,22.0,read from the sheet',
  '',
].join('\n')

describe('where a calibration file lives', () => {
  it('is under its instrument directory', () => {
    expect(calibrationPath('DOFSTA', 'ATOSU-58694-00007__20200922.csv'))
      .toBe('calibration/DOFSTA/ATOSU-58694-00007__20200922.csv')
  })
})

describe('what a file offers to correct', () => {
  it('reads every scalar and none of the lists', () => {
    expect(valuesByCoefficient(OPTAA)).toEqual({
      CC_acwo: null, CC_taarray: null, CC_tcal: 22,
    })
  })
})

describe('applying a correction', () => {
  it('changes the one value and nothing else in the file', () => {
    const corrected = applyCorrections(DOFSTA, [
      { coefficient: 'CC_frequency_offset', from: -0.5064574, to: -0.4839777 },
    ])
    expect(corrected).toBe(DOFSTA.replace(
      '43-3136,CC_frequency_offset,-5.064574e-001,',
      '43-3136,CC_frequency_offset,-4.839777e-001,'))
  })

  it('leaves a coefficient that happens to share the old value alone', () => {
    // CC_voltage_offset is the same number as CC_frequency_offset in this file.
    // Matching on the value rather than the name would change both.
    const corrected = applyCorrections(DOFSTA, [
      { coefficient: 'CC_frequency_offset', from: -0.5064574, to: -0.4839777 },
    ])
    expect(corrected).toContain('CC_voltage_offset,-5.064574e-001')
  })

  it('writes the note into the notes column', () => {
    const corrected = applyCorrections(OPTAA, [
      { coefficient: 'CC_tcal', from: 22, to: 21.5, note: 'transcribed from the .dev' },
    ])
    expect(corrected).toContain('CC_tcal,21.5,transcribed from the .dev')
  })

  it('quotes a note carrying a comma, rather than adding a column', () => {
    const corrected = applyCorrections(OPTAA, [
      { coefficient: 'CC_tcal', from: 22, to: 21.5, note: 'vendor .dev, second page' },
    ])
    expect(splitLine(corrected.split('\n')[3]!)).toHaveLength(4)
    expect(corrected).toContain('"vendor .dev, second page"')
  })

  it('leaves the notes column alone when no note is given', () => {
    const corrected = applyCorrections(OPTAA, [
      { coefficient: 'CC_tcal', from: 22, to: 21.5 },
    ])
    expect(corrected).toContain('CC_tcal,21.5,read from the sheet')
  })

  it('refuses a value the file no longer holds', () => {
    // The fork is checked against upstream first, so this means upstream moved
    // and the report on screen is older than the file it reports on.
    expect(() => applyCorrections(DOFSTA, [
      { coefficient: 'CC_frequency_offset', from: -0.9, to: -0.4839777 },
    ])).toThrow(/now reads -5.064574e-001 in asset-management/)
  })

  it('refuses a coefficient the file does not carry, rather than appending one', () => {
    expect(() => applyCorrections(DOFSTA, [
      { coefficient: 'CC_made_up', from: 1, to: 2 },
    ])).toThrow(/carries no CC_made_up/)
  })

  it('keeps the file exactly when nothing is corrected', () => {
    expect(applyCorrections(DOFSTA, [])).toBe(DOFSTA)
  })
})

describe('what the pull request says', () => {
  it('names the coefficient when there is one', () => {
    expect(correctionTitle('ATOSU-58694-00007__20200922.csv', [
      { coefficient: 'CC_frequency_offset', from: -0.5, to: -0.48 },
    ])).toBe('Correct CC_frequency_offset in ATOSU-58694-00007__20200922.csv')
  })

  it('counts them when there are several', () => {
    expect(correctionTitle('x.csv', [
      { coefficient: 'a', from: 1, to: 2 },
      { coefficient: 'b', from: 3, to: 4 },
    ])).toBe('Correct 2 coefficients in x.csv')
  })

  it('puts every value before and after it in the body', () => {
    const body = correctionBody('calibration/DOFSTA/x.csv', [
      { coefficient: 'CC_frequency_offset', from: -0.5064574, to: -0.4839777 },
    ], 'WR (wruef)')
    expect(body).toContain('| `CC_frequency_offset` | -0.5064574 | -0.4839777 |')
    expect(body).toContain('WR (wruef)')
    expect(body).toContain('raise the pull request to the upstream repository by hand')
  })
})

/**
 * A DOSTA's `CC_conc_coef` is two numbers in one quoted field, and one of them
 * disagrees with the vendor. Every array-valued difference in the report is two
 * elements long, so refusing them left exactly two rows uncorrectable for a
 * reason that only applies to an OPTAA's eighty-three.
 */
describe('correcting a coefficient that is a list', () => {
  const DOSTA = [
    'serial,name,value,notes',
    '476,CC_conc_coef,"[-9.765852e-01, 1.081678]",',
    '476,CC_csv,"[0.00289149, 0.000123681, 2.40123e-06]",',
    '',
  ].join('\n')

  it('writes each element in the notation it already used', () => {
    const corrected = applyCorrections(DOSTA, [{
      coefficient: 'CC_conc_coef',
      from: [-0.9765852, 1.081678],
      to: [-0.9768582, 1.081678],
    }])
    expect(corrected).toContain('"[-9.768582e-01, 1.081678]"')
  })

  it('keeps the quoting, the brackets and the spacing', () => {
    const corrected = applyCorrections(DOSTA, [{
      coefficient: 'CC_conc_coef',
      from: [-0.9765852, 1.081678],
      to: [-0.9768582, 1.081678],
    }])
    expect(splitLine(corrected.split('\n')[1]!)).toHaveLength(4)
    expect(corrected.split('\n')[2]).toBe(DOSTA.split('\n')[2])
  })

  it('refuses a list the file no longer holds', () => {
    expect(() => applyCorrections(DOSTA, [{
      coefficient: 'CC_conc_coef', from: [-0.9, 1.081678], to: [-0.97, 1.081678],
    }])).toThrow(/now reads/)
  })

  it('refuses a replacement of a different length', () => {
    expect(() => applyCorrections(DOSTA, [{
      coefficient: 'CC_conc_coef', from: [-0.9765852, 1.081678], to: [-0.9768582],
    }])).toThrow(/cannot change length/)
  })
})
