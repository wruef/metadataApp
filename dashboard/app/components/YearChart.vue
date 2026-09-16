<script setup lang="ts">
import { SEVERITY_TONE } from '~/display'
import { niceMax, type YearBar } from '~/overview'
import { SEVERITIES, SEVERITY_LABEL } from '~/store'

const { bars } = defineProps<{ bars: YearBar[] }>()

/** Plain numbers rather than a charting library: four stacked rectangles a year
 *  is not worth 90 KB of JavaScript, and the scale stays ours. */
const W = 900
const H = 250
const ML = 34
const MR = 10
const MT = 16
const MB = 34
const PW = W - ML - MR
const PH = H - MT - MB

const top = computed(() => niceMax(Math.max(0, ...bars.map((bar) => bar.total))))
const ticks = computed(() => [0, top.value / 2, top.value])
const width = computed(() => PW / Math.max(bars.length, 1))
const thickness = computed(() => Math.min(38, width.value - 12))

function y(value: number) {
  return MT + PH - (value / top.value) * PH
}

/** Each bar's segments, worst at the bottom where the axis is read from. */
const drawn = computed(() =>
  bars.map((bar, index) => {
    const x = ML + index * width.value + (width.value - thickness.value) / 2
    let stacked = 0
    const segments = []
    for (const severity of SEVERITIES) {
      const count = bar.counts[severity]
      if (!count) continue
      const height = (count / top.value) * PH
      segments.push({
        severity,
        y: MT + PH - ((stacked + count) / top.value) * PH,
        height: Math.max(height - 2, 1),
        count,
      })
      stacked += count
    }
    return { bar, x, segments, labelY: y(bar.total) - 6 }
  }),
)
</script>

<template>
  <div>
    <div class="flex flex-wrap gap-4 px-4 text-[12px] text-gray-700">
      <span v-for="severity in SEVERITIES" :key="severity" class="flex gap-1.5 items-center">
        <i
          class="block h-2.5 rounded-[2px] w-2.5"
          :style="{ background: `var(--${SEVERITY_TONE[severity]})` }"
        />
        {{ SEVERITY_LABEL[severity] }}
      </span>
    </div>
    <div class="px-4 pb-4 pt-1.5">
      <svg
        :viewBox="`0 0 ${W} ${H}`"
        width="100%"
        role="img"
        :aria-label="`Deployment verification by deploy year, ${bars[0]?.year} to ${bars[bars.length - 1]?.year}`"
        class="block h-auto max-w-full"
      >
        <g v-for="tick in ticks" :key="tick">
          <line :x1="ML" :x2="W - MR" :y1="y(tick)" :y2="y(tick)" stroke="var(--line-soft)" />
          <text
            :x="ML - 7"
            :y="y(tick) + 3.5"
            text-anchor="end"
            class="fill-gray-500 text-[10px] tabular-nums"
          >
            {{ tick }}
          </text>
        </g>

        <g v-for="entry in drawn" :key="entry.bar.year">
          <rect
            v-for="segment in entry.segments"
            :key="segment.severity"
            :x="entry.x"
            :y="segment.y"
            :width="thickness"
            :height="segment.height"
            rx="2"
            :fill="`var(--${SEVERITY_TONE[segment.severity]})`"
          >
            <title>
              {{ entry.bar.year }} · {{ SEVERITY_LABEL[segment.severity] }}: {{ segment.count }} of
              {{ entry.bar.total }} deployments
            </title>
          </rect>
          <text
            :x="entry.x + thickness / 2"
            :y="entry.labelY"
            text-anchor="middle"
            class="fill-gray-600 font-mono font-semibold text-[10px]"
          >
            {{ entry.bar.total }}
          </text>
          <text
            :x="entry.x + thickness / 2"
            :y="H - MB + 16"
            text-anchor="middle"
            class="fill-gray-500 text-[10px] tabular-nums"
          >
            {{ entry.bar.year.slice(2) }}
          </text>
        </g>

        <text :x="ML" :y="H - 4" class="fill-gray-500 text-[10px]">
          deploy year · the number above each bar is how many deployments the sheets carry
        </text>
      </svg>
    </div>
  </div>
</template>
