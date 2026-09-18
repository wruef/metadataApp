<script setup lang="ts">
import { useAuth, FORKS } from '~/auth'
import { sheetKey, useBatch } from '~/batch'
import { calibrationPath, type Correction } from '~/calfile'
import { parseList, scalar } from '~/csv'
import { deploymentPath, POSITION_FIELDS, type FieldCorrection } from '~/deployfile'
import { readDifference } from '~/display'
import { type Row } from '~/store'

/**
 * What disagrees on a row, and the correction of it.
 *
 * One table rather than a read-only one plus an editable copy behind a button.
 * A reviewer reads the vendor's number and writes the file's number on the same
 * line, which is the whole task; showing the numbers twice invited reading one
 * pair and typing against the other.
 *
 * Correcting is offered on the two checks that have a file to correct. Where a
 * reviewer is not signed in, or their fork is not in sync, the table is the
 * plain read-only one it has always been.
 *
 * A correction is queued rather than proposed. It joins the batch for its kind
 * -- coefficients with coefficients, positions with positions -- and the whole
 * batch goes over as one pull request from the queue page.
 */
const { check, row } = defineProps<{ check: string; row: Row }>()

const auth = useAuth()
const batch = useBatch()

interface Difference {
  coefficient?: string
  field?: string
  github?: number
  current?: unknown
  expected?: unknown
  difference?: number | null
  source?: string
  note?: string
}

const differences = computed(() =>
  (Array.isArray(row.differences) ? row.differences : []) as Difference[])

const isCalibration = computed(() => check === 'calibrations')
const isPosition = computed(() => check === 'positions')
/** A node is named SITE-NODE, fourteen characters; an instrument adds a port
 *  and an instrument code. Node deployments live in NODE_deployments.csv in the
 *  deployments repository, not on the asset-management sheets this corrects, so
 *  offering to correct one here wrote to a sheet with no such row. */
const isNode = computed(() => isPosition.value && String(row.refDes ?? '').length <= 14)
const correctable = computed(() => (isCalibration.value || isPosition.value) && !isNode.value)

/** What names a line, and what identifies the whole correction. */
const nameOf = (entry: Difference) => String(entry.coefficient ?? entry.field ?? '')
const heldBy = (entry: Difference) => (isCalibration.value ? entry.github : entry.current)

const path = computed(() => (isCalibration.value
  ? calibrationPath(String(row.instrument), String(row.fileName))
  : deploymentPath(String(row.refDes))))

/** Which batch this row's correction belongs in. */
const batchKey = computed<'calibrations' | 'sheets'>(
  () => (isCalibration.value ? 'calibrations' : 'sheets'))

/** What identifies the record within that batch -- the file for a calibration,
 *  the deployment for a position, because one sheet holds a whole array. */
const id = computed(() => (isCalibration.value
  ? path.value
  : sheetKey('position', String(row.refDes), row.deployNum as string | number)))

/** Queueing the same record twice replaces the earlier entry, so a row already
 *  in the queue says so rather than silently taking a second copy. */
const queuedAlready = computed(() => batch.entryFor(batchKey.value, id.value))

/** A short list is worth a text box; a long one is not. An OPTAA's `CC_acwo`
 *  is eighty-three numbers, where typing the whole array back is guessing. A
 *  DOSTA's `CC_conc_coef` is two, where it is just typing. */
const LIST_LIMIT = 8

/**
 * Which lines can be typed over.
 *
 * A calibration coefficient is one number, or a short list of them. A position
 * field is one of the four a position governs and nothing else.
 */
function editableLine(entry: Difference) {
  if (!isCalibration.value) return POSITION_FIELDS.includes(nameOf(entry))
  if (Array.isArray(entry.github)) return entry.github.length <= LIST_LIMIT
  return typeof entry.github === 'number' && Number.isFinite(entry.github)
}

/** The written form of a value, which is what a box holds and what a click
 *  takes. A list reads as the file writes it. */
function asText(value: unknown) {
  return Array.isArray(value) ? `[${value.join(', ')}]` : String(value)
}

const anyEditable = computed(() => correctable.value && differences.value.some(editableLine))

/** Asked once the reviewer could actually act on the answer. */
watchEffect(() => {
  if (anyEditable.value && auth.canSignOff) batch.checkSync('assetManagement')
})

const blocked = computed(() => batch.refusalFor('assetManagement'))
const editing = computed(() => anyEditable.value && auth.canSignOff && !blocked.value)

const values = ref<Record<string, string>>({})
const notes = ref<Record<string, string>>({})

