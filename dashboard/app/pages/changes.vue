<script setup lang="ts">
import { CHECKS, MOVEMENTS, useStore, type ComparedCheck, type Moved } from '~/store'

const store = useStore()
const comparison = computed(() => store.comparison)

const titleOf = (key: string) => CHECKS.find((check) => check.key === key)?.title ?? key
const when = (value?: string) => (value ? new Date(value).toLocaleString() : '—')

/** `unchanged` is a count, every other bucket is a list. */
function rows(check: ComparedCheck, key: string): Moved[] {
  const bucket = check[key as keyof ComparedCheck]
  return Array.isArray(bucket) ? bucket : []
}

/** Only the checks that actually moved are worth a section. */
const moved = computed(() =>
  Object.entries(comparison.value?.checks ?? {})
    .map(([key, check]) => ({ key, check }))
    .filter(({ check }) => MOVEMENTS.some((movement) => rows(check, movement.key).length)),
)
</script>

<template>
  <div class="max-w-5xl space-y-6">
    <div>
      <h1 class="font-semibold text-2xl">Changes</h1>
      <p class="max-w-prose mt-1 text-gray-600">
        Every row whose status is different between this run and an earlier one: what the change
        broke, what it fixed, and what appeared or disappeared. A run fills this page in only if it
        was told to compare itself with another run.
      </p>
    </div>

    <u-alert
      v-if="!comparison"
      color="neutral"
      variant="subtle"
      title="This run was not compared with anything"
      description="To get one, set the bar at the top of the page to Testing, name the branch, set Compare with to Production, and run the checks. This page fills in when that run publishes."
    />

    <template v-else>
      <!-- A row can move because the data changed or because the check changed.
           Fixing the silent-pass bug moved 114 rows with nothing in the
           repositories moving at all, so this cannot be a footnote. -->
      <u-alert
        v-if="!comparison.comparable"
        color="warning"
        variant="subtle"
        title="These runs cannot be compared directly"
      >
        <template #description>
          <ul class="list-disc mt-1 pl-5">
            <li v-for="reason in comparison.reasons" :key="reason">{{ reason }}</li>
          </ul>
          <p class="mt-2">
            A row that moved may be the check having changed rather than the data. Re-run both
            against the same version of the checks before trusting this.
          </p>
        </template>
      </u-alert>

      <div class="bg-white border border-gray-200 gap-x-10 gap-y-3 grid px-5 py-4 rounded-lg sm:grid-cols-2">
        <div>
          <div class="text-[11px] font-semibold text-gray-500 tracking-wider uppercase">Compared with</div>
          <div>{{ when(comparison.baselineRunAt) }}</div>
        </div>
        <div>
          <div class="text-[11px] font-semibold text-gray-500 tracking-wider uppercase">This run</div>
          <div>{{ when(comparison.currentRunAt) }}</div>
        </div>
        <div v-for="(source, name) in comparison.sources" :key="name" class="sm:col-span-2">
          <div class="text-[11px] font-semibold text-gray-500 tracking-wider uppercase">{{ name }}</div>
          <div class="font-mono text-sm">
            {{ source.baseline?.ref ?? '—' }} → {{ source.current.ref }}
          </div>
        </div>
      </div>

      <p v-if="!moved.length" class="text-gray-600">
        Nothing moved between these two runs.
      </p>

      <section v-for="entry in moved" :key="entry.key" class="space-y-3">
        <h2 class="font-semibold text-lg">{{ titleOf(entry.key) }}</h2>
        <div
          v-for="movement in MOVEMENTS"
          :key="movement.key"
          v-show="rows(entry.check, movement.key).length"
        >
          <div class="flex gap-2 items-baseline">
            <u-badge :color="movement.tone" variant="subtle" size="sm">
              {{ rows(entry.check, movement.key).length }} {{ movement.title }}
            </u-badge>
            <span class="text-gray-500 text-sm">{{ movement.hint }}</span>
          </div>
          <div class="border border-gray-200 mt-2 overflow-hidden rounded-lg">
            <div
              v-for="(row, index) in rows(entry.check, movement.key)"
              :key="index"
              class="bg-white border-b border-gray-100 last:border-b-0 px-4 py-2.5"
            >
              <div class="flex flex-wrap gap-x-3 gap-y-1 items-baseline">
                <span class="font-mono text-sm">{{ row.key.join(' · ') }}</span>
                <span v-if="row.was" class="text-gray-500 text-sm">{{ row.was }} → {{ row.now }}</span>
                <span v-if="row.fields" class="text-gray-500 text-sm">{{ row.fields.join(', ') }}</span>
              </div>
              <row-detail
                v-if="movement.key === 'newlyFailing'"
                :check="entry.key"
                :row="row.row"
                class="mt-2"
              />
            </div>
          </div>
        </div>
        <p class="text-gray-500 text-sm">{{ entry.check.unchanged }} rows unchanged</p>
      </section>
    </template>
  </div>
</template>
