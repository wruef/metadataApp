<script setup lang="ts">
import { useStore } from '~/store'

const store = useStore()
const report = computed(() => store.report)

/** A ref names what was asked for; the commit is the state it resolved to, and
 *  only that makes two runs comparable. */
const sources = computed(() =>
  Object.entries(report.value?.sources ?? {})
    .filter(([, value]) => value && typeof value === 'object')
    .map(([name, value]) => {
      const source = value as { repo: string; ref: string; commit: string | null }
      return { name, repo: source.repo, ref: source.ref, commit: source.commit?.slice(0, 7) ?? null }
    }),
)

const runAt = computed(() => (report.value ? new Date(report.value.runAt).toLocaleString() : ''))
const days = computed(() => Math.round(store.ageInDays))

/** Earlier runs, so a baseline can be reached rather than only the newest
 *  report. Reports predating a fix to the checks are not comparable with later
 *  ones, which is why each carries its own provenance. */
const runOptions = computed(() => [
  { label: 'Current run', value: '' },
  ...store.runs.map((run) => ({
    label: `${new Date(run.runAt).toLocaleString()} · ${run.name.replace(/^report_|\.json$/g, '')}`,
    value: run.name,
  })),
])
</script>

<template>
  <!-- Every view carries the stamp, so nothing is read without knowing which
       run it came from. Renders nothing at all rather than a half-filled one. -->
  <div v-if="report" class="border border-gray-200 rounded-lg bg-white">
    <div class="flex flex-wrap gap-x-8 gap-y-3 items-baseline px-5 py-4">
      <div>
        <div class="text-[11px] font-semibold text-gray-500 tracking-wider uppercase">Run</div>
        <div v-if="store.runs.length < 2" class="font-medium">{{ runAt }}</div>
        <u-select
          v-else
          :model-value="store.selected ?? ''"
          :items="runOptions"
          class="min-w-64"
          @update:model-value="(name: string) => store.load(name || undefined)"
        />
      </div>
      <div v-for="source in sources" :key="source.name">
        <div class="text-[11px] font-semibold text-gray-500 tracking-wider uppercase">
          {{ source.repo.split('/')[1] }}
        </div>
        <div class="font-mono text-sm">
          {{ source.ref }}
          <span v-if="source.commit" class="text-gray-400">· {{ source.commit }}</span>
        </div>
      </div>
      <div>
        <div class="text-[11px] font-semibold text-gray-500 tracking-wider uppercase">Parameters</div>
        <div class="font-mono text-sm">
          {{ report.parameters.commit.slice(0, 7) }}
          <span v-if="report.parameters.dirty" class="text-amber-600">· uncommitted</span>
        </div>
      </div>
    </div>

    <!-- Runs are started by a person, so the newest report can be a year old and
         still look authoritative. Say so rather than letting it pass as current. -->
    <div
      v-if="store.isStale"
      class="border-t border-amber-200 bg-amber-50 flex gap-2 items-center px-5 py-2 text-amber-800 text-sm"
    >
      <i class="fa-triangle-exclamation fas" />
      This report is {{ days }} days old — from a previous season. Nothing refreshes on its own.
    </div>
  </div>
</template>
