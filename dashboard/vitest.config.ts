import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

/** Nuxt's `~` alias, so a test can import the module under test the same way the
 *  app does — and, more to the point, can assert against the real declarations
 *  rather than a copy of them that drifts. */
export default defineConfig({
  resolve: {
    alias: { '~': fileURLToPath(new URL('./app', import.meta.url)) },
  },
  test: {
    /** What Nuxt puts in scope for every module. Without it a store cannot be
     *  imported at all, let alone driven. */
    setupFiles: ['./test/setup/nuxt.ts'],
  },
})
