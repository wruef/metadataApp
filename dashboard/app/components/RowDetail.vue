<script setup lang="ts">
import { readDifference, VERDICTS } from '~/display'
import { hitlKeyOf, HITL_SHEETS, type SheetKey } from '~/signoff'
import { useStore, type Row } from '~/store'

const { check, row } = defineProps<{ check: string; row: Row }>()
const store = useStore()

/** The coefficients or fields that actually disagree — the reason the row is in
 *  the queue, and what the old reports made you open a CSV to find. */
const differences = computed(() => (Array.isArray(row.differences) ? row.differences : []))

/**
 * What the check returned, verbatim.
 *
 * These are the fields the severity is taken from, so the list is the run's own
 * working shown beneath the sentence it produced — the raw verdicts a person
 * needs on the occasions the sentence is not enough.
 */
const rawOutput = computed(() =>
  [...Object.keys(VERDICTS[check] ?? {}), 'HITLstatus']
    .filter((field) => row[field] !== undefined && row[field] !== null && row[field] !== '')
    .map((field) => ({ field, value: String(row[field]) })),
)

const links = computed(() => {
  const found: { label: string; href: string }[] = []
  const add = (label: string, href: string | null) => href && found.push({ label, href })

  if (check === 'calibrations') {
    add(
      'asset-management',
      store.fileUrl('assetManagement', `calibration/${row.instrument}/${row.fileName}`),
    )
    // The two repos do not always name a sensor directory the same way, so the
    // vendor path is carried in the report rather than derived.
    for (const name of (row.vendorFiles as string[] | undefined) ?? []) {
      add(`Vendor file · ${name.split('.').slice(1).join('.')}`,
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

/** A sign-off settles a row as surely as the checks agreeing does. What the
 *  checks found stays on the row either way — under Raw check output, and in
 *  the differences table above it. */
const settled = computed(() => row.severity === 'ok' || row.severity === 'cleared')

/**
 * One note, where the file says the same thing about every coefficient.
 *
 * Collapsed only when *every* difference carries a note and they are all the
 * same. With some coefficients noted and some not, showing it once would
 * attribute it to coefficients the file says nothing about.
 *
 * It fires on no file today, so it is a guard rather than a change to what you
 * see. Of the rows that disagree at all, 80 disagree about exactly one
 * coefficient; one about two, whose notes differ; one about six, none of which
 * are noted. The repeated pressure-offset note repeats across *files*, one
 * difference each, not down a single table.
 */
const sharedNote = computed(() => {
  const notes = differences.value.map((entry) => String(entry.note ?? '').trim())
  if (notes.length < 2 || notes.some((note) => !note)) return ''
  return notes.every((note) => note === notes[0]) ? notes[0]! : ''
})

/** Only two checks are signed off; the rest have no sheet to record it in. */
const sheet = computed(() => (check in HITL_SHEETS ? (check as SheetKey) : null))
/** What a sign-off keys on — the line it writes into the 2i-HITL sheet. */
const hitlKey = computed(() => (sheet.value ? hitlKeyOf(sheet.value, row) : ''))

/** Reading a mismatch means reading both files. A text vendor file is compared
 *  and its differences marked; a pdf is put on screen for a person to read,
 *  which for a scan is the only honest way to check it. */
const comparable = computed(
  () => check === 'calibrations' && ((row.vendorFiles as string[] | undefined) ?? []).length > 0,
)
const comparing = ref(false)
</script>

<template>
  <div>
    <div class="det">
      <div>
        <!-- The sentence the run produced, ahead of any of its working. -->
        <h4>Why this row is {{ settled ? 'settled' : 'open' }}</h4>
        <p class="max-w-prose text-[13px] leading-relaxed">{{ row.reason }}.</p>

        <template v-if="differences.length">
          <h4>
            {{ check === 'positions' ? 'Fields that differ from the spreadsheet'
              : 'Coefficients that differ from the vendor file' }}
          </h4>
          <div class="coefwrap">
            <table class="coef">
              <thead>
                <tr>
                  <th>{{ check === 'positions' ? 'Field' : 'Coefficient' }}</th>
                  <th class="text-right">asset-management</th>
                  <th class="text-right">{{ check === 'positions' ? 'Spreadsheet' : 'Vendor' }}</th>
                  <th v-if="check !== 'positions'" class="text-right">Difference</th>
                  <!-- A constant carries no vendor value, so it is not a
                       disagreement with the vendor at all. -->
                  <th v-if="check !== 'positions'">Source</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="(entry, index) in differences" :key="index">
                  <tr>
                    <td>{{ entry.coefficient ?? entry.field }}</td>
                    <!-- What each file records, exactly as it was read. -->
                    <td class="num text-right">{{ entry.github ?? entry.current }}</td>
                    <td class="num text-right">{{ entry.expected ?? '—' }}</td>
                    <td v-if="check !== 'positions'" class="d num text-right">
                      {{ readDifference(entry.difference) }}
                    </td>
                    <td v-if="check !== 'positions'">{{ entry.source }}</td>
                  </tr>
                  <!-- What the asset-management file says about this coefficient:
                       where the value came from, which vendor file it was read
                       out of, that it is a constant. On a coefficient that
                       disagrees it is the context a reviewer would otherwise
                       open the file for. Its own line, because a note runs to a
                       sentence and a column would push the numbers off. -->
                  <tr v-if="entry.note && !sharedNote" class="note">
                    <td :colspan="check === 'positions' ? 3 : 5">
                      <span class="from">asset-management note</span>{{ entry.note }}
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
          <p v-if="sharedNote" class="coefnote">
            <span class="from">asset-management note</span>{{ sharedNote }}
          </p>
        </template>

        <template v-if="rawOutput.length">
          <h4>Raw check output</h4>
          <dl class="kv">
            <template v-for="entry in rawOutput" :key="entry.field">
              <dt>{{ entry.field }}</dt>
              <dd>{{ entry.value }}</dd>
            </template>
          </dl>
        </template>

        <template v-if="notes">
          <h4>Reviewer notes</h4>
          <p class="max-w-prose text-[12.5px] text-gray-700 leading-relaxed">{{ notes }}</p>
        </template>
      </div>

      <div>
        <h4>Sources</h4>
        <dl v-if="links.length || hitlKey || row.sourceRow" class="kv">
          <template v-for="link in links" :key="link.href">
            <dt>{{ link.label }}</dt>
            <dd>
              <a
                :href="link.href"
                target="_blank"
                rel="noopener"
                class="text-primary-700 hover:underline"
              >{{ link.href.split('/').pop() }}</a>
            </dd>
          </template>
          <template v-if="row.sourceRow">
            <dt>Spreadsheet row</dt>
            <dd>{{ row.sourceRow }}</dd>
          </template>
          <template v-if="hitlKey">
            <dt>2i-HITL key</dt>
            <dd>{{ hitlKey }}</dd>
          </template>
        </dl>
        <p v-else class="text-[12.5px] text-gray-500">Nothing further recorded for this row.</p>

        <div v-if="comparable" class="mt-3.5">
          <u-button size="sm" icon="i-lucide-columns-2" @click="comparing = true">
            View files side by side
          </u-button>
        </div>
      </div>
    </div>

    <side-by-side v-if="comparing" :row="row" @close="comparing = false" />
    <sign-off v-if="sheet" :sheet="sheet" :row="row" class="mt-4" />
    <!-- Below the sign-off deliberately. Recording a judgement is the common
         case and the safe one; changing the file is neither. -->
    <correct-file v-if="check === 'calibrations'" :row="row" />
    <correct-position v-if="check === 'positions'" :row="row" />
  </div>
</template>
