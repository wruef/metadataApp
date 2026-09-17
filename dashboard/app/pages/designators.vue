<script setup lang="ts">
import { useStore } from '~/store'

const store = useStore()
const search = ref('')

/** What the run covered, as opposed to what it found. */
const designators = computed(() => {
  const term = search.value.trim().toLowerCase()
  return (store.report?.referenceDesignators ?? []).filter((name) => name.toLowerCase().includes(term))
})

/** And what it could not cover. A check that quietly does less than you think
 *  is worse than one that says what it skipped, so the instruments with no
 *  calibration in asset-management are named rather than left to be inferred
 *  from an absence. */
const excluded = computed(() => store.report?.excludedInstruments ?? [])

/** The instrument alone, which is what the exclusion is a property of. */
const excludedNames = computed(() =>
  [...new Set(excluded.value.map((name) => name.replace(/\d+$/, '')))].sort(),
)
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
        {{ designators.length }} of {{ store.report?.referenceDesignators?.length ?? 0 }}
      </span>
    </div>

    <div class="bg-white border border-gray-200 gap-x-8 grid md:grid-cols-2 p-4 rounded-lg">
      <div v-for="name in designators" :key="name" class="border-b border-gray-50 font-mono py-1 text-sm">
        {{ name }}
      </div>
    </div>

    <div v-if="excluded.length">
      <h2 class="font-semibold text-lg">Excluded from calibration verification</h2>
      <p class="max-w-prose mt-1 text-gray-600 text-sm">
        asset-management holds no calibration for these {{ excluded.length }} instruments, so there
        is nothing to compare and nothing was missed. They are counted in no other figure —
        excluded is a category of its own, not a pass and not an omission.
      </p>
      <div class="bg-white border border-gray-200 gap-x-8 grid md:grid-cols-3 mt-3 p-4 rounded-lg">
        <div
          v-for="name in excludedNames"
          :key="name"
          class="border-b border-gray-50 font-mono py-1 text-sm text-gray-700"
        >
          {{ name }}
        </div>
      </div>
    </div>
  </div>
</template>
