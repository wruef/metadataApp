<script setup lang="ts">
import { useAuth } from '~/auth'
import { PRODUCTION, ready } from '~/dispatch'
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

      <!-- A branch run publishes under its own name and appears in the run
           picker; only a production run becomes the figures everyone reads. So
           this is safe to offer either way, and it is the only way to open a
           branch check in the dashboard rather than downloading a zip. -->
      <label
        class="flex gap-1.5 items-center"
        :title="testing
          ? 'Commits the run under its own name so you can open it from the run picker. Production figures are untouched.'
          : 'Commits the report and makes it the run everyone reads. Leave off for a look that changes nothing.'"
      >
        <input v-model="runs.source.publish" type="checkbox" >
        {{ testing ? 'Publish for review' : 'Publish' }}
      </label>

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
        it, and choose it in the dropdown below to view results.
      </template>
      <template v-else>
        Name a test branch to verify against. Once published, choose the run in the dropdown below
        to view results.
      </template>
    </div>

    <run-progress />
  </div>
</template>
