import tailwindcss from '@tailwindcss/vite'
import { defineNuxtConfig } from 'nuxt/config'

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
    // A Pages project site lives under /<repo>/. Set by the deploy workflow
    // from the repository name, so a fork publishes to its own path without
    // anything here being edited.
    baseURL: process.env.NUXT_APP_BASE_URL || '/',
    head: {
      // The mono face the identifier and coefficient columns are set in. Digits
      // have to line up for a serial number to be read down a column.
      link: [
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
      // Written only when a run is given a baseline to compare against.
      comparisonUrl: 'reports/comparison.json',
      // The deployment history a run built, fetched only when that view is
      // opened -- it is a couple of hundred kilobytes of csv.
      historyUrl: 'reports/history-latest.json',
      // Every run that has been published, so an earlier one can be opened.
      indexUrl: 'reports/index.json',
    },
  },
})
