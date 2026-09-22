<script setup lang="ts">
import { useAuth } from '~/auth'
import { GUIDE, REVIEW_GUIDE } from '~/paths'
import { useBatch } from '~/batch'
import { isNodeSignOff } from '~/signoff'
import { useStore } from '~/store'

const store = useStore()
const auth = useAuth()
const batch = useBatch()

/** What the check has waiting for a person — the same count as the segment the
 *  check opens on, so the rail and the table agree about how much is left. A
 *  signed-off row is in the cleared category rather than this one, so this is
 *  what is left rather than what was ever found. */
function needsVerifying(key: string) {
  return store.report?.checks?.[key]?.summary.verification ?? 0
}

/** Vendor calibrations the repository holds nothing for. */
const vendorOnly = computed(
  () => store.report?.checks?.calibrations?.missingFromGithub?.length ?? 0,
)

/** Sign-offs whose key matches no row this run produced. Nothing else on any
 *  screen shows them, which is the reason the rail carries a count.
 *
 *  Node sign-offs are left out. They match no row because no check reads them
 *  yet, and they are kept on purpose, so counting them here would be the rail
 *  asking for work nobody intends to do. */
const orphaned = computed(() =>
  Object.entries(store.report?.unmatchedSignOffs ?? {}).reduce(
    (total, [check, rows]) =>
      total + (rows ?? []).filter((row) => !isNodeSignOff(check, row.key)).length,
    0,
  ),
)

const runAt = computed(() =>
  store.report ? new Date(store.report.runAt).toLocaleDateString() : '',
)

/** The repositories this run read, at the ref it read them at — not wherever
 *  the branch has moved to since. */
const sources = computed(() =>
  Object.values(store.report?.sources ?? {})
    .filter((value) => value && typeof value === 'object')
    .map((value) => value as { repo: string; ref: string; commit: string | null }),
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

    <!-- The season's review, step by step. At the top because after a cruise
         it is the first thing to open, and it says which of everything below
         to do in what order. -->
    <a
      :href="REVIEW_GUIDE"
      target="_blank"
      rel="noopener"
      class="flex gap-3 items-center mt-3 mx-3 px-3 py-2 rounded-md bg-white/10 hover:bg-white/15 text-[13px] text-white"
    >
      <i class="fa-list-check fas w-4" />
      <span class="grow leading-tight">Post-cruise review,<br >step by step</span>
      <i class="fa-arrow-up-right-from-square fas text-[10px] text-white/40" />
    </a>

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
        <span v-if="needsVerifying(check.key)" class="n">
          {{ needsVerifying(check.key) }}
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
      <!-- A list to read rather than a queue to work, which is why it is here
           and no longer in an amber panel on top of the calibration table. -->
      <nuxt-link v-if="vendorOnly" to="/vendor-only" :class="LINK" active-class="on">
        <i class="fa-file-circle-question fas w-4" />
        <span class="grow">Not in asset-management</span>
        <span class="n">{{ vendorOnly }}</span>
      </nuxt-link>
      <!-- Judgements that have lost what they were about. Here rather than on a
           check, because no check has a row to put them on. -->
      <nuxt-link v-if="orphaned" to="/orphan-signoffs" :class="LINK" active-class="on">
        <i class="fa-link-slash fas w-4" />
        <span class="grow">Sign-offs with nothing to sign</span>
        <span class="n">{{ orphaned }}</span>
      </nuxt-link>
      <!-- A product rather than a queue: what was where and when, which the
           deployments repository holds. Its own action because it is proposed
           as one whole file set, not row by row. -->
      <nuxt-link to="/deployment-history" :class="LINK" active-class="on">
        <i class="fa-clock-rotate-left fas w-4" />
        <span class="grow">Deployment history</span>
      </nuxt-link>
      <!-- Corrections and sign-offs alike wait here, so the count is
           everything queued rather than the sign-offs alone. -->
      <nuxt-link v-if="batch.count" to="/queue" :class="LINK" active-class="on">
        <i class="fa-pen-to-square fas w-4" />
        <span class="grow">Queued changes</span>
        <span class="n hot">{{ batch.count }}</span>
      </nuxt-link>
    </nav>

    <!-- Which run this is, and what it read. Nothing refreshes on its own, so
         the date belongs in sight rather than one page in. -->
    <div v-if="store.report" class="mt-auto px-4 pt-5 text-[11px] text-white/55 leading-relaxed">
      Run <b class="font-mono font-normal text-white/80">{{ runAt }}</b><br >
      <template v-for="source in sources" :key="source.repo">
        <a
          class="text-[#a9d4ea] hover:underline"
          :href="`https://github.com/${source.repo}/tree/${source.commit && source.commit !== 'UNKNOWN' ? source.commit : source.ref}`"
          target="_blank"
          rel="noopener"
        >{{ source.repo.split('/')[1] }}</a><br >
      </template>
    </div>

    <!-- The guide is Markdown on GitHub rather than a page here, so this leaves
         the app. Opened in a tab of its own: a reviewer reads it while working
         the queue, and losing the queue to read about it would be perverse. -->
    <a
      :href="GUIDE"
      target="_blank"
      rel="noopener"
      :class="[LINK, store.report ? 'mt-4' : 'mt-auto']"
    >
      <i class="fa-book-open fas w-4" />
      <span class="grow">Docs</span>
      <i class="fa-arrow-up-right-from-square fas text-[10px] text-white/40" />
    </a>

    <!-- The two jobs that maintain a review's inputs: reading serial numbers
         out of the archive, and deleting runs nobody needs. Beside Settings
         because neither is part of reading a run. -->
    <nuxt-link to="/workflows" :class="LINK" active-class="on">
      <i class="fa-play fas w-4" />
      <span class="grow">Workflows</span>
    </nuxt-link>

    <!-- Who a sign-off would be attributed to, kept in sight rather than buried
         in a settings page. -->
    <nuxt-link to="/settings" :class="LINK" active-class="on">
      <img v-if="auth.user" :src="auth.user.avatarUrl" alt="" class="h-5 rounded-full w-5" >
      <i v-else class="fa-right-to-bracket fas w-4" />
      <span class="truncate">{{ auth.user?.login ?? 'Sign in' }}</span>
    </nuxt-link>
  </div>
</template>
