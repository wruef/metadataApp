import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import {
  constantDifferences,
  isPinned,
  isText,
  readAt,
  rawUrl,
  repoLines,
  vendorLines,
  vendorValues,
  type Difference,
} from '../app/files'

const read = (name: string) =>
  readFileSync(new URL(`./fixtures/${name}`, import.meta.url), 'utf8')

/** A real pair: the repository CSV and the vendor .xmlcon for one CTDBPN. */
const REPO = read('repo.csv')
const VENDOR = read('vendor.xmlcon')

describe('the repository side', () => {
  const lines = repoLines(REPO, new Set(['CC_C1', 'CC_D1']))

  it('marks the row for each differing coefficient', () => {
    const marked = lines.filter((line) => line.hit)
    expect(marked.map((line) => line.text.split(',')[1])).toEqual(['CC_C1', 'CC_D1'])
  })

  it('never marks the header, which names every coefficient column', () => {
    expect(lines[0]!.hit).toBe(false)
    expect(lines[0]!.text).toBe('serial,name,value,notes')
  })

  it('numbers lines from one, the way the file is quoted', () => {
    expect(lines[1]!.n).toBe(2)
  })

  it('marks nothing when nothing differs', () => {
    expect(repoLines(REPO, new Set()).some((line) => line.hit)).toBe(false)
  })
})

describe('the vendor side', () => {
  /** The value both files hold for CC_C1, written `1.022921e+003` in each. */
  const C1 = 1022.921

  it('finds the value however the vendor wrote it', () => {
    // The point of the whole exercise: this is what a string match cannot do.
    expect(VENDOR).not.toContain(String(C1))
    const marked = vendorLines(VENDOR, [C1]).filter((line) => line.hit)
    expect(marked).toHaveLength(1)
    expect(marked[0]!.text).toContain('<C1>')
  })

  it('marks nothing when no value is disputed', () => {
    expect(vendorLines(VENDOR, []).some((line) => line.hit)).toBe(false)
  })

  it('does not mark a value the file does not carry', () => {
    expect(vendorLines(VENDOR, [1022.922]).some((line) => line.hit)).toBe(false)
  })
})

describe('which differences have a vendor line at all', () => {
  const differences: Difference[] = [
    { coefficient: 'CC_C1', github: 1022.922, expected: 1022.921, difference: 0.001, source: 'vendor' },
    { coefficient: 'CC_offset', github: 4.13, expected: 0, difference: 4.13, source: 'constant' },
  ]

  it('leaves a constant out, because the vendor file has no such value', () => {
    expect(vendorValues(differences)).toEqual([1022.921])
    expect(constantDifferences(differences).map((each) => each.coefficient)).toEqual(['CC_offset'])
  })

  /** Zero appears all over a calibration file. Highlighting a constant's
   *  expected value would mark arbitrary lines and imply the vendor disagreed. */
  it('does not let a constant of zero light up the whole file', () => {
    expect(vendorLines(VENDOR, vendorValues(differences)).filter((line) => line.hit)).toHaveLength(1)
  })
})

describe('what can be shown', () => {
  /** Every extension the vendor repository actually holds. An allow-list here
   *  silently refused .dev, .dev.lambda, .tdf and .con — 323 real files. */
  it('accepts every vendor format on file', () => {
    for (const name of [
      'ATAPL-69827-10004__20240616.xmlcon',
      'SBE43-0361.CAL',
      'thing.csv',
      'ACS-179__20130422.dev',
      'ACS-179__20130422.dev.lambda',
      'sensor.tdf',
      'sensor.con',
      'sensor.xml',
    ]) {
      expect(isText(name), name).toBe(true)
    }
  })

  it('refuses a scan, which is on file but cannot be read here', () => {
    expect(isText('OPTAA-scan.pdf')).toBe(false)
    expect(isText('OPTAA-scan.PDF')).toBe(false)
  })
})

describe('a coefficient the vendor file does not carry', () => {
  const missing: Difference[] = [
    { coefficient: 'CC_taarray', github: 1.5, expected: null, difference: null, source: 'vendor' },
  ]

  it('has no value to look for, so it marks nothing', () => {
    expect(vendorValues(missing)).toEqual([])
    expect(vendorLines(VENDOR, vendorValues(missing)).some((line) => line.hit)).toBe(false)
  })
})

describe('reading the file the finding came from', () => {
  it('points at the ref the run read, not at the branch head', () => {
    expect(rawUrl('oceanobservatories/asset-management', 'a1b2c3', 'calibration/CTDBPN/x.csv')).toBe(
      'https://raw.githubusercontent.com/oceanobservatories/asset-management/a1b2c3/calibration/CTDBPN/x.csv',
    )
  })
})


describe('which version of the file is shown', () => {
  it('uses the commit when the run resolved one', () => {
    const source = { ref: 'master', commit: 'a'.repeat(40) }
    expect(isPinned(source)).toBe(true)
    expect(readAt(source)).toBe('a'.repeat(40))
  })

  /** The failure this exists for: a run that recorded no commit was shown at
   *  master, and a coefficient it reported as differing read as identical in
   *  both panes — the files on screen were not the files the check read. */
  it('falls back to the ref, and says the run was not pinned', () => {
    for (const commit of [null, undefined, 'UNKNOWN']) {
      const source = { ref: 'master', commit }
      expect(isPinned(source), String(commit)).toBe(false)
      expect(readAt(source)).toBe('master')
    }
  })
})
