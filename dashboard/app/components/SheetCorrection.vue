<script setup lang="ts">
import { FORKS, useAuth } from '~/auth'
import { sheetKey, useBatch } from '~/batch'
import { deploymentPath, kindOfField, STOP_FIELD, VERDICT_FIELD, verdictOf } from '~/deployfile'
import { type Row } from '~/store'

/**
 * Correcting the deployment sheet from a sheet-integrity finding.
 *
 * The deployments check has offered this since it could name the asset a raw
 * serial belongs to. This check could not: it would say a cruise was not in the
 * cruise list, or that a deployment had never been given an end date, and leave
 * the reviewer to open the sheet on GitHub and find the row by hand.
 *
 * Most of these findings come down to one column of one row, so one editor
 * serves all of them: the column comes from the verdict, the row from the
 * finding, and the correction joins the same batch and writes the same file a
 * position or asset correction does.
 *
 * Two findings are deliberately not offered. An asset in the wrong bulk record
 * is real and filed under a different record, so the fix usually belongs to
 * that record rather than to this sheet. A node in two places is named on a row
 * per instrument hanging off it, and correcting one row would leave the rest
 * saying the box is still there.
 */
const { row } = defineProps<{ row: Row }>()

const auth = useAuth()
const batch = useBatch()

const refDes = computed(() => String(row.refDes ?? ''))
const deployNum = computed(() => row.deployNum as string | number)
const verdict = computed(() => verdictOf(row.verdict))
const field = computed(() => VERDICT_FIELD[verdict.value] ?? '')

/** What the sheet says now, which is what the correction has to still find.
 *  A missing end date is a column holding nothing, not a column holding the
 *  value the finding is about — that is the asset, and it is not being changed. */
const held = computed(() => (field.value === STOP_FIELD ? '' : String(row.value ?? '')))

const id = computed(() => sheetKey(kindOfField(field.value), refDes.value, deployNum.value))
/** What this correction would replace, if the reviewer already queued one. */
const queuedAlready = computed(() => {
  const entry = batch.entryFor('sheets', id.value)
  return entry && entry.batch === 'sheets' ? entry : null
})

/** The start of the deployment that followed, carried as a field by the run.
 *  A slot cannot be occupied twice, so the one that ended is the one that ends
 *  no later than this — which makes it the obvious value and still a reviewer's
 *  decision, because the true recovery was some hours or days before it. */
const follows = computed(() =>
  (field.value === STOP_FIELD && typeof row.endsBefore === 'string' ? row.endsBefore : ''))

const typed = ref('')
const wanted = computed(() => typed.value.trim())
const changed = computed(() => Boolean(wanted.value) && wanted.value !== held.value)

const LABEL: Record<string, string> = {
  'sensor.uid': 'The instrument on the sheet',
  'mooring.uid': 'The mooring on the sheet',
  'node.uid': 'The node on the sheet',
  'electrical.uid': 'The electrical asset on the sheet',
  CUID_Deploy: 'The deploying cruise',
  stopDateTime: 'When this deployment ended',
}

function take() {
  typed.value = follows.value
}

function add() {
  batch.queueField(
    refDes.value, deployNum.value, field.value, held.value, wanted.value,
    wanted.value === follows.value
      ? 'The next deployment of this reference designator starts here, so this one '
        + 'had ended by then.'
      : 'Entered by hand from the deployment record.',
  )
}

const editUrl = computed(() => {
  const fork = auth.forkFor('assetManagement')
  const base = FORKS.find((each) => each.key === 'assetManagement')!.base
  return fork ? `https://github.com/${fork}/edit/${base}/${deploymentPath(refDes.value)}` : ''
})
</script>

<template>
  <div v-if="field" class="border-gray-200 border-t pt-3">
    <h4 class="font-semibold text-[11px] text-gray-500 tracking-wider uppercase">
      {{ LABEL[field] ?? field }}
    </h4>

    <fork-guard fork="assetManagement" :action="`correct ${field} on this deployment`" class="mt-2">
      <div class="flex flex-wrap gap-x-6 gap-y-2 items-end mt-2">
        <div>
          <div class="text-[11px] text-gray-500">On the sheet</div>
          <div class="font-mono text-sm">{{ held || '— nothing' }}</div>
        </div>

        <div v-if="follows">
          <div class="text-[11px] text-gray-500">The next deployment starts</div>
          <button
            class="font-mono text-primary-700 text-sm hover:underline"
            type="button"
            :title="`Use ${follows}`"
            @click="take"
          >{{ follows }}</button>
        </div>

        <div>
          <div class="text-[11px] text-gray-500">Correct to</div>
          <input
            v-model="typed"
            class="fld"
            :placeholder="held || field"
            :aria-label="`New ${field} for this deployment`"
          >
        </div>
      </div>

      <div class="flex flex-wrap gap-2 items-center mt-2.5">
        <u-button size="sm" color="primary" :disabled="!changed" @click="add">
          {{ queuedAlready ? 'Replace queued correction' : 'Add to batch' }}
        </u-button>
        <span v-if="queuedAlready" class="text-[12px] text-gray-500">
          Queued: {{ queuedAlready.corrections[0]?.to }}
        </span>
        <a
          v-if="editUrl"
          :href="editUrl"
          target="_blank"
          rel="noopener"
          class="text-[12px] text-gray-500 hover:underline"
        >Open the sheet on GitHub</a>
      </div>
    </fork-guard>
  </div>
</template>

<style scoped>
.fld {
  border: 1px solid #cdd8e1;
  border-radius: 5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
  padding: 3px 7px;
}
.fld:focus { border-color: #2b6cb0; outline: none }
</style>
