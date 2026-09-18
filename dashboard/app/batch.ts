import { defineStore } from 'pinia'

import { FORKS, useAuth, type ForkKey } from '~/auth'
import {
  applyCorrections,
  calibrationPath,
  correctionSection,
  correctionTitle,
  type Correction,
} from '~/calfile'
import {
  applyDeploymentCorrections,
  ASSET_FIELD,
  deploymentPath,
  deploymentSection,
  deploymentTitle,
  type FieldCorrection,
} from '~/deployfile'
import { useForkSync } from '~/forksync'
import { openPullRequest, readFile } from '~/github'
import { applyDecisions, hitlDate } from '~/hitl'
import { HITL_SHEETS, type SheetKey } from '~/signoff'

/**
 * Everything a reviewer has decided but not yet proposed, gathered into one
 * pull request per batch.
 *
 * A batch is keyed by the repository it writes to **and** by what the change
 * is. Both halves matter. The repository is a hard boundary — a pull request
 * cannot span two of them — and the kind is a boundary of review: a calibration
 * coefficient and a deployment position both land in asset-management, and
 * somebody approving a page of coefficients has not agreed to move an
 * instrument on the seabed. So the two travel separately even though they share
 * a fork.
 *
 * Corrections used to go one pull request per record, so that the unit of
 * review was the unit of harm. A season's work is thirty of them, which is
 * thirty branches to raise upstream by hand; the unit of review is kept instead
 * by giving each record its own section of the body, and by keeping the kinds
 * apart. What has not changed is where they go: a reviewer's own fork, never a
 * shared repository, with the onward request raised by hand.
 */

export type BatchKey = 'signoffs' | 'calibrations' | 'sheets'

export const BATCHES = [
  {
    key: 'signoffs',
    fork: 'hitl',
    title: 'Sign-offs',
    unit: 'row',
    what: 'the team record of who checked what',
    prefix: 'hitl',
    /** A sign-off records a judgement about a file rather than changing one, so
     *  a fork that has drifted from upstream does not invalidate it. */
    guarded: false,
  },
  {
    key: 'calibrations',
    fork: 'assetManagement',
    title: 'Calibration coefficients',
    unit: 'file',
    what: 'the calibration files every data product is computed from',
    prefix: 'calibration',
    guarded: true,
  },
  {
    key: 'sheets',
    fork: 'assetManagement',
    title: 'Deployment sheets',
    unit: 'deployment',
    what: 'what the deployment sheets say was in the water, and where',
    prefix: 'deployment',
    guarded: true,
  },
] as const satisfies readonly {
  key: BatchKey
  fork: ForkKey
  title: string
  unit: string
  what: string
  prefix: string
  guarded: boolean
}[]

export function batchDefinition(key: BatchKey) {
  return BATCHES.find((batch) => batch.key === key)!
}

/** The batches that write to one fork, in the order they are worth reading. */
export function batchesFor(fork: ForkKey) {
  return BATCHES.filter((batch) => batch.fork === fork)
}

export interface SignoffEntry {
  batch: 'signoffs'
  /** Sheet and line together: two sheets can hold the same identifier, and an
   *  assetID signed off in one is not the same decision as a file of that name
   *  signed off in another. */
  key: string
  sheet: SheetKey
  /** The line in the sheet, which is what the sheet is keyed on. */
  row: string
  status: 'Clear' | 'NotClear'
  notes: string
}

/** The queue's own identifier for one sign-off. */
export function signoffKey(sheet: SheetKey, row: string) {
  return `${sheet}:${row}`
}

export interface CalibrationEntry {
  batch: 'calibrations'
  key: string
  instrument: string
  fileName: string
  corrections: Correction[]
}

/**
 * One correction to one deployment's row on its array's sheet.
 *
 * Where it sat and which instrument it was are two different claims about the
 * same row, and a reviewer can make both. They are one batch because they are
 * one file: two pull requests editing `RS03AXPS_Deploy.csv` on branches cut
 * from the same base conflict the moment the first of them merges.
 */
export interface SheetEntry {
  batch: 'sheets'
  /** Kind and deployment together, so correcting where a deployment sat does
   *  not replace the correction of which instrument it was. */
  key: string
  kind: 'position' | 'asset'
  refDes: string
  deployNum: string | number
  /** One sentence saying what the new values were taken from, which is the
   *  whole justification the pull request offers for this row. */
  source: string
  corrections: FieldCorrection[]
}

