import { defineStore } from 'pinia'

import { FORKS, useAuth, type ForkKey } from '~/auth'
import { compareWithUpstream, syncRefusal, type Comparison } from '~/github'

/**
 * Whether a reviewer's fork may be written to.
 *
 * Everything this dashboard proposes is justified by a finding produced against
 * upstream, so a fork that is not exactly upstream is a fork whose files the
 * dashboard has never read. Shared by both things that write to one -- the
 * asset-management corrections and the deployment history -- so neither can be
 * written under a weaker rule than the other.
 *
 * Asked once per fork per session and cached: a reviewer working a queue should
 * not re-ask GitHub the same question per row. The write path re-asks at the
 * moment it writes, because upstream can move while somebody reads two files.
 */
export const useForkSync = defineStore('forkSync', () => {
  /** What GitHub said about each fork: how far it has moved from upstream, and
   *  which way. The sentence a reviewer reads is derived from this rather than
   *  stored, so the wording lives in one place -- `syncRefusal` -- and a cached
   *  answer can be re-read in different words without asking GitHub again. */
  const comparison = ref<Record<string, Comparison>>({})
  /** Why a fork could not be compared at all, which is not a fork in sync. */
  const failure = ref<Record<string, string>>({})
  const checking = ref<Record<string, boolean>>({})
  /** Which fork each cached answer was about. A fork renamed in Settings, or a
   *  different reviewer signing in, is asked afresh rather than told the
   *  previous fork's answer. */
  const checkedFor = ref<Record<string, string>>({})
  /** One question in flight per fork. A page that opens a hundred rows at once
   *  must not ask GitHub the same thing a hundred times. */
  const inFlight: Partial<Record<ForkKey, Promise<string | null>>> = {}

  function definitionOf(key: ForkKey) {
    return FORKS.find((each) => each.key === key)!
  }

  /** Why this fork may not be written to, or null. */
  function refusalFor(key: ForkKey): string | null {
    if (failure.value[key]) return failure.value[key]!
    const found = comparison.value[key]
    return found ? syncRefusal(found, definitionOf(key).upstream) : null
  }

  /** The same for every fork already asked about, which is what the components
   *  read. Derived, so nothing has to be kept in step with it. */
  const refusal = computed(() => Object.fromEntries(
    Object.keys(checkedFor.value).map((key) => [key, refusalFor(key as ForkKey)]),
  ) as Record<string, string | null>)

  async function check(key: ForkKey, force = false) {
    const fork = useAuth().forkFor(key)
    // Nothing to compare while signed out, and nothing to cache: the guard in
    // front of every write asks for initials first, so nobody sees this answer.
    if (!fork) return null
    if (!force && checkedFor.value[key] === fork) return refusalFor(key)
    const pending = inFlight[key]
    if (pending && !force) return pending

    const definition = definitionOf(key)
    checking.value = { ...checking.value, [key]: true }
    const asking = (async () => {
      try {
        const answer = await compareWithUpstream(fork, definition.upstream, definition.base)
        comparison.value = { ...comparison.value, [key]: answer }
        const { [key]: _cleared, ...rest } = failure.value
        failure.value = rest
      } catch (caught) {
        // A comparison that cannot be made is not a fork that is in sync.
        failure.value = { ...failure.value, [key]:
          `Could not check your fork against ${definition.upstream}: `
          + `${caught instanceof Error ? caught.message : String(caught)}` }
      }
      checkedFor.value = { ...checkedFor.value, [key]: fork }
      checking.value = { ...checking.value, [key]: false }
      delete inFlight[key]
      return refusalFor(key)
    })()
    inFlight[key] = asking
    return asking
  }

  return { comparison, checking, refusal, refusalFor, check, definitionOf }
})
