/**
 * Correcting one deployment's row on an asset-management deployment sheet.
 *
 * One sheet per array, around two hundred rows each, one row per deployment.
 * So unlike a calibration file this is a shared file: the row has to be found
 * before it can be changed, and every other row has to come back untouched.
 *
 * Reference designator and deployment number identify exactly one row in every
 * sheet, which is checked rather than assumed -- an instrument can be deployed
 * twice in a season, so the designator alone does not.
 */

import { asField, columnIndex, holdsValue, splitLine } from '~/csv'

/** The array a reference designator belongs to, which names its sheet. */
export function deploymentPath(refDes: string) {
  return `deployment/${refDes.slice(0, 8)}_Deploy.csv`
}

/** A node is named SITE-NODE, fourteen characters; an instrument adds a port
 *  and an instrument code. */
export const NODE_REFDES_LENGTH = 14

/** Every node deployment, in the deployments repository rather than on the
 *  asset-management sheets. One flat file for all of them, with the same
 *  columns a deployment sheet has, so the same correction writes it. */
export const NODE_PATH = 'NODE_deployments.csv'

export function isNodeRefDes(refDes: string) {
  return refDes.length <= NODE_REFDES_LENGTH
}

/** Which file holds this deployment's row, in whichever repository. */
export function sheetPathFor(refDes: string) {
  return isNodeRefDes(refDes) ? NODE_PATH : deploymentPath(refDes)
}

/** The columns a position governs, matching `POSITION_FIELDS` in positions.py. */
export const POSITION_FIELDS = ['lat', 'lon', 'water_depth', 'deployment_depth']

/** The column naming the instrument that was deployed. It is what the raw
 *  serial number is checked against, so a serial belonging to a different asset
 *  is a finding about this column and nothing else on the row. */
export const ASSET_FIELD = 'sensor.uid'

/** When a deployment came out of the water. Blank means it is still in. */
export const STOP_FIELD = 'stopDateTime'

/**
 * Which column a deployment-sheet finding is about, where one row's column is
 * the whole fix.
 *
 * Deliberately partial. `ASSET_IN_WRONG_BULK_RECORD` is left out because the
 * asset is real and filed under a different bulk record, so the fix is usually
 * to that record rather than to this sheet. `DUPLICATE_NODE_IN_DEPLOYMENT` is
 * left out because a node is named on a row per instrument hanging off it, and
 * correcting one row would leave the rest saying the box is still there —
 * that one needs an edit per row, by hand, and a reviewer should see them all
 * before starting.
 */
export const VERDICT_FIELD: Record<string, string> = {
  DUPLICATE_ASSET_IN_DEPLOYMENT: ASSET_FIELD,
  DEPLOYMENT_MISSING_END_DATE: STOP_FIELD,
  SENSOR_NOT_IN_BULK: ASSET_FIELD,
  MOORING_NOT_IN_PLATFORM_BULK: 'mooring.uid',
  NODE_NOT_IN_NODE_BULK: 'node.uid',
  ELECTRICAL_NOT_IN_ENG_BULK: 'electrical.uid',
  CRUISE_NOT_IN_CRUISE_LIST: 'CUID_Deploy',
}

/**
 * The queue's name for a correction to one column.
 *
 * The column, except where an editor already owns it. Which instrument a
 * deployment names can be corrected from the deployments check or from the
 * sheet check, and the two are the same claim about the same cell: they have to
 * replace each other in the queue rather than both travel and contradict
 * themselves in one pull request.
 */
export const kindOfField = (field: string) => (field === ASSET_FIELD ? 'asset' : field)

/** A verdict without the detail after the colon, which is what names the
 *  column the finding is about. */
export const verdictOf = (verdict: unknown) => String(verdict ?? '').split(':')[0]!.trim()

/**
 * Every column one deployment-sheet row offers to correct, with what the sheet
 * holds for each.
 *
 * A row can carry several findings — an asset in the water twice *and* no end
 * date — and each is a different column. Offering only the first would leave a
 * reviewer having fixed half of it and no way to see the rest.
 *
 * `verdicts` and `values` stay parallel in the report, so a finding's value is
 * the one beside it. Runs published before rows were combined carry neither and
 * fall back to the single verdict they do have.
 */
export function correctableFields(row: Record<string, unknown>) {
  const verdicts = Array.isArray(row.verdicts) && row.verdicts.length
    ? (row.verdicts as string[])
    : [String(row.verdict ?? '')]
  const values = Array.isArray(row.values) ? (row.values as string[]) : []
  const found: { verdict: string; field: string; held: string }[] = []
  verdicts.forEach((verdict, index) => {
    const field = VERDICT_FIELD[verdictOf(verdict)]
    if (!field || found.some((each) => each.field === field)) return
    // A missing end date is a column holding nothing. The value beside that
    // finding is the asset, and the asset is not what is being changed.
    const held = field === STOP_FIELD ? '' : String(values[index] ?? row.value ?? '')
    found.push({ verdict: verdictOf(verdict), field, held })
  })
  return found
}

