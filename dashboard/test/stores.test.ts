import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * The stores, driven directly.
 *
 * Everything here is a defect a review found by reading: a batch discarding
 * decisions taken while its pull request was in flight, two runs landing out of
 * order, a fork checked once per row. Each was invisible to a typecheck and to
 * every pure-module test, because the bug was in how the state moved.
 */

const github = vi.hoisted(() => ({
  openPullRequest: vi.fn(),
  readFile: vi.fn(),
  compareWithUpstream: vi.fn(),
}))

vi.mock('~/github', async () => {
  const actual = await vi.importActual<typeof import('../app/github')>('../app/github')
  return { ...actual, ...github }
})

const { useAuth } = await import('../app/auth')
const { useBatch } = await import('../app/batch')
const { useForkSync } = await import('../app/forksync')
const { useStore } = await import('../app/store')

/** A promise a test resolves when it chooses, to hold a call in flight. */
function deferred<T>() {
  let settle: (value: T) => void = () => {}
  const promise = new Promise<T>((resolve) => { settle = resolve })
  return { promise, settle }
}

function signedIn(initials = 'WR') {
  const auth = useAuth()
  auth.user = { login: 'wruef', avatarUrl: '' }
  auth.token = 'token'
  auth.status = 'signedIn'
  auth.initials = initials
  return auth
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  github.readFile.mockResolvedValue('githubFile,Reviewers,DateReviewed,Status,HITLnotes\n')
})

describe('proposing a batch', () => {
  it('discards what the pull request carried, and nothing decided since', async () => {
    // Clear and Flag are not disabled while a batch is in flight, so a reviewer
    // can and does keep working. Those decisions were never in the request, and
    // used to vanish with it.
    signedIn()
    const batch = useBatch()
    const held = deferred<string>()
    github.openPullRequest.mockReturnValue(held.promise)

    batch.queueSignoff({ sheet: 'calibrations', key: 'a.csv', status: 'Clear', notes: 'checked' })
    batch.queueSignoff({ sheet: 'calibrations', key: 'b.csv', status: 'Clear', notes: 'checked' })
    const sending = batch.submit('signoffs')
    await Promise.resolve()

    batch.queueSignoff({ sheet: 'calibrations', key: 'c.csv', status: 'Clear', notes: 'later' })
    held.settle('https://github.com/wruef/metadataApp/pull/9')
    await sending

    expect(batch.forBatch('signoffs').map((entry) => entry.key)).toEqual(['calibrations:c.csv'])
    expect(batch.results.signoffs).toMatchObject({ outcome: 'opened' })
  })

  it('keeps everything when the request failed', async () => {
    signedIn()
    const batch = useBatch()
    github.openPullRequest.mockRejectedValue(new Error('GitHub said no'))

    batch.queueSignoff({ sheet: 'calibrations', key: 'a.csv', status: 'Clear', notes: '' })
    await batch.submit('signoffs')

    expect(batch.count).toBe(1)
    expect(batch.results.signoffs).toMatchObject({ outcome: 'failed', detail: 'GitHub said no' })
  })

  it('keeps everything when the fork already said it', async () => {
    // openPullRequest returns null rather than opening an empty request.
    signedIn()
    const batch = useBatch()
    github.openPullRequest.mockResolvedValue(null)

    batch.queueSignoff({ sheet: 'calibrations', key: 'a.csv', status: 'Clear', notes: '' })
    await batch.submit('signoffs')

    expect(batch.count).toBe(1)
    expect(batch.results.signoffs).toMatchObject({ outcome: 'unchanged' })
  })
})

describe('asking whether a fork is in sync', () => {
  it('asks once however many rows want to know', async () => {
    // The Changes view mounts a row detail per newly failing row, each with a
    // watcher that asks. A hundred rows used to be a hundred requests.
    signedIn()
    const sync = useForkSync()
    github.compareWithUpstream.mockResolvedValue({ status: 'identical', ahead_by: 0, behind_by: 0 })

    const answers = await Promise.all(
      Array.from({ length: 20 }, () => sync.check('assetManagement')))

    expect(github.compareWithUpstream).toHaveBeenCalledTimes(1)
    expect(answers.every((answer) => answer === null)).toBe(true)
  })

  it('asks again when the fork named in settings changes', async () => {
    signedIn()
    const sync = useForkSync()
    github.compareWithUpstream.mockResolvedValue({ status: 'identical', ahead_by: 0, behind_by: 0 })

    await sync.check('assetManagement')
    useAuth().setFork('assetManagement', 'somebody-else/asset-management')
    await sync.check('assetManagement')

    expect(github.compareWithUpstream).toHaveBeenCalledTimes(2)
  })

  it('says nothing at all while signed out, rather than caching a failure', async () => {
    const sync = useForkSync()
    expect(await sync.check('assetManagement')).toBeNull()
    expect(github.compareWithUpstream).not.toHaveBeenCalled()
  })

  it('puts the comparison into words rather than storing the words', async () => {
    signedIn()
    const sync = useForkSync()
    github.compareWithUpstream.mockResolvedValue({ status: 'behind', ahead_by: 0, behind_by: 2 })

    const refusal = await sync.check('assetManagement')
    expect(refusal).toContain('2 commits behind')
    // the fact is what is kept; the sentence is derived from it
    expect(sync.comparison.assetManagement).toMatchObject({ status: 'behind', behind_by: 2 })
  })
})

describe('switching the run on screen', () => {
  const report = (runAt: string) => ({
    schemaVersion: 2, runAt, parameters: { commit: 'abc', dirty: false },
    sources: {}, referenceDesignators: [],
    checks: { deployments: { rows: [], summary: { problem: 0, total: 0 } } },
  })

  it('shows the run asked for last, whatever order they arrive in', async () => {
    const first = deferred<unknown>()
    const second = deferred<unknown>()
    globalThis.$fetch = vi.fn((url: string) => {
      if (url.endsWith('report_a.json')) return first.promise
      if (url.endsWith('report_b.json')) return second.promise
      return Promise.reject(new Error('no such file'))
    }) as never

    const store = useStore()
    const a = store.load('report_a.json')
    const b = store.load('report_b.json')

    // B resolves first, then the slower A arrives after it.
    second.settle(report('2026-09-18T00:00:00'))
    await b
    first.settle(report('2026-09-01T00:00:00'))
    await a

    expect(store.selected).toBe('report_b.json')
    expect(store.report?.runAt).toBe('2026-09-18T00:00:00')
  })

  it('keeps the run on screen when the one asked for cannot be opened', async () => {
    // A run deleted from the repository is still in a cached index, and picking
    // it used to take the whole page down with an error naming the wrong cause.
    globalThis.$fetch = vi.fn((url: string) => (url.endsWith('report_gone.json')
      ? Promise.reject(new Error('404'))
      : Promise.resolve(report('2026-09-18T00:00:00')))) as never

    const store = useStore()
    await store.load()
    expect(store.status).toBe('ready')

    await store.load('report_gone.json')
    expect(store.status).toBe('ready')
    expect(store.report?.runAt).toBe('2026-09-18T00:00:00')
    expect(store.switchError).toContain('404')
    expect(store.selected).toBeNull()
  })
})
