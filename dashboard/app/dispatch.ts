/**
 * What a verification run is started with, and how the run that was started is
 * recognised afterwards.
 *
 * Nuxt-free on purpose, so it can be tested directly: this is the half that
 * decides what the workflow verifies, and a mistake here runs the checks
 * against the wrong repository without anything looking wrong.
 */

/** The workflow that runs every check. */
export const WORKFLOW = 'verify.yaml'

/** What production means, matching the workflow's own defaults. */
export const PRODUCTION = {
  repo: 'oceanobservatories/asset-management',
  ref: 'master',
  calRef: 'master',
}

export interface Source {
  /** Production is what has been merged; testing is a branch or a fork. */
  mode: 'production' | 'testing'
  repo: string
  ref: string
  calRef: string
  /** A second ref to verify against, or '' for no comparison. */
  baseline: string
  /** Upload the report for the dashboard to read. */
  publish: boolean
}

export function newSource(): Source {
  return {
    mode: 'production',
    repo: PRODUCTION.repo,
    ref: '',
    calRef: '',
    baseline: '',
    publish: false,
  }
}

/**
 * The workflow's inputs.
 *
 * Every field falls back to the production value, so a half-filled testing form
 * verifies production rather than dispatching a run against a ref that does not
 * exist — the workflow would clone nothing and fail six steps later.
 */
export function dispatchInputs(source: Source) {
  const testing = source.mode === 'testing'
  return {
    asset_management_repo: (testing && source.repo.trim()) || PRODUCTION.repo,
    asset_management_ref: (testing && source.ref.trim()) || PRODUCTION.ref,
    calibration_files_ref: (testing && source.calRef.trim()) || PRODUCTION.calRef,
    // The baseline is chosen in testing mode and the choice outlives the mode
    // switch, so a production run would otherwise compare master with master.
    baseline_ref: testing ? source.baseline.trim() : '',
    // Publishing commits the run under its own name and puts it in the run
    // picker. Only a production run also becomes latest.json, so a branch run
    // publishing moves nothing that anyone else reads — which is why it is
    // offered here rather than refused.
    publish: source.publish,
  }
}

/** A testing run with no ref names nothing — it would verify production twice. */
export function ready(source: Source) {
  return source.mode === 'production' || source.ref.trim() !== ''
}

/**
 * How a published run is told apart from production in the run picker.
 *
 * Empty for a production run, because the stamp already says when it ran. For
 * anything else it names what differs: the fork's owner, the branch, or both.
 * Naming only the ref was not enough — a fork's `master` read as ` · master`,
 * which is exactly what production looks like.
 */
export function sourceLabel(sources?: Record<string, { repo: string; ref: string } | unknown>) {
  const source = sources?.assetManagement as { repo: string; ref: string } | undefined
  if (!source) return ''
  const forked = source.repo !== PRODUCTION.repo
  const branched = source.ref !== PRODUCTION.ref
  if (!forked && !branched) return ''
  const owner = source.repo.split('/')[0]
  if (forked && branched) return `${owner}@${source.ref}`
  return forked ? owner! : source.ref
}

export interface WorkflowRun {
  id: number
  created_at: string
  status: string
  conclusion: string | null
  html_url: string
}

/**
 * The run we just started, out of the workflow's recent runs.
 *
 * A dispatch returns no identifier — only 204 — so the run has to be found
 * afterwards. GitHub stamps `created_at` to the second while the dispatch is
 * timed in milliseconds, so a few seconds of slack keeps the run we started
 * from being missed; the window is short enough not to adopt an older one.
 */
export const SLACK_MS = 10_000

export function pickRun(runs: WorkflowRun[], since: number) {
  return runs.find((run) => Date.parse(run.created_at) >= since - SLACK_MS) ?? null
}

export interface Step {
  name: string
  status: string
  conclusion: string | null
}

/** Every step of every job, in order, as one list to read down. */
export function flattenSteps(jobs: { name: string; steps?: Step[] }[]) {
  return jobs.flatMap((job) => job.steps ?? [])
}
