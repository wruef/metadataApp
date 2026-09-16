<script setup lang="ts">
import { useAuth } from '~/auth'
import { HITL_SHEETS, useSignoff } from '~/signoff'
import { CHECKS } from '~/store'

const auth = useAuth()
const signoff = useSignoff()

const titleOf = (sheet: string) => CHECKS.find((check) => check.key === sheet)?.title ?? sheet
const fork = computed(() => auth.forkFor('hitl'))
</script>

<template>
  <div class="max-w-3xl space-y-6">
    <div>
      <h1 class="font-semibold text-2xl">Sign-offs</h1>
      <p class="max-w-prose mt-1 text-gray-600">
        Decisions accumulate here and go over as one pull request on your own fork. You raise the
        onward request to the shared repository by hand, so a batch is reviewed before it lands.
      </p>
    </div>

    <p v-if="!signoff.count" class="text-gray-600">
      Nothing queued. Open a row in any check and clear or flag it.
    </p>

    <template v-else>
      <div class="border border-gray-200 overflow-hidden rounded-lg">
        <div
          v-for="decision in signoff.queued"
          :key="`${decision.sheet}:${decision.key}`"
          class="bg-white border-b border-gray-100 last:border-b-0 px-4 py-3"
        >
          <div class="flex flex-wrap gap-x-3 gap-y-1 items-baseline">
            <u-badge :color="decision.status === 'Clear' ? 'success' : 'warning'" variant="subtle" size="sm">
              {{ decision.status }}
            </u-badge>
            <span class="font-mono text-sm">{{ decision.key }}</span>
            <span class="text-gray-500 text-sm">{{ titleOf(decision.sheet) }}</span>
            <u-button
              size="xs"
              color="neutral"
              variant="ghost"
              class="ml-auto"
              @click="signoff.unqueue(decision.sheet, decision.key)"
            >
              Remove
            </u-button>
          </div>
          <p v-if="decision.notes" class="mt-1 text-gray-700 text-sm">{{ decision.notes }}</p>
          <p v-else class="mt-1 text-amber-700 text-sm">No note — worth saying what convinced you.</p>
        </div>
      </div>

      <div class="bg-white border border-gray-200 p-5 rounded-lg space-y-3">
        <div class="text-sm">
          Proposed to <span class="font-mono">{{ fork }}</span>, touching
          <span class="font-mono">{{ Object.values(HITL_SHEETS).map((s) => s.path).join(' and ') }}</span>.
        </div>
        <div class="flex gap-2">
          <u-button :loading="signoff.submitting" :disabled="!auth.canSignOff" @click="signoff.submit()">
            Open pull request
          </u-button>
          <u-button color="neutral" variant="subtle" @click="signoff.discard()">Discard all</u-button>
        </div>
        <p v-if="!auth.canSignOff" class="text-amber-700 text-sm">
          <nuxt-link to="/settings" class="underline">Sign in with your initials</nuxt-link> first.
        </p>
      </div>
    </template>

    <u-alert
      v-if="signoff.result"
      :color="signoff.result.url ? 'success' : 'neutral'"
      variant="subtle"
      :description="signoff.result.message"
    >
      <template v-if="signoff.result.url" #description>
        {{ signoff.result.message }}
        <a :href="signoff.result.url" target="_blank" rel="noopener" class="ml-1 underline">Open it</a>
      </template>
    </u-alert>
  </div>
</template>
