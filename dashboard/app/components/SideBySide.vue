<script setup lang="ts">
import {
  constantDifferences,
  isPdf,
  isPinned,
  rawUrl,
  readAt,
  repoLines,
  vendorLines,
  vendorValues,
  type Difference,
} from '~/files'
import { useStore, type Row } from '~/store'

/**
 * The repository calibration file and the vendor original, together.
 *
 * This is what the old report made you do by hand: find the file, find the
 * vendor file, and read two numbers in two windows. The coefficients that
 * disagree are marked on both sides and each pane opens at the first one.
 */
const { row } = defineProps<{ row: Row }>()
const emit = defineEmits<{ close: [] }>()

const store = useStore()

const differences = computed(() => (row.differences ?? []) as Difference[])
const coefficients = computed(() => new Set(differences.value.map((each) => each.coefficient)))
const constants = computed(() => constantDifferences(differences.value))

/** Every vendor original on record. A text file is read and compared; a pdf is
 *  put on screen for a person to read, which is the only honest way to check a
 *  scan -- OCR misread three of seven coefficients on the first one tried, and
 *  invented a minus sign on a fourth. */
const readable = computed(() => (row.vendorFiles as string[] | undefined) ?? [])
const chosen = ref(readable.value[0] ?? '')
const scanned = computed(() => isPdf(chosen.value))

const repoPath = computed(() => `calibration/${row.instrument}/${row.fileName}`)
const vendorPath = computed(() => `${row.vendorDirectory}/${chosen.value}`)

function source(name: string) {
  const found = store.report?.sources?.[name]
  return found && typeof found === 'object' ? found : null
}

const repoText = ref('')
const vendorText = ref('')
/** A blob url for a pdf: raw.githubusercontent serves one as
 *  application/octet-stream with nosniff, which a browser downloads rather than
 *  renders, so the bytes are fetched and given their real type here. */
const vendorPdf = ref('')
const status = ref<'loading' | 'ready' | 'error'>('loading')
const error = ref('')

function releasePdf() {
  if (vendorPdf.value) URL.revokeObjectURL(vendorPdf.value)
  vendorPdf.value = ''
}

/** Fetched from raw.githubusercontent at the ref the run read, so what is on
 *  screen is the file the finding came from rather than today's version. */
async function load() {
  status.value = 'loading'
  error.value = ''
  const assets = source('assetManagement')
  const vendor = source('calibrationFiles')
  if (!assets || !vendor) {
    status.value = 'error'
    error.value = 'This run does not record which repositories it read.'
    return
  }
  releasePdf()
  try {
    const vendorFile = rawUrl(vendor.repo, readAt(vendor), vendorPath.value)
    repoText.value = await $fetch<string>(
      rawUrl(assets.repo, readAt(assets), repoPath.value), { responseType: 'text' })
    if (scanned.value) {
      const bytes = await $fetch<Blob>(vendorFile, { responseType: 'blob' })
      vendorPdf.value = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }))
      vendorText.value = ''
    } else {
      vendorText.value = await $fetch<string>(vendorFile, { responseType: 'text' })
    }
    status.value = 'ready'
  } catch (caught) {
    status.value = 'error'
    error.value = `Could not read both files. ${caught instanceof Error ? caught.message : String(caught)}`
  }
}

/** Named when the run pinned a commit, so the reader knows whether what is on
 *  screen is the file the check read or merely today's version of it. */
const unpinned = computed(() =>
  [source('assetManagement'), source('calibrationFiles')]
    .filter((each): each is NonNullable<typeof each> => Boolean(each) && !isPinned(each!))
    .map((each) => `${each.repo.split('/')[1]}@${each.ref}`),
)

const left = computed(() => repoLines(repoText.value, coefficients.value))
const right = computed(() => vendorLines(vendorText.value, vendorValues(differences.value)))

const root = useTemplateRef<HTMLElement>('root')

/** Scroll each pane to its first marked line.
 *
 *  Found in the DOM rather than by multiplying an index by an assumed line
 *  height: a wrapped line makes that arithmetic wrong, and a template ref
 *  cannot be used because both panes are rendered from one `v-for`, where Vue
 *  collects refs into an array instead of the element. */
function reveal() {
  for (const pane of root.value?.querySelectorAll<HTMLElement>('[data-pane]') ?? []) {
    const hit = pane.querySelector<HTMLElement>('[data-hit]')
    if (hit) pane.scrollTop = Math.max(0, hit.offsetTop - pane.clientHeight / 2)
  }
}

watch(chosen, load)
onUnmounted(releasePdf)
watch(status, async (value) => {
  if (value !== 'ready') return
  await nextTick()
  reveal()
})
onMounted(load)

function blobUrl(name: string, path: string) {
  return store.fileUrl(name, path)
}
</script>

