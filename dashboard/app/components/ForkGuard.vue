<script setup lang="ts">
import { FORKS, useAuth, type ForkKey } from '~/auth'
import { useForkSync } from '~/forksync'

/**
 * The gate every write to a fork stands behind, in one place.
 *
 * Three views carried their own copy of it -- the calibration table, the asset
 * panel and the history page -- and the copies had begun to disagree about when
 * to show the checking notice. The rule is the same for all of them: signed in
 * with initials, and the fork exactly upstream. A fork that is not exactly
 * upstream is a fork this dashboard has never read, so it is a refusal rather
 * than a warning. What is allowed through is the slot.
 */
const { fork, action } = defineProps<{ fork: ForkKey; action: string }>()

const auth = useAuth()
const sync = useForkSync()
const definition = FORKS.find((each) => each.key === fork)!

/** Asked once the reviewer could act on the answer. */
watchEffect(() => {
  if (auth.canSignOff) sync.check(fork)
})

const refusal = computed(() => sync.refusal[fork] ?? null)
const checking = computed(() => Boolean(sync.checking[fork]))
</script>

<template>
  <!-- One root, so a class on <fork-guard> lands on something whichever branch renders. -->
  <div>
  <div v-if="!auth.canSignOff" class="text-gray-500 text-[12.5px]">
    <nuxt-link to="/settings" class="text-primary-700 underline">Sign in</nuxt-link>
    with your initials to {{ action }}.
  </div>

  <p v-else-if="checking" class="text-gray-500 text-[12.5px]">
    Checking your fork against {{ definition.upstream }}…
  </p>

  <u-alert
    v-else-if="refusal"
    color="error"
    variant="subtle"
    title="Your fork is not in sync"
    :description="refusal"
  >
    <template #actions>
      <u-button size="xs" color="neutral" variant="subtle" @click="sync.check(fork, true)">
        Check again
      </u-button>
    </template>
  </u-alert>

  <slot v-else />
  </div>
</template>
