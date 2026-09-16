import tailwindcss from '@tailwindcss/vite'
import { defineNuxtConfig } from 'nuxt/config'

export default defineNuxtConfig({
  compatibilityDate: '2026-02-19',
  modules: ['@pinia/nuxt', '@nuxt/ui'],
  vite: { plugins: [tailwindcss() as never] },
  // Static: the report is a file on S3, and there is no backend to render against.
  ssr: false,
  css: ['@/assets/css/main.css'],
  colorMode: { preference: 'light', fallback: 'light' },
  // The mono face the identifier and coefficient columns are set in. Digits have
  // to line up for a serial number or a coefficient to be read down a column.
  app: {
    head: {
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
  components: [{ path: '@/components', pathPrefix: false }],
  runtimeConfig: {
    public: {
      // Where a run's report is published. Overridden at deploy time.
      reportUrl: '/reports/latest.json',
      // Written only when a run is given a baseline to compare against.
      comparisonUrl: '/reports/comparison.json',
      // Every run that has been published, so an earlier one can be opened.
      indexUrl: '/reports/index.json',
    },
  },
})
