<script setup lang="ts">
import { FORKS, useAuth } from '~/auth'
import { sheetKey, useBatch } from '~/batch'
import { ASSET_FIELD, deploymentPath } from '~/deployfile'
import { assetNamedByRawSerial } from '~/display'
import { type Row } from '~/store'

/**
 * Correcting which instrument a deployment says was in the water.
 *
 * A serial number read out of the raw archive that belongs to a different asset
 * is the commonest thing the deployments check finds, and until now the check
 * could say the sheet was wrong without offering any way to put it right. A
 * reviewer had to open the sheet on GitHub and find the row by hand.
 *
 * It writes the same file and the same row a position correction does, and
 * joins the same batch for that reason. What it claims is different, so it is
 * its own entry with its own section of the pull request.
 *
 * Only the raw serial number is offered as a value to take. The pre-deploy
 * photograph names an asset too, and is deliberately not offered: a photograph
 * of an instrument is not evidence of which instrument went in the water, which
 * is why it does not confirm a deployment either. Anything the run cannot
 * settle is typed, by somebody who knows what happened on the ship.
 */
const { row } = defineProps<{ row: Row }>()

const auth = useAuth()
const batch = useBatch()

const refDes = computed(() => String(row.refDes ?? ''))
const deployNum = computed(() => row.deployNum as string | number)
/** What the sheet says now, which is what the correction has to still find. */
const held = computed(() => String(row.AssetID ?? ''))

const id = computed(() => sheetKey('asset', refDes.value, deployNum.value))
const queuedAlready = computed(() => batch.entryFor('sheets', id.value))

/** The asset the serial in this deployment's raw file actually belongs to,
 *  where the run could place it. */
const fromRaw = computed(() => {
  const named = assetNamedByRawSerial(String(row.rawFile_verify ?? ''))
  return named && named !== held.value ? named : ''
})

const typed = ref('')
const wanted = computed(() => typed.value.trim())
const changed = computed(() => Boolean(wanted.value) && wanted.value !== held.value)

function take() {
  typed.value = fromRaw.value
}

function add() {
  batch.queueAsset(
    refDes.value, deployNum.value, held.value, wanted.value,
    wanted.value === fromRaw.value
      ? `The serial number in this deployment's raw file is \`${row.rawSN}\`, `
        + 'which belongs to this asset.'
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
  <div class="border-gray-200 border-t pt-3">
    <h4 class="font-semibold text-[11px] text-gray-500 tracking-wider uppercase">
      The instrument on the sheet
    </h4>

    <fork-guard fork="assetManagement" action="change which asset this deployment names" class="mt-2">
      <div class="flex flex-wrap gap-x-6 gap-y-2 items-end mt-2">
        <div>
          <div class="text-[11px] text-gray-500">On the sheet</div>
          <div class="font-mono text-sm">{{ held || '—' }}</div>
        </div>

        <div v-if="fromRaw">
          <div class="text-[11px] text-gray-500">The raw serial belongs to</div>
          <button
            class="font-mono text-primary-700 text-sm hover:underline"
            type="button"
            :title="`Use ${fromRaw}`"
            @click="take"
          >{{ fromRaw }}</button>
        </div>

        <div>
          <div class="text-[11px] text-gray-500">Correct to</div>
          <input
            v-model="typed"
            class="fld"
            :placeholder="held"
            aria-label="New asset ID for this deployment"
          >
        </div>
      </div>

      <div class="flex flex-wrap gap-2 items-center mt-2.5">
        <u-button size="sm" color="primary" :disabled="!changed" @click="add">
          {{ queuedAlready ? 'Replace in batch' : 'Add to batch' }}
        </u-button>
        <a
          v-if="editUrl"
          :href="editUrl"
          target="_blank"
          rel="noopener"
          class="text-[12.5px] text-primary-700 hover:underline"
        >Edit the whole sheet on GitHub</a>
      </div>

      <p class="mt-1.5 text-gray-500 text-[12.5px]">
        Rewrites <span class="font-mono">{{ ASSET_FIELD }}</span> on this one row of
        <span class="font-mono">{{ deploymentPath(refDes) }}</span>, and joins the deployment sheet
        batch. Every product computed for this deployment follows the asset, so nothing changes
        until you raise that request upstream.
      </p>

      <u-alert v-if="queuedAlready" class="mt-2" color="success" variant="subtle" title="Queued.">
        <template #description>
          Waiting with the other deployment sheet corrections.
          <nuxt-link to="/queue" class="underline">Open the queue</nuxt-link> to propose them.
        </template>
      </u-alert>
    </fork-guard>
  </div>
</template>

<style scoped>
.fld {
  border: 1px solid #cdd8e1;
  border-radius: 5px;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  padding: 2px 6px;
  min-width: 20ch;
}
.fld:focus { border-color: #2b6cb0; outline: none }
</style>
