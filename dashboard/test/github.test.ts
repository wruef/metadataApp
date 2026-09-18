import { describe, expect, it } from 'vitest'

import { authHeaders, isMissing, syncRefusal } from '../app/github'

/**
 * The sign-off path reads a sheet in order to add a line to it, so what a
 * failed read means decides what gets proposed.
 */
describe('a sheet the fork does not have', () => {
  it('is a 404 and nothing else', () => {
    expect(isMissing({ status: 404 })).toBe(true)
  })

  /** A revoked token, a rate limit, a repository the reviewer cannot see. None
   *  of them is an empty sheet, and treating one as empty would build the sheet
   *  from the single decision in hand and propose deleting every other
   *  sign-off in it. */
  it('is not any other failure', () => {
    expect(isMissing({ status: 403 })).toBe(false)
    expect(isMissing({ status: 401 })).toBe(false)
    expect(isMissing({ status: 500 })).toBe(false)
  })

  it('is not a failure that carries no status at all', () => {
    expect(isMissing(new Error('network down'))).toBe(false)
    expect(isMissing(undefined)).toBe(false)
    expect(isMissing(null)).toBe(false)
    expect(isMissing('404')).toBe(false)
  })
})

describe('the token is sent to github and nowhere else', () => {
  it('goes in the authorization header', () => {
    expect(authHeaders('abc')).toEqual({
      Authorization: 'Bearer abc',
      Accept: 'application/vnd.github+json',
    })
  })
})

/**
 * A calibration correction is written to a fork and justified by a finding
 * produced against upstream, so the fork has to be exactly upstream.
 */
describe('whether a fork may be corrected', () => {
  const UPSTREAM = 'oceanobservatories/asset-management'

  it('allows a fork that is exactly upstream', () => {
    expect(syncRefusal({ status: 'identical', ahead_by: 0, behind_by: 0 }, UPSTREAM)).toBeNull()
  })

  it('refuses a fork that is behind, which would revert what landed meanwhile', () => {
    const refusal = syncRefusal({ status: 'behind', ahead_by: 0, behind_by: 12 }, UPSTREAM)
    expect(refusal).toContain('12 commits behind')
    expect(refusal).toContain(UPSTREAM)
  })

  /** An onward pull request from an ahead fork carries its extra commits too,
   *  so the correction would not arrive upstream on its own. */
  it('refuses a fork that is ahead', () => {
    expect(syncRefusal({ status: 'ahead', ahead_by: 1, behind_by: 0 }, UPSTREAM))
      .toContain('1 commit ahead of')
  })

  it('says both numbers when the fork has diverged', () => {
    const refusal = syncRefusal({ status: 'diverged', ahead_by: 2, behind_by: 5 }, UPSTREAM)
    expect(refusal).toContain('5 commits behind')
    expect(refusal).toContain('2 commits ahead of')
  })

  it('says what to do about it', () => {
    expect(syncRefusal({ status: 'behind', ahead_by: 0, behind_by: 1 }, UPSTREAM))
      .toContain('Sync it on GitHub, run the checks again')
  })
})
