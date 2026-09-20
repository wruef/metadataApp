<script setup lang="ts">
import { WORKFLOW, type Step } from '~/dispatch'
import { useRuns } from '~/runs'
import { useStore } from '~/store'

/** A tray rather than a modal: a verification takes minutes, and there is no
 *  reason to stop reading the last run while the next one builds. */
const runs = useRuns()
const store = useStore()

function stepClass(step: Step) {
  if (step.status !== 'completed') return step.status === 'in_progress' ? 'run' : ''
  return step.conclusion === 'success' || step.conclusion === 'skipped' ? 'done' : 'bad'
}

const heading = computed(() => {
  if (runs.status === 'starting') return 'Starting the run…'
  if (runs.status === 'finding') return 'Waiting for GitHub to pick it up…'
  if (runs.status === 'running') return `Running ${runs.label}`
  if (runs.status === 'error') return 'It could not be started'
  return runs.run?.conclusion === 'success' ? 'Finished' : 'Failed'
})

const succeeded = computed(() => runs.status === 'done' && runs.run?.conclusion === 'success')
</script>

<template>
  <div
    v-if="runs.open"
    class="bg-white border border-gray-200 bottom-5 fixed max-w-[calc(100vw-2.5rem)] right-5 rounded-xl shadow-2xl w-[26rem] z-50 overflow-hidden"
  >
    <header class="bg-primary-900 flex gap-2.5 items-center px-3.5 py-2.5 text-white">
      <i
        class="fas text-xs"
        :class="runs.busy ? 'fa-spinner fa-spin' : succeeded ? 'fa-circle-check' : 'fa-circle-exclamation'"
      />
      <b class="font-semibold grow text-[12.5px]">{{ heading }}</b>
      <a
        v-if="runs.run"
        :href="runs.run.html_url"
        target="_blank"
        rel="noopener"
        class="text-[11px] text-[#a9d4ea] hover:underline"
      >
        On GitHub
      </a>
      <!-- Closing stops following the run. It does not stop the run. -->
      <button class="leading-none px-1 text-[#bcd6e6] text-lg" title="Stop following this run" @click="runs.stopWatching(); runs.open = false">
        ×
      </button>
    </header>

    <div v-if="runs.error" class="px-4 py-3 text-[12.5px] text-red-700 leading-relaxed">
      {{ runs.error }}
    </div>

    <div v-else-if="runs.steps.length" class="max-h-72 overflow-y-auto px-4">
      <div v-for="(step, index) in runs.steps" :key="index" class="step" :class="stepClass(step)">
        <span class="dot" />
        <span class="grow text-[12.5px]">{{ step.name }}</span>
      </div>
    </div>

    <div v-else class="px-4 py-3 text-[12.5px] text-gray-500">
      The workflow has been asked to run. Steps appear once GitHub has assigned it a machine.
    </div>

    <!-- The report on screen does not change when a run finishes: it is a file,
         and it is only replaced if the run was told to publish. -->
    <footer v-if="runs.status === 'done'" class="bg-gray-50 border-gray-200 border-t flex gap-2.5 items-center px-4 py-2.5">
      <u-button v-if="succeeded && runs.workflow === WORKFLOW" size="xs" @click="store.load()">
        Reload the report
      </u-button>
      <span class="text-[11.5px] text-gray-500 leading-snug">
        <template v-if="succeeded && runs.workflow === WORKFLOW">
          Only changes anything here if the run published.
        </template>
        <template v-else-if="succeeded">Read what it did on GitHub.</template>
        <template v-else>Open it on GitHub to read which step failed.</template>
      </span>
    </footer>
  </div>
</template>
