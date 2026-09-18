<script setup lang="ts">
import { useAuth } from '~/auth'
import { describe, pathOf, useBatch, type BatchKey, type Entry } from '~/batch'

/**
 * Everything decided and not yet proposed, grouped by the repository it writes
 * to and by what kind of change it is.
 *
 * Each group is one pull request. Two groups share the asset-management fork
 * and still travel separately, because approving a page of coefficients is not
 * agreeing to move an instrument on the seabed.
 */
const auth = useAuth()
const batch = useBatch()

/** The files a group would touch, named so a reviewer sees what a request
 *  carries before opening it. */
function paths(entries: Entry[]) {
  return [...new Set(entries.map(pathOf))].sort()
}

function plural(count: number, unit: string) {
  return `${count} ${unit}${count === 1 ? '' : 's'}`
}

const busy = (key: BatchKey) => Boolean(batch.submitting[key])
const anyBusy = computed(() => Object.values(batch.submitting).some(Boolean))
</script>

<template>
  <div class="max-w-3xl space-y-6">
    <div>
      <h1 class="font-semibold text-2xl">Queued changes</h1>
      <p class="max-w-prose mt-1 text-gray-600">
        Decisions gather here and go over as one pull request per group, on your own forks. You
        raise each onward request to the shared repository by hand, so a batch is read before it
        lands.
      </p>
    </div>

    <p v-if="!batch.byFork.length" class="text-gray-600">
      Nothing queued. Clear or flag a row in any check, or correct a value on one.
    </p>

    <template v-else>
      <!-- One block per fork, because a pull request cannot span two of them. -->
      <section v-for="group in batch.byFork" :key="group.fork.key" class="space-y-3">
        <div class="flex flex-wrap gap-x-2 items-baseline">
          <h2 class="font-semibold text-lg">{{ group.fork.repo }}</h2>
          <span class="font-mono text-gray-500 text-sm">{{ group.repo || 'sign in to name your fork' }}</span>
        </div>

        <div
          v-for="{ definition, entries } in group.groups"
          :key="definition.key"
          class="bg-white border border-gray-200 overflow-hidden rounded-lg"
        >
          <div class="bg-gray-50 border-b border-gray-200 flex flex-wrap gap-x-3 items-baseline px-4 py-2.5">
            <h3 class="font-medium">{{ definition.title }}</h3>
            <span class="text-gray-500 text-sm">
              {{ entries.length ? plural(entries.length, definition.unit) : 'proposed' }}
            </span>
            <span class="ml-auto text-gray-500 text-xs">one pull request</span>
          </div>

          <div
            v-for="entry in entries"
            :key="entry.key"
            class="border-b border-gray-100 last:border-b-0 px-4 py-3"
          >
            <div class="flex flex-wrap gap-x-3 gap-y-1 items-baseline">
              <u-badge
                v-if="entry.batch === 'signoffs'"
                :color="entry.status === 'Clear' ? 'success' : 'warning'"
                variant="subtle"
                size="sm"
              >
                {{ entry.status }}
              </u-badge>
              <span class="font-mono text-sm">{{ describe(entry).name }}</span>
              <u-button
                size="xs"
                color="neutral"
                variant="ghost"
                class="ml-auto"
                @click="batch.unqueue(entry.batch, entry.key)"
              >
                Remove
              </u-button>
            </div>
            <p
              class="mt-1 text-sm"
              :class="entry.batch === 'signoffs' && !entry.notes ? 'text-amber-700' : 'text-gray-700'"
            >
              {{ describe(entry).summary }}
            </p>
          </div>

          <div class="border-t border-gray-200 px-4 py-3 space-y-2.5">
            <p v-if="entries.length" class="text-gray-600 text-sm">
              Touching
              <span class="font-mono">{{ paths(entries).join(', ') }}</span>.
            </p>
            <!-- Known before the click: the write would be refused at the moment
                 of writing anyway, so the button says so rather than running
                 five requests' worth of nothing first. -->
            <p
              v-if="definition.guarded && batch.refusalFor(definition.fork)"
              class="text-red-700 text-sm"
            >
              {{ batch.refusalFor(definition.fork) }}
            </p>
            <div v-if="entries.length" class="flex flex-wrap gap-2">
              <u-button
                :loading="busy(definition.key)"
                :disabled="!auth.canSignOff || anyBusy || Boolean(definition.guarded && batch.refusalFor(definition.fork))"
                @click="batch.submit(definition.key)"
              >
                Open pull request
              </u-button>
              <u-button
                color="neutral"
                variant="subtle"
                :disabled="anyBusy"
                @click="batch.discard(definition.key)"
              >
                Discard these
              </u-button>
            </div>

            <u-alert
              v-if="batch.results[definition.key]"
              :color="batch.results[definition.key]!.url ? 'success' : 'error'"
              variant="subtle"
            >
              <template #description>
                <span class="whitespace-pre-line">{{ batch.results[definition.key]!.message }}</span>
                <a
                  v-if="batch.results[definition.key]!.url"
                  :href="batch.results[definition.key]!.url!"
                  target="_blank"
                  rel="noopener"
                  class="ml-1 underline"
                >Open it</a>
              </template>
            </u-alert>
          </div>
        </div>
      </section>

      <div v-if="batch.pending.length" class="bg-white border border-gray-200 p-5 rounded-lg space-y-3">
        <p class="text-gray-600 text-sm">
          {{ batch.pending.length }} pull request{{ batch.pending.length === 1 ? '' : 's' }} in all.
          They are opened one after another, never together: two branches cut from the same base at
          once is how the second one lands empty.
        </p>
        <div class="flex flex-wrap gap-2">
          <u-button
            :loading="anyBusy"
            :disabled="!auth.canSignOff || batch.pending.length < 2"
            @click="batch.submitAll()"
          >
            Open all {{ batch.pending.length }}
          </u-button>
          <u-button color="neutral" variant="subtle" :disabled="anyBusy" @click="batch.discard()">
            Discard everything
          </u-button>
        </div>
        <p v-if="!auth.canSignOff" class="text-amber-700 text-sm">
          <nuxt-link to="/settings" class="underline">Sign in with your initials</nuxt-link> first.
        </p>
      </div>
    </template>
  </div>
</template>