/** The value on the right is what the finding says the file should say. */
function take(entry: Difference) {
  if (entry.expected === null || entry.expected === undefined) return
  values.value = { ...values.value, [nameOf(entry)]: asText(entry.expected) }
}

function takeAll() {
  for (const entry of differences.value) if (editableLine(entry)) take(entry)
}

/** Only lines actually changed to a different value. */
const queued = computed(() => differences.value.flatMap((entry) => {
  if (!editableLine(entry)) return []
  const typed = (values.value[nameOf(entry)] ?? '').trim()
  if (!typed || typed === asText(heldBy(entry))) return []
  return [{ entry, typed }]
}))

/**
 * A typed value the file could not hold. Named so the button can refuse rather
 * than quietly drop it.
 *
 * A coefficient has to be a number. A position field does not: a profiler holds
 * no fixed depth and its deployment depth is the literal `N/A`, which is the
 * value rather than a missing one.
 */
const unreadable = computed(() => (isCalibration.value
  ? queued.value.filter(({ entry, typed }) => (Array.isArray(entry.github)
      ? parseList(typed)?.length !== entry.github.length
      : scalar(typed) === null)).map(({ entry }) => nameOf(entry))
  : []))

/** Into the queue, not into a pull request. The batch is proposed from the
 *  queue page, where a reviewer can see everything that would travel with it. */
function add() {
  if (isCalibration.value) {
    const corrections_: Correction[] = queued.value.map(({ entry, typed }) => {
      const note = (notes.value[nameOf(entry)] ?? '').trim()
      return {
        coefficient: nameOf(entry),
        from: entry.github as number | number[],
        to: Array.isArray(entry.github) ? parseList(typed)! : Number(typed),
        ...(note ? { note } : {}),
      }
    })
    batch.queueCalibration(String(row.instrument), String(row.fileName), corrections_)
  } else {
    const fields: FieldCorrection[] = queued.value.map(({ entry, typed }) => ({
      field: nameOf(entry), from: String(entry.current), to: typed,
    }))
    batch.queuePosition(String(row.refDes), row.deployNum as string | number,
                        String(row.positionName ?? ''), fields)
  }
}

/** The whole file on GitHub, for the cases a text box cannot do: an array
 *  coefficient, a column this table does not show, a wholesale rewrite. */
const editUrl = computed(() => {
  const fork = auth.forkFor('assetManagement')
  const base = FORKS.find((each) => each.key === 'assetManagement')!.base
  return fork ? `https://github.com/${fork}/edit/${base}/${path.value}` : ''
})

/**
 * One note, where the file says the same thing about every coefficient.
 *
 * Collapsed only when every difference carries a note and they are all the
 * same. With some noted and some not, showing it once would attribute it to
 * coefficients the file says nothing about.
 */
const sharedNote = computed(() => {
  const written = differences.value.map((entry) => String(entry.note ?? '').trim())
  if (written.length < 2 || written.some((note) => !note)) return ''
  return written.every((note) => note === written[0]) ? written[0]! : ''
})

const columns = computed(() => 3 + (isCalibration.value ? 2 : 0) + (editing.value ? 1 : 0)
  + (editing.value && isCalibration.value ? 1 : 0))
</script>

