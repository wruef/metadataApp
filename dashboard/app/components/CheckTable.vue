<script setup lang="ts">
import { SEVERITIES, SEVERITY_LABEL, type Check, type Severity } from '~/store'

const { check, checkKey, columns } = defineProps<{
  check: Check
  checkKey: string
  columns: readonly string[]
}>()

/** One row open at a time — the detail is for reading a finding in context,
 *  not for comparing several at once. */
const opened = ref<number | null>(null)
function toggle(index: number) {
  opened.value = opened.value === index ? null : index
}

/** A page at a time. A check can carry well over a thousand rows, and putting
 *  them all in the DOM meant every click re-rendered the lot. A queue is worked
 *  from the top by severity, so a page is how it is read anyway. */
const PAGE_SIZE = 50
const page = ref(1)

const search = ref('')
const chosen = ref<Severity[]>([])
const clearedOnly = ref<'all' | 'cleared' | 'open'>('all')

/** Ranked by consequence rather than row order — which is the whole reason the
 *  report carries a severity. */
const rows = computed(() => {
  const term = search.value.trim().toLowerCase()
  return check.rows
    .filter((row) => !chosen.value.length || chosen.value.includes(row.severity))
    .filter((row) =>
      clearedOnly.value === 'all' ? true : clearedOnly.value === 'cleared' ? row.cleared : !row.cleared,
    )
    .filter((row) => !term || columns.some((column) => String(row[column] ?? '').toLowerCase().includes(term)))
    .sort((a, b) => SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity))
})

const pageCount = computed(() => Math.max(1, Math.ceil(rows.value.length / PAGE_SIZE)))
const paged = computed(() => rows.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))
const firstShown = computed(() => (rows.value.length ? (page.value - 1) * PAGE_SIZE + 1 : 0))
const lastShown = computed(() => Math.min(page.value * PAGE_SIZE, rows.value.length))

/** Narrowing the filters can leave you past the end, and an open row on one page
 *  is not the same row on another. */
watch(rows, () => {
  page.value = 1
  opened.value = null
})
watch(page, () => {
  opened.value = null
})

function cell(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  return Array.isArray(value) ? value.join(', ') : String(value)
}

function label(column: string) {
  return column.replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2')
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap gap-2 items-center">
      <u-input v-model="search" placeholder="Search rows" icon="i-lucide-search" class="max-w-xs" />
      <u-select-menu
        v-model="chosen"
        :items="[...SEVERITIES]"
        multiple
        placeholder="Any severity"
        class="min-w-44"
      >
        <template #default="{ modelValue }">
          {{ modelValue?.length ? modelValue.map((s: Severity) => SEVERITY_LABEL[s]).join(', ') : 'Any severity' }}
        </template>
      </u-select-menu>
      <u-select
        v-model="clearedOnly"
        :items="[
          { label: 'Cleared and open', value: 'all' },
          { label: 'Open only', value: 'open' },
          { label: 'Cleared only', value: 'cleared' },
        ]"
        class="min-w-44"
      />
      <span class="text-gray-500 text-sm">
        Showing {{ firstShown }}–{{ lastShown }} of {{ rows.length }}
        <span v-if="rows.length !== check.rows.length">filtered from {{ check.rows.length }}</span>
      </span>
    </div>

    <div class="border border-gray-200 rounded-lg overflow-x-auto">
      <table class="min-w-full text-sm">
        <thead class="bg-gray-50 text-gray-600">
          <tr>
            <th class="w-8" />
            <th class="font-semibold px-3 py-2 text-left text-xs tracking-wide uppercase">Severity</th>
            <th
              v-for="column in columns"
              :key="column"
              class="font-semibold px-3 py-2 text-left text-xs tracking-wide uppercase whitespace-nowrap"
            >
              {{ label(column) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(row, index) in paged" :key="index">
            <tr
              class="border-t border-gray-100 cursor-pointer hover:bg-gray-50"
              :class="{ 'bg-gray-50': opened === index }"
              @click="toggle(index)"
            >
              <td class="pl-3 text-gray-400">
                <i :class="['fas', opened === index ? 'fa-chevron-down' : 'fa-chevron-right', 'text-[10px]']" />
              </td>
              <td class="px-3 py-2 whitespace-nowrap">
                <severity-badge :severity="row.severity" :cleared="row.cleared" />
              </td>
              <td v-for="column in columns" :key="column" class="px-3 py-2 whitespace-nowrap">
                {{ cell(row[column]) }}
              </td>
            </tr>
            <tr v-if="opened === index" class="bg-gray-50 border-t border-gray-100">
              <td :colspan="columns.length + 2" class="px-6 py-4">
                <row-detail :check="checkKey" :row="row" />
              </td>
            </tr>
          </template>
          <tr v-if="!paged.length">
            <td :colspan="columns.length + 2" class="px-3 py-8 text-center text-gray-500">
              Nothing matches those filters.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="pageCount > 1" class="flex gap-3 items-center justify-end">
      <u-button size="sm" color="neutral" variant="subtle" :disabled="page === 1" @click="page--">
        Previous
      </u-button>
      <span class="tabular-nums text-gray-600 text-sm">Page {{ page }} of {{ pageCount }}</span>
      <u-button
        size="sm"
        color="neutral"
        variant="subtle"
        :disabled="page === pageCount"
        @click="page++"
      >
        Next
      </u-button>
    </div>
  </div>
</template>
