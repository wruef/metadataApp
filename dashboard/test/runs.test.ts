import { describe, expect, it } from 'vitest'

import {
  dispatchInputs,
  sourceLabel,
  flattenSteps,
  newSource,
  pickRun,
  PRODUCTION,
  ready,
  SLACK_MS,
  type WorkflowRun,
} from '../app/dispatch'

function testing(overrides: Record<string, unknown> = {}) {
  return { ...newSource(), mode: 'testing' as const, ref: 'a-branch', ...overrides }
}

describe('what a run is dispatched with', () => {
  it('verifies production by default', () => {
    expect(dispatchInputs(newSource())).toEqual({
      asset_management_repo: PRODUCTION.repo,
      asset_management_ref: PRODUCTION.ref,
      calibration_files_ref: PRODUCTION.calRef,
      baseline_ref: '',
      publish: false,
    })
  })

  it('publishes a branch run when asked to, because it moves nothing', () => {
    // It is committed under its own name and appears in the run picker; only a
    // production run becomes the figures everyone reads. Publishing is how a
    // branch check gets into the dashboard at all rather than being downloaded
    // as a zip.
    expect(dispatchInputs(testing({ publish: true })).publish).toBe(true)
  })

  it('publishes a production run when asked to', () => {
    expect(dispatchInputs({ ...newSource(), publish: true }).publish).toBe(true)
  })

  it('does not publish unless asked', () => {
    expect(dispatchInputs(testing()).publish).toBe(false)
    expect(dispatchInputs(newSource()).publish).toBe(false)
  })

  it('takes the repository and ref from the testing fields', () => {
    const inputs = dispatchInputs(testing({ repo: 'wruef/asset-management', ref: 'fix-nutnr' }))
    expect(inputs.asset_management_repo).toBe('wruef/asset-management')
    expect(inputs.asset_management_ref).toBe('fix-nutnr')
  })

  it('falls back to production for any testing field left empty', () => {
    // A blank calibrationFiles ref is the common case: the branch under test is
    // usually only in asset-management.
    expect(dispatchInputs(testing({ calRef: '   ' })).calibration_files_ref).toBe(PRODUCTION.calRef)
    expect(dispatchInputs(testing({ repo: '' })).asset_management_repo).toBe(PRODUCTION.repo)
  })

  it('ignores the testing fields while the bar says production', () => {
    const source = { ...newSource(), repo: 'wruef/asset-management', ref: 'a-branch' }
    expect(dispatchInputs(source).asset_management_ref).toBe(PRODUCTION.ref)
  })

  it('passes a baseline through, and an empty one as no comparison', () => {
    expect(dispatchInputs(testing({ baseline: 'master' })).baseline_ref).toBe('master')
    expect(dispatchInputs(testing()).baseline_ref).toBe('')
  })

  it('drops a baseline chosen in testing once the bar says production', () => {
    // The select is only shown in testing, but its value outlives the switch.
    const source = { ...newSource(), baseline: 'master' }
    expect(dispatchInputs(source).baseline_ref).toBe('')
  })

  it('will not start a testing run that names nothing', () => {
    expect(ready(newSource())).toBe(true)
    expect(ready(testing({ ref: '' }))).toBe(false)
    expect(ready(testing({ ref: '  ' }))).toBe(false)
    expect(ready(testing())).toBe(true)
  })
})

describe('telling published runs apart', () => {
  const sources = (repo: string, ref: string) => ({ assetManagement: { repo, ref, commit: 'a' } })

  it('says nothing about a production run', () => {
    expect(sourceLabel(sources(PRODUCTION.repo, PRODUCTION.ref))).toBe('')
  })

  /** A fork's own master read as ' · master', which is exactly what production
   *  looks like — so a run against a fork was indistinguishable from one
   *  against what is merged. */
  it('names the fork when only the repository differs', () => {
    expect(sourceLabel(sources('wruef/asset-management', 'master'))).toBe('wruef')
  })

  it('names the branch when only the ref differs', () => {
    expect(sourceLabel(sources(PRODUCTION.repo, 'fix-nutnr'))).toBe('fix-nutnr')
  })

  it('names both when both differ', () => {
    expect(sourceLabel(sources('wruef/asset-management', 'fix-nutnr'))).toBe('wruef@fix-nutnr')
  })

  it('says nothing when the run recorded no source', () => {
    expect(sourceLabel(undefined)).toBe('')
    expect(sourceLabel({})).toBe('')
  })
})

describe('finding the run that was just started', () => {
  const at = (iso: string): WorkflowRun => ({
    id: Date.parse(iso),
    created_at: iso,
    status: 'in_progress',
    conclusion: null,
    html_url: 'https://github.com/x/y/actions/runs/1',
  })
  const since = Date.parse('2026-09-16T12:00:00Z')

  it('takes a run stamped a moment after the dispatch', () => {
    expect(pickRun([at('2026-09-16T12:00:03Z')], since)?.created_at).toBe('2026-09-16T12:00:03Z')
  })

  it('tolerates a stamp slightly before it, since GitHub rounds to the second', () => {
    const rounded = new Date(since - SLACK_MS + 1000).toISOString()
    expect(pickRun([at(rounded)], since)).not.toBeNull()
  })

  it('does not adopt an older run someone else started', () => {
    expect(pickRun([at('2026-09-16T11:40:00Z')], since)).toBeNull()
  })

  it('is empty until the run appears', () => {
    expect(pickRun([], since)).toBeNull()
  })
})

describe('steps', () => {
  it('reads every job as one list', () => {
    expect(
      flattenSteps([
        { name: 'verify', steps: [{ name: 'Clone', status: 'completed', conclusion: 'success' }] },
        { name: 'other', steps: [{ name: 'Run', status: 'in_progress', conclusion: null }] },
      ]).map((step) => step.name),
    ).toEqual(['Clone', 'Run'])
  })

  it('survives a job GitHub has not filled in yet', () => {
    expect(flattenSteps([{ name: 'verify' }])).toEqual([])
  })
})
