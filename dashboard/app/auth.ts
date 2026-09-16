import { defineStore } from 'pinia'

/** The repositories a reviewer proposes changes to, and what each one carries.
 *  Every one is a fork of the reviewer's own — nothing here ever targets a
 *  shared repository, and the onward pull request is raised by hand. */
export const FORKS = [
  { key: 'hitl', repo: 'metadataApp', base: 'main',
    what: 'HITL sign-offs, and the workflows a run is started from' },
  { key: 'assetManagement', repo: 'asset-management', base: 'master',
    what: 'position corrections to the deployment sheets' },
  { key: 'deployments', repo: 'deployments', base: 'main',
    what: 'deployment history and node positions' },
] as const

export type ForkKey = (typeof FORKS)[number]['key']

const TOKEN_KEY = 'rca.metadata.token'
const FORKS_KEY = 'rca.metadata.forks'
const INITIALS_KEY = 'rca.metadata.initials'

/** Browser storage can be unavailable or throw — a private window, blocked site
 *  data — and none of that should take the dashboard down. */
function read(key: string) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* the session simply does not persist */
  }
}

export interface User {
  login: string
  avatarUrl: string
}

export const useAuth = defineStore('auth', () => {
  const token = ref('')
  const user = ref<User | null>(null)
  const forks = ref<Record<string, string>>({})
  /** The 2i-HITL sheets identify reviewers by initials — "KB,WR" — not by
   *  GitHub login, so signing off needs the initials that column expects. */
  const initials = ref('')
  const status = ref<'signedOut' | 'checking' | 'signedIn' | 'error'>('signedOut')
  const error = ref('')

  const signedIn = computed(() => status.value === 'signedIn')

  /** The fork a given kind of change goes to, defaulting to the signed-in
   *  user's own fork of that repository. */
  function forkFor(key: ForkKey) {
    const definition = FORKS.find((fork) => fork.key === key)!
    return forks.value[key] || (user.value ? `${user.value.login}/${definition.repo}` : '')
  }

  function setInitials(value: string) {
    initials.value = value.trim().toUpperCase()
    write(INITIALS_KEY, initials.value)
  }

  function setFork(key: ForkKey, value: string) {
    forks.value = { ...forks.value, [key]: value.trim() }
    write(FORKS_KEY, JSON.stringify(forks.value))
  }

  /** Confirms the token works and says who it belongs to. The token is sent to
   *  api.github.com and nowhere else. */
  async function signIn(candidate: string) {
    const trimmed = candidate.trim()
    if (!trimmed) return
    status.value = 'checking'
    error.value = ''
    try {
      const account = await $fetch<{ login: string; avatar_url: string }>(
        'https://api.github.com/user',
        { headers: { Authorization: `Bearer ${trimmed}`, Accept: 'application/vnd.github+json' } },
      )
      token.value = trimmed
      user.value = { login: account.login, avatarUrl: account.avatar_url }
      status.value = 'signedIn'
      write(TOKEN_KEY, trimmed)
    } catch (caught) {
      // A rejected token is the common case: expired, or missing the scopes.
      error.value =
        caught && typeof caught === 'object' && 'status' in caught && caught.status === 401
          ? 'GitHub rejected that token. It may have expired, or it may not have access to your forks.'
          : `Could not reach GitHub: ${caught instanceof Error ? caught.message : String(caught)}`
      status.value = 'error'
    }
  }

  function signOut() {
    token.value = ''
    user.value = null
    status.value = 'signedOut'
    error.value = ''
    write(TOKEN_KEY, null)
  }

  /** Restores a previous session, revalidating rather than trusting the stored
   *  token — it may have been revoked since. */
  async function restore() {
    initials.value = read(INITIALS_KEY) ?? ''
    const stored = read(FORKS_KEY)
    if (stored) {
      try {
        forks.value = JSON.parse(stored)
      } catch {
        forks.value = {}
      }
    }
    const previous = read(TOKEN_KEY)
    if (previous) await signIn(previous)
  }

  /** Ready to sign off, as opposed to merely signed in. */
  const canSignOff = computed(() => signedIn.value && initials.value.length >= 2)

  /** Where a run is started. The same repository the sign-offs go to: it holds
   *  the workflows and the parameter files, so a run verifies against the
   *  parameters the reviewer actually has. */
  const workflowRepo = computed(() => forkFor('hitl'))
  const workflowRef = FORKS.find((fork) => fork.key === 'hitl')!.base

  return { token, user, forks, initials, status, error, signedIn, canSignOff,
           workflowRepo, workflowRef,
           signIn, signOut, restore, forkFor, setFork, setInitials }
})
