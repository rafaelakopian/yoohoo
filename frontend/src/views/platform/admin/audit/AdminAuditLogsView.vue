<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { Search, ChevronLeft, ChevronRight, ChevronDown, ChevronUp } from 'lucide-vue-next'
import { theme } from '@/theme'
import { adminApi, type AuditLogItem } from '@/api/platform/admin'

const logs = ref<AuditLogItem[]>([])
const totalLogs = ref(0)
const loading = ref(true)
const currentPage = ref(0)
const pageSize = 50

// Filters
const filterAction = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')
const searchTimeout = ref<ReturnType<typeof setTimeout> | null>(null)

// Expandable details
const expandedId = ref<string | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(totalLogs.value / pageSize)))

onMounted(() => fetchLogs())

async function fetchLogs() {
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      skip: currentPage.value * pageSize,
      limit: pageSize,
    }
    if (filterAction.value) params.action = filterAction.value
    if (filterDateFrom.value) params.date_from = new Date(filterDateFrom.value).toISOString()
    if (filterDateTo.value) params.date_to = new Date(filterDateTo.value + 'T23:59:59').toISOString()

    const result = await adminApi.getAuditLogs(params as any)
    logs.value = result.items
    totalLogs.value = result.total
  } catch {
    // Handled silently
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  if (searchTimeout.value) clearTimeout(searchTimeout.value)
  searchTimeout.value = setTimeout(() => {
    currentPage.value = 0
    fetchLogs()
  }, 300)
}

function applyDateFilter() {
  currentPage.value = 0
  fetchLogs()
}

function goToPage(page: number) {
  currentPage.value = page
  fetchLogs()
}

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

function formatDate(d: string) {
  return new Date(d).toLocaleString('nl-NL', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDetails(details: Record<string, unknown> | null): string {
  if (!details) return '-'
  return JSON.stringify(details, null, 2)
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 :class="theme.text.h2">Audit logs</h2>
        <p :class="[theme.text.body, 'mt-1']">Beveiligingsgebeurtenissen en gebruikersacties</p>
      </div>
    </div>

    <!-- Filters -->
    <div :class="[theme.card.base, 'mb-4']">
      <div class="p-4 flex flex-wrap gap-4 items-end">
        <div class="flex-1 min-w-48">
          <label :class="theme.form.label">Actie</label>
          <div class="relative">
            <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-body" />
            <input
              v-model="filterAction"
              @input="onFilterChange"
              type="text"
              placeholder="Zoek op actie..."
              :class="[theme.form.input, 'pl-10']"
            />
          </div>
        </div>
        <div>
          <label :class="theme.form.label">Vanaf</label>
          <input
            v-model="filterDateFrom"
            @change="applyDateFilter"
            type="date"
            :class="theme.form.input"
          />
        </div>
        <div>
          <label :class="theme.form.label">Tot</label>
          <input
            v-model="filterDateTo"
            @change="applyDateFilter"
            type="date"
            :class="theme.form.input"
          />
        </div>
      </div>
    </div>

    <!-- Table -->
    <div :class="theme.card.base">
      <div v-if="loading" :class="theme.list.empty">
        <p :class="theme.text.muted">Laden...</p>
      </div>

      <div v-else-if="logs.length === 0" :class="theme.list.empty">
        <p :class="theme.text.muted">Geen audit logs gevonden</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-navy-100 text-left">
              <th class="px-6 py-3 font-medium text-navy-700">Datum</th>
              <th class="px-6 py-3 font-medium text-navy-700">Gebruiker</th>
              <th class="px-6 py-3 font-medium text-navy-700">Actie</th>
              <th class="px-6 py-3 font-medium text-navy-700">IP</th>
              <th class="px-6 py-3 font-medium text-navy-700 text-right">Details</th>
            </tr>
          </thead>
          <tbody :class="theme.list.divider">
            <template v-for="log in logs" :key="log.id">
              <tr class="hover:bg-surface transition-colors">
                <td class="px-6 py-3 text-body whitespace-nowrap">{{ formatDate(log.created_at) }}</td>
                <td class="px-6 py-3">
                  <span v-if="log.user_email" class="text-navy-900">{{ log.user_email }}</span>
                  <span v-else class="text-body">Systeem</span>
                </td>
                <td class="px-6 py-3">
                  <span :class="[theme.badge.base, theme.badge.info]">{{ log.action }}</span>
                </td>
                <td class="px-6 py-3 text-body font-mono text-xs">{{ log.ip_address || '-' }}</td>
                <td class="px-6 py-3 text-right">
                  <button
                    v-if="log.details"
                    @click="toggleExpand(log.id)"
                    class="text-accent-700 hover:text-accent-800 inline-flex items-center gap-1 text-xs"
                  >
                    <component :is="expandedId === log.id ? ChevronUp : ChevronDown" :size="14" />
                    {{ expandedId === log.id ? 'Verbergen' : 'Tonen' }}
                  </button>
                  <span v-else class="text-body text-xs">-</span>
                </td>
              </tr>
              <tr v-if="expandedId === log.id && log.details">
                <td colspan="5" class="px-6 py-3 bg-surface">
                  <pre class="text-xs text-navy-700 font-mono whitespace-pre-wrap">{{ formatDetails(log.details) }}</pre>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-between px-6 py-3 border-t border-navy-100">
          <p class="text-xs text-body">{{ totalLogs }} log{{ totalLogs === 1 ? '' : 's' }} totaal</p>
          <div class="flex items-center gap-1">
            <button
              @click="goToPage(currentPage - 1)"
              :disabled="currentPage === 0"
              class="p-1.5 rounded text-body hover:text-navy-900 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft :size="16" />
            </button>
            <span class="text-xs text-navy-700 px-2">{{ currentPage + 1 }} / {{ totalPages }}</span>
            <button
              @click="goToPage(currentPage + 1)"
              :disabled="currentPage >= totalPages - 1"
              class="p-1.5 rounded text-body hover:text-navy-900 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight :size="16" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
