<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import {
  Upload,
  ArrowRight,
  ArrowLeft,
  Check,
  AlertCircle,
  FileSpreadsheet,
  X,
  Loader2,
  RotateCcw,
  Sparkles,
  RefreshCw,
  Ban,
} from 'lucide-vue-next'
import { importerApi } from '@/api/shared/importer'
import type {
  ImportPreviewResponse,
  ImportBatchResponse,
  ImportFieldInfo,
} from '@/types/models'
import { theme } from '@/theme'

const props = defineProps<{
  entityType: string
  onComplete: () => void
}>()

const emit = defineEmits<{
  close: []
}>()

// --- Wizard state ---
const step = ref(1)
const loading = ref(false)
const error = ref<string | null>(null)

// Step 1: Upload
const dragOver = ref(false)
const selectedFile = ref<File | null>(null)
const uploadProgress = ref(0)

// Step 2: Mapping
const preview = ref<ImportPreviewResponse | null>(null)
const columnMapping = ref<Record<string, string>>({})
const duplicateStrategy = ref<'skip' | 'enrich' | 'replace'>('skip')

// Step 3: Preview pagination
const previewPage = ref(1)
const previewPerPage = 5

// Step 4: Result
const result = ref<ImportBatchResponse | null>(null)
const rollbackLoading = ref(false)
const rollbackDone = ref(false)
const showCelebration = ref(false)

// Animated counters
const animatedImported = ref(0)
const animatedUpdated = ref(0)
const animatedSkipped = ref(0)
const animatedErrors = ref(0)

const stepLabels = ['Bestand uploaden', 'Kolommen koppelen', 'Controleren', 'Resultaat']

// --- Computed ---
const progressPercent = computed(() => ((step.value - 1) / (stepLabels.length - 1)) * 100)

const unmappedHeaders = computed(() => {
  if (!preview.value) return []
  return preview.value.detected_headers.filter((h) => !columnMapping.value[h])
})

const mappedCount = computed(() => Object.keys(columnMapping.value).length)

const requiredFieldsMapped = computed(() => {
  if (!preview.value) return false
  const requiredFields = preview.value.available_fields
    .filter((f) => f.required)
    .map((f) => f.name)
  const mappedFields = new Set(Object.values(columnMapping.value))
  return requiredFields.every((f) => {
    if (mappedFields.has(f)) return true
    // full_name satisfies first_name requirement (split happens server-side)
    if (f === 'first_name' && mappedFields.has('full_name')) return true
    return false
  })
})

const previewRows = computed(() => {
  if (!preview.value) return []
  const start = (previewPage.value - 1) * previewPerPage
  return preview.value.preview_rows.slice(start, start + previewPerPage)
})

const previewTotalPages = computed(() => {
  if (!preview.value) return 1
  return Math.max(1, Math.ceil(preview.value.preview_rows.length / previewPerPage))
})

function stepCircleClass(s: number): string {
  if (step.value > s) return 'bg-green-100 border-2 border-green-300 text-green-700'
  if (step.value === s) return 'bg-accent-50 border-2 border-accent-400 text-accent-700 shadow-sm'
  return 'bg-white border-2 border-navy-200 text-navy-400'
}

// --- Step 1: File handling ---

function onDrop(event: DragEvent) {
  dragOver.value = false
  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    selectFile(files[0])
  }
}

function onFileInput(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    selectFile(target.files[0])
  }
}

function selectFile(file: File) {
  const allowedExts = ['.xlsx', '.xls', '.csv']
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'))
  if (!allowedExts.includes(ext)) {
    error.value = 'Alleen .xlsx, .xls of .csv bestanden zijn toegestaan.'
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    error.value = 'Bestand is te groot (max 5MB).'
    return
  }
  error.value = null
  selectedFile.value = file
}

async function uploadAndPreview() {
  if (!selectedFile.value) return
  loading.value = true
  error.value = null
  uploadProgress.value = 0

  const interval = setInterval(() => {
    uploadProgress.value = Math.min(uploadProgress.value + Math.random() * 15, 90)
  }, 200)

  try {
    preview.value = await importerApi.preview(props.entityType, selectedFile.value)
    columnMapping.value = { ...preview.value.suggested_mapping }
    uploadProgress.value = 100
    clearInterval(interval)
    await new Promise((r) => setTimeout(r, 300))
    step.value = 2
  } catch (e: unknown) {
    clearInterval(interval)
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Upload mislukt.'
  } finally {
    loading.value = false
    uploadProgress.value = 0
  }
}

