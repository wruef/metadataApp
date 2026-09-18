import { defineStore } from 'pinia'

import { FORKS, useAuth, type ForkKey } from '~/auth'
import { compareWithUpstream, syncRefusal } from '~/github'

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
  /** Why each fork may not be written to. Missing means not asked yet, null
   *  means it may. */
  const refusal = ref<Record<string, string | null>>({})
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

  async function check(key: ForkKey, force = false) {
    const fork = useAuth().forkFor(key)
    // Nothing to compare while signed out, and nothing to cache: the guard in
    // front of every write asks for initials first, so nobody sees this answer.
    if (!fork) return null
    if (!force && key in refusal.value && checkedFor.value[key] === fork) return refusal.value[key]!
    const pending = inFlight[key]
    if (pending && !force) return pending

    const definition = definitionOf(key)
    checking.value = { ...checking.value, [key]: true }
    const asking = (async () => {
      let answer: string | null
      try {
        answer = syncRefusal(
          await compareWithUpstream(fork, definition.upstream, definition.base),
          definition.upstream)
      } catch (caught) {
        // A comparison that cannot be made is not a fork that is in sync.
        answer = `Could not check your fork against ${definition.upstream}: `
          + `${caught instanceof Error ? caught.message : String(caught)}`
      }
      refusal.value = { ...refusal.value, [key]: answer }
      checkedFor.value = { ...checkedFor.value, [key]: fork }
      checking.value = { ...checking.value, [key]: false }
      delete inFlight[key]
      return answer
    })()
    inFlight[key] = asking
    return asking
  }

  return { refusal, checking, check, definitionOf }
})
