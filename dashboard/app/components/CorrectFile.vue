<script setup lang="ts">
import { useAuth } from '~/auth'
import { calibrationPath, type Correction } from '~/calfile'
import { scalar } from '~/csv'
import { useCorrections } from '~/corrections'
import { type Difference } from '~/files'
import { type Row } from '~/store'

/**
 * Correcting the asset-management calibration file itself.
 *
 * Every other write in this dashboard records a judgement about a file. This
 * one changes it, and every data product computed from that coefficient
 * changes with it -- so it is its own pull request, on the reviewer's own fork,
 * and it refuses to start from anything but the file the finding came from.
 */
const { row } = defineProps<{ row: Row }>()

const auth = useAuth()
const corrections = useCorrections()

const path = computed(() => calibrationPath(String(row.instrument), String(row.fileName)))
const busy = computed(() => Boolean(corrections.submitting[path.value]))
const result = computed(() => corrections.results[path.value])

/** Only a coefficient the report read as one number can be typed over. An
 *  OPTAA's eighty-three value array is not editable through a text box. */
const editable = computed(() =>
  ((row.differences ?? []) as Difference[]).filter(
    (each) => typeof each.github === 'number' && Number.isFinite(each.github),
  ),
)

const open = ref(false)
/** What the reviewer has typed, by coefficient. Empty means leave it alone. */
const values = ref<Record<string, string>>({})
const notes = ref<Record<string, string>>({})

async function start() {
  open.value = true
  values.value = {}
  notes.value = {}
  await corrections.checkSync()
}

/** The vendor's own number, which is what the finding says the file should say.
 *  Absent on a constant, where there is no vendor value to take. */
function take(entry: Difference) {
  if (entry.expected === null || entry.expected === undefined) return
  values.value = { ...values.value, [entry.coefficient]: String(entry.expected) }
}

/** Only the coefficients actually changed to a different number. */
const queued = computed<Correction[]>(() =>
  editable.value.flatMap((entry) => {
    const typed = (values.value[entry.coefficient] ?? '').trim()
    const to = scalar(typed)
    if (to === null || to === entry.github) return []
    const note = (notes.value[entry.coefficient] ?? '').trim()
    return [{ coefficient: entry.coefficient, from: entry.github, to, ...(note ? { note } : {}) }]
  }),
)

/** A typed value that is not a number at all, which is a mistake rather than a
 *  blank. Named separately so the button can refuse rather than ignore it. */
const unreadable = computed(() =>
  editable.value.filter((entry) => {
    const typed = (values.value[entry.coefficient] ?? '').trim()
    return typed !== '' && scalar(typed) === null
  }).map((entry) => entry.coefficient),
)

const blocked = computed(() => corrections.refusal || null)
</script>

<template>
  <div v-if="editable.length" class="border-gray-200 border-t mt-4 pt-3">
    <div v-if="!open" class="flex flex-wrap gap-2.5 items-center">
      <u-button size="sm" color="neutral" variant="subtle" icon="i-lucide-pencil" @click="start">
        Correct this file
      </u-button>
      <span class="text-gray-500 text-sm">
        Changes the calibration file, not the review record. Opens its own pull request on your fork.
      </span>
    </div>

    <div v-else class="space-y-3">
      <div class="flex gap-2 items-baseline justify-between">
        <h4 class="font-semibold text-[13px]">Correct {{ row.fileName }}</h4>
        <u-button size="xs" color="neutral" variant="ghost" @click="open = false">Close</u-button>
      </div>

      <div v-if="!auth.canSignOff" class="text-gray-500 text-sm">
        <nuxt-link to="/settings" class="text-primary-700 underline">Sign in</nuxt-link>
        with your initials to propose a correction.
      </div>

      <template v-else>
        <p v-if="corrections.checking" class="text-gray-500 text-sm">
          Checking your fork against oceanobservatories/asset-management…
        </p>

        <!-- A fork that is not exactly upstream is a fork whose files this
             dashboard has never read, so this is a refusal rather than a
             warning. Syncing is one button on GitHub. -->
        <u-alert
          v-else-if="blocked"
          color="error"
          variant="subtle"
          title="Your fork is not in sync"
          :description="blocked"
        >
          <template #actions>
            <u-button size="xs" color="neutral" variant="subtle" @click="corrections.checkSync(true)">
              Check again
            </u-button>
          </template>
        </u-alert>

        <template v-else>
          <div class="coefwrap">
            <table class="coef">
              <thead>
                <tr>
                  <th>Coefficient</th>
                  <th class="text-right">In the file</th>
                  <th class="text-right">Vendor</th>
                  <th>Correct to</th>
                  <th>Note for the file</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="entry in editable" :key="entry.coefficient">
                  <td>{{ entry.coefficient }}</td>
                  <td class="num text-right">{{ entry.github }}</td>
                  <td class="num text-right">
                    <button
                      v-if="entry.expected !== null && entry.expected !== undefined"
                      class="text-primary-700 hover:underline"
                      type="button"
                      @click="take(entry)"
                    >{{ entry.expected }}</button>
                    <span v-else>—</span>
                  </td>
                  <td>
                    <input
                      v-model="values[entry.coefficient]"
                      class="fld num"
                      :placeholder="String(entry.github)"
                      :aria-label="`New value for ${entry.coefficient}`"
                    >
                  </td>
                  <td>
                    <input
                      v-model="notes[entry.coefficient]"
                      class="fld"
                      placeholder="optional"
                      :aria-label="`Note for ${entry.coefficient}`"
                    >
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="text-gray-500 text-[12.5px]">
            Click a vendor value to take it. Anything left blank is left alone, and the number is
            written in the notation the line already uses.
          </p>

          <p v-if="unreadable.length" class="text-red-700 text-[12.5px]">
            Not a number: {{ unreadable.join(', ') }}.
          </p>

          <div class="flex flex-wrap gap-2.5 items-center">
            <u-button
              size="sm"
              color="primary"
              :loading="busy"
              :disabled="!queued.length || unreadable.length > 0"
              @click="corrections.proposeCalibration(String(row.instrument), String(row.fileName), queued)"
            >
              Propose {{ queued.length || '' }} correction{{ queued.length === 1 ? '' : 's' }}
            </u-button>
            <span class="text-gray-500 text-sm">
              to <b>{{ auth.forkFor('assetManagement') }}</b> only. Raise the pull request upstream
              by hand; no data changes until that one is merged.
            </span>
          </div>
        </template>
      </template>

      <u-alert
        v-if="result"
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
    </div>
  </div>
</template>

<style scoped>
.fld {
  border: 1px solid var(--color-gray-300, #d1d5db);
  border-radius: 5px;
  font-size: 12.5px;
  padding: 3px 6px;
  width: 100%;
}
.fld:focus { border-color: #2b6cb0; outline: none; }
</style>
