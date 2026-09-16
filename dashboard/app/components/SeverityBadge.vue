<script setup lang="ts">
import { SEVERITY_LABEL, type Severity } from '~/store'

/** Plain elements, not `u-badge`. A table can hold well over a thousand rows,
 *  and a component instance per badge made every click re-render thousands of
 *  them — the cost showed up as the page not responding. */
const CLASSES: Record<Severity, string> = {
  problem: 'bg-red-50 text-red-700 ring-red-600/20',
  review: 'bg-amber-50 text-amber-800 ring-amber-600/20',
  unchecked: 'bg-gray-100 text-gray-600 ring-gray-500/20',
  ok: 'bg-green-50 text-green-700 ring-green-600/20',
}

const { severity, cleared = false } = defineProps<{ severity: Severity; cleared?: boolean }>()
</script>

<template>
  <span class="flex gap-1.5 items-center">
    <span
      class="font-medium inline-flex px-2 py-0.5 ring-inset ring-1 rounded-md text-xs whitespace-nowrap"
      :class="CLASSES[severity]"
    >
      {{ SEVERITY_LABEL[severity] }}
    </span>
    <!-- A sign-off outranks a failing check, but the failing check stays visible
         on the row: cleared, and noted. -->
    <span
      v-if="cleared"
      class="bg-primary-50 font-medium inline-flex px-2 py-0.5 ring-inset ring-1 ring-primary-600/20 rounded-md text-primary-700 text-xs whitespace-nowrap"
    >
      Cleared
    </span>
  </span>
</template>
