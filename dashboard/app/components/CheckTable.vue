<script setup lang="ts">
import { useAuth } from '~/auth'
import { compareValues, identity, splitVerdict, toneOf, SEVERITY_TONE, type Tone } from '~/display'
import { ALL, ATTENTION, matchesWhere, type Where } from '~/query'
import { useBatch } from '~/batch'
import { hitlKeyOf, HITL_SHEETS, type SheetKey } from '~/signoff'
import { SEVERITIES, SEVERITY_LABEL, type Check, type Facet, type Row } from '~/store'

const { check, checkKey, columns, facets } = defineProps<{
  check: Check
  checkKey: string
  columns: readonly string[]
  facets: readonly Facet[]
}>()

/**
 * Clearing and flagging from the row itself.
 *
 * A reviewer works down a queue, and most rows need no more than a verdict, so
 * the decision lives where the eye already is. It opens the row as well, because
 * a sign-off with no note is a worse record than none.
 */
const auth = useAuth()
const batch = useBatch()
const sheet = computed(() => (checkKey in HITL_SHEETS ? (checkKey as SheetKey) : null))

function keyOf(row: Row) {
  return sheet.value ? hitlKeyOf(sheet.value, row) : ''
}

function queuedFor(row: Row) {
  return sheet.value ? batch.decisionFor(sheet.value, keyOf(row)) : undefined
}

function decide(index: number, row: Row, status: 'Clear' | 'NotClear') {
  if (!sheet.value) return
  batch.queueSignoff({
    sheet: sheet.value,
    key: keyOf(row),
    status,
    notes: String(row.HITLnotes ?? '').trim(),
  })
  opened.value = index
}

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

/** A link from the overview names the rows it counted, so the table it opens
 *  shows exactly those and not a superset the reader has to narrow again. */
const route = useRoute()
const asked = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] : '')

/** Otherwise the check opens on its queue, not on the 1,558 rows that already
 *  agree. A check with nothing outstanding opens on everything instead, so it
 *  never greets you with an empty table. */
const fallback = (check.summary.attention ?? check.summary.problem + check.summary.review) > 0
  ? ATTENTION
  : ALL

const severity = ref<string>(asked('severity') || fallback)
/** Empty means the facet is not narrowing anything. */
const picked = reactive<Record<string, string>>(
  Object.fromEntries(facets.map((facet) => [facet.key, asked(facet.key)])),
)
const clearedOnly = ref<string>(asked('cleared') || 'all')
const search = ref(asked('q'))

/**
 * Sorting, which is off until a header is clicked.
 *
 * Off means the queue order the report exists for: worst first, so the rows
 * that need a person are the ones on the first page. A column sort is for
 * answering a different question — every calibration for one instrument in date
 * order, say — so it is something you turn on, and a third click turns it off
 * again rather than leaving the table in a state with no way back.
 */
const REVIEW_STATUS = 'severity'
const sortColumn = ref(asked('sort'))
const sortAsc = ref(asked('dir') !== 'desc')

/** The filters, back into the address bar. A filtered table is a URL only if
 *  narrowing one writes the URL; reading the query on open was half of that,
 *  and the half that let a link in but never produced one. Only what differs
 *  from how the check opens is written, so a fresh page has a clean address. */
const router = useRouter()
watch([severity, picked, clearedOnly, search, sortColumn, sortAsc], () => {
  const query: Record<string, string> = {}
  if (severity.value !== fallback) query.severity = severity.value
  for (const [key, value] of Object.entries(picked)) if (value) query[key] = value
  if (clearedOnly.value !== 'all') query.cleared = clearedOnly.value
  if (search.value) query.q = search.value
  if (sortColumn.value) {
    query.sort = sortColumn.value
    if (!sortAsc.value) query.dir = 'desc'
  }
  router.replace({ query })
}, { deep: true })

function sortBy(column: string) {
  if (sortColumn.value !== column) {
    sortColumn.value = column
    sortAsc.value = true
  } else if (sortAsc.value) {
    sortAsc.value = false
  } else {
    sortColumn.value = ''
  }
}

/** What a screen reader announces, and what the arrow in the header shows. */
function sortState(column: string) {
  if (sortColumn.value !== column) return 'none'
  return sortAsc.value ? 'ascending' : 'descending'
}

/**
 * The filters as one clause, optionally leaving one out.
 *
 * Leaving one out is what lets a control show honest counts: the choices in the
 * instrument dropdown are counted against every *other* filter, so picking one
 * narrows the table without the numbers beside the alternatives going stale.
 */
function where(skip?: string): Where {
  const built: Where = { cleared: clearedOnly.value, q: search.value }
  if (skip !== 'severity') built.severity = severity.value
  for (const facet of facets) {
    if (facet.key !== skip && picked[facet.key]) built[facet.key] = picked[facet.key]
  }
  return built
}

function matches(row: Row, skip?: string) {
  return matchesWhere(row, facets, where(skip), columns)
}

/** Ranked by consequence rather than row order — which is the whole reason the
 *  report carries a review status — until a column is sorted on instead. */
