<script setup lang="ts">
import { CHECKS, useStore } from '~/store'

const store = useStore()
</script>

<template>
  <div class="bg-primary-800 flex flex-col min-h-full p-4 text-white">
    <nuxt-link class="flex items-center justify-center" to="/">
      <i class="fa-clipboard-check fas mb-1 mr-3 text-[28px]" />
      <span class="font-semibold text-lg text-nowrap uppercase">Metadata</span>
    </nuxt-link>
    <div class="bg-white h-px mb-3 mt-3 opacity-20" />

    <nav class="space-y-1">
      <nuxt-link
        v-for="check in store.checks"
        :key="check.key"
        :to="`/checks/${check.key}`"
        class="flex gap-3 items-center px-3 py-2 rounded-md text-gray-100 text-sm hover:bg-primary-700"
        active-class="bg-primary-700 font-medium"
      >
        <i :class="['fas', check.icon, 'w-4']" />
        <span class="grow">{{ check.title }}</span>
        <!-- The count that decides whether it is worth opening. -->
        <u-badge
          v-if="store.report?.checks[check.key]?.summary.problem"
          color="error"
          variant="solid"
          size="sm"
        >
          {{ store.report.checks[check.key].summary.problem }}
        </u-badge>
      </nuxt-link>
    </nav>

    <div class="bg-white h-px mb-3 mt-3 opacity-20" />
    <nuxt-link
      to="/designators"
      class="flex gap-3 items-center px-3 py-2 rounded-md text-gray-100 text-sm hover:bg-primary-700"
      active-class="bg-primary-700 font-medium"
    >
      <i class="fa-list fas w-4" />
      <span>Reference designators</span>
    </nuxt-link>
  </div>
</template>
