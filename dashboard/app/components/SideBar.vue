<script setup lang="ts">
import { useAuth } from '~/auth'
import { useSignoff } from '~/signoff'
import { useStore } from '~/store'

const store = useStore()
const auth = useAuth()
const signoff = useSignoff()

/** What the check has waiting for a person — the same count as the segment the
 *  check opens on, so the rail and the table agree about how much is left. */
function attention(key: string) {
  const summary = store.report?.checks?.[key]?.summary
  return summary ? summary.problem + summary.review : 0
}
function hot(key: string) {
  return (store.report?.checks?.[key]?.summary.problem ?? 0) > 0
}

const runAt = computed(() =>
  store.report ? new Date(store.report.runAt).toLocaleDateString() : '',
)

/** The repositories this run read, at the ref it read them at — not wherever
 *  the branch has moved to since. */
const sources = computed(() =>
  Object.values(store.report?.sources ?? {})
    .filter((value) => value && typeof value === 'object')
    .map((value) => value as { repo: string; ref: string }),
)

const LINK =
  'flex gap-3 items-center pl-3 pr-4 py-2 text-[13.5px] text-gray-100 hover:text-white'
</script>

<template>
  <div class="rail flex flex-col min-h-full pb-6 pt-4 text-white">
    <nuxt-link to="/" class="flex gap-2.5 items-center px-4 pb-3.5">
      <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden="true" class="shrink-0">
        <circle cx="13" cy="13" r="11.2" stroke="#7fc4e8" stroke-width="1.5" />
        <path
          d="M3 13.5c2.6-2.6 4.3 2.6 6.9 0s4.3 2.6 6.9 0 4.3 2.6 6.9 0"
          stroke="#fff"
          stroke-width="1.5"
          stroke-linecap="round"
        />
        <circle cx="13" cy="7" r="1.9" fill="#fff" />
      </svg>
      <b class="font-semibold leading-tight text-[13px] tracking-[0.09em] uppercase">
        Metadata<br >Verification
      </b>
    </nuxt-link>

    <div class="bg-white/20 h-px mx-4" />

    <div class="rail-label px-4 pb-1.5 pt-4">Checks</div>
    <nav class="nav flex flex-col">
      <nuxt-link
        v-for="check in store.checks"
        :key="check.key"
        :to="`/checks/${check.key}`"
        :class="LINK"
        active-class="on"
      >
        <i :class="['fas', check.icon, 'w-4']" />
        <span class="grow">{{ check.title }}</span>
        <span v-if="attention(check.key)" class="n" :class="{ hot: hot(check.key) }">
          {{ attention(check.key) }}
        </span>
      </nuxt-link>
    </nav>

    <div class="bg-white/20 h-px mt-3.5 mx-4" />

    <div class="rail-label px-4 pb-1.5 pt-4">This run</div>
    <nav class="nav flex flex-col">
      <nuxt-link to="/changes" :class="LINK" active-class="on">
        <i class="fa-code-compare fas w-4" />
        <span>Changes</span>
      </nuxt-link>
      <nuxt-link to="/designators" :class="LINK" active-class="on">
        <i class="fa-list fas w-4" />
        <span class="grow">Reference designators</span>
        <span v-if="store.report?.referenceDesignators?.length" class="n">
          {{ store.report.referenceDesignators.length }}
        </span>
      </nuxt-link>
      <nuxt-link v-if="signoff.count" to="/queue" :class="LINK" active-class="on">
        <i class="fa-pen-to-square fas w-4" />
        <span class="grow">Sign-offs</span>
        <span class="n hot">{{ signoff.count }}</span>
      </nuxt-link>
    </nav>

    <!-- Which run this is, and what it read. Nothing refreshes on its own, so
         the date belongs in sight rather than one page in. -->
    <div v-if="store.report" class="mt-auto px-4 pt-5 text-[11px] text-white/55 leading-relaxed">
      Run <b class="font-mono font-normal text-white/80">{{ runAt }}</b><br >
      <template v-for="source in sources" :key="source.repo">
        <a
          class="text-[#a9d4ea] hover:underline"
          :href="`https://github.com/${source.repo}/tree/${source.ref}`"
          target="_blank"
          rel="noopener"
        >{{ source.repo.split('/')[1] }}</a><br >
      </template>
    </div>

    <!-- Who a sign-off would be attributed to, kept in sight rather than buried
         in a settings page. -->
    <nuxt-link to="/settings" :class="[LINK, 'mt-4']" active-class="on">
      <img v-if="auth.user" :src="auth.user.avatarUrl" alt="" class="h-5 rounded-full w-5" >
      <i v-else class="fa-right-to-bracket fas w-4" />
      <span class="truncate">{{ auth.user?.login ?? 'Sign in' }}</span>
    </nuxt-link>
  </div>
</template>