<template>
  <div v-if="differences.length">
    <h4>
      {{ isPosition ? 'Fields that differ from the spreadsheet'
        : 'Coefficients that differ from the vendor file' }}
    </h4>

    <div class="coefwrap">
      <table class="coef">
        <thead>
          <tr>
            <th>{{ isPosition ? 'Field' : 'Coefficient' }}</th>
            <th class="text-right">{{ isPosition ? 'On the sheet' : 'asset-management' }}</th>
            <th class="text-right">{{ isPosition ? 'Spreadsheet' : 'Vendor' }}</th>
            <th v-if="isCalibration" class="text-right">Difference</th>
            <!-- A constant carries no vendor value, so it is not a
                 disagreement with the vendor at all. -->
            <th v-if="isCalibration">Source</th>
            <th v-if="editing">Correct to</th>
            <th v-if="editing && isCalibration">Note for the file</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(entry, index) in differences" :key="index">
            <tr>
              <td>{{ nameOf(entry) }}</td>
              <!-- What each file records, exactly as it was read. -->
              <td class="num text-right">{{ asText(heldBy(entry)) }}</td>
              <td class="num text-right">
                <button
                  v-if="editing && editableLine(entry)
                    && entry.expected !== null && entry.expected !== undefined"
                  class="text-primary-700 hover:underline"
                  type="button"
                  :title="`Use ${entry.expected}`"
                  @click="take(entry)"
                >{{ asText(entry.expected) }}</button>
                <span v-else>{{ entry.expected === undefined || entry.expected === null
                  ? '—' : asText(entry.expected) }}</span>
              </td>
              <td v-if="isCalibration" class="d num text-right">
                {{ readDifference(entry.difference) }}
              </td>
              <td v-if="isCalibration">{{ entry.source }}</td>
              <td v-if="editing">
                <input
                  v-if="editableLine(entry)"
                  v-model="values[nameOf(entry)]"
                  class="fld num"
                  :placeholder="asText(heldBy(entry))"
                  :aria-label="`New value for ${nameOf(entry)}`"
                >
                <span v-else class="notedit">too many values to type</span>
              </td>
              <td v-if="editing && isCalibration">
                <input
                  v-if="editableLine(entry)"
                  v-model="notes[nameOf(entry)]"
                  class="fld"
                  placeholder="optional"
                  :aria-label="`Note for ${nameOf(entry)}`"
                >
              </td>
            </tr>
            <!-- What the asset-management file says about this coefficient:
                 where the value came from, which vendor file it was read out
                 of, that it is a constant. Its own line, because a note runs
                 to a sentence and a column would push the numbers off. -->
            <tr v-if="entry.note && !sharedNote" class="note">
              <td :colspan="columns">
                <span class="from">asset-management note</span>{{ entry.note }}
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <p v-if="sharedNote" class="coefnote">
      <span class="from">asset-management note</span>{{ sharedNote }}
    </p>

    <!-- A node's position is not on these sheets at all. -->
    <p v-if="isNode" class="mt-2 text-gray-500 text-[12.5px]">
      A node's position lives in <span class="font-mono">NODE_deployments.csv</span> in the
      deployments repository, which this dashboard does not write.
      <span class="font-mono">publish-metadata positions --node-fork</span> proposes it.
    </p>

    <!-- Correcting the file, under the numbers it is about. -->
    <fork-guard v-if="correctable && anyEditable" fork="assetManagement" action="correct these values" class="mt-2">
      <template #default>
        <p v-if="unreadable.length" class="mt-2 text-red-700 text-[12.5px]">
          Cannot be read as the value this coefficient holds: {{ unreadable.join(', ') }}.
        </p>
        <div class="flex flex-wrap gap-2 items-center mt-2.5">
          <u-button
            size="sm"
            color="primary"
            :disabled="!queued.length || unreadable.length > 0"
            @click="add"
          >
            {{ queuedAlready ? 'Replace in batch' : 'Add to batch' }}:
            {{ queued.length || '' }}
            {{ isPosition ? 'field' : 'coefficient' }}{{ queued.length === 1 ? '' : 's' }}
          </u-button>
          <u-button size="xs" color="neutral" variant="subtle" @click="takeAll">
            Take every {{ isPosition ? 'spreadsheet' : 'vendor' }} value
          </u-button>
          <a
            v-if="editUrl"
            :href="editUrl"
            target="_blank"
            rel="noopener"
            class="text-[12.5px] text-primary-700 hover:underline"
          >Edit the whole file on GitHub</a>
        </div>
        <p class="mt-1.5 text-gray-500 text-[12.5px]">
          Joins the {{ isPosition ? 'deployment sheet' : 'calibration' }} batch, which goes over as
          one pull request on <b>{{ auth.forkFor('assetManagement') }}</b>. Sign-offs travel
          separately, and nothing anyone computes changes until you raise that request upstream.
        </p>
      </template>
    </fork-guard>

    <template v-if="correctable && anyEditable">
      <u-alert
        v-if="queuedAlready"
        class="mt-2"
        color="success"
        variant="subtle"
        title="Queued."
      >
        <template #description>
          Waiting with the other {{ isPosition ? 'deployment sheet' : 'calibration' }} corrections.
          <nuxt-link to="/queue" class="underline">Open the queue</nuxt-link>
          to propose them.
        </template>
      </u-alert>
    </template>
  </div>
</template>

<style scoped>
.fld {
  border: 1px solid #cdd8e1;
  border-radius: 5px;
  font-family: inherit;
  font-size: 12px;
  padding: 2px 6px;
  min-width: 11ch;
  width: 100%;
}
.fld:focus { border-color: #2b6cb0; outline: none }
/* A coefficient a text box cannot hold, said rather than left blank. */
.notedit { color: #93a5b4; font-size: 11px }
</style>
