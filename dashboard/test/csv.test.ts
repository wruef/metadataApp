import { describe, expect, it } from 'vitest'

import { asField, columnIndex, holdsValue, matchNotation, scalar, splitLine } from '../app/csv'

/** A real OPTAA calibration line: the value is a bracketed list, quoted, full
 *  of commas. Splitting on commas would make eighty-five columns of it. */
const OPTAA = 'ACS-134,CC_acwo,"[-0.84614, -0.579381, -0.3752]",'

describe('splitting a line', () => {
  it('leaves a quoted list as one field', () => {
    expect(splitLine(OPTAA)).toEqual(
      ['ACS-134', 'CC_acwo', '"[-0.84614, -0.579381, -0.3752]"', ''])
  })

  it('rejoins to exactly the line it was given', () => {
    expect(splitLine(OPTAA).join(',')).toBe(OPTAA)
  })

  it('keeps empty trailing columns, which a deployment sheet is full of', () => {
    expect(splitLine('TN313,,,,RS03AXPS-PC03A-05-ADCPTD302')).toHaveLength(5)
  })
})

describe('quoting a value on the way back in', () => {
  it('leaves an ordinary one alone', () => {
    expect(asField('45.830481')).toBe('45.830481')
  })

  it('quotes one carrying a comma, so it stays one column', () => {
    expect(asField('vendor .dev, second page')).toBe('"vendor .dev, second page"')
  })

  it('doubles a quote inside one', () => {
    expect(asField('the "old" sheet')).toBe('"the ""old"" sheet"')
  })
})

describe('what can be typed over', () => {
  it('reads a single number', () => {
    expect(scalar('-5.064574e-001')).toBe(-0.5064574)
    expect(scalar(' 22.0 ')).toBe(22)
  })

  it('refuses a list, so no array is edited through one text box', () => {
    expect(scalar('"[-0.84614, -0.579381]"')).toBeNull()
  })

  it('refuses a sheet reference', () => {
    expect(scalar('SheetRef:CC_taarray')).toBeNull()
  })

  /** A profiler holds no fixed depth, so its deployment depth is the literal
   *  N/A -- the value, not a missing one. */
  it('refuses N/A', () => {
    expect(scalar('N/A')).toBeNull()
  })
})

describe('whether the file still holds what the run read', () => {
  /** The two spell the same value differently, so this cannot be a string
   *  comparison: a file writing -5.064574e-001 against a report carrying
   *  -0.5064574 shares no substring at all. */
  it('compares numbers as numbers', () => {
    expect(holdsValue('-5.064574e-001', -0.5064574)).toBe(true)
    expect(holdsValue('2611', 2611)).toBe(true)
    expect(holdsValue('44.637213', 44.637213)).toBe(true)
  })

  it('notices a value that has moved', () => {
    expect(holdsValue('-5.064574e-001', -0.9)).toBe(false)
  })

  it('compares anything that is not a number as text', () => {
    expect(holdsValue('N/A', 'N/A')).toBe(true)
    expect(holdsValue('N/A', 187)).toBe(false)
  })

  it('does not read an empty cell as a zero', () => {
    expect(holdsValue('', 0)).toBe(false)
  })
})

describe('writing a corrected number', () => {
  it('keeps the notation the line already used', () => {
    // The vendor publishes -0.4839777; the file writes exponents with a
    // three-digit power, and a correction should read as a changed digit.
    expect(matchNotation('-5.064574e-001', '-0.4839777')).toBe('-4.839777e-001')
  })

  it('keeps a plain decimal plain', () => {
    expect(matchNotation('22.0', '21.5')).toBe('21.5')
  })

  it('carries a positive exponent across', () => {
    expect(matchNotation('1.022921e+003', '1022.5')).toBe('1.022500e+003')
  })

  it('leaves a value that is not a number as it was typed', () => {
    expect(matchNotation('187', 'N/A')).toBe('N/A')
  })
})

describe('finding a column by name', () => {
  it('reads the header of a real deployment sheet', () => {
    const index = columnIndex(
      'CUID_Deploy,deployedBy,Reference Designator,deploymentNumber,lat,lon,notes')
    expect(index['Reference Designator']).toBe(2)
    expect(index.lat).toBe(4)
    expect(index.notes).toBe(6)
  })
})