export type Entry = SignoffEntry | CalibrationEntry | SheetEntry

/** What identifies one correction to one deployment. Not the sheet, which holds
 *  every deployment on its array, and not the deployment on its own. */
export function sheetKey(kind: SheetEntry['kind'], refDes: string, deployNum: string | number) {
  return `${kind}:${refDes}#${deployNum}`
}

/** The file in the fork an entry writes to. Several entries can share one: a
 *  deployment sheet holds every deployment on its array. */
export function pathOf(entry: Entry) {
  if (entry.batch === 'signoffs') return HITL_SHEETS[entry.sheet].path
  if (entry.batch === 'calibrations') return calibrationPath(entry.instrument, entry.fileName)
  return deploymentPath(entry.refDes)
}

/** What the queue shows for one entry: what it is about, and what it would do. */
export function describe(entry: Entry): { name: string; summary: string } {
  if (entry.batch === 'signoffs') {
    return {
      name: entry.row,
      summary: entry.notes || 'No note — worth saying what convinced you.',
    }
  }
  if (entry.batch === 'calibrations') {
    return {
      name: entry.fileName,
      summary: entry.corrections
        .map((each) => `${each.coefficient}: ${each.from} → ${each.to}`)
        .join(', '),
    }
  }
  return {
    name: `${entry.refDes} deployment ${entry.deployNum}`,
    summary: entry.corrections.map((each) => `${each.field}: ${each.from} → ${each.to}`).join(', '),
  }
}

function groupByPath(entries: Entry[]) {
  const groups = new Map<string, Entry[]>()
  for (const entry of entries) {
    const path = pathOf(entry)
    groups.set(path, [...(groups.get(path) ?? []), entry])
  }
  return groups
}

const message = (caught: unknown) => (caught instanceof Error ? caught.message : String(caught))

export interface Built {
  files: Record<string, string>
  title: string
  body: string
}

/**
 * The pull request one batch would open: the files it writes, and the review.
 *
 * `current` is what the fork holds for every path the batch touches, already
 * read. Kept out of this function so the whole shape of a proposal can be
 * tested without a network.
 *
 * It refuses the whole batch rather than proposing part of it. A record that no
 * longer reads what the run read means the file has moved since the report on
 * screen, and that casts the same doubt over every other record in the batch —
 * so dropping the stale one and writing the rest would be writing from a report
 * already known to be out of date.
 */
export function buildBatch(
  batch: BatchKey,
  entries: Entry[],
  current: Record<string, string | null>,
  by: string,
  initials: string,
  when = new Date(),
): Built {
  if (batch === 'signoffs') return buildSignoffs(entries as SignoffEntry[], current, by, initials, when)

  const files: Record<string, string> = {}
  const sections: string[] = []
  const failed: string[] = []

  for (const [path, forPath] of groupByPath(entries)) {
    const held = current[path]
    if (held === null || held === undefined) {
      failed.push(`${path}: your fork has no such file`)
      continue
    }
    let text = held
    for (const entry of forPath) {
      const { name } = describe(entry)
      try {
        if (entry.batch === 'calibrations') {
          text = applyCorrections(text, entry.corrections)
          sections.push(correctionSection(path, entry.corrections))
        } else if (entry.batch === 'sheets') {
          const applied = applyDeploymentCorrections(
            text, entry.refDes, entry.deployNum, entry.corrections)
          text = applied.text
          sections.push(deploymentSection(entry.refDes, entry.deployNum, entry.source,
                                          entry.corrections, applied.clearedNote))
        }
      } catch (caught) {
        failed.push(`${name}: ${message(caught)}`)
      }
    }
    files[path] = text
  }

  if (failed.length) {
    throw new Error(
      [`${failed.length} of ${entries.length} could not be applied, so nothing was proposed:`,
       ...failed.map((each) => `• ${each}`),
       'The files have moved since the run on screen. Start a run against them and work from it.',
      ].join('\n'))
  }

  const definition = batchDefinition(batch)
  return {
    files,
    title: batchTitle(batch, entries),
    body: [
      sections.join('\n\n---\n\n'),
      '',
      `Proposed from the metadata dashboard by ${by}.`,
      '',
      `This changes ${definition.what} rather than recording a judgement about ${
        entries.length === 1 ? 'it' : 'them'}.`,
      'Review it here, then raise the pull request to the upstream repository by hand.',
    ].join('\n'),
  }
}

