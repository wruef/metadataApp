/**
 * Correcting a position on an asset-management deployment sheet.
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

/** The columns a position governs, matching `POSITION_FIELDS` in positions.py. */
export const POSITION_FIELDS = ['lat', 'lon', 'water_depth', 'deployment_depth']

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
 * The sheet with one deployment's position corrected.
 *
 * Throws rather than guessing. No such deployment, a column the sheet does not
 * carry, or a value that is no longer what the run read all mean the sheet has
 * moved on since the report -- and writing anyway would revert somebody else's
 * work or correct the wrong deployment.
 */
export function applyPositionCorrections(
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

  // The note claims the position is provisional. Correcting it to the
  // spreadsheet is what makes it not, so leaving the claim behind would be a
  // sheet that contradicts itself.
  const notesAt = column.notes
  const clearedNote = notesAt !== undefined
    && (fields[notesAt] ?? '').includes(PRELIMINARY_NOTE)
  if (clearedNote) fields[notesAt!] = ''

  lines[index] = fields.join(',')
  return { text: lines.join('\n'), clearedNote }
}

/** What the pull request is called. */
export function positionTitle(refDes: string, deployNum: string | number,
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
export function positionSection(
  refDes: string,
  deployNum: string | number,
  positionName: string,
  corrections: FieldCorrection[],
  clearedNote: boolean,
) {
  const rows = corrections.map((each) => `| \`${each.field}\` | ${each.from} | ${each.to} |`)
  return [
    `\`${deploymentPath(refDes)}\` — **${refDes}** deployment **${deployNum}**`,
    '',
    '| field | was | now |',
    '|---|---|---|',
    ...rows,
    '',
    `Taken from the RCA position spreadsheet${positionName ? `, position \`${positionName}\`` : ''}.`,
    ...(clearedNote
      ? ['', `The \`notes\` column said "${PRELIMINARY_NOTE}", which this correction makes untrue,`
         + ' so it has been cleared.']
      : []),
  ].join('\n')
}
