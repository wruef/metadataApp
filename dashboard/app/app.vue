<script setup lang="ts">
import { useAuth } from '~/auth'
import { useStore } from '~/store'

const store = useStore()
const auth = useAuth()
const route = useRoute()

/** Signing in must not depend on a report existing, or on one loading. */
const showPage = computed(() => route.path === '/settings' || store.status === 'ready')
onMounted(() => {
  store.load()
  // Revalidated rather than trusted: a stored token may have been revoked.
  auth.restore()
})
</script>

<template>
  <u-app>
    <div class="bg-gray-50 flex min-h-screen">
      <aside class="shrink-0 w-56"><side-bar /></aside>
      <main class="grow min-w-0 p-6">
        <!-- Exactly one NuxtPage. Two of them in a v-if chain are the same
             component type, so Vue reuses the instance and its router view
             stops resolving the new route: the address bar moves and the page
             does not. -->
        <nuxt-page v-if="showPage" />
        <div v-else-if="store.status === 'loading'" class="text-gray-500">Loading the latest run…</div>
        <u-alert
          v-else
          color="error"
          variant="subtle"
          title="No report to show"
          :description="`${store.error}. A report is written by the verify workflow — nothing is produced on a schedule.`"
        />
      </main>
    </div>
  </u-app>
</template>