// --- Step 2: Mapping ---

function getFieldLabel(fieldName: string): string {
  const field = preview.value?.available_fields.find((f) => f.name === fieldName)
  return field?.label ?? fieldName
}

function usedFields(): Set<string> {
  return new Set(Object.values(columnMapping.value))
}

function availableFieldsForHeader(header: string): ImportFieldInfo[] {
  if (!preview.value) return []
  const used = usedFields()
  const currentMapping = columnMapping.value[header]
  return preview.value.available_fields.filter(
    (f) => !used.has(f.name) || f.name === currentMapping,
  )
}

function setMapping(header: string, fieldName: string) {
  if (fieldName === '') {
    const newMapping = { ...columnMapping.value }
    delete newMapping[header]
    columnMapping.value = newMapping
  } else {
    columnMapping.value = { ...columnMapping.value, [header]: fieldName }
  }
}

// --- Step 3: Execute ---

async function executeImport() {
  if (!preview.value) return
  loading.value = true
  error.value = null
  try {
    result.value = await importerApi.execute(
      props.entityType,
      preview.value.batch_id,
      columnMapping.value,
      duplicateStrategy.value,
    )
    step.value = 4
    await nextTick()
    showCelebration.value = true
    animateCountUp()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Import mislukt.'
  } finally {
    loading.value = false
  }
}

function animateCountUp() {
  if (!result.value) return
  const duration = 1200
  const steps = 40
  const interval = duration / steps

  const targets = {
    imported: result.value.imported_count,
    updated: result.value.updated_count,
    skipped: result.value.skipped_count,
    errors: result.value.error_count,
  }

  let currentStep = 0
  const timer = setInterval(() => {
    currentStep++
    const progress = currentStep / steps
    const eased = 1 - Math.pow(1 - progress, 3)

    animatedImported.value = Math.round(targets.imported * eased)
    animatedUpdated.value = Math.round(targets.updated * eased)
    animatedSkipped.value = Math.round(targets.skipped * eased)
    animatedErrors.value = Math.round(targets.errors * eased)

    if (currentStep >= steps) {
      clearInterval(timer)
      animatedImported.value = targets.imported
      animatedUpdated.value = targets.updated
      animatedSkipped.value = targets.skipped
      animatedErrors.value = targets.errors
    }
  }, interval)
}

// --- Step 4: Rollback ---

async function rollback() {
  if (!result.value) return
  rollbackLoading.value = true
  error.value = null
  try {
    await importerApi.rollback(props.entityType, result.value.id)
    rollbackDone.value = true
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Terugdraaien mislukt.'
  } finally {
    rollbackLoading.value = false
  }
}

function finish() {
  props.onComplete()
  emit('close')
}

const strategyOptions = [
  {
    value: 'skip' as const,
    label: 'Overslaan',
    description: 'Bestaande gegevens behouden, duplicaat niet importeren.',
    icon: Ban,
  },
  {
    value: 'enrich' as const,
    label: 'Verrijken',
    description: 'Alleen lege velden invullen, bestaande waarden behouden.',
    icon: Sparkles,
  },
  {
    value: 'replace' as const,
    label: 'Vervangen',
    description: 'Alle velden overschrijven met de gegevens uit het bestand.',
    icon: RefreshCw,
  },
]
</script>

