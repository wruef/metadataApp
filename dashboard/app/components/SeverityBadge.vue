<script setup lang="ts">
import { SEVERITY_TONE } from '~/display'
import { SEVERITY_LABEL, type Severity } from '~/store'

/** Plain elements, not `u-badge`. A table can hold well over a thousand rows,
 *  and a component instance per badge made every click re-render thousands of
 *  them — the cost showed up as the page not responding.
 *
 *  The dot carries the severity and the word carries the finding, so a column
 *  of these scans on colour alone and still reads when it is printed. */
const { severity, cleared = false } = defineProps<{ severity: Severity; cleared?: boolean }>()
</script>

<template>
  <span class="flex gap-1.5 items-center">
    <span class="b" :class="SEVERITY_TONE[severity]">{{ SEVERITY_LABEL[severity] }}</span>
    <!-- A sign-off outranks a failing check, but the failing check stays visible
         on the row: cleared, and noted. -->
    <span v-if="cleared" class="b plain">CLEARED</span>
  </span>
</template>
