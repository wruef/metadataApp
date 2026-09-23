<script setup lang="ts">
import { countsIn, deployYears, designatorsFor, inTheWater, type Scope } from '~/designators'
import { useStore } from '~/store'

const store = useStore()
const search = ref('')

/** Every deployment the run judged, which is where the years come from. */
const rows = computed(() => store.report?.checks?.deployments?.rows ?? [])
const years = computed(() => deployYears(rows.value))

const scope = ref<Scope>('all')
const year = ref('')
watchEffect(() => {
  if (!year.value && years.value.length) year.value = years.value[0]!
})

const SCOPES = [
  { value: 'all', label: 'All time' },
  { value: 'now', label: 'In the water now' },
  { value: 'notNow', label: 'Not in the water' },
  { value: 'year', label: 'Deployed in' },
  { value: 'absent', label: 'Not deployed in' },
] as const

/** Which deployment each designator has in the water, so the list can say what
 *  is down there rather than only that something is. */
const open = computed(() => inTheWater(rows.value))

/** What the run covered, as opposed to what it found. */
const chosen = computed(() =>
  designatorsFor(store.report?.referenceDesignators ?? [], rows.value, scope.value, year.value))

const designators = computed(() => {
  const term = search.value.trim().toLowerCase()
  return chosen.value.filter((name) => name.toLowerCase().includes(term))
})

/** How many deployments each had that year, so "deployed in 2026" can say
 *  whether it went in once or was turned around twice. */
const counts = computed(() => countsIn(rows.value, year.value))

const blurb = computed(() => ({
  all: 'Every reference designator with a deployment in this run — what was covered, rather than what was found.',
  now: 'Every reference designator with a deployment that has no end date, which is what the sheets say is on the seafloor right now.',
  notNow: 'Every reference designator the run covered whose last deployment has been closed out, so the sheets say nothing of it is in the water.',
  year: `Every reference designator with a deployment that went in the water in ${year.value}.`,
  absent: `Every reference designator the run covered that has no deployment starting in ${year.value}. Either nobody turned it around that season, or its deployment never reached the sheets.`,
}[scope.value]))

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
      <p class="max-w-prose mt-1 text-gray-600">{{ blurb }}</p>
    </div>

    <div class="flex flex-wrap gap-3 items-center">
      <div class="seg">
        <button
          v-for="option in SCOPES"
          :key="option.value"
          :aria-pressed="scope === option.value"
          @click="scope = option.value"
        >{{ option.label }}</button>
      </div>

      <select
        v-if="scope === 'year' || scope === 'absent'"
        v-model="year"
        class="fld"
        aria-label="Deployment year"
      >
        <option v-for="each in years" :key="each" :value="each">{{ each }}</option>
      </select>

      <u-input v-model="search" placeholder="Filter" icon="i-lucide-search" class="max-w-xs" />
      <span class="text-gray-500 text-sm">{{ designators.length }} of {{ chosen.length }}</span>
    </div>

    <div
      class="bg-white border border-gray-200 gap-x-8 grid p-4 rounded-lg"
      :class="scope === 'now' ? '' : 'md:grid-cols-2'"
    >
      <div
        v-for="name in designators"
        :key="name"
        class="border-b border-gray-50 flex gap-2 items-baseline justify-between py-1"
      >
        <span class="font-mono text-sm">{{ name }}</span>
        <span
          v-if="scope === 'year' && (counts.get(name) ?? 0) > 1"
          class="text-[11px] text-gray-500"
        >{{ counts.get(name) }} deployments</span>
        <!-- What is actually down there, and since when. Two open deployments
             of one designator is a sheet error rather than two instruments, so
             both are named rather than one picked. -->
        <span v-if="scope === 'now'" class="text-[11px] text-gray-500 text-right">
          <span v-for="each in open.get(name) ?? []" :key="String(each.deployNum)" class="block">
            <span class="font-mono">{{ each.AssetID }}</span>
            since {{ String(each.deployDate ?? '').slice(0, 10) }}
          </span>
        </span>
      </div>
      <p v-if="!designators.length" class="py-1 text-gray-500 text-sm">
        Nothing matches that filter.
      </p>
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

<style scoped>
.fld {
  background: #fff;
  border: 1px solid #cdd8e1;
  border-radius: 5px;
  font-size: 13px;
  padding: 4px 7px;
}
.fld:focus { border-color: #2b6cb0; outline: none }
</style>
