import { describe, expect, it } from 'vitest'

import { withBase } from '../app/paths'

describe('where the dashboard looks for a report', () => {
  it('serves from the domain root when there is no base', () => {
    expect(withBase('/', 'reports/latest.json')).toBe('/reports/latest.json')
  })

  /** The whole reason this exists: a Pages project site is under /<repo>/, and
   *  an absolute path asks github.io for a file that is not there. */
  it('serves from the repository path on a Pages project site', () => {
    expect(withBase('/metadataApp/', 'reports/latest.json')).toBe(
      '/metadataApp/reports/latest.json',
    )
  })

  it('does not double the separator, whichever side carries it', () => {
    expect(withBase('/metadataApp', '/reports/latest.json')).toBe('/metadataApp/reports/latest.json')
    expect(withBase('', 'reports/latest.json')).toBe('/reports/latest.json')
  })

  it('leaves a full URL alone, for a report kept somewhere else', () => {
    expect(withBase('/metadataApp/', 'https://example.org/report.json')).toBe(
      'https://example.org/report.json',
    )
  })
})
