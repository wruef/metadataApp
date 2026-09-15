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

export const useStore = defineStore('report', () => {
  const report = shallowRef<Report | null>(null)
  const status = ref<'loading' | 'ready' | 'error'>('loading')
  const error = ref('')

  async function load() {
    status.value = 'loading'
    try {
      const url = useRuntimeConfig().public.reportUrl as string
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

  return { report, status, error, load, checks, ageInDays, isStale, fileUrl }
})
