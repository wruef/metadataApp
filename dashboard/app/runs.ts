import { defineStore } from 'pinia'

import { useAuth } from '~/auth'
import {
  dispatchInputs,
  flattenSteps,
  newSource,
  pickRun,
  WORKFLOW,
  type Source,
  type Step,
  type WorkflowRun,
} from '~/dispatch'
import { authHeaders } from '~/github'

/**
 * Starting a verification run from the dashboard.
 *
 * A run is an event someone chooses — there is no schedule — so this is the
 * control that makes that choice without leaving for the Actions tab. It posts
 * a `workflow_dispatch` to the reviewer's own copy of this repository and then
 * follows the run it started. What a run is dispatched *with* lives in
 * `dispatch.ts`, which is where it can be tested.
 */

const API = 'https://api.github.com/repos'

export type RunStatus = 'idle' | 'starting' | 'finding' | 'running' | 'done' | 'error'

/** How often a run in flight is asked about. A verification takes minutes. */
const POLL_MS = 5_000

export const useRuns = defineStore('runs', () => {
  const source = reactive<Source>(newSource())
  const status = ref<RunStatus>('idle')
  const error = ref('')
  const run = shallowRef<WorkflowRun | null>(null)
  const steps = shallowRef<Step[]>([])
  const open = ref(false)
  /** Which workflow is being followed, and what to call it on screen. The tray
   *  is shared by all three, so it has to say which one it is showing. */
  const workflow = ref(WORKFLOW)
  const label = ref('all checks')

  let timer: ReturnType<typeof setTimeout> | null = null

  const busy = computed(
    () => status.value === 'starting' || status.value === 'finding' || status.value === 'running',
  )

  function options() {
    return { headers: authHeaders(useAuth().token) }
  }

  /** Stops following the run. The run itself keeps going on GitHub. */
  function stopWatching() {
    if (timer) clearTimeout(timer)
    timer = null
  }

  function fail(caught: unknown) {
    stopWatching()
    status.value = 'error'
    const code =
      caught && typeof caught === 'object' && 'status' in caught ? Number(caught.status) : 0
    error.value =
      code === 403 || code === 404
        ? 'GitHub refused that. A fine-grained token needs Actions set to read and write on this repository, and the workflow has to exist on its default branch.'
        : caught instanceof Error
          ? caught.message
          : String(caught)
  }

  /**
   * Starts a workflow and follows it until it finishes.
   *
   * ``what`` is what the tray calls it, as a noun phrase: "Running all checks",
   * "Running the serial number extraction".
   */
  async function dispatch(file: string, inputs: Record<string, unknown>, what: string) {
    const auth = useAuth()
    const repo = auth.workflowRepo
    stopWatching()
    workflow.value = file
    label.value = what
    error.value = ''
    run.value = null
    steps.value = []
    status.value = 'starting'
    open.value = true
    const since = Date.now()
    try {
      await $fetch(`${API}/${repo}/actions/workflows/${file}/dispatches`, {
        ...options(),
        method: 'POST',
        body: { ref: auth.workflowRef, inputs },
      })
      status.value = 'finding'
      poll(repo, since)
    } catch (caught) {
      fail(caught)
    }
  }

  /** The verification run, which is what the bar at the top starts. */
  function start() {
    return dispatch(WORKFLOW, dispatchInputs(source), 'all checks')
  }

  async function poll(repo: string, since: number) {
    try {
      if (!run.value) {
        const found = await $fetch<{ workflow_runs: WorkflowRun[] }>(
          `${API}/${repo}/actions/workflows/${workflow.value}/runs?event=workflow_dispatch&per_page=5`,
          options(),
        )
        run.value = pickRun(found.workflow_runs, since)
        if (run.value) status.value = 'running'
      } else {
        run.value = await $fetch<WorkflowRun>(`${API}/${repo}/actions/runs/${run.value.id}`, options())
        const jobs = await $fetch<{ jobs: { name: string; steps?: Step[] }[] }>(
          `${API}/${repo}/actions/runs/${run.value.id}/jobs`,
          options(),
        )
        steps.value = flattenSteps(jobs.jobs)
        if (run.value.status === 'completed') {
          stopWatching()
          status.value = 'done'
          return
        }
      }
      timer = setTimeout(() => poll(repo, since), POLL_MS)
    } catch (caught) {
      fail(caught)
    }
  }

  return { source, status, error, run, steps, open, busy, workflow, label,
           start, dispatch, stopWatching }
})
