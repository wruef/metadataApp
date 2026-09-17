import { defineStore } from 'pinia'

import { siteOf, yearOf } from '~/display'
import { withBase } from '~/paths'

/** Worst first — the order a queue is worked in. `cleared` is a category of its
 *  own rather than a flag beside a severity: a row a reviewer signed off is not
 *  a problem and not work waiting on anybody. What the checks found is kept on
 *  the row as `finding`, and shown beside the badge. */
export const SEVERITIES = ['problem', 'review', 'unchecked', 'cleared', 'ok', 'excluded'] as const
export type Severity = (typeof SEVERITIES)[number]

export const SEVERITY_LABEL: Record<Severity, string> = {
  problem: 'Problem',
  review: 'Needs a person',
  unchecked: 'Not checked',
  cleared: 'Cleared in review',
  ok: 'Agreed',
  excluded: 'Excluded',
}

/** Nuxt UI badge colours. `as const` keeps the literal types, which is what the
 *  badge's own colour prop expects; `satisfies` still checks every severity has
 *  one. Annotating this `Record<Severity, string>` widens the values back to
 *  string and the badge rejects them. */
export const SEVERITY_COLOR = {
  problem: 'error',
  review: 'warning',
  unchecked: 'neutral',
  cleared: 'success',
  ok: 'success',
  excluded: 'neutral',
} as const satisfies Record<Severity, string>

export interface Row {
  /** The category the row is in — `cleared` once a reviewer has signed it off,
   *  whatever its checks found. */
  severity: Severity
  /** What the checks themselves found, kept whatever the sign-off says. Absent
   *  on runs published before it was carried. */
  finding?: Severity
  cleared: boolean
  [key: string]: unknown
}

/** A vendor calibration with no repository file, and whatever a reviewer has
 *  recorded about it. Signed off in the calibration sheet under the name the
 *  repository file would have. */
export interface VendorOnly {
  file: string
  instrument: string
  hitlKey: string
  HITLstatus: string
  HITLnotes: string
}

export interface Check {
  rows: Row[]
  /** `attention` is what is waiting on a person: the problem and review rows,
   *  which a signed-off row is never one of. `verified` is agreed plus cleared.
   *  Both optional because runs published before they were carried have
   *  neither, and the dashboard falls back to the severities. */
  summary: Record<Severity | 'cleared' | 'total', number> & {
    attention?: number
    verified?: number
    /** The rows this check could judge at all: total less excluded. */
    considered?: number
  }
  /** Vendor originals the repository holds nothing for. Runs published before
   *  each carried its instrument and sign-off have a bare list of names. */
  missingFromGithub?: (VendorOnly | string)[]
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
  /** The instruments asset-management holds no calibration for, so nothing
   *  could be compared and nothing was missed. */
  excludedInstruments?: string[]
  /** Every note already written in each 2i-HITL sheet, most used first — the
   *  reasons a sign-off picks from. Absent on runs published before it was
   *  carried, which is why signing off falls back to free text alone. */
  hitlNotes?: Record<string, string[]>
  checks: Record<string, Check>
}

/**
 * A dropdown over one column of a check.
 *
 * Which ones a check gets is a property of that check: an instrument means
 * something to a calibration file and nothing to a deployment sheet. Options
 * are built from the rows actually in the report rather than declared here, so
 * a new instrument or a new verdict appears without anything being edited.
 */
export interface Facet {
  key: string
  /** Shown when nothing is picked — "All instruments". */
  label: string
  of: (row: Row) => string
}