<template>
  <div class="import-wizard">
    <!-- ── Step indicator ── -->
    <div class="relative mb-8">
      <div class="flex items-center justify-between relative z-10">
        <template v-for="(label, i) in stepLabels" :key="i">
          <div class="flex flex-col items-center gap-1.5" style="min-width: 80px">
            <div
              class="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-500"
              :class="stepCircleClass(i + 1)"
            >
              <Transition name="step-check" mode="out-in">
                <Check v-if="step > i + 1" :size="16" :key="'done-' + i" />
                <span v-else :key="'num-' + i">{{ i + 1 }}</span>
              </Transition>
            </div>
            <span
              class="text-xs font-medium transition-colors duration-300 hidden md:block text-center"
              :class="step >= i + 1 ? 'text-navy-900' : 'text-muted'"
            >
              {{ label }}
            </span>
          </div>
        </template>
      </div>
      <!-- Progress track -->
      <div class="absolute top-[18px] left-[40px] right-[40px] h-0.5 bg-navy-100 z-0">
        <div
          class="h-full bg-accent-700 rounded-full transition-all duration-700 ease-out"
          :style="{ width: progressPercent + '%' }"
        />
      </div>
    </div>

    <!-- Error -->
    <Transition name="fade-slide">
      <div v-if="error" :class="theme.alert.error" class="flex items-start gap-2">
        <AlertCircle :size="16" class="shrink-0 mt-0.5" />
        <span>{{ error }}</span>
      </div>
    </Transition>

    <!-- ═══════════ Step 1: Upload ═══════════ -->
    <Transition name="wizard-step" mode="out-in">
      <div v-if="step === 1" key="step-1">
        <div
          class="relative border-2 border-dashed rounded-2xl transition-all duration-300 overflow-hidden"
          :class="[
            dragOver
              ? 'border-accent-600 bg-accent-50/50 scale-[1.01]'
              : 'border-navy-200 bg-white hover:border-navy-300',
            selectedFile ? 'py-8 px-6' : 'py-16 px-8',
          ]"
          @dragover.prevent="dragOver = true"
          @dragleave="dragOver = false"
          @drop.prevent="onDrop"
        >
          <!-- Upload progress overlay -->
          <Transition name="fade">
            <div
              v-if="loading"
              class="absolute inset-0 bg-white/90 flex flex-col items-center justify-center z-10"
            >
              <div class="w-16 h-16 rounded-full bg-accent-50 flex items-center justify-center mb-4 upload-pulse">
                <Upload :size="28" class="text-accent-700" />
              </div>
              <div class="w-48 h-1.5 bg-navy-100 rounded-full overflow-hidden mb-2">
                <div
                  class="h-full bg-accent-700 rounded-full transition-all duration-300"
                  :style="{ width: uploadProgress + '%' }"
                />
              </div>
              <p :class="theme.text.muted" class="text-sm">Bestand verwerken...</p>
            </div>
          </Transition>

          <!-- Empty state -->
          <div v-if="!selectedFile" class="text-center">
            <div class="w-20 h-20 rounded-2xl bg-navy-50 flex items-center justify-center mx-auto mb-5">
              <FileSpreadsheet :size="36" class="text-navy-300" />
            </div>
            <p :class="theme.text.h3" class="mb-1">Sleep je bestand hierheen</p>
            <p :class="theme.text.muted" class="mb-6">of klik om te selecteren</p>
            <label :class="[theme.btn.primarySm, 'cursor-pointer inline-flex items-center gap-2']">
              <Upload :size="16" />
              Bestand kiezen
              <input type="file" accept=".xlsx,.xls,.csv" class="hidden" @change="onFileInput" />
            </label>
            <p :class="theme.text.muted" class="mt-4 text-xs">
              Ondersteund: .xlsx, .xls, .csv (max 5MB)
            </p>
          </div>

          <!-- File selected -->
          <div v-else class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-xl bg-green-50 flex items-center justify-center shrink-0">
              <FileSpreadsheet :size="24" class="text-green-600" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="font-medium text-navy-900 truncate">{{ selectedFile.name }}</p>
              <p :class="theme.text.muted" class="text-xs">
                {{ (selectedFile.size / 1024).toFixed(0) }} KB
              </p>
            </div>
            <button
              @click="selectedFile = null; error = null"
              class="p-2 rounded-lg hover:bg-navy-50 transition-colors"
            >
              <X :size="18" class="text-navy-400" />
            </button>
          </div>
        </div>

        <div class="flex justify-end mt-8">
          <button
            @click="uploadAndPreview"
            :disabled="!selectedFile || loading"
            :class="[theme.btn.primarySm, 'flex items-center gap-2 disabled:opacity-40']"
          >
            Volgende
            <ArrowRight :size="16" />
          </button>
        </div>
      </div>
    </Transition>

    <!-- ═══════════ Step 2: Mapping ═══════════ -->
    <Transition name="wizard-step" mode="out-in">
      <div v-if="step === 2 && preview" key="step-2">
        <!-- Summary bar -->
        <div class="flex flex-wrap items-center gap-4 mb-5">
          <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-lg bg-accent-50 flex items-center justify-center">
              <FileSpreadsheet :size="16" class="text-accent-700" />
            </div>
            <div>
              <p class="text-sm font-medium text-navy-900">
                {{ preview.total_rows }} rijen gevonden
              </p>
              <p :class="theme.text.muted" class="text-xs">
                {{ mappedCount }}/{{ preview.detected_headers.length }} kolommen gekoppeld
              </p>
            </div>
          </div>
          <Transition name="fade-slide">
            <div
              v-if="!requiredFieldsMapped"
              class="flex items-center gap-1.5 text-red-600 text-xs ml-auto"
            >
              <AlertCircle :size="14" />
              Verplichte velden ontbreken
            </div>
          </Transition>
        </div>

        <!-- Mapping cards -->
        <div class="space-y-2 mb-8">
          <div
            v-for="header in preview.detected_headers"
            :key="header"
            class="mapping-card rounded-xl border transition-all duration-200"
            :class="
              columnMapping[header]
                ? 'border-green-200 bg-green-50/30'
                : 'border-navy-100 bg-white hover:border-navy-200'
            "
          >
            <div class="flex items-center gap-4 px-4 py-3">
              <!-- Source column -->
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-navy-900 truncate">{{ header }}</p>
                <p :class="theme.text.muted" class="text-xs truncate">
                  {{ preview.preview_rows[0]?.[header] ?? '—' }}
                </p>
              </div>

              <ArrowRight
                :size="16"
                class="shrink-0"
                :class="columnMapping[header] ? 'text-green-500' : 'text-navy-200'"
              />

              <!-- Target field -->
              <div class="flex-1 min-w-0">
                <select
                  :value="columnMapping[header] || ''"
                  @change="setMapping(header, ($event.target as HTMLSelectElement).value)"
                  class="w-full px-3 py-2 border rounded-lg text-sm bg-white outline-none transition-all"
                  :class="
                    columnMapping[header]
                      ? 'border-green-300 focus:ring-2 focus:ring-green-200'
                      : 'border-navy-200 focus:ring-2 focus:ring-accent-200'
                  "
                >
                  <option value="">— Overslaan —</option>
                  <option
                    v-for="field in availableFieldsForHeader(header)"
                    :key="field.name"
                    :value="field.name"
                  >
                    {{ field.label }}{{ field.required ? ' *' : '' }}
                  </option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <!-- Duplicate strategy cards -->
        <div class="mb-8">
          <h4 :class="[theme.text.h4, 'mb-3']">Hoe omgaan met duplicaten?</h4>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <button
              v-for="opt in strategyOptions"
              :key="opt.value"
              @click="duplicateStrategy = opt.value"
              class="text-left p-4 rounded-xl border-2 transition-all duration-200"
              :class="
                duplicateStrategy === opt.value
                  ? 'border-accent-600 bg-accent-50/50 shadow-sm'
                  : 'border-navy-100 bg-white hover:border-navy-200'
              "
            >
              <div class="flex items-center gap-2 mb-2">
                <div
                  class="w-8 h-8 rounded-lg flex items-center justify-center"
                  :class="
                    duplicateStrategy === opt.value
                      ? 'bg-accent-100 text-accent-700'
                      : 'bg-navy-50 text-navy-400'
                  "
                >
                  <component :is="opt.icon" :size="16" />
                </div>
                <span
                  class="font-medium text-sm"
                  :class="duplicateStrategy === opt.value ? 'text-accent-700' : 'text-navy-900'"
                >
                  {{ opt.label }}
                </span>
              </div>
              <p :class="theme.text.muted" class="text-xs leading-relaxed">
                {{ opt.description }}
              </p>
            </button>
          </div>
        </div>

        <div class="flex justify-between">
          <button :class="theme.btn.ghost" @click="step = 1; preview = null; error = null">
            <ArrowLeft :size="16" class="inline -mt-0.5 mr-1" />
            Terug
          </button>
          <button
            @click="step = 3"
            :disabled="!requiredFieldsMapped"
            :class="[theme.btn.primarySm, 'flex items-center gap-2 disabled:opacity-40']"
          >
            Volgende
            <ArrowRight :size="16" />
          </button>
        </div>
      </div>
    </Transition>

    <!-- ═══════════ Step 3: Confirm ═══════════ -->
    <Transition name="wizard-step" mode="out-in">
      <div v-if="step === 3 && preview" key="step-3">
        <!-- Summary badges -->
        <div class="flex flex-wrap gap-2.5 mb-6">
          <div
            class="flex items-center gap-2 px-4 py-2 rounded-full bg-accent-50 text-accent-700"
          >
            <FileSpreadsheet :size="14" />
            <span class="text-sm font-medium">{{ preview.total_rows }} rijen</span>
          </div>
          <div class="flex items-center gap-2 px-4 py-2 rounded-full bg-green-50 text-green-700">
            <Check :size="14" />
            <span class="text-sm font-medium">{{ mappedCount }} gekoppeld</span>
          </div>
          <div
            v-if="unmappedHeaders.length > 0"
            class="flex items-center gap-2 px-4 py-2 rounded-full bg-navy-50 text-navy-600"
          >
            <span class="text-sm font-medium">{{ unmappedHeaders.length }} overgeslagen</span>
          </div>
          <div class="flex items-center gap-2 px-4 py-2 rounded-full bg-navy-50 text-navy-600">
            <component
              :is="strategyOptions.find((s) => s.value === duplicateStrategy)?.icon"
              :size="14"
            />
            <span class="text-sm font-medium">
              {{ strategyOptions.find((s) => s.value === duplicateStrategy)?.label }}
            </span>
          </div>
        </div>

        <!-- Mapping overview -->
        <div :class="[theme.card.base, 'overflow-hidden mb-6']">
          <div :class="theme.list.sectionHeader">
            <h4 :class="theme.text.h4">Koppeling overzicht</h4>
          </div>
          <div class="p-4 space-y-2">
            <div
              v-for="(field, header) in columnMapping"
              :key="header"
              class="flex items-center gap-3 text-sm"
            >
              <span class="text-navy-700 font-medium min-w-0 truncate flex-1">{{ header }}</span>
              <ArrowRight :size="14" class="text-navy-300 shrink-0" />
              <span :class="[theme.badge.base, theme.badge.success]">
                {{ getFieldLabel(field) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Preview table -->
        <div :class="[theme.card.base, 'overflow-hidden mb-6']">
          <div :class="theme.list.sectionHeader">
            <h4 :class="theme.text.h4">Preview</h4>
            <span :class="theme.text.muted" class="text-xs">
              {{ (previewPage - 1) * previewPerPage + 1 }}–{{
                Math.min(previewPage * previewPerPage, preview.preview_rows.length)
              }}
              van {{ preview.preview_rows.length }}
            </span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-xs">
              <thead>
                <tr class="border-b border-navy-100">
                  <th
                    v-for="(field, header) in columnMapping"
                    :key="header"
                    class="px-3 py-2.5 text-left font-medium text-navy-700 whitespace-nowrap"
                  >
                    {{ getFieldLabel(field) }}
                  </th>
                </tr>
              </thead>
              <tbody :class="theme.list.divider">
                <tr
                  v-for="(row, i) in previewRows"
                  :key="i"
                  class="hover:bg-surface transition-colors"
                >
                  <td
                    v-for="(field, header) in columnMapping"
                    :key="header"
                    class="px-3 py-2 text-body whitespace-nowrap"
                  >
                    {{ row[header] ?? '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div
            v-if="previewTotalPages > 1"
            class="flex items-center justify-center gap-2 py-3 border-t border-navy-100"
          >
            <button
              @click="previewPage--"
              :disabled="previewPage <= 1"
              class="p-1.5 rounded-lg hover:bg-surface disabled:opacity-30 transition-colors"
            >
              <ArrowLeft :size="14" />
            </button>
            <span class="text-xs text-navy-700">{{ previewPage }} / {{ previewTotalPages }}</span>
            <button
              @click="previewPage++"
              :disabled="previewPage >= previewTotalPages"
              class="p-1.5 rounded-lg hover:bg-surface disabled:opacity-30 transition-colors"
            >
              <ArrowRight :size="14" />
            </button>
          </div>
        </div>

        <div class="flex justify-between">
          <button :class="theme.btn.ghost" @click="step = 2; error = null">
            <ArrowLeft :size="16" class="inline -mt-0.5 mr-1" />
            Terug
          </button>
          <button
            @click="executeImport"
            :disabled="loading"
            :class="[theme.btn.primarySm, 'flex items-center gap-2 disabled:opacity-40']"
          >
            <Loader2 v-if="loading" :size="16" class="animate-spin" />
            <template v-else>
              <Check :size="16" />
              Importeren
            </template>
          </button>
        </div>
      </div>
    </Transition>

    <!-- ═══════════ Step 4: Result ═══════════ -->
    <Transition name="wizard-step" mode="out-in">
      <div v-if="step === 4 && result" key="step-4">
        <!-- Success / Warning state -->
        <div v-if="!rollbackDone" class="text-center py-4">
          <div class="mx-auto mb-6" :class="showCelebration ? 'celebration-enter' : 'opacity-0'">
            <div
              class="w-20 h-20 rounded-full flex items-center justify-center mx-auto"
              :class="result.error_count > 0 ? 'bg-yellow-100' : 'bg-green-100'"
            >
              <Check v-if="result.error_count === 0" :size="36" class="text-green-600" />
              <AlertCircle v-else :size="36" class="text-yellow-600" />
            </div>
          </div>

          <h3 :class="[theme.text.h2, 'mb-2']">
            {{ result.error_count === 0 ? 'Import succesvol!' : 'Import voltooid met waarschuwingen' }}
          </h3>
          <p :class="[theme.text.muted, 'mb-8']">{{ result.file_name }}</p>

          <!-- Animated counters -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div
              class="result-card p-5 rounded-xl bg-green-50 border border-green-100"
              style="animation-delay: 200ms"
            >
              <p class="text-3xl font-bold text-green-700 tabular-nums">
                {{ animatedImported }}
              </p>
              <p class="text-sm text-green-600 mt-1">Nieuw</p>
            </div>
            <div
              class="result-card p-5 rounded-xl bg-accent-50 border border-accent-100"
              style="animation-delay: 350ms"
            >
              <p class="text-3xl font-bold text-accent-700 tabular-nums">
                {{ animatedUpdated }}
              </p>
              <p class="text-sm text-accent-600 mt-1">Bijgewerkt</p>
            </div>
            <div
              class="result-card p-5 rounded-xl bg-navy-50 border border-navy-100"
              style="animation-delay: 500ms"
            >
              <p class="text-3xl font-bold text-navy-600 tabular-nums">
                {{ animatedSkipped }}
              </p>
              <p class="text-sm text-navy-500 mt-1">Overgeslagen</p>
            </div>
            <div
              class="result-card p-5 rounded-xl border"
              :class="
                result.error_count > 0
                  ? 'bg-red-50 border-red-100'
                  : 'bg-navy-50 border-navy-100'
              "
              style="animation-delay: 650ms"
            >
              <p
                class="text-3xl font-bold tabular-nums"
                :class="result.error_count > 0 ? 'text-red-700' : 'text-navy-600'"
              >
                {{ animatedErrors }}
              </p>
              <p
                class="text-sm mt-1"
                :class="result.error_count > 0 ? 'text-red-600' : 'text-navy-500'"
              >
                Fouten
              </p>
            </div>
          </div>
        </div>

        <!-- Rollback done -->
        <div v-else class="text-center py-8">
          <div
            class="w-16 h-16 rounded-full bg-yellow-100 flex items-center justify-center mx-auto mb-4"
          >
            <RotateCcw :size="28" class="text-yellow-600" />
          </div>
          <h3 :class="[theme.text.h2, 'mb-2']">Import teruggedraaid</h3>
          <p :class="[theme.text.body, 'max-w-md mx-auto']">
            De import is succesvol teruggedraaid. Geïmporteerde leerlingen zijn gedeactiveerd en
            bijgewerkte gegevens zijn hersteld.
          </p>
        </div>

        <div class="flex justify-between">
          <button
            v-if="!rollbackDone && result.status === 'completed'"
            @click="rollback"
            :disabled="rollbackLoading"
            :class="[theme.btn.dangerOutline, 'flex items-center gap-2']"
          >
            <Loader2 v-if="rollbackLoading" :size="16" class="animate-spin" />
            <RotateCcw v-else :size="16" />
            Terugdraaien
          </button>
          <div v-else />
          <button :class="theme.btn.primarySm" @click="finish">Sluiten</button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* ── Step transitions ── */
.wizard-step-enter-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.wizard-step-leave-active {
  transition: all 0.2s ease-in;
}
.wizard-step-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.wizard-step-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* ── Fade slide (errors) ── */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}
.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ── Fade (overlay) ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ── Step check icon swap ── */
.step-check-enter-active {
  transition: all 0.3s ease;
}
.step-check-leave-active {
  transition: all 0.15s ease;
}
.step-check-enter-from {
  opacity: 0;
  transform: scale(0.5);
}
.step-check-leave-to {
  opacity: 0;
  transform: scale(0.5);
}

/* ── Upload pulse ── */
.upload-pulse {
  animation: uploadPulse 2s ease-in-out infinite;
}
@keyframes uploadPulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.08);
    opacity: 0.8;
  }
}

/* ── Celebration scale-in ── */
.celebration-enter {
  animation: scaleIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}
@keyframes scaleIn {
  from {
    transform: scale(0);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

/* ── Result cards fade-in-up ── */
.result-card {
  animation: fadeInUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ── Mapping card hover ── */
.mapping-card {
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.2s ease;
}
.mapping-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
</style>
