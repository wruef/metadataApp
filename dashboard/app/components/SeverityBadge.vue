<script setup lang="ts">
import { SEVERITY_COLOR, SEVERITY_LABEL, type Severity } from '~/store'

const { severity, cleared = false } = defineProps<{ severity: Severity; cleared?: boolean }>()
</script>

<template>
  <div class="flex gap-1.5 items-center">
    <u-badge :color="SEVERITY_COLOR[severity]" variant="subtle" size="sm">
      {{ SEVERITY_LABEL[severity] }}
    </u-badge>
    <!-- A sign-off outranks a failing check, but the failing check stays visible
         on the row: cleared, and noted. -->
    <u-badge v-if="cleared" color="primary" variant="soft" size="sm">
      <i class="fa-check fas mr-1" />Cleared
    </u-badge>
  </div>
</template>
