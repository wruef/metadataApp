import { matchesWhere, type Where } from '~/query'
import { SEVERITIES, type Facet, type Row, type Severity } from '~/store'

/**
 * The overview: what needs a person, and how the deployment record has held up
 * over the years.
 *
 * Nuxt-free so it can be tested. The queue is the piece that earns the page —
 * a summary saying *86 problems* tells a reviewer nothing they can act on,
 * where *31 calibration files disagree with the vendor and nobody has signed
 * them off* is a morning's work with a known shape.
 */

export interface Queued {
  check: string
  title: string
  /** What the finding means, in the words someone would use out loud. */
  detail: string
  /** The rows it counts — and, as a query string, the view it opens. */
  where: Where
}

/**
 * Every situation worth naming, as a filter over one check.
 *
 * Deliberately expressed as a `Where` and nothing else: the count beside the
 * title and the table the link opens are then the same rows by construction,
 * and cannot drift into disagreeing. Each excludes rows a reviewer has already
 * signed off, because those do not need a person.
 */
export const QUEUE: Queued[] = [
  {
    check: 'calibrations',
    title: 'Coefficients that disagree with the vendor',
    detail:
      'A coefficient in the asset-management file differs from the vendor original. Comparison is exact, so this is a transcription to reconcile rather than noise.',
    where: { vendorMatch: 'MISMATCH', cleared: 'open' },
  },
  {
    check: 'calibrations',
    title: 'Calibration files with no vendor original to check against',
    detail:
      'The file is in asset-management, but calibrationFiles holds nothing to compare it with. Nothing has verified these coefficients.',
    where: { vendorMatch: 'NO_VENDOR_FILE', cleared: 'open' },
  },
  {
    check: 'calibrations',
    title: 'Disagreements only with the constants file',
    detail:
      'The only differences are against coefficientConstants.csv, where no vendor value is involved. Lesser than a vendor mismatch, but still someone deciding the constant is right.',
    where: { vendorMatch: 'CONSTANT_MISMATCH', cleared: 'open' },
  },
  {
    check: 'deployments',
    title: 'Deployments the raw archive contradicts',
    detail:
      'The serial number recovered from the first raw file names a different asset than the deployment sheet does.',
    where: { rawFile_verify: 'MISMATCH', cleared: 'open' },
  },
  {
    check: 'deployments',
    title: 'Deployments a pre-deploy photograph contradicts',
    detail:
      'The serial read from the cruise image does not match the asset on the sheet.',
    where: { image_verify: 'MISMATCH', cleared: 'open' },
  },
  {
    check: 'deployments',
    title: 'Deployments whose instrument has no calibration at all',
    detail:
      'The instrument needs a calibration and asset-management holds none for this asset — not one dated after the deployment, none.',
    where: { calFile_verify: 'none', cleared: 'open' },
  },
  {
    check: 'deployments',
    title: 'Deployments with no valid calibration on file',
    detail:
      'The instrument needs a calibration and asset-management has none covering the deployment.',
    where: { calFile_verify: 'NO_VALID_FILE', cleared: 'open' },
  },
  {
    check: 'deployments',
    title: 'Deployments a raw-archive extraction would settle',
    detail:
      'These instrument classes write their serial number into the raw file, so extraction closes them without anyone finding a photograph.',
    where: { verificationStatus: 'RAW_SN_POSSIBLE', cleared: 'open' },
  },
  {
    check: 'deployments',
    title: 'Deployments with a calibration older than fifteen months',
    detail:
      'A calibration is on file but predates the deployment by more than the interval the instrument teams treat as current.',
    where: { calFile_verify: 'VALID_FILE_CAL_OLDER_THAN_15MONTHS', cleared: 'open' },
  },
  {
    check: 'positions',
    title: 'Deployment positions that disagree with the spreadsheet',
    detail:
      'Latitude, longitude or depth on the deployment sheet differs from the RCA position record.',
    where: { verdict: 'MISMATCH', cleared: 'open' },
  },
  {
    check: 'sensorBulk',
    title: 'Serial numbers that disagree with sensor bulk',
    detail:
      'The RCA instrument list and sensor_bulk_load-AssetRecord.csv hold different serials for one asset ID.',
    where: { verdict: 'MISMATCH', cleared: 'open' },
  },
  {
    check: 'sensorBulk',
    title: 'Assets missing from the OOI sensor bulk record',
    detail:
      'The RCA list carries an asset that the shared bulk record has never heard of.',
    where: { verdict: 'MISSING_FROM_SENSOR_BULK', cleared: 'open' },
  },
  {
    check: 'sensorBulk',
    title: 'Serials that agree but are written differently',
    detail:
      'The same number formatted two ways — leading zeros, a prefix. Harmless to read and a trap for anything matching on the string.',
    where: { verdict: 'FORMAT_MATCH', cleared: 'open' },
  },
  {
    check: 'deploymentSheets',
    title: 'Sheet entries naming something no other record knows',
    detail:
      'A deployment sheet names an asset, mooring or cruise that is absent from the record that should define it.',
    where: { severity: 'problem', cleared: 'open' },
  },
]

export interface QueueCount extends Queued {
  count: number
  /** The worst severity among the rows it matches, which is how it ranks. */
  worst: Severity
}

/**
 * The queue, worst first, with anything that matches nothing left out.
 *
 * Ranked by the severity of the rows themselves rather than by a label written
 * here, so an item cannot claim to be urgent while matching only settled rows.
 */
export function queueCounts(
  checks: Record<string, { rows: Row[] } | undefined>,
  facetsOf: (check: string) => readonly Facet[],
): QueueCount[] {
  const counted: QueueCount[] = []
  for (const item of QUEUE) {
    const rows = checks[item.check]?.rows
    if (!rows) continue
    const matched = rows.filter((row) => matchesWhere(row, facetsOf(item.check), item.where))
    if (!matched.length) continue
    let worst: Severity = 'ok'
    for (const row of matched) {
      if (SEVERITIES.indexOf(row.severity) < SEVERITIES.indexOf(worst)) worst = row.severity
    }
    counted.push({ ...item, count: matched.length, worst })
  }
  return counted.sort(
    (a, b) => SEVERITIES.indexOf(a.worst) - SEVERITIES.indexOf(b.worst) || b.count - a.count,
  )
}

export interface YearBar {
  year: string
  total: number
  counts: Record<Severity, number>
}

/** Deployments by the year they went in the water, split by severity. */
export function byYear(rows: Row[], yearOf: (row: Row) => string): YearBar[] {
  const years = new Map<string, YearBar>()
  for (const row of rows) {
    const year = yearOf(row)
    if (!year) continue
    let bar = years.get(year)
    if (!bar) {
      bar = { year, total: 0, counts: { problem: 0, review: 0, unchecked: 0, cleared: 0, ok: 0, excluded: 0 } }
      years.set(year, bar)
    }
    bar.total++
    bar.counts[row.severity]++
  }
  return [...years.values()].sort((a, b) => a.year.localeCompare(b.year))
}

/**
 * A round number at or above the tallest bar, for the top gridline.
 *
 * The prototype pinned this at 145, which is fine until a season is bigger than
 * the one it was drawn against and the bars run off the top of the chart.
 */
export function niceMax(value: number) {
  if (value <= 0) return 1
  const magnitude = 10 ** Math.floor(Math.log10(value))
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (value <= step * magnitude) return step * magnitude
  }
  return 10 * magnitude
}