/** The checks, in the order they are worth working. */
export const CHECKS = [
  { key: 'calibrations', title: 'Calibrations', icon: 'fa-flask',
    blurb: 'Repository calibration files against the vendor originals.',
    columns: ['fileName', 'instrument', 'vendorMatch', 'calRepo_check', 'serialNumber', 'HITLstatus'],
    facets: [
      { key: 'instrument', label: 'All instruments', of: (row) => String(row.instrument ?? '') },
      { key: 'vendorMatch', label: 'Any comparison', of: (row) => String(row.vendorMatch ?? '') },
      { key: 'HITLstatus', label: 'Any sign-off', of: (row) => String(row.HITLstatus ?? '') },
    ] },
  { key: 'deployments', title: 'Deployments', icon: 'fa-anchor',
    blurb: 'Every deployment: its calibration file, its raw serial number, its sign-off.',
    // No verificationStatus column: it is the raw serial and the sign-off read
    // together, and both are columns of their own. The review status badge on
    // the left already says what it concluded, so a column repeating it was
    // one more thing to read that told you nothing new. The value is still on
    // the row and still under Raw check output.
    columns: ['refDes', 'deployNum', 'deployYear', 'AssetID', 'rawFile_verify', 'image_verify', 'calFile_verify', 'HITLstatus'],
    facets: [
      { key: 'site', label: 'All sites', of: (row) => siteOf(row.refDes) },
      // From the year the run settled, falling back to the timestamp for runs
      // published before it carried one.
      { key: 'year', label: 'All years', of: (row) => String(row.deployYear ?? yearOf(row.deployDate)) },
      // Kept as a filter though it is no longer a column: it is the only way to
      // ask for the deployments nothing confirms, which the review status
      // cannot isolate because it folds in the calibration findings too.
      { key: 'verificationStatus', label: 'Any confirmation', of: (row) => String(row.verificationStatus ?? '') },
      // Deployments are signed off in 2i_HITL_deploymentVerification.csv exactly
      // as calibrations are, and every row has carried the status all along --
      // it was the one check that never showed it.
      { key: 'HITLstatus', label: 'Any sign-off', of: (row) => String(row.HITLstatus ?? '') },
      { key: 'calFile_verify', label: 'Any calibration', of: (row) => String(row.calFile_verify ?? '') },
      // The raw verdict carries the serial numbers behind it in the same string
      // — MISMATCH: raw: 379: ATAPL-… — so the verdict is what it groups on.
      { key: 'rawFile_verify', label: 'Any raw file', of: (row) => String(row.rawFile_verify ?? '').split(':')[0]!.trim() },
      { key: 'image_verify', label: 'Any image', of: (row) => String(row.image_verify ?? '') },
    ] },
  { key: 'positions', title: 'Positions', icon: 'fa-location-dot',
    blurb: 'Deployment sheets against the RCA position spreadsheet.',
    columns: ['refDes', 'deployNum', 'deployYear', 'positionName', 'verdict', 'sourceRow'],
    facets: [
      { key: 'site', label: 'All sites', of: (row) => siteOf(row.refDes) },
      { key: 'deployYear', label: 'All years', of: (row) => String(row.deployYear ?? '') },
      { key: 'verdict', label: 'Any verdict', of: (row) => String(row.verdict ?? '') },
      // How the spreadsheet row was found: by a curated HITL entry, by year, or
      // carried over from the previous deployment.
      { key: 'resolution', label: 'Any match', of: (row) => String(row.resolution ?? '') },
    ] },
  { key: 'sensorBulk', title: 'Sensor bulk', icon: 'fa-barcode',
    blurb: 'Serial numbers between the RCA instrument list and the OOI sensor bulk record.',
    columns: ['assetID', 'instrumentType', 'rcaSerials', 'bulkSerial', 'verdict', 'HITLstatus'],
    facets: [
      { key: 'verdict', label: 'Any verdict', of: (row) => String(row.verdict ?? '') },
      // Only the RCA instrument list names a type, so this is empty for exactly
      // the assets it has never heard of.
      { key: 'instrumentType', label: 'All instrument types',
        of: (row) => (Array.isArray(row.instrumentType) ? row.instrumentType.join(', ') : '') },
      { key: 'HITLstatus', label: 'Any sign-off', of: (row) => String(row.HITLstatus ?? '') },
    ] },
  { key: 'deploymentSheets', title: 'Duplicate asset deployments', icon: 'fa-table',
    blurb: 'The same asset deployed twice at once, and sheet entries naming something no other record knows.',
    columns: ['refDes', 'deployNum', 'deployYear', 'value', 'verdict'],
    facets: [
      { key: 'verdict', label: 'Any verdict', of: (row) => String(row.verdict ?? '') },
      { key: 'deployYear', label: 'All years', of: (row) => String(row.deployYear ?? '') },
      { key: 'refDes', label: 'All designators', of: (row) => String(row.refDes ?? '') },
    ] },
] as const satisfies readonly {
  key: string
  title: string
  icon: string
  blurb: string
  columns: readonly string[]
  facets: readonly Facet[]
}[]

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
  /** The same per-check summaries the run's own report carries. */
  summary: Record<string, Check['summary']>
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
      const config = useRuntimeConfig()
      const base = config.app.baseURL
      const latest = withBase(base, config.public.reportUrl as string)
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
      // The comparison that belongs to the run being read, not whichever one
      // was newest. Published runs are named report_<stamp> and their
      // comparisons comparison_<stamp>, so one follows from the other; the
      // fixed url is the fallback for the current run.
      const comparisonUrl = name
        ? url.replace(/[^/]+$/, name.replace('report_', 'comparison_'))
        : withBase(base, config.public.comparisonUrl as string)
      // Absent unless a run was given a baseline, so a failure here is normal
      // and must not take the rest of the dashboard down with it.
      try {
        comparison.value = await $fetch<Comparison>(comparisonUrl)
      } catch {
        comparison.value = null
      }
      // Absent until a run has been published, and never fatal.
      try {
        runs.value = await $fetch<RunEntry[]>(withBase(base, config.public.indexUrl as string))
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

  /** A link to a file as it stood in the run being read — at the commit where
   *  the run resolved one, because a ref moves and the link would then point at
   *  a different file than the check saw. */
  function fileUrl(sourceName: string, path: string) {
    const source = report.value?.sources?.[sourceName]
    if (!source || typeof source !== 'object') return null
    const at = source.commit && source.commit !== 'UNKNOWN' ? source.commit : source.ref
    return `https://github.com/${source.repo}/blob/${at}/${path}`
  }

  return { report, comparison, runs, selected, status, error, load, checks, ageInDays, isStale, fileUrl }
})