function buildSignoffs(
  entries: SignoffEntry[],
  current: Record<string, string | null>,
  by: string,
  initials: string,
  when: Date,
): Built {
  const files: Record<string, string> = {}
  for (const [sheet, definition] of Object.entries(HITL_SHEETS)) {
    const forSheet = entries.filter((entry) => entry.sheet === sheet)
    if (!forSheet.length) continue
    files[definition.path] = applyDecisions(
      current[definition.path] ?? null, definition.key,
      forSheet.map(({ row, status, notes }) => ({ key: row, status, notes })), initials, when)
  }
  return {
    files,
    title: `HITL sign-offs, ${hitlDate(when)}`,
    body: `${entries.length} row(s) signed off by ${by}.\n\n`
      + 'Review here, then raise the pull request to the upstream repository by hand.',
  }
}

/** What the pull request is called. One record keeps the title it would have
 *  had on its own, because a batch of one is not a batch to read about. */
export function batchTitle(batch: BatchKey, entries: Entry[]) {
  const only = entries.length === 1 ? entries[0]! : null
  if (batch === 'calibrations') {
    const calibrations = entries as CalibrationEntry[]
    return only && only.batch === 'calibrations'
      ? correctionTitle(only.fileName, only.corrections)
      : `Correct coefficients in ${calibrations.length} calibration files`
  }
  if (batch === 'sheets') {
    return only && only.batch === 'sheets'
      ? deploymentTitle(only.refDes, only.deployNum, only.corrections)
      : `Correct ${entries.length} deployment sheet rows`
  }
  return `HITL sign-offs, ${hitlDate()}`
}

export interface Result {
  url: string | null
  message: string
}

