<script setup lang="ts">
import { useSignoff } from '~/signoff'
import { useStore, type Row, type VendorOnly } from '~/store'

const store = useStore()
const signoff = useSignoff()
const search = ref('')

/**
 * Vendor calibrations the repository holds nothing for.
 *
 * Not rows in the calibration table, because there is no repository file to be
 * a row — which is why they used to sit in an amber panel above it, 146 names
 * in a scrolling box on top of the queue someone was trying to work.
 *
 * They are still worth a decision, so each is signed off in the calibration
 * sheet under the name the repository file would have if it were ingested. A
 * note taken now is already attached to the file on the day it arrives.
 */
const missing = computed<VendorOnly[]>(() =>
  (store.report?.checks?.calibrations?.missingFromGithub ?? []).map((entry) =>
    // Runs published before each carried its instrument have a bare name.
    typeof entry === 'string'
      ? { file: entry, instrument: '', hitlKey: `${entry}.csv`, HITLstatus: 'NA', HITLnotes: '' }
      : entry,
  ),
)

const shown = computed(() => {
  const term = search.value.trim().toLowerCase()
  return missing.value.filter(
    (entry) =>
      entry.file.toLowerCase().includes(term) || entry.instrument.toLowerCase().includes(term),
  )
})

/** One open at a time, the way a check table opens a row. */
const opened = ref<string | null>(null)
const toggle = (key: string) => (opened.value = opened.value === key ? null : key)

/** What the sign-off control expects: it reads the note and the key off the row
 *  and writes to the sheet the key belongs to. */
const asRow = (entry: VendorOnly): Row => ({
  severity: 'unchecked',
  cleared: entry.HITLstatus === 'Clear',
  hitlKey: entry.hitlKey,
  HITLstatus: entry.HITLstatus,
  HITLnotes: entry.HITLnotes,
  fileName: `${entry.file}.csv`,
})

const queuedFor = (entry: VendorOnly) => signoff.decisionFor('calibrations', entry.hitlKey)
</script>

<template>
  <div class="max-w-4xl space-y-5">
    <div>
      <h1 class="font-semibold text-2xl">Not in asset-management</h1>
      <p class="max-w-prose mt-1 text-gray-600">
        Vendor calibrations on file in calibrationFiles that the repository holds nothing for.
        Nothing compares them, because there is no repository file to compare. Clearing one records
        the decision in the calibration sheet under the name the repository file would have.
      </p>
    </div>

    <run-stamp />

    <div class="flex gap-3 items-center">
      <u-input v-model="search" placeholder="Filter" icon="i-lucide-search" class="max-w-xs" />
      <span class="text-gray-500 text-sm">{{ shown.length }} of {{ missing.length }}</span>
    </div>

    <div class="border border-gray-200 overflow-hidden rounded-lg">
      <table class="min-w-full text-sm">
        <thead class="bg-gray-50 text-gray-600">
          <tr>
            <th class="w-8" />
            <th class="font-semibold px-3 py-2 text-left text-[10px] tracking-wider uppercase">
              File name
            </th>
            <th class="font-semibold px-3 py-2 text-left text-[10px] tracking-wider uppercase">
              Instrument
            </th>
            <th class="font-semibold px-3 py-2 text-left text-[10px] tracking-wider uppercase">
              Sign-off
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="entry in shown" :key="entry.file">
            <tr
              class="border-t border-gray-100 cursor-pointer hover:bg-primary-50"
              :class="{ 'bg-primary-50': opened === entry.hitlKey }"
              @click="toggle(entry.hitlKey)"
            >
              <td class="pl-3 text-gray-400">
                <i :class="['fas', opened === entry.hitlKey ? 'fa-chevron-down' : 'fa-chevron-right', 'text-[10px]']" />
              </td>
              <td class="font-mono px-3 py-1.5">{{ entry.file }}</td>
              <td class="px-3 py-1.5 text-gray-700">{{ entry.instrument || '—' }}</td>
              <td class="px-3 py-1.5">
                <span v-if="queuedFor(entry)" class="b warn">{{ queuedFor(entry)!.status }} · queued</span>
                <span v-else-if="entry.HITLstatus === 'Clear'" class="b ok">Cleared</span>
                <span v-else-if="entry.HITLstatus === 'NotClear'" class="b crit">Flagged</span>
                <span v-else class="text-gray-400">—</span>
              </td>
            </tr>
            <tr v-if="opened === entry.hitlKey" class="bg-primary-50/40 border-t border-gray-100">
              <td colspan="4" class="px-4 py-3">
                <template v-if="entry.HITLnotes">
                  <h4 class="font-bold text-[10px] text-gray-500 tracking-wider uppercase">
                    Reviewer notes
                  </h4>
                  <p class="max-w-prose mb-3 text-[12.5px] text-gray-700 leading-relaxed">
                    {{ entry.HITLnotes }}
                  </p>
                </template>
                <sign-off sheet="calibrations" :row="asRow(entry)" />
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      <p v-if="!shown.length" class="px-3 py-3 text-gray-500 text-sm">
        {{ missing.length ? 'Nothing matches that filter.' : 'Every vendor calibration has a repository file.' }}
      </p>
    </div>
  </div>
</template>
