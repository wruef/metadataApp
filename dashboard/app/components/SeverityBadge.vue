<script setup lang="ts">
import { SEVERITY_TONE } from '~/display'
import { SEVERITY_LABEL, type Severity } from '~/store'

/** Plain elements, not `u-badge`. A table can hold well over a thousand rows,
 *  and a component instance per badge made every click re-render thousands of
 *  them — the cost showed up as the page not responding.
 *
 *  The dot carries the severity and the word carries the finding, so a column
 *  of these scans on colour alone and still reads when it is printed. */
const { severity, finding } = defineProps<{ severity: Severity; finding?: Severity }>()

const tone = computed(() => SEVERITY_TONE[severity])

/** What the checks found, shown beside a sign-off that did not erase it. Some
 *  signed-off calibrations still carry real transcription errors, so the
 *  disagreement has to stay on screen rather than being covered by the
 *  reviewer's decision. */
const flagged = computed(() =>
  severity === 'cleared' && finding && finding !== 'ok' ? finding : null,
)
</script>

<template>
  <span class="flex gap-1.5 items-center">
    <span class="b" :class="tone">{{ SEVERITY_LABEL[severity] }}</span>
    <span v-if="flagged" class="b" :class="SEVERITY_TONE[flagged]">
      {{ SEVERITY_LABEL[flagged] }}
    </span>
  </span>
</template>
