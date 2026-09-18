<script setup lang="ts">
import { FORKS, useAuth } from '~/auth'
import { calibrationPath, type Correction } from '~/calfile'
import { deploymentKey, useCorrections } from '~/corrections'
import { scalar } from '~/csv'
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
 */
const { check, row } = defineProps<{ check: string; row: Row }>()

const auth = useAuth()
const corrections = useCorrections()

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
const correctable = computed(() => isCalibration.value || isPosition.value)

/** What names a line, and what identifies the whole correction. */
const nameOf = (entry: Difference) => String(entry.coefficient ?? entry.field ?? '')
const heldBy = (entry: Difference) => (isCalibration.value ? entry.github : entry.current)

const path = computed(() => (isCalibration.value
  ? calibrationPath(String(row.instrument), String(row.fileName))
  : deploymentPath(String(row.refDes))))

const id = computed(() => (isCalibration.value
  ? path.value
  : deploymentKey(String(row.refDes), row.deployNum as string | number)))

const busy = computed(() => Boolean(corrections.submitting[id.value]))
const result = computed(() => corrections.results[id.value])

/**
 * Which lines can be typed over.
 *
 * A calibration coefficient has to be one number: an OPTAA's `CC_acwo` is
 * eighty-three of them in one field, and a text box would be guessing. A
 * position field is one of the four a position governs and nothing else.
 */
function editableLine(entry: Difference) {
  if (isCalibration.value) return typeof entry.github === 'number' && Number.isFinite(entry.github)
  return POSITION_FIELDS.includes(nameOf(entry))
}

const anyEditable = computed(() => correctable.value && differences.value.some(editableLine))

/** Asked once the reviewer could actually act on the answer. */
watchEffect(() => {
  if (anyEditable.value && auth.canSignOff) corrections.checkSync()
})

const blocked = computed(() => corrections.refusal)
const editing = computed(() => anyEditable.value && auth.canSignOff && !blocked.value)

const values = ref<Record<string, string>>({})
const notes = ref<Record<string, string>>({})

/** The value on the right is what the finding says the file should say. */
function take(entry: Difference) {
  if (entry.expected === null || entry.expected === undefined) return
  values.value = { ...values.value, [nameOf(entry)]: String(entry.expected) }
}

function takeAll() {
  for (const entry of differences.value) if (editableLine(entry)) take(entry)
}

/** Only lines actually changed to a different value. */
const queued = computed(() => differences.value.flatMap((entry) => {
  if (!editableLine(entry)) return []
  const typed = (values.value[nameOf(entry)] ?? '').trim()
  if (!typed || typed === String(heldBy(entry))) return []
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
  ? queued.value.filter(({ typed }) => scalar(typed) === null).map(({ entry }) => nameOf(entry))
  : []))

function propose() {
  if (isCalibration.value) {
    const corrections_: Correction[] = queued.value.map(({ entry, typed }) => {
      const note = (notes.value[nameOf(entry)] ?? '').trim()
      return { coefficient: nameOf(entry), from: entry.github as number,
               to: Number(typed), ...(note ? { note } : {}) }
    })
    corrections.proposeCalibration(String(row.instrument), String(row.fileName), corrections_)
  } else {
    const fields: FieldCorrection[] = queued.value.map(({ entry, typed }) => ({
      field: nameOf(entry), from: String(entry.current), to: typed,
    }))
    corrections.proposePosition(String(row.refDes), row.deployNum as string | number,
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
              <td class="num text-right">{{ heldBy(entry) }}</td>
              <td class="num text-right">
                <button
                  v-if="editing && editableLine(entry)
                    && entry.expected !== null && entry.expected !== undefined"
                  class="text-primary-700 hover:underline"
                  type="button"
                  :title="`Use ${entry.expected}`"
                  @click="take(entry)"
                >{{ entry.expected }}</button>
                <span v-else>{{ entry.expected ?? '—' }}</span>
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
                  :placeholder="String(heldBy(entry))"
                  :aria-label="`New value for ${nameOf(entry)}`"
                >
                <span v-else class="notedit">not one number</span>
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

    <!-- Correcting the file, under the numbers it is about. -->
    <template v-if="correctable && anyEditable">
      <p v-if="corrections.checking" class="mt-2 text-gray-500 text-[12.5px]">
        Checking your fork against oceanobservatories/asset-management…
      </p>

      <!-- A fork that is not exactly upstream is a fork this dashboard has
           never read, so this is a refusal rather than a warning. -->
      <u-alert
        v-else-if="blocked && auth.canSignOff"
        class="mt-2"
        color="error"
        variant="subtle"
        title="Cannot correct the file: your fork is not in sync"
        :description="blocked"
      >
        <template #actions>
          <u-button size="xs" color="neutral" variant="subtle" @click="corrections.checkSync(true)">
            Check again
          </u-button>
        </template>
      </u-alert>

      <p v-else-if="!auth.canSignOff" class="mt-2 text-gray-500 text-[12.5px]">
        <nuxt-link to="/settings" class="text-primary-700 underline">Sign in</nuxt-link>
        with your initials to correct these values.
      </p>

      <template v-else>
        <p v-if="unreadable.length" class="mt-2 text-red-700 text-[12.5px]">
          Not a number: {{ unreadable.join(', ') }}.
        </p>
        <div class="flex flex-wrap gap-2 items-center mt-2.5">
          <u-button
            size="sm"
            color="primary"
            :loading="busy"
            :disabled="!queued.length || unreadable.length > 0"
            @click="propose"
          >
            Correct {{ queued.length || '' }}
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
          Its own pull request on <b>{{ auth.forkFor('assetManagement') }}</b>, not batched with
          your sign-offs. Nothing anyone computes changes until you raise that one upstream.
        </p>
      </template>

      <u-alert
        v-if="result"
        class="mt-2"
        :color="result.url ? 'success' : 'error'"
        variant="subtle"
        :title="result.message"
      >
        <template v-if="result.url" #description>
          <a :href="result.url" target="_blank" rel="noopener" class="underline">
            Review it on GitHub
          </a>
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
