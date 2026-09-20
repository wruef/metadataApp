<script setup lang="ts">
import { useAuth } from '~/auth'
import { REFDES_FILE, useDeployHistory } from '~/deployhistory'
import { describeProposal } from '~/github'
import { useStore } from '~/store'

/**
 * The published deployment history, and the one button that proposes it.
 *
 * Not a check. Every other view answers "what is wrong"; this one answers "what
 * was where, and when", and its output is a product the deployments repository
 * holds rather than a queue anybody works.
 */
const auth = useAuth()
const store = useStore()
const history = useDeployHistory()

onMounted(() => history.load())
/** Reading a different run means a different history, so it follows the picker. */
watch(() => store.selected, () => history.load())

const expanded = ref('')
const preview = (text: string) => text.split('\n').slice(0, 6).join('\n')

const builtAt = computed(() =>
  history.bundle ? new Date(history.bundle.runAt).toLocaleString() : '')
const types = computed(() => history.files.filter((file) => file.name !== REFDES_FILE).length)
</script>

<template>
  <div class="max-w-5xl space-y-6">
    <div>
      <h1 class="font-semibold text-2xl">Deployment history</h1>
      <p class="max-w-prose mt-1 text-gray-600">
        One file per instrument type saying what was where and when, with the calibration that was
        in force for each deployment. The run builds it; this proposes it to your own fork of the
        deployments repository.
      </p>
    </div>

    <p v-if="history.status === 'loading'" class="text-gray-600">Loading what the run built…</p>

    <u-alert
      v-else-if="history.status === 'error'"
      color="neutral"
      variant="subtle"
      title="This run published no deployment history"
      :description="history.error"
    />

    <template v-else-if="history.bundle">
      <div class="bg-white border border-gray-200 gap-x-10 gap-y-3 grid px-5 py-4 rounded-lg sm:grid-cols-3">
        <div>
          <div class="text-[11px] font-semibold text-gray-500 tracking-wider uppercase">Built by the run of</div>
          <div>{{ builtAt }}</div>
        </div>
        <div>
          <div class="text-[11px] font-semibold text-gray-500 tracking-wider uppercase">Deployments</div>
          <div>{{ history.deployments }}</div>
        </div>
        <div>
          <div class="text-[11px] font-semibold text-gray-500 tracking-wider uppercase">Instrument types</div>
          <div>{{ types }}</div>
        </div>
      </div>

      <!-- The same rule as an asset-management correction, for the same
           reason: a fork that is not exactly upstream is a fork this dashboard
           has never read. -->
      <fork-guard fork="deployments" action="propose this history">
        <div class="flex flex-wrap gap-2.5 items-center">
          <u-button
            size="sm"
            color="primary"
            :loading="history.submitting"
            @click="history.propose()"
          >
            Propose this history
          </u-button>
          <span class="text-gray-500 text-sm">
            One pull request to <b>{{ auth.forkFor('deployments') }}</b> carrying all
            {{ history.files.length }} files. Raise the pull request upstream by hand.
          </span>
        </div>
      </fork-guard>

      <u-alert
        v-if="history.result"
        :color="describeProposal(history.result).tone"
        variant="subtle"
        :title="describeProposal(history.result).text"
      >
        <template v-if="history.result.url" #description>
          <a :href="history.result.url" target="_blank" rel="noopener" class="underline">
            Review it on GitHub
          </a>
        </template>
      </u-alert>

      <section class="space-y-2">
        <h2 class="font-semibold text-lg">What would be committed</h2>
        <p class="max-w-prose text-gray-600 text-[13px]">
          Exactly these files, exactly as the run wrote them. Anything else the repository holds,
          such as the node deployments, is left untouched.
        </p>
        <div class="border border-gray-200 overflow-hidden rounded-lg">
          <div
            v-for="file in history.files"
            :key="file.name"
            class="bg-white border-b border-gray-100 last:border-b-0"
          >
            <button
              class="flex gap-3 items-baseline px-4 py-2.5 text-left w-full hover:bg-gray-50"
              type="button"
              @click="expanded = expanded === file.name ? '' : file.name"
            >
              <span class="font-mono grow text-sm">{{ file.name }}</span>
              <span class="text-gray-500 text-sm">{{ file.rows }} rows</span>
            </button>
            <pre
              v-if="expanded === file.name"
              class="bg-gray-50 border-gray-100 border-t overflow-x-auto px-4 py-3 text-[11.5px]"
            >{{ preview(file.text) }}</pre>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
