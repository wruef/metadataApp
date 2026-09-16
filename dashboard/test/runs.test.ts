import { describe, expect, it } from 'vitest'

import {
  dispatchInputs,
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

  it('will not start a testing run that names nothing', () => {
    expect(ready(newSource())).toBe(true)
    expect(ready(testing({ ref: '' }))).toBe(false)
    expect(ready(testing({ ref: '  ' }))).toBe(false)
    expect(ready(testing())).toBe(true)
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
