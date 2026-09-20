<script setup lang="ts">
import { repoFile } from '~/paths'
import { HITL_SHEETS, type SheetKey } from '~/signoff'
import { CHECKS, useStore, type UnmatchedSignOff } from '~/store'

/**
 * Sign-offs the run could not attach to anything.
 *
 * A 2i-HITL sheet is keyed by whatever identified a row when somebody signed
 * it: a calibration file name, a reference designator with its year and
 * deployment number, an asset ID. When the thing behind the key stops existing
 * — a calibration file asset-management no longer carries, a deployment
 * renumbered out of a sheet — the line stays in the sheet and matches nothing.
 *
 * Until this page it was then invisible. No row carried it, so no screen showed
 * it, and 52 judgements somebody had made sat in the sheets with nobody able to
 * see them. That is the whole reason this exists: it is not a queue and nothing
 * here is signed off. It is a list of decisions that have lost what they were
 * about, for somebody to fix the key or delete the line.
 */
const store = useStore()
const search = ref('')

const titles = Object.fromEntries(CHECKS.map((check) => [check.key, check.title]))

/** Flattened across the checks, because the question a reader arrives with is
 *  "what has come loose", not "what has come loose in the deployment sheet". */
const all = computed(() =>
  Object.entries(store.report?.unmatchedSignOffs ?? {}).flatMap(([check, rows]) =>
    (rows ?? []).map((row) => ({ ...row, check })),
  ),
)

const shown = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return all.value
  return all.value.filter(
    (row) =>
      row.key.toLowerCase().includes(term) ||
      row.notes.toLowerCase().includes(term) ||
      row.reviewers.toLowerCase().includes(term),
  )
})

/** Which sheet a line has to be edited in — the same mapping a sign-off writes
 *  through, so the two cannot name different files. */
const sheetPath = (check: string) => HITL_SHEETS[check as SheetKey]?.path ?? ''
const sheetName = (check: string) => sheetPath(check).split('/').pop() ?? check
const sheetUrl = (check: string) => repoFile(sheetPath(check))

const opened = ref<string | null>(null)
const toggle = (key: string) => (opened.value = opened.value === key ? null : key)
const rowId = (row: UnmatchedSignOff & { check: string }) => `${row.check}:${row.key}`
</script>

<template>
  <div class="max-w-4xl space-y-5">
    <div>
      <h1 class="font-semibold text-2xl">Sign-offs with nothing to sign</h1>
      <p class="max-w-prose mt-1 text-gray-600">
        Lines in the 2i-HITL sheets whose key matches no row this run produced. The calibration file
        or the deployment they were written against is gone from the records, so the judgement
        cannot be shown anywhere else. Either the key needs correcting or the line needs deleting,
        and both are edits to the sheet rather than anything this page can do.
      </p>
    </div>

    <run-stamp />

    <div class="flex gap-3 items-center">
      <u-input v-model="search" placeholder="Filter" icon="i-lucide-search" class="max-w-xs" />
      <span class="text-gray-500 text-sm">{{ shown.length }} of {{ all.length }}</span>
    </div>

    <div class="border border-gray-200 overflow-hidden rounded-lg">
      <table class="min-w-full text-sm">
        <thead class="bg-gray-50 text-gray-600">
          <tr>
            <th class="w-8" />
            <th class="font-semibold px-3 py-2 text-left text-[10px] tracking-wider uppercase">Key</th>
            <th class="font-semibold px-3 py-2 text-left text-[10px] tracking-wider uppercase">Sheet</th>
            <th class="font-semibold px-3 py-2 text-left text-[10px] tracking-wider uppercase">Decision</th>
            <th class="font-semibold px-3 py-2 text-left text-[10px] tracking-wider uppercase">Reviewed</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="row in shown" :key="rowId(row)">
            <tr
              class="border-t border-gray-100 cursor-pointer hover:bg-primary-50"
              :class="{ 'bg-primary-50': opened === rowId(row) }"
              tabindex="0"
              role="button"
              :aria-expanded="opened === rowId(row)"
              @click="toggle(rowId(row))"
              @keydown.enter.prevent="toggle(rowId(row))"
              @keydown.space.prevent="toggle(rowId(row))"
            >
              <td class="pl-3 text-gray-400">
                <i :class="['fas', opened === rowId(row) ? 'fa-chevron-down' : 'fa-chevron-right', 'text-[10px]']" />
              </td>
              <td class="font-mono px-3 py-1.5">{{ row.key }}</td>
              <td class="px-3 py-1.5 text-gray-700">{{ titles[row.check] ?? row.check }}</td>
              <td class="px-3 py-1.5">
                <span v-if="row.status === 'Clear'" class="b ok">Cleared</span>
                <span v-else-if="row.status === 'NotClear'" class="b crit">Flagged</span>
                <span v-else class="text-gray-600">{{ row.status }}</span>
              </td>
              <td class="px-3 py-1.5 text-gray-600">{{ row.dateReviewed || '—' }}</td>
            </tr>
            <tr v-if="opened === rowId(row)" class="bg-primary-50/40 border-t border-gray-100">
              <td colspan="5" class="px-4 py-3">
                <template v-if="row.notes">
                  <h4 class="font-bold text-[10px] text-gray-500 tracking-wider uppercase">
                    Reviewer notes
                  </h4>
                  <p class="max-w-prose mb-3 text-[12.5px] text-gray-700 leading-relaxed">
                    {{ row.notes }}
                  </p>
                </template>
                <p class="text-[12.5px] text-gray-600">
                  Signed off by <b>{{ row.reviewers || 'nobody named' }}</b>. Nothing in this run
                  carries the key <span class="font-mono">{{ row.key }}</span>, so the decision is
                  not shown on any check. Correct or remove the line in
                  <a :href="sheetUrl(row.check)" target="_blank" rel="noopener" class="text-primary-700 underline">
                    {{ sheetName(row.check) }}
                  </a>.
                </p>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      <p v-if="!shown.length" class="px-3 py-3 text-gray-500 text-sm">
        {{ all.length ? 'Nothing matches that filter.' : 'Every sign-off in the sheets matches a row in this run.' }}
      </p>
    </div>
  </div>
</template>
