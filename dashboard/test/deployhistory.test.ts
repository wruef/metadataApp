import { describe, expect, it } from 'vitest'

import { historyUrlFor, rowCount } from '../app/deployhistory'

/** A real `ADCPFP_deployments.csv`, which is the smallest file the deployments
 *  repository holds. Written by history.py, trailing newline and all. */
const ADCPFP = 'sensorType,referenceDesignator,startTime,endTime,assetID,instrumentSN,lat,lon,'
  + 'githubCalibrationFile,vendorCalibrationFile\n'
  + 'ADCPFP,RS01SBPS-SF01A-4B-ADCPFP001,2014-08-01 00:00:00,,ATAPL-58307-00001,'
  + "\"['16480']\",44.52897,-125.38966,none,none\n"

describe('counting what is in a file', () => {
  it('does not count the header', () => {
    expect(rowCount(ADCPFP)).toBe(1)
  })

  /** history.py ends every file with a newline, which would otherwise read as
   *  one more deployment than the run found. */
  it('does not count the trailing newline', () => {
    expect(rowCount('a,b\n1,2\n3,4\n')).toBe(2)
  })

  it('counts a header on its own as nothing, not as minus one', () => {
    expect(rowCount('sensorType,referenceDesignator\n')).toBe(0)
    expect(rowCount('')).toBe(0)
  })
})

/**
 * A history belongs to the run that built it, so reading an earlier run has to
 * reach that run's history rather than the newest one.
 */
describe('which history belongs to which run', () => {
  const LATEST = '/metadataApp/reports/history-latest.json'

  it('is the fixed url for the current run', () => {
    expect(historyUrlFor(LATEST, null)).toBe(LATEST)
  })

  it('follows from the report name for a published run', () => {
    expect(historyUrlFor(LATEST, 'report_20260917T230227Z.json'))
      .toBe('/metadataApp/reports/history_20260917T230227Z.json')
  })

  it('keeps the directory the reports are served from', () => {
    expect(historyUrlFor('/sub/path/reports/history-latest.json', 'report_20260101T000000Z.json'))
      .toBe('/sub/path/reports/history_20260101T000000Z.json')
  })
})
