<script setup lang="ts">
import { CHECKS, useStore } from '~/store'

const store = useStore()
const route = useRoute()

const definition = computed(() => CHECKS.find((check) => check.key === route.params.check))
const check = computed(() => store.report?.checks[route.params.check as string])
</script>

<template>
  <div class="space-y-5">
    <div v-if="!definition || !check" class="text-gray-500">No such check in this report.</div>
    <template v-else>
      <div>
        <h1 class="flex font-semibold gap-3 items-center text-2xl">
          <i :class="['fas', definition.icon, 'text-primary-600']" />
          {{ definition.title }}
        </h1>
        <p class="max-w-prose mt-1 text-gray-600">{{ definition.blurb }}</p>
      </div>

      <run-stamp />

      <!-- Vendor originals on file that the repository holds nothing for: not a
           row in the table, because there is no repository file to be a row. -->
      <u-alert
        v-if="check.missingFromGithub?.length"
        color="warning"
        variant="subtle"
        :title="`${check.missingFromGithub.length} vendor files have no calibration file in the repository`"
      >
        <template #description>
          <div class="font-mono max-h-32 mt-1 overflow-y-auto text-xs">
            <div v-for="name in check.missingFromGithub" :key="name">{{ name }}</div>
          </div>
        </template>
      </u-alert>

      <check-table :check="check" :columns="definition.columns" />
    </template>
  </div>
</template>
