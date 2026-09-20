<script setup lang="ts">
import { useAuth } from '~/auth'
import {
  EXTRACT_WORKFLOW,
  PRUNE_WORKFLOW,
  extractInputs,
  newExtraction,
  newPrune,
  pruneInputs,
} from '~/dispatch'
import { useRuns } from '~/runs'
import { useStore } from '~/store'

/**
 * The two workflows that maintain the inputs rather than produce a report.
 *
 * Both were run from the Actions tab, which meant leaving the one screen that
 * says whether they are worth running: the count of deployments an extraction
 * would settle, and the number of runs cluttering the picker. They are here
 * with those counts beside them, and they are followed in the same tray a
 * verification run is.
 */
const auth = useAuth()
const runs = useRuns()
const store = useStore()

const extraction = reactive(newExtraction())
const prune = reactive(newPrune())

/** Why an extraction is worth running: the deployments whose instrument class
 *  writes a serial into its raw data and that have none on record yet. */
const settleable = computed(() =>
  (store.report?.checks?.deployments?.rows ?? [])
    .filter((row) => row.verificationStatus === 'RAW_SN_POSSIBLE').length)

const published = computed(() => store.runs.length)
/** What a prune would leave, so the number in the box means something. */
const wouldDelete = computed(() => Math.max(0, published.value - Math.max(1, prune.keep || 1)))

const repo = computed(() => auth.workflowRepo)
</script>

<template>
  <div class="max-w-3xl space-y-6">
    <div>
      <h1 class="font-semibold text-2xl">Workflows</h1>
      <p class="max-w-prose mt-1 text-gray-600">
        Two jobs that keep a review's inputs current. Neither produces a report: one reads serial
        numbers out of the raw archive and proposes them as a pull request, the other deletes
        published runs. Both run in
        <span class="font-mono">{{ repo || 'your fork of this repository' }}</span>, which is where
        your runs go.
      </p>
    </div>

    <div v-if="!auth.canSignOff" class="text-gray-600">
      <nuxt-link to="/settings" class="text-primary-700 underline">Sign in with your initials</nuxt-link>
      to start a workflow. The token needs <b>Actions</b> set to read and write on that repository.
    </div>

    <template v-else>
      <!-- Serial numbers out of the raw archive. -->
      <section class="bg-white border border-gray-200 p-5 rounded-lg space-y-3">
        <div>
          <h2 class="font-semibold text-lg">Extract serial numbers</h2>
          <p class="max-w-prose mt-1 text-gray-600 text-sm">
            Reads the raw data archive for every deployment whose instrument class writes a serial
            number into its own data and has none on record yet. It proposes
            <span class="font-mono">params/rawFileSN.csv</span> as a pull request for you to read
            and merge; the next verification run reads it.
          </p>
        </div>

        <p class="text-sm" :class="settleable ? 'text-gray-700' : 'text-gray-500'">
          <template v-if="settleable">
            <b>{{ settleable }}</b> deployment{{ settleable === 1 ? '' : 's' }} in this run would be
            settled by one.
          </template>
          <template v-else>
            Nothing in this run is waiting on one. Worth running after a cruise, once the season's
            deployment sheets are merged.
          </template>
        </p>

        <div class="flex flex-wrap gap-x-6 gap-y-3 items-end">
          <div>
            <label for="refdes" class="block text-[11px] text-gray-500">
              Only these reference designators (optional, space separated)
            </label>
            <input
              id="refdes"
              v-model="extraction.refdes"
              class="fld mt-1 w-[26rem]"
              placeholder="leave empty to attempt every deployment without a serial"
            >
          </div>
          <label class="flex gap-2 items-center text-sm">
            <input v-model="extraction.everything" type="checkbox" >
            Re-read everything
          </label>
        </div>
        <p v-if="extraction.everything" class="text-amber-700 text-[12.5px]">
          Every deployment, including the ones already settled. Hours rather than minutes, and only
          worth it after the extractor itself changes.
        </p>

        <u-button
          :disabled="runs.busy"
          @click="runs.dispatch(EXTRACT_WORKFLOW, extractInputs(extraction), 'the serial number extraction')"
        >
          Run the extraction
        </u-button>
      </section>

      <!-- Runs that are no longer worth keeping. -->
      <section class="bg-white border border-gray-200 p-5 rounded-lg space-y-3">
        <div>
          <h2 class="font-semibold text-lg">Delete published runs</h2>
          <p class="max-w-prose mt-1 text-gray-600 text-sm">
            Every published run stays in the <b>Run</b> dropdown until somebody removes it, and an
            afternoon of test runs buries the ones worth reading. A deleted run is still in the
            repository's history; it just leaves the dropdown.
          </p>
        </div>

        <p class="text-gray-700 text-sm">
          <b>{{ published }}</b> run{{ published === 1 ? '' : 's' }} published.
          <template v-if="wouldDelete">
            Keeping {{ Math.max(1, prune.keep || 1) }} would delete <b>{{ wouldDelete }}</b>.
          </template>
          <template v-else>Keeping that many deletes nothing.</template>
        </p>

        <div class="flex flex-wrap gap-x-6 gap-y-3 items-end">
          <div>
            <label for="keep" class="block text-[11px] text-gray-500">Keep the newest</label>
            <input id="keep" v-model.number="prune.keep" type="number" min="1" class="fld mt-1 w-24" >
          </div>
          <label class="flex gap-2 items-center text-sm">
            <input v-model="prune.dryRun" type="checkbox" >
            Say what would go and change nothing
          </label>
        </div>
        <p v-if="!prune.dryRun" class="text-amber-700 text-[12.5px]">
          This one deletes. The run the dashboard opens on is never deleted, whatever the rule
          reaches.
        </p>

        <u-button
          :color="prune.dryRun ? 'primary' : 'error'"
          :disabled="runs.busy"
          @click="runs.dispatch(PRUNE_WORKFLOW, pruneInputs(prune), 'the run deletion')"
        >
          {{ prune.dryRun ? 'Show what would go' : `Delete ${wouldDelete} run${wouldDelete === 1 ? '' : 's'}` }}
        </u-button>
      </section>

      <p class="text-gray-500 text-sm">
        Each is followed in the tray at the bottom right. Closing the tray stops following it; it
        does not stop the job.
      </p>
    </template>
  </div>
</template>

<style scoped>
.fld {
  border: 1px solid #cdd8e1;
  border-radius: 5px;
  font-size: 13px;
  padding: 3px 7px;
}
.fld:focus { border-color: #2b6cb0; outline: none }
</style>