<template>
  <div
    class="bg-[rgba(10,26,38,0.5)] fixed inset-0 z-[80] flex items-center justify-center p-6"
    @click.self="emit('close')"
  >
    <div
      ref="root"
      class="bg-white flex flex-col max-h-[86vh] max-w-full overflow-hidden rounded-xl shadow-2xl w-[78rem]"
      role="dialog"
      aria-modal="true"
      aria-label="Calibration file against the vendor original"
    >
      <header class="border-b border-gray-200 flex gap-3 items-center px-5 py-3.5">
        <h3 class="font-semibold text-[15px]">Calibration against the vendor original</h3>
        <span class="font-mono text-[12px] text-gray-500 truncate">{{ row.fileName }}</span>
        <select
          v-if="readable.length > 1"
          v-model="chosen"
          class="sel ml-auto"
          aria-label="Which vendor file"
        >
          <option v-for="name in readable" :key="name" :value="name">{{ name }}</option>
        </select>
        <button
          class="leading-none ml-auto px-1.5 text-gray-500 text-xl last:ml-0"
          :class="{ 'ml-0': readable.length > 1 }"
          aria-label="Close"
          @click="emit('close')"
        >
          ×
        </button>
      </header>

      <div class="grow overflow-y-auto p-5">
        <!-- The numbers themselves, before the files they came out of. -->
        <div v-if="differences.length" class="flex flex-wrap gap-2 mb-3.5">
          <div
            v-for="each in differences"
            :key="each.coefficient"
            class="bg-white border border-gray-200 border-l-[3px] px-3 py-1.5 rounded-md"
            :style="{ borderLeftColor: `var(--${each.source === 'vendor' ? 'crit' : 'warn'})` }"
          >
            <div class="font-mono font-semibold text-[11.5px]">{{ each.coefficient }}</div>
            <div class="font-mono mt-0.5 text-[11px] text-gray-600">
              repo <b class="text-gray-900">{{ each.github }}</b> ·
              <template v-if="each.expected === null">
                <span class="text-[var(--crit)]">not in the vendor file</span>
              </template>
              <template v-else>
                {{ each.source === 'vendor' ? 'vendor' : each.source }}
                <span class="text-[var(--crit)]">{{ each.expected }}</span> · Δ {{ each.difference }}
              </template>
            </div>
          </div>
        </div>

        <!-- Why part of the left pane has nothing marked opposite it. -->
        <div
          v-if="constants.length"
          class="bg-primary-100 border border-primary-200 mb-3 px-3 py-2.5 rounded-md text-[12px] text-primary-900 leading-normal"
        >
          <span class="font-mono">{{ constants.map((each) => each.coefficient).join(', ') }}</span>
          {{ constants.length === 1 ? 'is' : 'are' }} not read from the vendor file at all — the
          check compares against the fixed value in
          <span class="font-mono">params/coefficientConstants.csv</span>. Nothing is marked on the
          vendor side for {{ constants.length === 1 ? 'it' : 'them' }}.
        </div>

        <!-- Without a commit the panes are today's files, which may not be the
             ones the finding came from. Saying so beats quietly showing the
             wrong bytes beside a difference that looks invented. -->
        <div
          v-if="unpinned.length && status === 'ready'"
          class="bg-amber-50 border border-amber-200 mb-3 px-3 py-2.5 rounded-md text-[12px] text-amber-900 leading-normal"
        >
          This run did not record which commit it read of
          <span class="font-mono">{{ unpinned.join(', ') }}</span>, so these files are shown at the
          branch as it stands now. If a marked coefficient reads the same on both sides, the run read
          a different version of the file than this.
        </div>

        <div
          v-if="scanned && status === 'ready'"
          class="bg-amber-50 border border-amber-200 mb-3 px-3 py-2.5 rounded-md text-[12px] text-amber-900 leading-normal"
        >
          This calibration is only on record as a scan, so nothing has compared it. The values
          asset-management holds are on the left and the certificate is on the right — read them
          across, then clear or flag the row. Text recognition is deliberately not used: on the
          first scan tried it misread three of seven coefficients and invented a minus sign on a
          fourth, and a wrong digit here reads as a perfectly plausible number.
        </div>

        <div v-if="status === 'loading'" class="py-10 text-center text-gray-500 text-sm">
          Reading both files…
        </div>
        <div
          v-else-if="status === 'error'"
          class="bg-red-50 border border-red-200 px-3 py-2.5 rounded-md text-[12.5px] text-red-800"
        >
          {{ error }}
        </div>

        <div v-else class="gap-3.5 grid lg:grid-cols-2">
          <div
            v-for="pane in [
              { key: 'repo', title: 'asset-management', path: repoPath, lines: left, repo: 'assetManagement' },
              { key: 'vendor', title: 'vendor original', path: vendorPath, lines: right, repo: 'calibrationFiles' },
            ]"
            :key="pane.key"
            class="border border-gray-200 flex flex-col min-w-0 overflow-hidden rounded-lg"
          >
            <header class="bg-gray-50 border-b border-gray-200 flex gap-2 items-center px-3 py-2">
              <span class="font-bold text-[10px] text-gray-500 tracking-wider uppercase">
                {{ pane.title }}
              </span>
              <a
                :href="blobUrl(pane.repo, pane.path) ?? '#'"
                target="_blank"
                rel="noopener"
                class="font-mono ml-auto max-w-[60%] text-[11px] text-primary-700 truncate hover:underline"
              >
                {{ pane.path }}
              </a>
            </header>
            <!-- A scan is put on screen rather than read by machine: the only
                 person who can verify it is a person. -->
            <iframe
              v-if="pane.key === 'vendor' && scanned"
              :src="vendorPdf"
              class="bg-gray-100 h-[34rem] w-full"
              title="The vendor certificate"
            />
            <!-- `relative`, because the scroll position is worked out from each
                 marked line's offset within this box. -->
            <div
              v-else
              data-pane
              class="font-mono max-h-[34rem] overflow-auto relative text-[11px] leading-[18px]"
            >
              <div
                v-for="line in pane.lines"
                :key="line.n"
                :data-hit="line.hit ? '' : undefined"
                class="flex gap-2.5 px-2.5 whitespace-pre"
                :class="line.hit ? 'bg-[var(--crit-bg)] font-semibold text-[var(--crit-ink)]' : ''"
              >
                <span class="flex-none min-w-6 select-none text-right" :class="line.hit ? 'text-[var(--crit)]' : 'text-gray-400'">
                  {{ line.n }}
                </span>
                <span>{{ line.text || ' ' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
