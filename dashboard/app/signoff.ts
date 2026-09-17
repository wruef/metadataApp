import { defineStore } from 'pinia'

import { FORKS, useAuth } from '~/auth'
import { openPullRequest, readFile } from '~/github'
import { applyDecisions, hitlDate, type Decision as HitlDecision } from '~/hitl'

/** The two checks a reviewer signs off, and the sheet each one is recorded in.
 *  `key` is the column that identifies a row, and matches how the check itself
 *  looks a sign-off up. `of` rebuilds that identifier for a run published
 *  before the report carried it — see `hitlKeyOf`. */
export const HITL_SHEETS = {
  calibrations: {
    path: '2i_HITL/2i_HITL_calibrationVerification.csv',
    key: 'githubFile',
    of: (row: Record<string, unknown>) => String(row.fileName),
  },
  deployments: {
    path: '2i_HITL/2i_HITL_deploymentVerification.csv',
    key: 'referenceDesignatorYearDeployNum',
    of: (row: Record<string, unknown>) =>
      `${row.refDes}.${new Date(String(row.deployDate)).getFullYear()}.${row.deployNum}`,
  },
  /** Serial numbers that disagree between the RCA list and OOI's record are
   *  mostly a judgement about which record is right, and there was nowhere to
   *  write that judgement down — so 131 of them came back every run. */
  sensorBulk: {
    path: '2i_HITL/2i_HITL_sensorVerification.csv',
    key: 'assetID',
    of: (row: Record<string, unknown>) => String(row.assetID),
  },
} as const

export type SheetKey = keyof typeof HITL_SHEETS

/**
 * The line a sign-off writes to, as the run itself identified it.
 *
 * Taken from the row rather than rebuilt here. The fallback reads the year out
 * of the deployment date in the reader's own timezone, so a deployment dated
 * near midnight on the 31st of December belongs to one year in Seattle and the
 * next in UTC — and a sign-off then appends a second line to the sheet for a
 * deployment that already has one, instead of updating it. Runs published
 * before the report carried the key still have to be signed off, which is why
 * the fallback stays.
 */
export function hitlKeyOf(sheet: SheetKey, row: Record<string, unknown>) {
  return typeof row.hitlKey === 'string' && row.hitlKey
    ? row.hitlKey
    : HITL_SHEETS[sheet].of(row)
}

export interface Decision extends HitlDecision {
  sheet: SheetKey
}

export const useSignoff = defineStore('signoff', () => {
  const queued = ref<Decision[]>([])
  const submitting = ref(false)
  const result = ref<{ url: string | null; message: string } | null>(null)

  const count = computed(() => queued.value.length)

  function decisionFor(sheet: SheetKey, key: string) {
    return queued.value.find((decision) => decision.sheet === sheet && decision.key === key)
  }

  /** Queueing the same row twice replaces the earlier decision — a reviewer
   *  changing their mind before submitting is not two sign-offs. */
  function queue(decision: Decision) {
    queued.value = [
      ...queued.value.filter((each) => !(each.sheet === decision.sheet && each.key === decision.key)),
      decision,
    ]
  }

  function unqueue(sheet: SheetKey, key: string) {
    queued.value = queued.value.filter((each) => !(each.sheet === sheet && each.key === key))
  }

  function discard() {
    queued.value = []
    result.value = null
  }

  /** One pull request carrying the whole batch, against the reviewer's own fork.
   *  They raise the onward request to the shared repository by hand. */
  async function submit() {
    const auth = useAuth()
    const fork = auth.forkFor('hitl')
    submitting.value = true
    result.value = null
    try {
      // The branch the sheets live on, from the fork table rather than assumed:
      // this repository is on main and asset-management is on master, and a
      // sign-off written against the wrong one fails at the GitHub call.
      const base = FORKS.find((each) => each.key === 'hitl')!.base
      const files: Record<string, string> = {}
      for (const [sheet, definition] of Object.entries(HITL_SHEETS)) {
        const decisions = queued.value.filter((decision) => decision.sheet === sheet)
        if (!decisions.length) continue
        const current = await readFile(fork, definition.path, base)
        files[definition.path] = applyDecisions(current, definition.key, decisions, auth.initials)
      }

      const url = await openPullRequest(
        fork, base, files,
        `HITL sign-offs, ${hitlDate()}`,
        `${queued.value.length} row(s) signed off by ${auth.initials} (${auth.user?.login}).\n\n` +
          'Review here, then raise the pull request to the upstream repository by hand.',
      )
      result.value = url
        ? { url, message: 'Pull request opened on your fork.' }
        : { url: null, message: 'Your fork already matches these sign-offs — nothing to propose.' }
      if (url) queued.value = []
    } catch (caught) {
      result.value = {
        url: null,
        message: `Could not open the pull request: ${caught instanceof Error ? caught.message : String(caught)}`,
      }
    } finally {
      submitting.value = false
    }
  }

  return { queued, count, submitting, result, queue, unqueue, discard, submit, decisionFor }
})
