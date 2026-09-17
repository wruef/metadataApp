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
  const branch = `hitl-${new Date().toISOString().replace(/[-:.]/g, '').slice(0, 15)}Z`
  await post('git/refs', { ref: `refs/heads/${branch}`, sha: commit.sha })
  const pull = await post<{ html_url: string }>('pulls', {
    title,
    body,
    head: branch,
    base,
  })
  return pull.html_url
}
