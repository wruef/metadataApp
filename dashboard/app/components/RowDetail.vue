<script setup lang="ts">
import { HITL_SHEETS, type SheetKey } from '~/signoff'
import { useStore, type Row } from '~/store'

const { check, row } = defineProps<{ check: string; row: Row }>()
const store = useStore()

/** The coefficients or fields that actually disagree — the reason the row is in
 *  the queue, and what the old reports made you open a CSV to find. */
const differences = computed(() => (Array.isArray(row.differences) ? row.differences : []))

const links = computed(() => {
  const found: { label: string; href: string }[] = []
  const add = (label: string, href: string | null) => href && found.push({ label, href })

  if (check === 'calibrations') {
    add(
      'Repository file',
      store.fileUrl('assetManagement', `calibration/${row.instrument}/${row.fileName}`),
    )
    // The two repos do not always name a sensor directory the same way, so the
    // vendor path is carried in the report rather than derived.
    for (const name of (row.vendorFiles as string[] | undefined) ?? []) {
      add(`Vendor original · ${name.split('.').slice(1).join('.')}`,
          store.fileUrl('calibrationFiles', `${row.vendorDirectory}/${name}`))
    }
  }

  const refDes = row.refDes as string | undefined
  if (refDes && refDes.length > 14) {
    add('Deployment sheet', store.fileUrl('assetManagement', `deployment/${refDes.slice(0, 8)}_Deploy.csv`))
  }
  return found
})

const notes = computed(() => String(row.HITLnotes ?? '').trim())

/** Only two checks are signed off; the rest have no sheet to record it in. */
const sheet = computed(() => (check in HITL_SHEETS ? (check as SheetKey) : null))
</script>

<template>
  <div class="space-y-4 text-sm">
    <div v-if="links.length" class="flex flex-wrap gap-2">
      <a
        v-for="link in links"
        :key="link.href"
        :href="link.href"
        target="_blank"
        rel="noopener"
        class="bg-white border border-gray-200 gap-1.5 inline-flex items-center px-2.5 py-1 rounded-md hover:border-primary-400"
      >
        <i class="fa-arrow-up-right-from-square fas text-[10px] text-gray-400" />
        {{ link.label }}
      </a>
    </div>

    <div v-if="differences.length">
      <div class="font-semibold mb-1 text-[11px] text-gray-500 tracking-wider uppercase">
        {{ differences.length }} {{ differences.length === 1 ? 'difference' : 'differences' }}
      </div>
      <table class="bg-white border border-gray-200 rounded-md">
        <thead class="text-[11px] text-gray-500 uppercase">
          <tr>
            <th class="font-semibold px-3 py-1.5 text-left">{{ check === 'positions' ? 'Field' : 'Coefficient' }}</th>
            <th class="font-semibold px-3 py-1.5 text-right">In the repository</th>
            <th class="font-semibold px-3 py-1.5 text-right">Expected</th>
            <th v-if="check !== 'positions'" class="font-semibold px-3 py-1.5 text-right">Difference</th>
            <th v-if="check !== 'positions'" class="font-semibold px-3 py-1.5 text-left">Source</th>
          </tr>
        </thead>
        <tbody class="font-mono tabular-nums">
          <tr v-for="(difference, index) in differences" :key="index" class="border-t border-gray-100">
            <td class="px-3 py-1.5">{{ difference.coefficient ?? difference.field }}</td>
            <td class="px-3 py-1.5 text-right">{{ difference.github ?? difference.current }}</td>
            <td class="px-3 py-1.5 text-right">{{ difference.expected }}</td>
            <td v-if="check !== 'positions'" class="px-3 py-1.5 text-right">{{ difference.difference }}</td>
            <!-- A constant carries no vendor value, so it is not a disagreement
                 with the vendor at all. -->
            <td v-if="check !== 'positions'" class="px-3 py-1.5">{{ difference.source }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="row.sourceRow" class="text-gray-600">
      Position taken from row {{ row.sourceRow }} of the RCA position spreadsheet.
    </div>

    <div v-if="notes">
      <div class="font-semibold mb-1 text-[11px] text-gray-500 tracking-wider uppercase">Reviewer notes</div>
      <p class="text-gray-700">{{ notes }}</p>
    </div>

    <div v-if="!links.length && !differences.length && !notes && !row.sourceRow" class="text-gray-500">
      Nothing further recorded for this row.
    </div>

    <sign-off v-if="sheet" :sheet="sheet" :row="row" />
  </div>
</template>
