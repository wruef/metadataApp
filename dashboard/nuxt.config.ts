import tailwindcss from '@tailwindcss/vite'
import { defineNuxtConfig } from 'nuxt/config'

// A Pages project site lives under /<repo>/. Set by the deploy workflow from the
// repository name, so a fork publishes to its own path without anything here
// being edited.
const base = process.env.NUXT_APP_BASE_URL || '/'

export default defineNuxtConfig({
  compatibilityDate: '2026-02-19',
  modules: ['@pinia/nuxt', '@nuxt/ui'],
  vite: { plugins: [tailwindcss() as never] },
  // Static: a run's report is a file served beside the site, and there is no
  // backend to render against.
  ssr: false,
  css: ['@/assets/css/main.css'],
  colorMode: { preference: 'light', fallback: 'light' },
  components: [{ path: '@/components', pathPrefix: false }],
  app: {
    baseURL: base,
    head: {
      link: [
        // Named here rather than from the app, so it is in the HTML the browser
        // is served. A page that names no icon has the browser ask the *origin*
        // root for /favicon.ico, which on a project site is a 404 on every
        // load; naming it after hydration would still leave that first request.
        { rel: 'icon', type: 'image/svg+xml', href: `${base.replace(/\/$/, '')}/favicon.svg` },
        // The mono face the identifier and coefficient columns are set in.
        // Digits have to line up for a serial number to be read down a column.
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap',
        },
      ],
    },
  },
  runtimeConfig: {
    public: {
      // Relative, and joined to the base above: these sit beside the site, and
      // an absolute path would look for them at the domain root instead.
      reportUrl: 'reports/latest.json',
      // The comparison belonging to the run above, under a fixed name for the
      // same reason the history has one. Written only when that run was given a
      // baseline, and deleted when it was not, so it can never be an earlier
      // run's comparison read as this one's.
      comparisonUrl: 'reports/comparison-latest.json',
      // The deployment history a run built, fetched only when that view is
      // opened -- it is a couple of hundred kilobytes of csv.
      historyUrl: 'reports/history-latest.json',
      // Every run that has been published, so an earlier one can be opened.
      indexUrl: 'reports/index.json',
    },
  },
})