const rows = computed(() => {
  const found = check.rows.filter((row) => matches(row))
  const direction: 1 | -1 = sortAsc.value ? 1 : -1
  if (!sortColumn.value) {
    return found.sort((a, b) => SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity))
  }
  // Review status sorts by its rank, not by the word: 'problem' before 'review'
  // is the order that means something, and alphabetically it is the reverse.
  if (sortColumn.value === REVIEW_STATUS) {
    return found.sort(
      (a, b) => direction * (SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity)),
    )
  }
  const column = sortColumn.value
  return found.sort((a, b) => compareValues(a[column], b[column], direction))
})

const severityCounts = computed(() => {
  const base = check.rows.filter((row) => matches(row, 'severity'))
  const counts: Record<string, number> = { [ALL]: base.length, [ATTENTION]: 0 }
  for (const row of base) {
    counts[row.severity] = (counts[row.severity] ?? 0) + 1
    // A signed-off row is in the cleared category, never in these two, so
    // nothing here has to exclude it.
    if (row.severity === 'problem' || row.severity === 'review') counts[ATTENTION]!++
  }
  return counts
})

/** The segments, in the order a queue is worked. A severity the check has none
 *  of anywhere is left out rather than shown as a permanent zero. */
const segments = computed(() => [
  { value: ATTENTION, label: 'Needs attention' },
  ...SEVERITIES.filter((s) => check.summary[s] > 0).map((s) => ({
    value: s as string,
    label: SEVERITY_LABEL[s],
  })),
  { value: ALL, label: 'All' },
])

const dropdowns = computed(() =>
  facets.map((facet) => {
    const counts = new Map<string, number>()
    for (const row of check.rows) {
      if (!matches(row, facet.key)) continue
      const value = facet.of(row)
      if (value) counts.set(value, (counts.get(value) ?? 0) + 1)
    }
    const options = [...counts.entries()].sort(([a], [b]) => a.localeCompare(b))
    // A chosen value whose rows the other filters have excluded still has to be
    // in the list, or the dropdown goes blank and cannot be undone.
    const chosen = picked[facet.key]
    if (chosen && !counts.has(chosen)) options.unshift([chosen, 0])
    return { facet, options }
  }),
)

const filtered = computed(
  () =>
    severity.value !== fallback ||
    clearedOnly.value !== 'all' ||
    search.value.trim() !== '' ||
    sortColumn.value !== '' ||
    facets.some((facet) => picked[facet.key]),
)

function reset() {
  severity.value = fallback
  for (const facet of facets) picked[facet.key] = ''
  clearedOnly.value = 'all'
  search.value = ''
  sortColumn.value = ''
}

const pageCount = computed(() => Math.max(1, Math.ceil(rows.value.length / PAGE_SIZE)))
const firstShown = computed(() => (rows.value.length ? (page.value - 1) * PAGE_SIZE + 1 : 0))
const lastShown = computed(() => Math.min(page.value * PAGE_SIZE, rows.value.length))

/** What each cell renders as, worked out once per page rather than three times
 *  per cell in the template. */
interface Cell {
  tone: Tone | null
  token: string
  detail: string
  dim: string
  strong: string
  tail: string
  text: string
}

const paged = computed(() =>
  rows.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE).map((row) => ({
    row,
    stripe: SEVERITY_TONE[row.severity],
    cells: columns.map((column): Cell => {
      const raw = row[column]
      const text =
        raw === null || raw === undefined || raw === ''
          ? '—'
          : Array.isArray(raw)
            ? raw.join(', ')
            : String(raw)
      const named = identity(column, text)
      if (named) {
        return { tone: null, token: '', detail: '', text: '', ...named, tail: named.tail ?? '' } as Cell
      }
      const tone = toneOf(checkKey, column, text)
      if (tone) {
        const { token, detail } = splitVerdict(text)
        return { tone, token, detail, dim: '', strong: '', tail: '', text: '' }
      }
      return { tone: null, token: '', detail: '', dim: '', strong: '', tail: '', text }
    }),
  })),
)

/** Narrowing the filters can leave you past the end, and an open row on one page
 *  is not the same row on another. */
watch(rows, () => {
  page.value = 1
  opened.value = null
})
watch(page, () => {
  opened.value = null
})

function label(column: string) {
  return column.replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2')
}
</script>

