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

const report = (runAt: string, comparedWith: string | null = null) => ({
  schemaVersion: 2, runAt, comparedWith, parameters: { commit: 'abc', dirty: false },
  sources: {}, referenceDesignators: [],
  checks: { deployments: { rows: [], summary: { problem: 0, total: 0 } } },
})

describe('a run published under the older schema', () => {
  /** Schema 2 ranked a row `problem` where one record disagreed with another
   *  and `review` where nothing had established it either way. Every one of
   *  those runs is still in the picker, and next season's review is read
   *  against one, so they have to go on rendering: a severity with no label has
   *  no colour and no segment, and the table shows blank badges. */
  it('is read with the two old categories folded into one', async () => {
    globalThis.$fetch = vi.fn(() => Promise.resolve({
      schemaVersion: 2,
      runAt: '2026-09-18T00:00:00',
      sources: {},
      checks: {
        deployments: {
          rows: [
            { severity: 'problem', finding: 'problem', cleared: false },
            { severity: 'review', cleared: false },
            { severity: 'ok', cleared: false },
          ],
          summary: { problem: 1, review: 1, unchecked: 0, cleared: 0, ok: 1,
                     excluded: 0, attention: 2, total: 3 },
        },
      },
    })) as never

    const store = useStore()
    await store.load()
    const check = store.report!.checks.deployments!
    expect(check.rows.map((row) => row.severity)).toEqual([
      'verification', 'verification', 'ok'])
    expect(check.rows[0]!.finding).toBe('verification')
    expect(check.summary.verification).toBe(2)
    // The old keys are gone, so nothing can read one by accident and get a
    // number that means half the category.
    expect('problem' in check.summary).toBe(false)
    expect('attention' in check.summary).toBe(false)
  })

  it('leaves a current run alone', async () => {
    globalThis.$fetch = vi.fn(() => Promise.resolve({
      schemaVersion: 3,
      runAt: '2026-09-18T00:00:00',
      comparedWith: null,
      sources: {},
      checks: {
        deployments: {
          rows: [{ severity: 'verification', cleared: false }],
          summary: { verification: 1, unchecked: 0, cleared: 0, ok: 0,
                     excluded: 0, total: 1 },
        },
      },
    })) as never

    const store = useStore()
    await store.load()
    expect(store.report!.checks.deployments!.summary.verification).toBe(1)
  })
})

describe('the comparison a run is read with', () => {
  /** Which urls were asked for, so a request that should not happen is visible
   *  as an absence rather than as a caught error nobody sees. */
  function serving(files: Record<string, unknown>) {
    const asked: string[] = []
    globalThis.$fetch = vi.fn((url: string) => {
      asked.push(url)
      // The whole file name, not a suffix: `comparison-latest.json` ends with
      // `latest.json`, and matching loosely served the report as the comparison.
      const name = url.split('/').pop() ?? ''
      return name in files ? Promise.resolve(files[name]) : Promise.reject(new Error('404'))
    }) as never
    return asked
  }

  it('is not asked for at all when the run was given no baseline', async () => {
    // It would 404, because a comparison is only published where there was a
    // baseline. The browser reports that in the console, which reads as a fault
    // in a page that is working exactly as intended.
    const asked = serving({ 'latest.json': report('2026-09-18T00:00:00') })
    await useStore().load()
    expect(asked.some((url) => url.includes('comparison'))).toBe(false)
  })

  it('is not asked for on a run published before the report said', async () => {
    // No run published before `comparedWith` existed ever carried a comparison.
    const old = report('2026-09-18T00:00:00') as Record<string, unknown>
    delete old.comparedWith
    const asked = serving({ 'latest.json': old })
    await useStore().load()
    expect(asked.some((url) => url.includes('comparison'))).toBe(false)
  })

  it('is asked for, and shown, when the run names what it was measured against', async () => {
    const asked = serving({
      'latest.json': report('2026-09-18T00:00:00', 'master'),
      'comparison-latest.json': { currentRunAt: '2026-09-18T00:00:00', checks: {} },
    })
    const store = useStore()
    await store.load()
    expect(asked.some((url) => url.includes('comparison-latest.json'))).toBe(true)
    expect(store.comparison).not.toBeNull()
  })

  it('shows none when the comparison belongs to another run', async () => {
    // The pair are separate files and can come apart.
    serving({
      'latest.json': report('2026-09-18T00:00:00', 'master'),
      'comparison-latest.json': { currentRunAt: '2026-09-01T00:00:00', checks: {} },
    })
    const store = useStore()
    await store.load()
    expect(store.comparison).toBeNull()
  })
})

describe('switching the run on screen', () => {

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
