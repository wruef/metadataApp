import { describe, expect, it } from 'vitest'

import { authHeaders, isMissing } from '../app/github'

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
