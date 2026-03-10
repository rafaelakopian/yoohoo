<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  History,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Loader2,
  FileSpreadsheet,
  Clock,
} from 'lucide-vue-next'
import { importerApi } from '@/api/shared/importer'
import type { ImportBatchResponse, ImportBatchDetailResponse } from '@/types/models'
import { theme } from '@/theme'

const props = defineProps<{
  entityType: string
}>()

const batches = ref<ImportBatchResponse[]>([])
const total = ref(0)
const page = ref(1)
const perPage = 20
const loading = ref(false)
const error = ref<string | null>(null)

// Expandable detail
const expandedBatchId = ref<string | null>(null)
const detailData = ref<Record<string, ImportBatchDetailResponse>>({})
const detailLoading = ref<string | null>(null)

// Rollback
const rollbackLoading = ref<string | null>(null)

onMounted(() => fetchHistory())

async function fetchHistory() {
  loading.value = true
  error.value = null
  try {
    const result = await importerApi.getHistory(props.entityType, page.value, perPage)
    batches.value = result.items
    total.value = result.total
  } catch {
    error.value = 'Kon import-geschiedenis niet laden.'
  } finally {
    loading.value = false
  }
}

async function toggleDetail(batchId: string) {
  if (expandedBatchId.value === batchId) {
    expandedBatchId.value = null
    return
  }
  expandedBatchId.value = batchId
  if (!detailData.value[batchId]) {
    detailLoading.value = batchId
    try {
      detailData.value[batchId] = await importerApi.getBatchDetail(props.entityType, batchId)
    } catch {
      error.value = 'Kon details niet laden.'
      expandedBatchId.value = null
    } finally {
      detailLoading.value = null
    }
  }
}

async function rollback(batchId: string) {
  rollbackLoading.value = batchId
  try {
    await importerApi.rollback(props.entityType, batchId)
    await fetchHistory()
    expandedBatchId.value = null
  } catch {
    error.value = 'Terugdraaien mislukt.'
  } finally {
    rollbackLoading.value = null
  }
}

function statusBadge(status: string): string[] {
  switch (status) {
    case 'completed':
      return [theme.badge.base, theme.badge.success]
    case 'rolled_back':
      return [theme.badge.base, theme.badge.warning]
    case 'failed':
      return [theme.badge.base, theme.badge.error]
    default:
      return [theme.badge.base, theme.badge.default]
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'completed':
      return 'Voltooid'
    case 'rolled_back':
      return 'Teruggedraaid'
    case 'failed':
      return 'Mislukt'
    case 'processing':
      return 'Bezig...'
    default:
      return status
  }
}

function recordStatusBadge(status: string): string[] {
  switch (status) {
    case 'imported':
      return [theme.badge.base, theme.badge.success]
    case 'updated':
      return [theme.badge.base, 'bg-accent-50 text-accent-700 ring-1 ring-accent-200']
    case 'skipped':
      return [theme.badge.base, theme.badge.default]
    case 'error':
      return [theme.badge.base, theme.badge.error]
    case 'rolled_back':
      return [theme.badge.base, theme.badge.warning]
    default:
      return [theme.badge.base, theme.badge.default]
  }
}