<template>
  <div>
    <!-- Stays put while a long table scrolls under it: the filters are how a
         queue is worked, and scrolling back up to change one is the friction
         that stops people narrowing at all. -->
    <div class="-mx-6 bg-gray-50 border-b border-gray-200 px-6 py-3 sticky top-0 z-20">
      <div class="flex flex-wrap gap-2 items-center">
        <div class="seg">
          <button
            v-for="segment in segments"
            :key="segment.value"
            :aria-pressed="severity === segment.value"
            @click="severity = segment.value"
          >
            {{ segment.label }}
            <span class="c">{{ severityCounts[segment.value] ?? 0 }}</span>
          </button>
        </div>

        <!-- One dropdown per column worth narrowing by, built from the rows the
             report actually holds. A facet the current filters leave with a
             single choice is hidden rather than shown as a dead control. -->
        <select
          v-for="entry in dropdowns"
          v-show="entry.options.length > 1 || picked[entry.facet.key]"
          :key="entry.facet.key"
          v-model="picked[entry.facet.key]"
          class="sel"
          :aria-label="entry.facet.label"
        >
          <option value="">{{ entry.facet.label }}</option>
          <option v-for="[value, count] in entry.options" :key="value" :value="value">
            {{ value }} ({{ count }})
          </option>
        </select>

        <input
          v-model="search"
          type="search"
          placeholder="Search rows"
          aria-label="Search rows"
          class="bg-white border border-gray-300 min-w-52 px-2.5 py-1 rounded-md text-[12.5px] focus:border-primary-500 focus:outline-none"
        >

        <button
          v-if="filtered"
          class="px-2 py-1 text-[12.5px] text-gray-500 hover:text-primary-700"
          @click="reset"
        >
          Reset
        </button>

        <span class="font-mono ml-auto tabular-nums text-gray-500 text-xs">
          {{ firstShown }}–{{ lastShown }} of {{ rows.length }}
          <span v-if="rows.length !== check.rows.length">· {{ check.rows.length }} in the check</span>
        </span>
      </div>
    </div>

    <div class="border border-gray-200 border-t-0 overflow-x-auto rounded-b-lg">
      <table class="min-w-full text-sm">
        <thead class="bg-gray-50 text-gray-600">
          <tr>
            <th class="w-1" />
            <th class="w-8" />
            <!-- Every header sorts. A third click returns the table to the queue
                 order it opens in, so there is always a way back. -->
            <th class="sortable" :aria-sort="sortState(REVIEW_STATUS)">
              <button type="button" @click="sortBy(REVIEW_STATUS)">
                Review status<i class="ind" :class="sortState(REVIEW_STATUS)" />
              </button>
            </th>
            <th
              v-for="column in columns"
              :key="column"
              class="sortable whitespace-nowrap"
              :aria-sort="sortState(column)"
            >
              <button type="button" @click="sortBy(column)">
                {{ label(column) }}<i class="ind" :class="sortState(column)" />
              </button>
            </th>
            <th v-if="sheet && auth.canSignOff" class="w-px" />
          </tr>
        </thead>
        <tbody>
          <template v-for="(entry, index) in paged" :key="index">
            <tr
              class="border-t border-gray-100 cursor-pointer hover:bg-primary-50"
              :class="{ 'bg-primary-50': opened === index }"
              tabindex="0"
              role="button"
              :aria-expanded="opened === index"
              @click="toggle(index)"
              @keydown.enter.prevent="toggle(index)"
              @keydown.space.prevent="toggle(index)"
            >
              <!-- The severity, readable down the edge of the table without
                   reading a single word. -->
              <td class="stripe"><i :style="{ background: `var(--${entry.stripe})` }" /></td>
              <td class="pl-3 text-gray-400">
                <i :class="['fas', opened === index ? 'fa-chevron-down' : 'fa-chevron-right', 'text-[10px]']" />
              </td>
              <td class="px-3 py-2 whitespace-nowrap">
                <severity-badge :severity="entry.row.severity" :finding="entry.row.finding" />
              </td>
              <td
                v-for="(cell, column) in entry.cells"
                :key="column"
                class="px-3 py-2 whitespace-nowrap"
              >
                <span v-if="cell.strong" class="refdes">
                  <span class="dim">{{ cell.dim }}</span><b>{{ cell.strong }}</b><span class="dim">{{ cell.tail }}</span>
                </span>
                <template v-else-if="cell.tone">
                  <span class="b" :class="cell.tone">{{ cell.token }}</span>
                  <span v-if="cell.detail" class="font-mono ml-2 text-[11px] text-gray-500">
                    {{ cell.detail }}
                  </span>
                </template>
                <template v-else>{{ cell.text }}</template>
              </td>
              <td v-if="sheet && auth.canSignOff" class="px-3 py-2" @click.stop>
                <div class="rowact">
                  <span
                    v-if="queuedFor(entry.row)"
                    class="b"
                    :class="queuedFor(entry.row)!.status === 'Clear' ? 'ok' : 'crit'"
                  >
                    QUEUED {{ queuedFor(entry.row)!.status }}
                  </span>
                  <template v-else>
                    <button class="clr" @click="decide(index, entry.row, 'Clear')">Clear</button>
                    <button class="flg" @click="decide(index, entry.row, 'NotClear')">Flag</button>
                  </template>
                </div>
              </td>
            </tr>
            <tr v-if="opened === index" class="bg-primary-50 border-t border-gray-100">
              <td :colspan="columns.length + (sheet && auth.canSignOff ? 4 : 3)" class="px-6 py-4">
                <row-detail :check="checkKey" :row="entry.row" />
              </td>
            </tr>
          </template>
          <tr v-if="!paged.length">
            <td :colspan="columns.length + (sheet && auth.canSignOff ? 4 : 3)" class="px-3 py-8 text-center text-gray-500">
              Nothing matches those filters.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="pageCount > 1" class="flex gap-3 items-center justify-end mt-3">
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
