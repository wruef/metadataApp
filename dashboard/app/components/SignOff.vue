<script setup lang="ts">
import { useAuth } from '~/auth'
import { HITL_SHEETS, useSignoff, type SheetKey } from '~/signoff'
import type { Row } from '~/store'

const { sheet, row } = defineProps<{ sheet: SheetKey; row: Row }>()
const auth = useAuth()
const signoff = useSignoff()

const key = computed(() => HITL_SHEETS[sheet].of(row))
const queued = computed(() => signoff.decisionFor(sheet, key.value))
const notes = ref('')

watchEffect(() => {
  notes.value = queued.value?.notes ?? String(row.HITLnotes ?? '').trim()
})

function decide(status: 'Clear' | 'NotClear') {
  signoff.queue({ sheet, key: key.value, status, notes: notes.value.trim() })
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
          @click="signoff.unqueue(sheet, key)"
        >
          Undo
        </u-button>
        <!-- A sign-off does not erase the failing check; it records a judgement
             beside it. Saying so where the decision is made keeps that honest. -->
        <span v-if="queued" class="text-gray-500 text-sm">
          queued as <b>{{ queued.status }}</b> — the check stays on the row
        </span>
      </div>
      <u-input
        v-model="notes"
        placeholder="Why — what you checked, and what convinced you"
        class="max-w-xl"
        size="sm"
        @blur="queued && decide(queued.status)"
      />
    </div>
  </div>
</template>
