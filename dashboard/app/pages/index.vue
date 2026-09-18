<script setup lang="ts">
import { SEVERITY_TONE, yearOf } from '~/display'
import { byYear, queueCounts } from '~/overview'
import { CHECKS, SEVERITIES, SEVERITY_LABEL, useStore, type Severity } from '~/store'

const store = useStore()

const checks = computed(() => store.report?.checks ?? {})
const facetsOf = (key: string) => CHECKS.find((check) => check.key === key)?.facets ?? []

const queue = computed(() => queueCounts(checks.value, facetsOf))

const years = computed(() =>
  byYear(checks.value.deployments?.rows ?? [], (row) => String(row.deployYear ?? yearOf(row.deployDate))),
)

/** A link that opens the check already filtered to exactly these rows. */
function href(check: string, where: Record<string, string | undefined>) {
  const query = new URLSearchParams(
    Object.entries(where).filter(([, value]) => value) as [string, string][],
  )
  return `/checks/${check}?${query}`
}

const summary = (key: string) => checks.value[key]?.summary

/** How many rows each severity holds, as a proportion bar. */
function shares(key: string) {
  const found = summary(key)
  if (!found) return []
  return SEVERITIES.map((severity) => ({ severity, count: found[severity] })).filter(
    (share) => share.count,
  )
}

const signedOff = computed(() =>
  Object.values(checks.value).reduce((total, check) => total + (check.summary.cleared ?? 0), 0),
)

/** Agreed with the record, or settled by a reviewer. A sign-off is how the
 *  things a check cannot settle get settled, so leaving them out of the
 *  headline would leave the record looking permanently unfinished. */
const verified = (key: string) => {
  const found = summary(key)
  if (!found) return 0
  return found.verified ?? found.ok + found.cleared
}

/** What the check could judge at all. An excluded row — an instrument
 *  asset-management holds no calibration for — is in no other number, so
 *  measuring against the row count would make the record look worse every time
 *  one of them was deployed. */
const considered = (key: string) => {
  const found = summary(key)
  if (!found) return 0
  return found.considered ?? found.total
}

/** The headline measures, each the answer to a question someone actually asks. */
const tiles = computed(() => {
  const deployments = summary('deployments')
  const calibrations = summary('calibrations')
  const positions = summary('positions')
  // A calibration with no comparison rule and no vendor file was never checked
  // against anything, so it does not belong in the denominator. A signed-off one
  // does: nothing machine-readable could be compared, but a person read it. That
  // falls out of the counts, because a cleared row is no longer 'unchecked'.
  const neverChecked = calibrations?.unchecked ?? 0
  const compared = considered('calibrations') - neverChecked
  return [
    {
      key: 'deployments',
      label: 'Deployments verified',
      value: verified('deployments'),
      of: considered('deployments'),
      note: `carry independent evidence that the instrument on the sheet is the one in the water, or a reviewer's sign-off — ${deployments?.cleared ?? 0} of them.`,
    },
    {
      key: 'calibrations',
      label: 'Calibrations verified',
      value: verified('calibrations'),
      of: compared,
      note: `agreeing with the vendor or signed off. Of the ${calibrations?.total ?? 0} files, ${neverChecked} have nothing to compare against.`,
    },
    {
      key: 'positions',
      label: 'Positions matching the spreadsheet',
      value: verified('positions'),
      of: considered('positions'),
      note: 'latitude, longitude and depth as the RCA position record has them.',
    },
  ]
})
</script>

<template>
  <div class="max-w-6xl space-y-6">
    <div>
      <h1 class="font-semibold text-2xl">Metadata verification</h1>
      <p class="max-w-prose mt-1 text-gray-600">
        Every deployed sensor correctly assigned, and every calibration file matching the vendor
        original. Work the queue by consequence: problems first, then what needs a person.
      </p>
    </div>

    <run-stamp />

    <div class="gap-4 grid sm:grid-cols-2 xl:grid-cols-4">
      <nuxt-link
        v-for="tile in tiles"
        :key="tile.key"
        :to="`/checks/${tile.key}`"
        class="bg-white block border border-gray-200 p-4 rounded-lg hover:border-primary-400"
      >
        <div class="font-bold text-[10.5px] text-gray-500 tracking-[0.09em] uppercase">
          {{ tile.label }}
        </div>
        <div class="font-mono font-semibold leading-none mt-1.5 text-3xl">
          <span class="text-[var(--ok)]">{{ tile.value }}</span>
          <span class="text-[17px] text-gray-500">/{{ tile.of }}</span>
        </div>
        <div class="mt-1.5 text-[12px] text-gray-500 leading-snug">{{ tile.note }}</div>
        <div class="bg-gray-100 flex gap-0.5 h-[5px] mt-3 overflow-hidden rounded-sm">
          <i
            v-for="share in shares(tile.key)"
            :key="share.severity"
            class="block h-full"
            :style="{ background: `var(--${SEVERITY_TONE[share.severity]})`, flex: share.count }"
          />
        </div>
      </nuxt-link>

      <div class="bg-white border border-gray-200 p-4 rounded-lg">
        <div class="font-bold text-[10.5px] text-gray-500 tracking-[0.09em] uppercase">
          Signed off by a reviewer
        </div>
        <div class="font-mono font-semibold leading-none mt-1.5 text-3xl">{{ signedOff }}</div>
        <div class="mt-1.5 text-[12px] text-gray-500 leading-snug">
          rows a person has cleared, across every check. A sign-off outranks a failing check but
          does not erase it.
        </div>
      </div>
    </div>

    <!-- The piece that makes the page worth opening: not how many problems there
         are, but which situations they are, and a way into each. -->
    <div class="bg-white border border-gray-200 overflow-hidden rounded-lg">
      <h2 class="border-b border-gray-100 flex gap-2.5 items-baseline px-4 py-3">
        <span class="font-semibold text-[13px]">What needs a person</span>
        <span class="text-[12px] text-gray-500">ranked by consequence, not by row order</span>
      </h2>
      <div v-if="!queue.length" class="px-4 py-6 text-gray-500 text-sm">
        Nothing outstanding in this run.
      </div>
      <nuxt-link
        v-for="(item, index) in queue"
        :key="index"
        :to="href(item.check, item.where)"
        class="border-b border-gray-100 flex gap-3.5 items-start last:border-b-0 px-4 py-3 hover:bg-primary-50"
      >
        <span
          class="font-mono font-semibold leading-tight min-w-11 text-[19px] text-right"
          :style="{ color: `var(--${SEVERITY_TONE[item.worst]})` }"
        >
          {{ item.count }}
        </span>
        <span class="grow">
          <span class="block font-semibold leading-snug text-[13px]">{{ item.title }}</span>
          <span class="block max-w-[88ch] mt-0.5 text-[12px] text-gray-500 leading-normal">
            {{ item.detail }}
          </span>
        </span>
        <span class="self-center text-[11.5px] text-primary-700 whitespace-nowrap">Open →</span>
      </nuxt-link>
    </div>

    <div v-if="years.length" class="bg-white border border-gray-200 overflow-hidden rounded-lg">
      <h2 class="border-b border-gray-100 flex gap-2.5 items-baseline px-4 py-3">
        <span class="font-semibold text-[13px]">Deployment verification by year</span>
        <span class="text-[12px] text-gray-500">
          every deployment on the cabled-array sheets, {{ years[0]?.year }}–{{ years[years.length - 1]?.year }}
        </span>
      </h2>
      <year-chart :bars="years" />
    </div>
  </div>
</template>
