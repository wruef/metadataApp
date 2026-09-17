<script setup lang="ts">
import { useAuth } from '~/auth'
import { canPublish, PRODUCTION, ready } from '~/dispatch'
import { useRuns } from '~/runs'
import { useStore } from '~/store'

const auth = useAuth()
const runs = useRuns()
const store = useStore()

const testing = computed(() => runs.source.mode === 'testing')

/** What the report on screen was actually run against, which is not what the
 *  bar is pointing at until a new run has been published. */
const shown = computed(() => {
  const source = store.report?.sources?.assetManagement
  return source && typeof source === 'object' ? `${source.repo}@${source.ref}` : null
})
</script>

<template>
  <div>
    <div class="srcbar" :class="{ testing }">
      <span class="lbl">Verifying</span>
      <div class="seg">
        <button
          :aria-pressed="!testing"
          @click="runs.source.mode = 'production'"
        >
          Production
        </button>
        <button :aria-pressed="testing" @click="runs.source.mode = 'testing'">Testing</button>
      </div>

      <template v-if="testing">
        <input
          v-model="runs.source.repo"
          aria-label="Asset management repository"
          placeholder="owner/asset-management"
          size="28"
        >
        <input
          v-model="runs.source.ref"
          aria-label="Asset management ref"
          placeholder="branch, tag or sha"
          size="18"
        >
        <input
          v-model="runs.source.calRef"
          aria-label="Calibration files ref"
          :placeholder="`calibrationFiles @ ${PRODUCTION.calRef}`"
          size="20"
        >
        <span class="lbl">Compare with</span>
        <select v-model="runs.source.baseline" aria-label="Comparison baseline">
          <option value="">No comparison</option>
          <option :value="PRODUCTION.ref">Production · {{ PRODUCTION.ref }}</option>
        </select>
      </template>
      <template v-else>
        <span class="src">{{ PRODUCTION.repo }}<b>@{{ PRODUCTION.ref }}</b></span>
        <span class="src">OOI-CabledArray/calibrationFiles<b>@{{ PRODUCTION.calRef }}</b></span>
      </template>

      <span class="grow" />

      <label
        v-if="canPublish(runs.source)"
        class="flex gap-1.5 items-center"
        title="Commits the report to this repository, which republishes the dashboard with it. Leave off for a look that changes nothing."
      >
        <input v-model="runs.source.publish" type="checkbox" >
        Publish
      </label>
      <!-- A branch run answers a question about a branch. Publishing it would
           replace the figures everyone else reads, so it is not offered here
           and the workflow refuses it too. -->
      <span v-else class="lbl">Testing runs do not publish</span>

      <button
        v-if="auth.signedIn"
        class="go"
        :disabled="runs.busy || !ready(runs.source)"
        @click="runs.start()"
      >
        {{ runs.busy ? 'Running…' : 'Run all checks' }}
      </button>
      <nuxt-link v-else to="/settings" class="go">Sign in to run</nuxt-link>
    </div>

    <!-- Pointing the bar somewhere does not change a single number on screen.
         Saying so is the difference between a source selector and a lie. -->
    <div
      v-if="testing"
      class="bg-amber-50 border-b border-amber-200 px-6 py-2.5 text-[12.5px] text-amber-900 leading-relaxed"
    >
      <template v-if="ready(runs.source)">
        A run would verify <b>{{ runs.source.repo }}@{{ runs.source.ref }}</b
        ><template v-if="runs.source.baseline"> against <b>{{ runs.source.baseline }}</b></template
        >. Everything below is still the run
        <template v-if="shown">of <b>{{ shown }}</b></template> already loaded — start a run, publish
        it, and reload to see the difference.
      </template>
      <template v-else>
        Name a branch, tag or sha to verify. Until then a run would verify production, which the
        report below already shows.
      </template>
    </div>

    <run-progress />
  </div>
</template>
