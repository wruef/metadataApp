<script setup lang="ts">
import { FORKS, useAuth } from '~/auth'

const auth = useAuth()
const candidate = ref('')
const revealed = ref(false)

async function submit() {
  await auth.signIn(candidate.value)
  if (auth.signedIn) candidate.value = ''
}
</script>

<template>
  <div class="max-w-2xl space-y-6">
    <div>
      <h1 class="font-semibold text-2xl">Sign in</h1>
      <p class="max-w-prose mt-1 text-gray-600">
        Clearing a row or correcting a position opens a pull request under your own GitHub identity,
        so the reviewer column fills honestly. That needs a token.
      </p>
    </div>

    <!-- Signed in -->
    <div v-if="auth.signedIn" class="space-y-5">
      <div class="bg-white border border-gray-200 flex gap-3 items-center px-5 py-4 rounded-lg">
        <img :src="auth.user!.avatarUrl" alt="" class="h-9 rounded-full w-9" >
        <div class="grow">
          <div class="font-medium">{{ auth.user!.login }}</div>
          <div class="text-gray-500 text-sm">Signed in to GitHub</div>
        </div>
        <u-button color="neutral" variant="subtle" @click="auth.signOut()">Sign out</u-button>
      </div>

      <div>
        <h2 class="font-semibold">Your initials</h2>
        <p class="max-w-prose mt-1 text-gray-600 text-sm">
          The 2i-HITL sheets have identified reviewers by initials since 2019 — <span class="font-mono">KB,WR</span>
          — so a sign-off adds yours to that column rather than your GitHub login.
        </p>
        <u-input
          id="initials"
          :model-value="auth.initials"
          placeholder="WR"
          maxlength="4"
          class="max-w-24 mt-2"
          @update:model-value="(value: string) => auth.setInitials(value)"
        />
        <p v-if="!auth.canSignOff" class="mt-1 text-amber-700 text-sm">
          Needed before you can clear or flag a row.
        </p>
      </div>

      <div>
        <h2 class="font-semibold">Your forks</h2>
        <p class="max-w-prose mt-1 text-gray-600 text-sm">
          Changes are proposed to your own fork, never to a shared repository. You raise the onward
          pull request by hand, so nothing generated reaches everyone else without you deciding it
          should.
        </p>
        <div class="mt-3 space-y-3">
          <div v-for="fork in FORKS" :key="fork.key">
            <label class="block font-medium text-sm" :for="`fork-${fork.key}`">{{ fork.repo }}</label>
            <div class="text-gray-500 text-sm">{{ fork.what }}</div>
            <u-input
              :id="`fork-${fork.key}`"
              :model-value="auth.forkFor(fork.key)"
              :placeholder="`${auth.user!.login}/${fork.repo}`"
              class="max-w-md mt-1"
              @update:model-value="(value: string) => auth.setFork(fork.key, value)"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Signed out -->
    <div v-else class="space-y-5">
      <form class="bg-white border border-gray-200 p-5 rounded-lg space-y-3" @submit.prevent="submit">
        <label class="block font-medium text-sm" for="token">GitHub personal access token</label>
        <div class="flex gap-2">
          <u-input
            id="token"
            v-model="candidate"
            :type="revealed ? 'text' : 'password'"
            placeholder="github_pat_…"
            class="grow"
            autocomplete="off"
          />
          <u-button color="neutral" variant="subtle" @click="revealed = !revealed">
            {{ revealed ? 'Hide' : 'Show' }}
          </u-button>
          <u-button type="submit" :loading="auth.status === 'checking'">Sign in</u-button>
        </div>
        <p class="text-gray-500 text-sm">
          Kept in this browser only. It is sent to api.github.com and nowhere else — this dashboard
          has no backend to send it to.
        </p>
      </form>

      <u-alert v-if="auth.status === 'error'" color="error" variant="subtle" :description="auth.error" />

      <div class="text-gray-700 text-sm">
        <h2 class="font-semibold text-gray-900">Creating the token</h2>
        <ol class="list-decimal mt-2 pl-5 space-y-1">
          <li>
            Open
            <a class="text-primary-700 underline" href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">
              a new fine-grained token</a>.
          </li>
          <li>Under <b>Repository access</b>, select only your forks of the three repositories below.</li>
          <li>Under <b>Permissions</b>, set <b>Contents</b> and <b>Pull requests</b> to read and write.</li>
          <li>Give it an expiry you are comfortable with, then paste it above.</li>
        </ol>
        <p class="mt-2">
          Nothing else is needed — no organisation access, and no permissions on the upstream
          repositories. You can revoke it at any time from
          <a class="text-primary-700 underline" href="https://github.com/settings/tokens" target="_blank" rel="noopener">your token settings</a>.
        </p>
      </div>
    </div>
  </div>
</template>
