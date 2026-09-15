<script setup lang="ts">
import { SEVERITIES, SEVERITY_LABEL, useStore } from '~/store'

const store = useStore()
const summaryOf = (key: string) => store.report?.checks?.[key]?.summary
</script>

<template>
  <div class="max-w-6xl space-y-6">
    <div>
      <h1 class="font-semibold text-2xl">Metadata verification</h1>
      <p class="max-w-prose mt-1 text-gray-600">
        Every deployed sensor correctly assigned, and every calibration file matching the vendor
        original. Work the queue by consequence: problems first, then what needs a person.
      </p>
    </div>

    <run-stamp />

    <div class="gap-4 grid sm:grid-cols-2 xl:grid-cols-3">
      <nuxt-link
        v-for="check in store.checks"
        :key="check.key"
        :to="`/checks/${check.key}`"
        class="bg-white border border-gray-200 block p-5 rounded-lg hover:border-primary-400"
      >
        <div class="flex gap-3 items-center">
          <i :class="['fas', check.icon, 'text-primary-600']" />
          <h2 class="font-semibold">{{ check.title }}</h2>
          <span class="ml-auto text-gray-400 text-sm">{{ summaryOf(check.key)?.total }} rows</span>
        </div>
        <p class="mt-2 text-gray-600 text-sm">{{ check.blurb }}</p>

        <div class="flex gap-4 mt-4">
          <div v-for="severity in SEVERITIES" :key="severity">
            <div
              class="font-semibold tabular-nums text-xl"
              :class="{
                'text-red-600': severity === 'problem' && summaryOf(check.key)?.[severity],
                'text-amber-600': severity === 'review' && summaryOf(check.key)?.[severity],
                'text-gray-400': !summaryOf(check.key)?.[severity],
              }"
            >
              {{ summaryOf(check.key)?.[severity] }}
            </div>
            <div class="text-[11px] text-gray-500 uppercase tracking-wide">
              {{ SEVERITY_LABEL[severity] }}
            </div>
          </div>
        </div>

        <div v-if="summaryOf(check.key)?.cleared" class="mt-3 text-gray-500 text-sm">
          {{ summaryOf(check.key)?.cleared }} signed off by a reviewer
        </div>
      </nuxt-link>
    </div>
  </div>
</template>
