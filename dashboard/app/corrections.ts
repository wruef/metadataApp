import { defineStore } from 'pinia'

import { FORKS, useAuth } from '~/auth'
import {
  applyCorrections,
  calibrationPath,
  correctionBody,
  correctionTitle,
  type Correction,
} from '~/calfile'
import {
  applyPositionCorrections,
  deploymentPath,
  positionBody,
  positionTitle,
  type FieldCorrection,
} from '~/deployfile'
import { useForkSync } from '~/forksync'
import { openPullRequest, readFile } from '~/github'

/**
 * Proposing a corrected asset-management file to the reviewer's own fork: a
 * calibration file's coefficients, or one deployment's position.
 *
 * Deliberately not part of the sign-off queue, and deliberately one pull
 * request per record -- one calibration file, or one deployment. A sign-off records a judgement about a file and a wrong one
 * is a wrong opinion; this changes the file, and a wrong digit here changes
 * every data product computed from it. One record per request keeps the unit of
 * review the same as the unit of harm, and keeps a correction out of a batch
 * somebody merges on the strength of its title.
 *
 * It reaches the fork only. The onward pull request to the shared repository is
 * raised by hand, and no data moves until that one is reviewed and merged.
 *
 * Two guards, both refusals rather than warnings. The fork has to be exactly
 * upstream, and the value has to still read what the run read. Between them
 * they mean a correction can only ever start from the file the finding came
 * from.
 */
export { calibrationPath }

export const useCorrections = defineStore('corrections', () => {
  /** Keyed by file path, so two rows of the same file cannot submit at once. */
  const submitting = ref<Record<string, boolean>>({})
  const results = ref<Record<string, { url: string | null; message: string }>>({})

  const sync = useForkSync()
  const fork = () => useAuth().forkFor('assetManagement')
  const definition = FORKS.find((each) => each.key === 'assetManagement')!

  /** Why the fork may not be corrected, or null. Asked before the editor opens,
   *  so a reviewer is told to sync their fork before typing a number into it. */
  const refusal = computed(() => sync.refusal.assetManagement ?? null)
  const checking = computed(() => Boolean(sync.checking.assetManagement))
  const checkSync = (force = false) => sync.check('assetManagement', force)

  /**
   * One record corrected, proposed as its own pull request.
   *
   * `rewrite` is handed the file as the fork holds it and returns the corrected
   * text with the title and body to propose it under. Both kinds of correction
   * go through here, so neither can be written without the guards.
   *
   * `id` is what the editor watches for its own result, and is the record
   * rather than the file: one deployment sheet holds two hundred deployments.
   */
  async function propose(
    id: string,
    path: string,
    prefix: string,
    rewrite: (current: string, by: string) => { text: string; title: string; body: string },
  ) {
    const auth = useAuth()
    submitting.value = { ...submitting.value, [id]: true }
    const { [id]: _cleared, ...rest } = results.value
    results.value = rest
    try {
      // Re-asked at the moment of writing, not trusted from when the editor
      // opened: upstream can move while a reviewer is reading two files.
      const blocked = await checkSync(true)
      if (blocked) throw new Error(blocked)

      const repo = fork()
      const current = await readFile(repo, path, definition.base)
      if (current === null) {
        throw new Error(`${repo} has no ${path}. Check the fork named on the settings page.`)
      }
      // Throws when a value no longer reads what the run read. The fork matches
      // upstream by now, so that means upstream has moved and the report on
      // screen is older than the file.
      const { text, title, body } = rewrite(current, `${auth.initials} (${auth.user?.login})`)
      const url = await openPullRequest(
        repo, definition.base, { [path]: text }, title, body, prefix)
      results.value = {
        ...results.value,
        [id]: url
          ? { url, message: 'Pull request opened on your asset-management fork.' }
          : { url: null, message: 'Your fork already holds these values — nothing to propose.' },
      }
    } catch (caught) {
      results.value = {
        ...results.value,
        [id]: { url: null, message: caught instanceof Error ? caught.message : String(caught) },
      }
    } finally {
      submitting.value = { ...submitting.value, [id]: false }
    }
  }

  /** A calibration file's coefficients. */
  function proposeCalibration(instrument: string, fileName: string, corrections: Correction[]) {
    const path = calibrationPath(instrument, fileName)
    return propose(path, path, 'calibration', (current, by) => ({
      text: applyCorrections(current, corrections),
      title: correctionTitle(fileName, corrections),
      body: correctionBody(path, corrections, by),
    }))
  }

  /** One deployment's position on its array's sheet. */
  function proposePosition(
    refDes: string,
    deployNum: string | number,
    positionName: string,
    corrections: FieldCorrection[],
  ) {
    return propose(
      deploymentKey(refDes, deployNum), deploymentPath(refDes), 'position',
      (current, by) => {
        const { text, clearedNote } = applyPositionCorrections(
          current, refDes, deployNum, corrections)
        return {
          text,
          title: positionTitle(refDes, deployNum, corrections),
          body: positionBody(refDes, deployNum, positionName, corrections, by, clearedNote),
        }
      },
    )
  }

  return { submitting, results, refusal, checking, checkSync,
           proposeCalibration, proposePosition }
})

/** One deployment of one instrument, which is what a position correction is
 *  about -- not the sheet, which holds every deployment on its array. */
export function deploymentKey(refDes: string, deployNum: string | number) {
  return `${refDes}#${deployNum}`
}
