<script setup lang="ts">
import { correctableFields } from '~/deployfile'
import { VERDICTS } from '~/display'
import { hitlKeyOf, HITL_SHEETS, type SheetKey } from '~/signoff'
import { useStore, type Row } from '~/store'

const { check, row } = defineProps<{ check: string; row: Row }>()
const store = useStore()

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
 *  the table of what disagrees. */
const settled = computed(() => row.severity === 'ok' || row.severity === 'cleared')

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

        <!-- The numbers that disagree, and the correction of them on the same
             line. A read-only table beside an editable copy showed every
             number twice, and invited reading one pair while typing at the
             other. -->
        <difference-table :check="check" :row="row" />

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
        <dl v-if="links.length || hitlKey || row.sourceRow || row.rawFilesTried" class="kv">
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
          <!-- What the extraction actually read. A row holding no serial says
               which files were tried rather than sending a reviewer to the
               parameter file to find out. -->
          <template v-if="row.rawFilesTried">
            <dt>Raw files read</dt>
            <dd>
              <span class="break-all">{{ String(row.rawFilesTried).split(' ').join(', ') }}</span>
              <span v-if="row.rawAttemptedAt" class="text-gray-500">
                · {{ row.rawAttemptedAt }}
              </span>
            </dd>
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
    <!-- Correcting the record comes before signing off on it: a serial number
         that belongs to another asset is a sheet to fix, not a judgement to
         write down. -->
    <asset-correction v-if="check === 'deployments'" :row="row" class="mt-4" />
    <!-- One per column the row's findings are about: a deployment can be an
         asset in the water twice *and* one nobody closed out, and each is a
         different cell of the sheet. -->
    <sheet-correction
      v-for="each in check === 'deploymentSheets' ? correctableFields(row) : []"
      :key="each.field"
      :row="row"
      :field="each.field"
      :held="each.held"
      class="mt-4"
    />
    <sign-off v-if="sheet" :sheet="sheet" :row="row" class="mt-4" />
  </div>
</template>
