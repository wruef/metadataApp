import { useAuth } from '~/auth'

const API = 'https://api.github.com/repos'

/** A regular file, as git spells it in a tree entry. */
const FILE_MODE = '100644'

export function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' }
}

const headers = authHeaders

/** A file as the fork currently holds it. Returns null when the fork does not
 *  have it — a fresh fork of a repository that never had the file. */
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
  } catch {
    return null
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
