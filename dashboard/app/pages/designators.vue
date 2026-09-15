<script setup lang="ts">
import { useStore } from '~/store'

const store = useStore()
const search = ref('')

/** What the run covered, as opposed to what it found. */
const designators = computed(() => {
  const term = search.value.trim().toLowerCase()
  return (store.report?.referenceDesignators ?? []).filter((name) => name.toLowerCase().includes(term))
})
</script>

<template>
  <div class="max-w-4xl space-y-5">
    <div>
      <h1 class="font-semibold text-2xl">Reference designators</h1>
      <p class="mt-1 text-gray-600">
        Every reference designator with a deployment in this run — what was covered, rather than
        what was found.
      </p>
    </div>

    <div class="flex gap-3 items-center">
      <u-input v-model="search" placeholder="Filter" icon="i-lucide-search" class="max-w-xs" />
      <span class="text-gray-500 text-sm">
        {{ designators.length }} of {{ store.report?.referenceDesignators.length ?? 0 }}
      </span>
    </div>

    <div class="bg-white border border-gray-200 gap-x-8 grid md:grid-cols-2 p-4 rounded-lg">
      <div v-for="name in designators" :key="name" class="border-b border-gray-50 font-mono py-1 text-sm">
        {{ name }}
      </div>
    </div>
  </div>
</template>
