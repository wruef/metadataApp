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

      <!-- Keyed, so moving between checks builds a fresh table rather than
           reusing one carrying the previous check's filters. -->
      <check-table
        :key="definition.key"
        :check="check"
        :check-key="definition.key"
        :columns="definition.columns"
        :facets="definition.facets"
      />
    </template>
  </div>
</template>
