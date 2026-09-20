import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

/**
 * The file names the workflow writes against the ones the dashboard asks for.
 *
 * These agree by convention and nothing enforced it. The dashboard asked for
 * `reports/comparison.json`, which is gitignored and never committed, so the
 * Changes view was empty on the run the site opens on however many baselines
 * had been run — and nothing failed anywhere, because a missing comparison is
 * a normal thing for a run with no baseline. It was found by a reader noticing
 * a 404 in a browser console.
 *
 * So both sides are read here from their own source: the published names out of
 * `nuxt.config.ts`, and what the workflow commits out of the shell it runs.
 */
const read = (path: string) => readFileSync(new URL(path, import.meta.url), 'utf8')

const CONFIG = read('../nuxt.config.ts')
const WORKFLOW = read('../../.github/workflows/verify.yaml')

/** What `public:` in the Nuxt config gives a name to — the fixed urls the store
 *  fetches for the run the site opens on. */
function configured(key: string) {
  const found = CONFIG.match(new RegExp(`${key}:\\s*'([^']+)'`))
  if (!found) throw new Error(`${key} is not in nuxt.config.ts`)
  return found[1]!
}

const FIXED = ['reportUrl', 'comparisonUrl', 'historyUrl', 'indexUrl']

describe('the run the site opens on', () => {
  it.each(FIXED)('has %s written by the verification workflow', (key) => {
    // `git add -f $files` is what lands in the repository, so the name has to
    // reach `files` — being copied somewhere is not being published.
    const path = configured(key)
    expect(WORKFLOW).toContain(path)
    expect(WORKFLOW).toMatch(new RegExp(`files=.*${path.replace('.', '\\.')}`))
  })

  it('never points at a path the repository ignores', () => {
    // reports/comparison.json is the run's working output and is gitignored.
    // Asking for it is the exact fault this file exists for.
    const ignored = readFileSync(new URL('../../.gitignore', import.meta.url), 'utf8')
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith('#'))
    for (const key of FIXED) {
      expect(ignored).not.toContain(configured(key))
    }
  })
})

describe('a run picked out of the dropdown', () => {
  /** The store reaches a run's comparison and history by rewriting the stem of
   *  its report name, so the three have to be published under matching stems. */
  it('has its comparison and history published beside its report', () => {
    expect(WORKFLOW).toContain('reports/report_$stamp.json')
    expect(WORKFLOW).toContain('reports/comparison_$stamp.json')
    expect(WORKFLOW).toContain('reports/history_$stamp.json')
  })

  it('has a comparison name the store can derive from the report name', () => {
    const store = read('../app/store.ts')
    // If either prefix is renamed, this is what stops the pair coming apart.
    expect(store).toContain("name.replace('report_', 'comparison_')")
  })
})
