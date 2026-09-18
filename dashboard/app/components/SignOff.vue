<script setup lang="ts">
import { useAuth } from '~/auth'
import { useBatch } from '~/batch'
import { hitlKeyOf, type SheetKey } from '~/signoff'
import { useStore, type Row } from '~/store'

const { sheet, row } = defineProps<{ sheet: SheetKey; row: Row }>()
const auth = useAuth()
const batch = useBatch()
const store = useStore()

const key = computed(() => hitlKeyOf(sheet, row))
const queued = computed(() => batch.decisionFor(sheet, key.value))
const notes = ref('')

watchEffect(() => {
  notes.value = queued.value?.notes ?? String(row.HITLnotes ?? '').trim()
})

/** Every reason already written in this sheet, carried in the report because
 *  the sheet holds notes for rows this run does not — a sign-off on a
 *  calibration file since removed still carries wording worth reusing. */
const reasons = computed(() => store.report?.hitlNotes?.[sheet] ?? [])

/** What the asset-management file itself says about the coefficients that
 *  disagree. A reviewer clearing one of these usually writes down exactly that
 *  — the pressure offset added on purpose, the vendor file a value was read out
 *  of — so it is offered rather than retyped from the panel above. */
const fileNotes = computed(() => {
  const differences = Array.isArray(row.differences) ? row.differences : []
  const notes = differences.map((entry) =>
    String((entry as Record<string, unknown>).note ?? '').trim(),
  )
  return [...new Set(notes.filter(Boolean))]
})

const options = computed(() => [...fileNotes.value, ...reasons.value])

/** The dropdown follows the text rather than driving it, so editing a reason
 *  after picking it falls back to 'Something else' instead of leaving the two
 *  controls disagreeing about what the note says. */
const picked = computed({
  get: () => (options.value.includes(notes.value) ? notes.value : ''),
  set: (value: string) => {
    notes.value = value
    if (queued.value) decide(queued.value.status)
  },
})

function decide(status: 'Clear' | 'NotClear') {
  batch.queueSignoff({ sheet, key: key.value, status, notes: notes.value.trim() })
}
</script>

<template>
  <div class="border-gray-200 border-t pt-3">
    <div v-if="!auth.canSignOff" class="text-gray-500 text-sm">
      <nuxt-link to="/settings" class="text-primary-700 underline">Sign in</nuxt-link>
      with your initials to clear or flag this row.
    </div>

    <div v-else class="space-y-2">
      <div class="flex flex-wrap gap-2 items-center">
        <u-button
          size="sm"
          :color="queued?.status === 'Clear' ? 'success' : 'neutral'"
          :variant="queued?.status === 'Clear' ? 'solid' : 'subtle'"
          @click="decide('Clear')"
        >
          <i class="fa-check fas" /> Clear
        </u-button>
        <u-button
          size="sm"
          :color="queued?.status === 'NotClear' ? 'warning' : 'neutral'"
          :variant="queued?.status === 'NotClear' ? 'solid' : 'subtle'"
          @click="decide('NotClear')"
        >
          <i class="fa-flag fas" /> Flag
        </u-button>
        <u-button
          v-if="queued"
          size="sm"
          color="neutral"
          variant="ghost"
          @click="batch.unqueueSignoff(sheet, key)"
        >
          Undo
        </u-button>
        <!-- A sign-off does not erase the failing check; it records a judgement
             beside it. Saying so where the decision is made keeps that honest. -->
        <span v-if="queued" class="text-gray-500 text-sm">
          queued as <b>{{ queued.status }}</b> — the check stays on the row
        </span>
      </div>
      <div class="flex flex-col gap-2 max-w-xl">
        <!-- What the team already writes, so a queue reads as one vocabulary
             rather than fifty spellings of the same judgement. -->
        <select
          v-if="options.length"
          v-model="picked"
          class="sel"
          style="max-width: 100%"
          aria-label="Reason this row was reviewed"
        >
          <option value="">Something else — write it below</option>
          <!-- What the file says about the coefficients in question, first:
               on a row that disagrees it is usually the answer. -->
          <optgroup v-if="fileNotes.length" label="From the asset-management file">
            <option v-for="note in fileNotes" :key="note" :value="note">{{ note }}</option>
          </optgroup>
          <optgroup v-if="reasons.length" label="Written before in 2i-HITL">
            <option v-for="reason in reasons" :key="reason" :value="reason">{{ reason }}</option>
          </optgroup>
        </select>
        <u-input
          v-model="notes"
          aria-label="Reason for the decision"
          placeholder="Why — what you checked, and what convinced you"
          size="sm"
          @blur="queued && decide(queued.status)"
        />
      </div>
    </div>
  </div>
</template>