export const useBatch = defineStore('batch', () => {
  /** Everything queued, across every batch. Deliberately not persisted: a
   *  correction is proposed from the run that justified it, and a queue
   *  surviving a reload would outlive the report it was built against. */
  const entries = ref<Entry[]>([])
  const submitting = ref<Record<string, boolean>>({})
  const results = ref<Record<string, Result>>({})

  const sync = useForkSync()
  const auth = useAuth()

  const count = computed(() => entries.value.length)

  const forBatch = (batch: BatchKey) => entries.value.filter((entry) => entry.batch === batch)

  /** The batches with something in them: what there is to propose. */
  const pending = computed(() =>
    BATCHES.map((definition) => ({ definition, entries: forBatch(definition.key) }))
      .filter((group) => group.entries.length))

  /** The batches the queue page shows. A batch that has just been proposed is
   *  empty and still belongs on screen: its result is the link to what it
   *  became, and clearing the rows must not take that away with them. */
  const shown = computed(() =>
    BATCHES.map((definition) => ({ definition, entries: forBatch(definition.key) }))
      .filter((group) => group.entries.length || results.value[group.definition.key]))

  /** The forks those batches write to, each with its own batches under it. */
  const byFork = computed(() =>
    FORKS.map((fork) => ({
      fork,
      repo: auth.forkFor(fork.key),
      groups: shown.value.filter((group) => group.definition.fork === fork.key),
    })).filter((each) => each.groups.length))

  function entryFor(batch: BatchKey, key: string) {
    return entries.value.find((entry) => entry.batch === batch && entry.key === key)
  }

  /** Queueing the same record twice replaces the earlier entry — a reviewer
   *  changing their mind before proposing is not two decisions. */
  function queue(entry: Entry) {
    entries.value = [
      ...entries.value.filter((each) => !(each.batch === entry.batch && each.key === entry.key)),
      entry,
    ]
    // Whatever this batch last became, it is not what is in it now.
    const { [entry.batch]: _stale, ...rest } = results.value
    results.value = rest
  }

  function unqueue(batch: BatchKey, key: string) {
    entries.value = entries.value.filter((each) => !(each.batch === batch && each.key === key))
  }

  /** One batch, or everything when no batch is named. */
  function discard(batch?: BatchKey) {
    entries.value = batch ? entries.value.filter((each) => each.batch !== batch) : []
    if (batch) {
      const { [batch]: _cleared, ...rest } = results.value
      results.value = rest
    } else {
      results.value = {}
    }
  }

  /** --- what each check queues --- */

  function queueSignoff(
    decision: { sheet: SheetKey; key: string; status: 'Clear' | 'NotClear'; notes: string },
  ) {
    const { sheet, key: row, status, notes } = decision
    queue({ batch: 'signoffs', key: signoffKey(sheet, row), sheet, row, status, notes })
  }

  function unqueueSignoff(sheet: SheetKey, row: string) {
    unqueue('signoffs', signoffKey(sheet, row))
  }

  /** What a row shows as already decided. */
  function decisionFor(sheet: SheetKey, row: string) {
    return entryFor('signoffs', signoffKey(sheet, row)) as SignoffEntry | undefined
  }

  function queueCalibration(instrument: string, fileName: string, corrections: Correction[]) {
    queue({ batch: 'calibrations', key: calibrationPath(instrument, fileName),
            instrument, fileName, corrections })
  }

  function queueSheet(kind: SheetEntry['kind'], refDes: string, deployNum: string | number,
                     source: string, corrections: FieldCorrection[]) {
    queue({ batch: 'sheets', key: sheetKey(kind, refDes, deployNum),
            kind, refDes, deployNum, source, corrections })
  }

  function queuePosition(refDes: string, deployNum: string | number, positionName: string,
                         corrections: FieldCorrection[]) {
    queueSheet('position', refDes, deployNum,
               `Taken from the RCA position spreadsheet${
                 positionName ? `, position \`${positionName}\`` : ''}.`,
               corrections)
  }

  /** Which instrument the sheet says was in the water. */
  function queueAsset(refDes: string, deployNum: string | number,
                      from: string, to: string, source: string) {
    queueSheet('asset', refDes, deployNum, source, [{ field: ASSET_FIELD, from, to }])
  }

  /** --- the fork guard, asked before a reviewer types rather than after --- */

  const refusalFor = (fork: ForkKey) => sync.refusal[fork] ?? null
  const checkingFor = (fork: ForkKey) => Boolean(sync.checking[fork])
  const checkSync = (fork: ForkKey, force = false) => sync.check(fork, force)

  /** One batch, proposed as one pull request on the reviewer's own fork. */
  async function submit(batch: BatchKey) {
    const definition = batchDefinition(batch)
    const forkDefinition = FORKS.find((each) => each.key === definition.fork)!
    const mine = forBatch(batch)
    if (!mine.length) return
    submitting.value = { ...submitting.value, [batch]: true }
    const { [batch]: _cleared, ...rest } = results.value
    results.value = rest
    const fork = auth.forkFor(definition.fork)
    try {
      // Re-asked at the moment of writing, not trusted from when the reviewer
      // queued: upstream can move while a queue is being built.
      if (definition.guarded) {
        const blocked = await sync.check(definition.fork, true)
        if (blocked) throw new Error(blocked)
      }
      const current: Record<string, string | null> = {}
      for (const path of new Set(mine.map(pathOf))) {
        current[path] = await readFile(fork, path, forkDefinition.base)
      }
      const built = buildBatch(batch, mine, current,
                               `${auth.initials} (${auth.user?.login})`, auth.initials)
      const url = await openPullRequest(
        fork, forkDefinition.base, built.files, built.title, built.body, definition.prefix)
      results.value = {
        ...results.value,
        [batch]: url
          ? { url, message: `Pull request opened on ${fork}.` }
          : { url: null, message: `${fork} already holds these values — nothing to propose.` },
      }
      if (url) discardEntries(batch, mine)
    } catch (caught) {
      results.value = { ...results.value, [batch]: { url: null, message: message(caught) } }
    } finally {
      submitting.value = { ...submitting.value, [batch]: false }
    }
  }

  /** Clears the entries the request carried, and only those. Anything queued
   *  into the batch while the request was in flight was not in it, and must
   *  not vanish as though it had been. The result stays: it is the link to
   *  what the batch became. */
  function discardEntries(batch: BatchKey, sent: Entry[]) {
    const keys = new Set(sent.map((each) => each.key))
    entries.value = entries.value.filter((each) => !(each.batch === batch && keys.has(each.key)))
  }

  /** Every batch with something in it, one pull request each, in order. Run one
   *  at a time rather than together: they write to the same forks, and two
   *  branches cut from the same base at once is how a second one lands empty. */
  async function submitAll() {
    // Named up front: submitting empties each batch, and the list they come
    // from is derived from what is still queued.
    const keys = pending.value.map((group) => group.definition.key)
    for (const key of keys) await submit(key)
  }

  return { entries, count, pending, shown, byFork, submitting, results,
           forBatch, entryFor, queue, unqueue, discard,
           queueSignoff, unqueueSignoff, decisionFor, queueCalibration, queuePosition, queueAsset,
           refusalFor, checkingFor, checkSync, submit, submitAll }
})
