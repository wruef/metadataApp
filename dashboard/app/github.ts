import { useAuth } from '~/auth'

const API = 'https://api.github.com/repos'

/** A regular file, as git spells it in a tree entry. */
const FILE_MODE = '100644'

export function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' }
}

const headers = authHeaders

/**
 * Whether a failed read means the file is not there.
 *
 * Only a 404 does. A revoked token, a rate limit, a network blip and a
 * repository the reviewer cannot see all fail too, and none of them is an empty
 * file — which matters because the caller reads a sheet in order to add a line
 * to it. Treating any failure as *the fork has no sheet yet* would build the
 * sheet from the one decision in hand and propose a pull request deleting every
 * other sign-off in it.
 */
export function isMissing(error: unknown) {
  return Boolean(error) && typeof error === 'object' && 'status' in error!
    && (error as { status: unknown }).status === 404
}

/** A file as the fork currently holds it. Returns null only when the fork does
 *  not have it — a fresh fork of a repository that never had the file. Any
 *  other failure is thrown, because it is not an empty file. */
export async function readFile(repo: string, path: string, ref: string) {
  const auth = useAuth()
  try {
    const response = await $fetch<{ content: string; encoding: string }>(
      `${API}/${repo}/contents/${path}?ref=${ref}`,
      { headers: headers(auth.token) },
    )
    return response.encoding === 'base64'
      ? new TextDecoder().decode(Uint8Array.from(atob(response.content.replace(/\n/g, '')), (c) => c.charCodeAt(0)))
      : response.content
  } catch (caught) {
    if (isMissing(caught)) return null
    throw caught
  }
}

/**
 * Propose files to a fork as a pull request: one commit carrying every changed
 * file, on a new branch, under the signed-in reviewer's own identity.
 *
 * Mirrors `publish.py` deliberately — same shape, same guard. If the tree
 * matches what the fork already holds, nothing is created and null comes back,
 * because an empty pull request is noise.
 */
export async function openPullRequest(
  repo: string,
  base: string,
  files: Record<string, string>,
  title: string,
  body: string,
  /** Names the branch, so a calibration correction is told apart from a batch
   *  of sign-offs in the fork's branch list at a glance. */
  prefix = 'hitl',
) {
  const auth = useAuth()
  const options = { headers: headers(auth.token) }
  const post = <T>(path: string, payload: Record<string, unknown>) =>
    $fetch<T>(`${API}/${repo}/${path}`, { ...options, method: 'POST', body: payload })

  const baseRef = await $fetch<{ object: { sha: string } }>(
    `${API}/${repo}/git/ref/heads/${base}`,
    options,
  )
  const baseSha = baseRef.object.sha
  const baseCommit = await $fetch<{ tree: { sha: string } }>(
    `${API}/${repo}/git/commits/${baseSha}`,
    options,
  )

  const tree = await post<{ sha: string }>('git/trees', {
    base_tree: baseCommit.tree.sha,
    tree: Object.entries(files)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([path, content]) => ({ path, mode: FILE_MODE, type: 'blob', content })),
  })
  if (tree.sha === baseCommit.tree.sha) return null

  const commit = await post<{ sha: string }>('git/commits', {
    message: title,
    tree: tree.sha,
    parents: [baseSha],
  })
  const branch = `${prefix}-${new Date().toISOString().replace(/[-:.]/g, '').slice(0, 15)}Z`
  await post('git/refs', { ref: `refs/heads/${branch}`, sha: commit.sha })
  const pull = await post<{ html_url: string }>('pulls', {
    title,
    body,
    head: branch,
    base,
  })
  return pull.html_url
}

/** What GitHub says about two branches in the same network. */
export interface Comparison {
  status: 'identical' | 'behind' | 'ahead' | 'diverged'
  ahead_by: number
  behind_by: number
}

/**
 * Why a fork may not be written to, or null when it may.
 *
 * A correction is proposed against a fork, but the finding that justifies it
 * was produced against upstream -- so a fork that is not exactly upstream is a
 * fork whose files this dashboard has never read.
 *
 * Behind, and the pull request silently reverts whatever landed upstream
 * meanwhile. Ahead, and the onward pull request to upstream carries those extra
 * commits along with the correction, so what arrives for review is not what was
 * reviewed here. Both are refused. Syncing a fork is one button on GitHub;
 * unpicking a calibration record from an unrelated commit is not.
 */
export function syncRefusal(comparison: Comparison, upstream: string) {
  if (comparison.status === 'identical') return null
  const commits = (count: number) => `${count} commit${count === 1 ? '' : 's'}`

  // What to do differs by which way the fork has moved, and getting it wrong
  // costs work: GitHub's Sync fork on a fork that is *ahead* offers to discard
  // the commits, which for a fork that is ahead because a correction has not
  // been merged upstream yet would throw that correction away.
  const behind = `Press Sync fork on GitHub, then run the checks again — a correction `
    + 'has to start from what the run read.'
  const ahead = `Those are changes ${upstream} does not have yet. Raise them upstream and wait `
    + 'for them to merge. Do not press Sync fork: on a fork that is ahead it offers to '
    + 'discard them.'

  const { how, what } = {
    behind: { how: `${commits(comparison.behind_by)} behind`, what: behind },
    ahead: { how: `${commits(comparison.ahead_by)} ahead of`, what: ahead },
    diverged: {
      how: `${commits(comparison.behind_by)} behind and ${commits(comparison.ahead_by)} ahead of`,
      what: `${ahead} Once they have, press Sync fork and run the checks again.`,
    },
  }[comparison.status]

  return `Your fork is ${how} ${upstream}. ${what}`
}

/**
 * How the reviewer's fork stands against upstream.
 *
 * Asked of the fork rather than of upstream, with the base spelled
 * ``owner:branch``: the token is scoped to the reviewer's own repositories, and
 * a request to the shared repository would be the one call that needs access
 * they were never asked for.
 */
export async function compareWithUpstream(fork: string, upstream: string, base: string) {
  const auth = useAuth()
  const owner = upstream.split('/')[0]
  return await $fetch<Comparison>(
    `${API}/${fork}/compare/${owner}:${base}...${base}`,
    { headers: headers(auth.token) },
  )
}
