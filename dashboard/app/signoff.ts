/** The three checks a reviewer signs off, and the sheet each one is recorded in.
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
