import { computed, reactive, ref, shallowRef, watch, watchEffect } from 'vue'

/**
 * The handful of things Nuxt puts in scope for every module.
 *
 * The stores hold the logic no pure module can: what is queued, which run is on
 * screen, whether a fork may be written to. None of it was testable, because a
 * plain vitest run has no auto-imports and every store fails at `ref is not
 * defined`. Assigning them here is what lets a store be driven directly.
 *
 * `$fetch` and `useRuntimeConfig` are stubs a test replaces. The default throws
 * rather than returning nothing, so a test that forgets to stub one fails
 * saying so instead of asserting against silence.
 */
declare global {
  // eslint-disable-next-line no-var
  var $fetch: (...args: never[]) => Promise<unknown>
  // eslint-disable-next-line no-var
  var useRuntimeConfig: () => { app: { baseURL: string }; public: Record<string, string> }
}

Object.assign(globalThis, { computed, reactive, ref, shallowRef, watch, watchEffect })

globalThis.useRuntimeConfig = () => ({
  app: { baseURL: '/' },
  public: {
    reportUrl: 'reports/latest.json',
    comparisonUrl: 'reports/comparison-latest.json',
    historyUrl: 'reports/history-latest.json',
    indexUrl: 'reports/index.json',
  },
})

globalThis.$fetch = () => {
  throw new Error('$fetch was called but this test did not stub it')
}

export {}
