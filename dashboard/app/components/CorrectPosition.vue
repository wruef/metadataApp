<script setup lang="ts">
import { useAuth } from '~/auth'
import { deploymentKey, useCorrections } from '~/corrections'
import { deploymentPath, POSITION_FIELDS, type FieldCorrection } from '~/deployfile'
import { type Row } from '~/store'

/**
 * Correcting a deployment's position on the asset-management sheet.
 *
 * The same shape as correcting a calibration file, and the same refusals, with
 * one difference that matters: a calibration file is one record, and a
 * deployment sheet holds every deployment on its array. So the unit here is the
 * deployment, and the editor says which sheet it is about to touch.
 */
const { row } = defineProps<{ row: Row }>()

const auth = useAuth()
const corrections = useCorrections()

const refDes = computed(() => String(row.refDes))
const deployNum = computed(() => row.deployNum as string | number)
const id = computed(() => deploymentKey(refDes.value, deployNum.value))
const path = computed(() => deploymentPath(refDes.value))
const busy = computed(() => Boolean(corrections.submitting[id.value]))
const result = computed(() => corrections.results[id.value])

interface Difference { field: string; current: unknown; expected: unknown }

/** Only a field a position governs. The check reports nothing else, but a
 *  report is a file on disk and this writes to a shared sheet. */
const editable = computed(() =>
  ((row.differences ?? []) as Difference[]).filter(
    (each) => POSITION_FIELDS.includes(each.field),
  ),
)

const open = ref(false)
const values = ref<Record<string, string>>({})

async function start() {
  open.value = true
  values.value = {}
  await corrections.checkSync()
}

/** The spreadsheet's own value, which is what the finding says the sheet should
 *  say. Taking it is the common case; the box is there for the other one. */
function take(entry: Difference) {
  values.value = { ...values.value, [entry.field]: String(entry.expected) }
}

function takeAll() {
  values.value = Object.fromEntries(
    editable.value.map((entry) => [entry.field, String(entry.expected)]))
}

/** Only the fields actually changed to something else. */
const queued = computed<FieldCorrection[]>(() =>
  editable.value.flatMap((entry) => {
    const typed = (values.value[entry.field] ?? '').trim()
    if (!typed || typed === String(entry.current)) return []
    return [{ field: entry.field, from: String(entry.current), to: typed }]
  }),
)

const blocked = computed(() => corrections.refusal || null)
</script>

<template>
  <div v-if="editable.length" class="border-gray-200 border-t mt-4 pt-3">
    <div v-if="!open" class="flex flex-wrap gap-2.5 items-center">
      <u-button size="sm" color="neutral" variant="subtle" icon="i-lucide-pencil" @click="start">
        Correct the deployment sheet
      </u-button>
      <span class="text-gray-500 text-sm">
        Changes this deployment's row in {{ path }}. Opens its own pull request on your fork.
      </span>
    </div>

    <div v-else class="space-y-3">
      <div class="flex gap-2 items-baseline justify-between">
        <h4 class="font-semibold text-[13px]">
          Correct {{ refDes }} deployment {{ deployNum }}
        </h4>
        <u-button size="xs" color="neutral" variant="ghost" @click="open = false">Close</u-button>
      </div>

      <div v-if="!auth.canSignOff" class="text-gray-500 text-sm">
        <nuxt-link to="/settings" class="text-primary-700 underline">Sign in</nuxt-link>
        with your initials to propose a correction.
      </div>

      <template v-else>
        <p v-if="corrections.checking" class="text-gray-500 text-sm">
          Checking your fork against oceanobservatories/asset-management…
        </p>

        <!-- A fork that is not exactly upstream is a fork whose files this
             dashboard has never read, so this is a refusal rather than a
             warning. Syncing is one button on GitHub. -->
        <u-alert
          v-else-if="blocked"
          color="error"
          variant="subtle"
          title="Your fork is not in sync"
          :description="blocked"
        >
          <template #actions>
            <u-button size="xs" color="neutral" variant="subtle" @click="corrections.checkSync(true)">
              Check again
            </u-button>
          </template>
        </u-alert>

        <template v-else>
          <div class="coefwrap">
            <table class="coef">
              <thead>
                <tr>
                  <th>Field</th>
                  <th class="text-right">On the sheet</th>
                  <th class="text-right">Spreadsheet</th>
                  <th>Correct to</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="entry in editable" :key="entry.field">
                  <td>{{ entry.field }}</td>
                  <td class="num text-right">{{ entry.current }}</td>
                  <td class="num text-right">
                    <button
                      class="text-primary-700 hover:underline"
                      type="button"
                      @click="take(entry)"
                    >{{ entry.expected }}</button>
                  </td>
                  <td>
                    <input
                      v-model="values[entry.field]"
                      class="fld num"
                      :placeholder="String(entry.current)"
                      :aria-label="`New value for ${entry.field}`"
                    >
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="flex flex-wrap gap-2.5 items-center">
            <u-button size="xs" color="neutral" variant="subtle" @click="takeAll">
              Take every spreadsheet value
            </u-button>
            <span class="text-gray-500 text-[12.5px]">
              The spreadsheet is the authority on where anything was put, so this is usually the
              whole answer. A box left blank is left alone.
            </span>
          </div>

          <div class="flex flex-wrap gap-2.5 items-center">
            <u-button
              size="sm"
              color="primary"
              :loading="busy"
              :disabled="!queued.length"
              @click="corrections.proposePosition(
                refDes, deployNum, String(row.positionName ?? ''), queued)"
            >
              Propose {{ queued.length || '' }} correction{{ queued.length === 1 ? '' : 's' }}
            </u-button>
            <span class="text-gray-500 text-sm">
              to <b>{{ auth.forkFor('assetManagement') }}</b> only. Raise the pull request upstream
              by hand; no data changes until that one is merged.
            </span>
          </div>
          <p class="text-gray-500 text-[12.5px]">
            Only this deployment's row is touched. If its notes say the parameters are
            preliminary, correcting the position clears that too — the position is no longer
            provisional once it comes from the spreadsheet.
          </p>
        </template>
      </template>

      <u-alert
        v-if="result"
        :color="result.url ? 'success' : 'error'"
        variant="subtle"
        :title="result.message"
      >
        <template v-if="result.url" #description>
          <a :href="result.url" target="_blank" rel="noopener" class="underline">
            Review it on GitHub
          </a>
        </template>
      </u-alert>
    </div>
  </div>
</template>

<style scoped>
.fld {
  border: 1px solid var(--color-gray-300, #d1d5db);
  border-radius: 5px;
  font-size: 12.5px;
  padding: 3px 6px;
  width: 100%;
}
.fld:focus { border-color: #2b6cb0; outline: none; }
</style>