/** A deployment sheet carries this until a position is confirmed. Once it is,
 *  the note is no longer true, so correcting a position clears it -- which is
 *  what `applyPositions` in positions.py does to the same column. */
export const PRELIMINARY_NOTE = 'The following parameters are preliminary'

export interface FieldCorrection {
  field: string
  /** As the run read it, which the sheet must still hold. */
  from: string
  to: string
}

/** Which row of the sheet a deployment is, or -1. */
function rowOf(lines: string[], column: Record<string, number>, refDes: string, deployNum: string) {
  return lines.findIndex((line, index) => {
    if (!index || !line.trim()) return false
    const fields = splitLine(line)
    return fields[column['Reference Designator']!]?.trim() === refDes
      && fields[column.deploymentNumber!]?.trim() === String(deployNum)
  })
}

export interface Applied {
  text: string
  /** Whether the preliminary-parameters note was cleared along with the position. */
  clearedNote: boolean
}

/**
 * The sheet with one deployment's row corrected.
 *
 * Any column the sheet carries, which in practice is a position or the asset
 * that was deployed. Both are corrections to the same row of the same file, and
 * the rules for writing one are the rules for writing the other.
 *
 * Throws rather than guessing. No such deployment, a column the sheet does not
 * carry, or a value that is no longer what the run read all mean the sheet has
 * moved on since the report -- and writing anyway would revert somebody else's
 * work or correct the wrong deployment.
 */
export function applyDeploymentCorrections(
  text: string,
  refDes: string,
  deployNum: string | number,
  corrections: FieldCorrection[],
): Applied {
  const lines = text.split('\n')
  const column = columnIndex(lines[0] ?? '')
  const index = rowOf(lines, column, refDes, String(deployNum))
  if (index < 0) {
    throw new Error(
      `${deploymentPath(refDes)} has no ${refDes} deployment ${deployNum}. `
      + 'Run the checks again before correcting this.',
    )
  }

  const fields = splitLine(lines[index]!)
  for (const correction of corrections) {
    const at = column[correction.field]
    if (at === undefined) {
      throw new Error(`The sheet carries no ${correction.field} column.`)
    }
    const held = fields[at] ?? ''
    if (!holdsValue(held, correction.from)) {
      throw new Error(
        `${correction.field} now reads ${held.trim() || '(empty)'} on this deployment, not `
        + `${correction.from} as the run read it. Run the checks again before correcting this.`,
      )
    }
    fields[at] = asField(correction.to)
  }

  // The note claims the *position* is provisional. Correcting it to the
  // spreadsheet is what makes it not, so leaving the claim behind would be a
  // sheet that contradicts itself. Correcting which instrument was deployed
  // says nothing about where it sat, so it leaves the note alone.
  const correctsPosition = corrections.some((each) => POSITION_FIELDS.includes(each.field))
  const notesAt = column.notes
  const clearedNote = correctsPosition && notesAt !== undefined
    && (fields[notesAt] ?? '').includes(PRELIMINARY_NOTE)
  if (clearedNote) fields[notesAt!] = ''

  lines[index] = fields.join(',')
  return { text: lines.join('\n'), clearedNote }
}

/** What the pull request is called when it carries one deployment. */
export function deploymentTitle(refDes: string, deployNum: string | number,
                                corrections: FieldCorrection[]) {
  const named = corrections.length === 1
    ? corrections[0]!.field
    : `${corrections.length} fields`
  return `Correct ${named} for ${refDes} deployment ${deployNum}`
}

/**
 * One deployment's worth of review: every value before and after it.
 *
 * A section rather than a whole body -- one sheet holds every deployment on its
 * array, so a batch can carry several of them against the same file, and each
 * still has to be readable on its own.
 */
export function deploymentSection(
  /** The file this row is in, which differs between an array sheet and the
   *  node file, so it is passed rather than derived from the designator. */
  path: string,
  refDes: string,
  deployNum: string | number,
  /** One sentence saying where the new values came from. It is the whole
   *  justification a reviewer of the pull request is given, so it is written
   *  where the correction is made rather than guessed at here. */
  source: string,
  corrections: FieldCorrection[],
  clearedNote: boolean,
) {
  const rows = corrections.map((each) => `| \`${each.field}\` | ${each.from} | ${each.to} |`)
  return [
    `\`${path}\` — **${refDes}** deployment **${deployNum}**`,
    '',
    '| field | was | now |',
    '|---|---|---|',
    ...rows,
    ...(source ? ['', source] : []),
    ...(clearedNote
      ? ['', `The \`notes\` column said "${PRELIMINARY_NOTE}", which this correction makes untrue,`
         + ' so it has been cleared.']
      : []),
  ].join('\n')
}