function recordStatusLabel(status: string): string {
  switch (status) {
    case 'imported':
      return 'Nieuw'
    case 'updated':
      return 'Bijgewerkt'
    case 'skipped':
      return 'Overgeslagen'
    case 'error':
      return 'Fout'
    case 'rolled_back':
      return 'Teruggedraaid'
    default:
      return status
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('nl-NL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'zojuist'
  if (minutes < 60) return `${minutes} min. geleden`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} uur geleden`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'gisteren'
  return `${days} dagen geleden`
}

function totalPages(): number {
  return Math.max(1, Math.ceil(total.value / perPage))
}
</script>

<template>
  <div>
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <!-- Loading -->
    <div v-if="loading" :class="[theme.card.padded, 'text-center']">
      <Loader2 :size="24" class="mx-auto animate-spin text-navy-300 mb-2" />
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="batches.length === 0" :class="theme.emptyState.wrapper">
      <div :class="theme.emptyState.iconWrap">
        <History :size="24" :class="theme.emptyState.icon" />
      </div>
      <p :class="theme.emptyState.title">Nog geen imports</p>
      <p :class="theme.emptyState.description">
        Importeer een bestand om hier de geschiedenis te zien.
      </p>
    </div>

    <!-- Batch list -->
    <div v-else class="space-y-3">
      <div
        v-for="batch in batches"
        :key="batch.id"
        :class="theme.card.base"
        class="overflow-hidden transition-shadow duration-200"
        :style="expandedBatchId === batch.id ? 'box-shadow: 0 4px 12px rgba(0,0,0,0.06)' : ''"
      >
        <!-- Batch row (clickable) -->
        <button
          class="w-full text-left px-5 py-4 flex items-center gap-4 hover:bg-surface/50 transition-colors"
          @click="toggleDetail(batch.id)"
        >
          <!-- Icon -->
          <div
            class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
            :class="
              batch.status === 'completed'
                ? 'bg-green-50'
                : batch.status === 'rolled_back'
                  ? 'bg-yellow-50'
                  : batch.status === 'failed'
                    ? 'bg-red-50'
                    : 'bg-navy-50'
            "
          >
            <FileSpreadsheet
              :size="20"
              :class="
                batch.status === 'completed'
                  ? 'text-green-600'
                  : batch.status === 'rolled_back'
                    ? 'text-yellow-600'
                    : batch.status === 'failed'
                      ? 'text-red-600'
                      : 'text-navy-400'
              "
            />
          </div>

          <!-- Info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-0.5">
              <p class="text-sm font-medium text-navy-900 truncate">{{ batch.file_name }}</p>
              <span :class="statusBadge(batch.status)">{{ statusLabel(batch.status) }}</span>
            </div>
            <div class="flex items-center gap-3 text-xs">
              <span class="flex items-center gap-1 text-body">
                <Clock :size="12" />
                {{ timeAgo(batch.created_at) }}
              </span>
              <span class="text-body">{{ batch.total_rows }} rijen</span>
              <span class="text-green-600">{{ batch.imported_count }} nieuw</span>
              <span v-if="batch.updated_count > 0" class="text-accent-600">
                {{ batch.updated_count }} bijgewerkt
              </span>
              <span v-if="batch.error_count > 0" class="text-red-600">
                {{ batch.error_count }} fouten
              </span>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-2 shrink-0">
            <button
              v-if="batch.status === 'completed'"
              @click.stop="rollback(batch.id)"
              :disabled="rollbackLoading === batch.id"
              :class="[theme.btn.dangerOutline, 'text-xs px-3 py-1.5']"
            >
              <Loader2
                v-if="rollbackLoading === batch.id"
                :size="14"
                class="inline animate-spin mr-1"
              />
              <RotateCcw v-else :size="14" class="inline mr-1" />
              Terugdraaien
            </button>
            <ChevronDown
              :size="18"
              class="text-navy-400 transition-transform duration-200"
              :class="expandedBatchId === batch.id ? 'rotate-180' : ''"
            />
          </div>
        </button>

        <!-- Expanded detail -->
        <Transition name="expand">
          <div v-if="expandedBatchId === batch.id" class="border-t border-navy-100">
            <!-- Loading -->
            <div v-if="detailLoading === batch.id" class="py-8 text-center">
              <Loader2 :size="20" class="mx-auto animate-spin text-navy-300" />
            </div>

            <!-- Detail content -->
            <div v-else-if="detailData[batch.id]">
              <!-- Summary counts -->
              <div class="grid grid-cols-4 gap-3 p-4 bg-surface/50">
                <div class="text-center">
                  <p class="text-lg font-bold text-green-700">
                    {{ detailData[batch.id].batch.imported_count }}
                  </p>
                  <p class="text-xs text-green-600">Nieuw</p>
                </div>
                <div class="text-center">
                  <p class="text-lg font-bold text-accent-700">
                    {{ detailData[batch.id].batch.updated_count }}
                  </p>
                  <p class="text-xs text-accent-600">Bijgewerkt</p>
                </div>
                <div class="text-center">
                  <p class="text-lg font-bold text-navy-600">
                    {{ detailData[batch.id].batch.skipped_count }}
                  </p>
                  <p class="text-xs text-navy-500">Overgeslagen</p>
                </div>
                <div class="text-center">
                  <p
                    class="text-lg font-bold"
                    :class="
                      detailData[batch.id].batch.error_count > 0
                        ? 'text-red-700'
                        : 'text-navy-600'
                    "
                  >
                    {{ detailData[batch.id].batch.error_count }}
                  </p>
                  <p
                    class="text-xs"
                    :class="
                      detailData[batch.id].batch.error_count > 0
                        ? 'text-red-600'
                        : 'text-navy-500'
                    "
                  >
                    Fouten
                  </p>
                </div>
              </div>

              <!-- Records table -->
              <div class="overflow-x-auto">
                <table class="w-full text-xs">
                  <thead>
                    <tr class="border-b border-navy-100 text-left bg-surface/30">
                      <th class="px-4 py-2.5 font-medium text-navy-700 w-16">Rij</th>
                      <th class="px-4 py-2.5 font-medium text-navy-700 w-28">Status</th>
                      <th class="px-4 py-2.5 font-medium text-navy-700">Data</th>
                      <th class="px-4 py-2.5 font-medium text-navy-700 w-48">Foutmelding</th>
                    </tr>
                  </thead>
                  <tbody :class="theme.list.divider">
                    <tr
                      v-for="record in detailData[batch.id].records"
                      :key="record.id"
                      class="hover:bg-surface/30 transition-colors"
                    >
                      <td class="px-4 py-2 text-navy-700 font-medium">{{ record.row_number }}</td>
                      <td class="px-4 py-2">
                        <span :class="recordStatusBadge(record.status)">
                          {{ recordStatusLabel(record.status) }}
                        </span>
                      </td>
                      <td class="px-4 py-2 text-body max-w-xs truncate">
                        {{
                          Object.values(record.mapped_data ?? record.raw_data)
                            .filter(Boolean)
                            .join(', ')
                        }}
                      </td>
                      <td class="px-4 py-2 text-red-600 text-xs">
                        {{ record.error_message ?? '—' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- Detail metadata -->
              <div
                class="flex items-center justify-between px-4 py-2.5 border-t border-navy-100 bg-surface/30"
              >
                <span :class="theme.text.muted" class="text-xs">
                  {{ formatDate(batch.created_at) }}
                </span>
                <span :class="theme.text.muted" class="text-xs">
                  {{ detailData[batch.id].total_records }} records totaal
                </span>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <!-- Pagination -->
      <div v-if="total > perPage" class="flex items-center justify-between pt-2">
        <p :class="theme.text.muted" class="text-sm">
          {{ (page - 1) * perPage + 1 }}–{{ Math.min(page * perPage, total) }} van {{ total }}
        </p>
        <div class="flex items-center gap-2">
          <button
            @click="page--; fetchHistory()"
            :disabled="page <= 1"
            class="p-1.5 rounded-lg hover:bg-surface disabled:opacity-30 transition-colors"
          >
            <ChevronLeft :size="16" />
          </button>
          <span class="text-sm text-navy-700">{{ page }} / {{ totalPages() }}</span>
          <button
            @click="page++; fetchHistory()"
            :disabled="page >= totalPages()"
            class="p-1.5 rounded-lg hover:bg-surface disabled:opacity-30 transition-colors"
          >
            <ChevronRight :size="16" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Expandable row transition ── */
.expand-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}
.expand-leave-active {
  transition: all 0.2s ease-in;
  overflow: hidden;
}
.expand-enter-from {
  opacity: 0;
  max-height: 0;
}
.expand-enter-to {
  opacity: 1;
  max-height: 600px;
}
.expand-leave-from {
  opacity: 1;
  max-height: 600px;
}
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
