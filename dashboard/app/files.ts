/**
 * Reading the two files behind a calibration finding.
 *
 * Nuxt-free so it can be tested against the real file formats, which is where
 * this gets hard: the repository CSV writes `1.022921e+003` and the report
 * carries `1022.921`, so nothing here may compare numbers as strings.
 */

/**
 * A vendor file worth putting on screen.
 *
 * Named as what cannot be shown rather than what can. The vendor originals run
 * to `.cal`, `.xmlcon`, `.dev`, `.dev.lambda`, `.tdf`, `.con`, `.xml` and
 * `.csv`, and an allow-list written from memory missed over three hundred of
 * them. Everything an instrument vendor ships is text except the scans, and the
 * check already has a verdict saying so — `PDF_NOTCOMPARED`.
 */
const BINARY = ['.pdf', '.zip', '.xlsx', '.xls', '.doc', '.docx', '.png', '.jpg', '.jpeg', '.tif']

export function isText(name: string) {
  const lower = name.toLowerCase()
  return !BINARY.some((extension) => lower.endsWith(extension))
}

/** A scan, or any certificate the vendor only published as a pdf. */
export function isPdf(name: string) {
  return name.toLowerCase().endsWith('.pdf')
}

/** The file as the run read it — at that ref, not wherever the branch is now. */
export function rawUrl(repo: string, ref: string, path: string) {
  return `https://raw.githubusercontent.com/${repo}/${ref}/${path}`
}

export interface Pinned {
  ref: string
  commit?: string | null
}

/**
 * Whether a run resolved the commit it read.
 *
 * A run that only records `master` cannot be shown faithfully: master moves,
 * and the file on screen may not be the one the finding came from. This is not
 * hypothetical — the first report served to the dashboard recorded no commits,
 * and a coefficient it reported as differing reads as identical in the files
 * fetched at the same ref.
 */
export function isPinned(source: Pinned) {
  return Boolean(source.commit && source.commit !== 'UNKNOWN')
}

/** The exact commit where the run recorded one, otherwise the ref it asked for. */
export function readAt(source: Pinned) {
  return isPinned(source) ? source.commit! : source.ref
}

export interface Line {
  n: number
  text: string
  hit: boolean
}

function numbered(lines: string[], hit: (line: string, index: number) => boolean): Line[] {
  return lines.map((text, index) => ({ n: index + 1, text, hit: hit(text, index) }))
}

/**
 * The repository CSV, with the rows holding a differing coefficient marked.
 *
 * Its columns are `serial,name,value,notes`, so the coefficient is named
 * outright and this side can be matched exactly.
 */
export function repoLines(text: string, coefficients: Set<string>) {
  return numbered(text.replace(/\s+$/, '').split('\n'), (line, index) => {
    if (!index) return false
    return coefficients.has((line.split(',')[1] ?? '').trim())
  })
}

/** Every number on a line, whatever notation it was written in. */
const NUMBER = /-?\d+\.?\d*(?:[eE][-+]?\d+)?/g

/**
 * The vendor file, with the lines carrying a disputed value marked.
 *
 * Matched on the parsed number rather than its text: a vendor `.xmlcon` writes
 * `2.76372092e-004` where the report carries `0.000276372092`, and the same
 * value in two notations shares no substring at all. Equality is exact, because
 * the comparison that produced the finding was exact.
 */
export function vendorLines(text: string, values: number[]) {
  const wanted = new Set(values)
  return numbered(text.replace(/\s+$/, '').split('\n'), (line) => {
    if (!wanted.size) return false
    return (line.match(NUMBER) ?? []).some((token) => wanted.has(Number(token)))
  })
}

export interface Difference {
  coefficient: string
  github: number
  /** Null where the vendor file carries no such coefficient at all, which is a
   *  finding in itself and not a value to look for. */
  expected: number | null
  difference: number | null
  /** `vendor` when the expected value was read out of the vendor file;
   *  `constant` when it came from `params/coefficientConstants.csv`. */
  source: string
}

/**
 * Only vendor-sourced differences have a line to point at.
 *
 * A constant is not in the vendor file — the check compares against a fixed
 * value in the parameters. Highlighting its expected value would mark whatever
 * line happened to contain a zero, which is worse than marking nothing.
 */
export function vendorValues(differences: Difference[]) {
  return differences
    .filter((each) => each.source === 'vendor' && each.expected !== null)
    .map((each) => each.expected as number)
}

export function constantDifferences(differences: Difference[]) {
  return differences.filter((each) => each.source === 'constant')
}
