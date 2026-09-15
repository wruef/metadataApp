<script setup lang="ts">
import { useStore } from '~/store'

const store = useStore()
onMounted(store.load)
</script>

<template>
  <u-app>
    <div class="bg-gray-50 flex min-h-screen">
      <aside class="shrink-0 w-56"><side-bar /></aside>
      <main class="grow min-w-0 p-6">
        <div v-if="store.status === 'loading'" class="text-gray-500">Loading the latest run…</div>
        <u-alert
          v-else-if="store.status === 'error'"
          color="error"
          variant="subtle"
          title="No report to show"
          :description="`${store.error}. A report is written by the verify workflow — nothing is produced on a schedule.`"
        />
        <nuxt-page v-else />
      </main>
    </div>
  </u-app>
</template>
