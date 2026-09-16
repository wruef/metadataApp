import { defineStore } from 'pinia'

/** Worst first — the order a queue is worked in. */
export const SEVERITIES = ['problem', 'review', 'unchecked', 'ok'] as const
export type Severity = (typeof SEVERITIES)[number]

export const SEVERITY_LABEL: Record<Severity, string> = {
  problem: 'Problem',
  review: 'Needs a person',
  unchecked: 'Not checked',
  ok: 'Agreed',
}

/** Nuxt UI badge colours. `as const` keeps the literal types, which is what the
 *  badge's own colour prop expects; `satisfies` still checks every severity has
 *  one. Annotating this `Record<Severity, string>` widens the values back to
 *  string and the badge rejects them. */
export const SEVERITY_COLOR = {
  problem: 'error',
  review: 'warning',
  unchecked: 'neutral',
  ok: 'success',
} as const satisfies Record<Severity, string>

export interface Row {
  severity: Severity
  cleared: boolean
  [key: string]: unknown
}

export interface Check {
  rows: Row[]
  summary: Record<Severity | 'cleared' | 'total', number>
  missingFromGithub?: string[]
}

export interface Source {
  repo: string
  ref: string
  commit: string | null
}

export interface Report {
  schemaVersion: number
  runAt: string
  sources: Record<string, Source | string | null>
  parameters: { commit: string; dirty: boolean }
  referenceDesignators: string[]
  checks: Record<string, Check>
}

/** The checks, in the order they are worth working. */
export const CHECKS = [
  { key: 'calibrations', title: 'Calibrations', icon: 'fa-flask',
    blurb: 'Repository calibration files against the vendor originals.',
    columns: ['fileName', 'instrument', 'vendorMatch', 'calRepo_check', 'serialNumber', 'HITLstatus'] },
  { key: 'deployments', title: 'Deployments', icon: 'fa-anchor',
    blurb: 'Every deployment: its calibration file, its raw serial number, its sign-off.',
    columns: ['refDes', 'deployNum', 'AssetID', 'verificationStatus', 'rawFile_verify', 'image_verify', 'calFile_verify'] },
  { key: 'positions', title: 'Positions', icon: 'fa-location-dot',
    blurb: 'Deployment sheets against the RCA position spreadsheet.',
    columns: ['refDes', 'deployNum', 'deployYear', 'positionName', 'verdict', 'sourceRow'] },
  { key: 'sensorBulk', title: 'Sensor bulk', icon: 'fa-barcode',
    blurb: 'Serial numbers between the RCA instrument list and the OOI sensor bulk record.',
    columns: ['assetID', 'rcaSerials', 'bulkSerial', 'verdict'] },
  { key: 'deploymentSheets', title: 'Sheet integrity', icon: 'fa-table',
    blurb: 'Deployment sheet entries that name something no other record knows about.',
    columns: ['refDes', 'deployNum', 'value', 'verdict'] },
] as const

export interface Moved {
  key: string[]
  row: Row
  was?: Severity
  now?: Severity
  fields?: string[]
}

export interface ComparedCheck {
  newlyFailing: Moved[]
  newlyPassing: Moved[]
  new: Moved[]
  gone: Moved[]
  changed: Moved[]
  unchanged: number
}

export interface Comparison {
  baselineRunAt: string
  currentRunAt: string
  comparable: boolean
  reasons: string[]
  sources: Record<string, { baseline: Source | null; current: Source }>
  checks: Record<string, ComparedCheck>
}

/** The buckets a reader works through, most consequential first. */
export const MOVEMENTS = [
  { key: 'newlyFailing', title: 'Newly failing', hint: 'what this change broke', tone: 'error' },
  { key: 'newlyPassing', title: 'Newly passing', hint: 'what it fixed', tone: 'success' },
  { key: 'new', title: 'New rows', hint: 'not present in the baseline', tone: 'neutral' },
  { key: 'gone', title: 'Gone', hint: 'in the baseline, not in this run', tone: 'neutral' },
  { key: 'changed', title: 'Changed otherwise', hint: 'same severity, different finding', tone: 'neutral' },
] as const

export interface RunEntry {
  name: string
  runAt: string
  parameters: { commit: string; dirty: boolean }
  sources: Record<string, Source>
  summary: Record<string, Record<string, number>>
}

export const useStore = defineStore('report', () => {
  const report = shallowRef<Report | null>(null)
  const comparison = shallowRef<Comparison | null>(null)
  const runs = shallowRef<RunEntry[]>([])
  /** null means whichever run is current. */
  const selected = ref<string | null>(null)
  const status = ref<'loading' | 'ready' | 'error'>('loading')
  const error = ref('')

  async function load(name?: string) {
    status.value = 'loading'
    selected.value = name ?? null
    try {
      const config = useRuntimeConfig().public
      const latest = config.reportUrl as string
      // Runs sit beside the current one, so a name replaces the last segment.
      const url = name ? latest.replace(/[^/]+$/, name) : latest
      const fetched = await $fetch<Report>(url)
      // A report that is not a report must say so. Fetching the wrong url
      // returns the page itself, and a truthy non-report renders as a blank
      // screen with an error only the console sees.
      if (!fetched || typeof fetched !== 'object' || !fetched.checks) {
        const got =
          fetched && typeof fetched === 'object'
            ? `an object with: ${Object.keys(fetched).join(', ')}`
            : `${typeof fetched}`
        throw new Error(`${url} did not return a run report — got ${got}`)
      }
      report.value = fetched
      status.value = 'ready'
      // Absent unless a run was given a baseline, so a failure here is normal
      // and must not take the rest of the dashboard down with it.
      try {
        comparison.value = await $fetch<Comparison>(
          useRuntimeConfig().public.comparisonUrl as string,
        )
      } catch {
        comparison.value = null
      }
      // Absent until a run has been published, and never fatal.
      try {
        runs.value = await $fetch<RunEntry[]>(config.indexUrl as string)
      } catch {
        runs.value = []
      }
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : String(caught)
      status.value = 'error'
    }
  }

  const checks = computed(() => CHECKS.filter((check) => report.value?.checks?.[check.key]))

  /** Nothing refreshes on its own, so a report that is no longer current has to
   *  look it. A season runs roughly a year, so anything older is out of date. */
  const ageInDays = computed(() => {
    if (!report.value) return 0
    return (Date.now() - new Date(report.value.runAt).getTime()) / 86400000
  })
  const isStale = computed(() => ageInDays.value > 365)

  /** A link to a file as it stood in the run being read — the ref the report
   *  names, not whatever the branch has moved on to since. */
  function fileUrl(sourceName: string, path: string) {
    const source = report.value?.sources?.[sourceName]
    if (!source || typeof source !== 'object') return null
    return `https://github.com/${source.repo}/blob/${source.ref}/${path}`
  }

  return { report, comparison, runs, selected, status, error, load, checks, ageInDays, isStale, fileUrl }
})
