import { describe, expect, it } from 'vitest'

import { authHeaders, describeProposal, isMissing, syncRefusal } from '../app/github'

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

  it('tells a fork that is behind to sync', () => {
    expect(syncRefusal({ status: 'behind', ahead_by: 0, behind_by: 1 }, UPSTREAM))
      .toContain('Press Sync fork')
  })

  /** Sync fork on a fork that is ahead offers to discard the commits. Telling
   *  somebody to press it would throw away a correction that upstream has not
   *  merged yet, which is the usual reason a fork is ahead at all. */
  it('never tells a fork that is ahead to sync', () => {
    const refusal = syncRefusal({ status: 'ahead', ahead_by: 1, behind_by: 0 }, UPSTREAM)!
    expect(refusal).toContain('Do not press Sync fork')
    expect(refusal).toContain('Raise them upstream')
  })

  it('tells a diverged fork to get its own work merged before syncing', () => {
    const refusal = syncRefusal({ status: 'diverged', ahead_by: 1, behind_by: 1 }, UPSTREAM)!
    expect(refusal).toContain('Raise them upstream')
    expect(refusal).toContain('Once they have, press Sync fork')
  })
})


/**
 * The store records what happened; this is the one place it becomes a sentence,
 * so two pages showing the same outcome cannot word it differently.
 */
describe('what proposing a batch produced', () => {
  it('names the fork the pull request was opened on', () => {
    const said = describeProposal({ outcome: 'opened', url: 'https://x/pull/1', fork: 'wruef/asset-management' })
    expect(said.tone).toBe('success')
    expect(said.text).toContain('wruef/asset-management')
  })

  it('reads as neither success nor failure when the fork already says it', () => {
    // An empty pull request is not created, and that is not an error.
    const said = describeProposal({ outcome: 'unchanged', url: null, fork: 'wruef/deployments' })
    expect(said.tone).toBe('neutral')
    expect(said.text).toContain('nothing to propose')
  })

  it('shows a failure in the words it arrived in', () => {
    const said = describeProposal({
      outcome: 'failed', url: null, fork: 'wruef/asset-management',
      detail: 'Your fork is 2 commits behind oceanobservatories/asset-management.',
    })
    expect(said.tone).toBe('error')
    expect(said.text).toContain('2 commits behind')
  })

  it('still says something when a failure arrived with no detail', () => {
    const said = describeProposal({ outcome: 'failed', url: null, fork: 'wruef/deployments' })
    expect(said.tone).toBe('error')
    expect(said.text).toContain('wruef/deployments')
  })
})
