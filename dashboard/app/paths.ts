/**
 * Where the dashboard looks for the files it reads.
 *
 * A GitHub Pages project site is served from a subdirectory —
 * `https://wruef.github.io/metadataApp/` — so an absolute `/reports/latest.json`
 * asks github.io for a file that is not there. Every path the app fetches is
 * therefore relative and joined to the base the site was built for.
 */
export function withBase(base: string, path: string) {
  // A full URL is someone pointing the dashboard at a report kept elsewhere.
  if (/^[a-z]+:\/\//i.test(path)) return path
  return `${(base || '/').replace(/\/$/, '')}/${path.replace(/^\//, '')}`
}

/**
 * The written guides, which are Markdown in this repository rather than pages
 * in the app: a reviewer has to be able to read how to get a token before they
 * have a dashboard they can sign in to, and GitHub renders them as they are.
 */
export const DOCS = 'https://github.com/wruef/metadataApp/blob/main/docs'
export const GUIDE = `${DOCS}/using-the-dashboard.md`
