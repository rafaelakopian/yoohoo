<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import {
  ScrollText, Search, ChevronLeft, ChevronRight, ChevronDown,
  Shield, User, Globe, Filter, Clock,
} from 'lucide-vue-next'
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

const hasActiveFilters = computed(() =>
  filterAction.value !== '' || filterDateFrom.value !== '' || filterDateTo.value !== ''
)

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

    // Params built dynamically from filter refs — API type expects fixed shape
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

function clearFilters() {
  filterAction.value = ''
  filterDateFrom.value = ''
  filterDateTo.value = ''
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

function timeAgo(d: string): string {
  const diff = Date.now() - new Date(d).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'zojuist'
  if (mins < 60) return `${mins}m geleden`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}u geleden`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d geleden`
  return ''
}

function formatDetails(details: Record<string, unknown> | null): string {
  if (!details) return '-'
  return JSON.stringify(details, null, 2)
}

// Action category coloring
function actionCategory(action: string): string {
  if (action.startsWith('auth.')) return 'accent'
  if (action.startsWith('security.') || action.startsWith('session.')) return 'red'
  if (action.startsWith('tenant.') || action.startsWith('org.')) return 'green'
  if (action.startsWith('billing.') || action.startsWith('invoice.')) return 'purple'
  if (action.startsWith('user.') || action.startsWith('member.')) return 'blue'
  return 'default'
}

function actionDotColor(action: string): string {
  const cat = actionCategory(action)
  const dots: Record<string, string> = {
    accent: 'bg-accent-500',
    red: 'bg-red-500',
    green: 'bg-green-500',
    purple: 'bg-purple-500',
    blue: 'bg-accent-600',
    default: 'bg-navy-400',
  }
  return dots[cat] ?? 'bg-navy-400'
}

function actionBadgeStyle(action: string): string {
  const cat = actionCategory(action)
  const badges: Record<string, string> = {
    accent: 'bg-accent-50 text-accent-700 ring-1 ring-accent-200',
    red: 'bg-red-50 text-red-700 ring-1 ring-red-200',
    green: 'bg-green-50 text-green-700 ring-1 ring-green-200',
    purple: 'bg-purple-50 text-purple-700 ring-1 ring-purple-200',
    blue: 'bg-accent-50 text-accent-700 ring-1 ring-accent-200',
    default: theme.badge.default,
  }
  return badges[cat] ?? theme.badge.default
}

// Page range for pagination
const visiblePages = computed(() => {
  const total = totalPages.value
  const current = currentPage.value
  const pages: number[] = []
  const start = Math.max(0, current - 2)
  const end = Math.min(total - 1, current + 2)
  for (let i = start; i <= end; i++) pages.push(i)
  return pages
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <ScrollText class="w-6 h-6 text-navy-700" />
        <div>
          <h2 :class="theme.text.h2">Audit Logs</h2>
          <p :class="theme.text.muted" class="text-sm mt-0.5">Beveiligingsgebeurtenissen en gebruikersacties</p>
        </div>
      </div>
      <div v-if="!loading && totalLogs > 0" class="text-right">
        <p :class="theme.text.muted" class="text-xs">
          {{ totalLogs.toLocaleString('nl-NL') }} gebeurtenis{{ totalLogs === 1 ? '' : 'sen' }}
        </p>
      </div>
    </div>

    <!-- ──── Filter Bar ──── -->
    <div :class="theme.card.base" class="p-4">
      <div class="flex flex-wrap items-end gap-3">
        <div class="flex-1 min-w-[200px]">
          <label :class="theme.form.label" class="text-xs">Actie</label>
          <div class="relative">
            <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
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
          <label :class="theme.form.label" class="text-xs">Vanaf</label>
          <input
            v-model="filterDateFrom"
            @change="applyDateFilter"
            type="date"
            :class="theme.form.input"
            class="!w-auto"
          />
        </div>
        <div>
          <label :class="theme.form.label" class="text-xs">Tot</label>
          <input
            v-model="filterDateTo"
            @change="applyDateFilter"
            type="date"
            :class="theme.form.input"
            class="!w-auto"
          />
        </div>
        <button
          v-if="hasActiveFilters"
          :class="theme.btn.link"
          class="flex items-center gap-1 pb-2.5"
          @click="clearFilters"
        >
          <Filter :size="14" />
          Wis filters
        </button>
      </div>
    </div>

    <!-- ──── Loading Skeleton ──── -->
    <template v-if="loading">
      <div class="overflow-hidden rounded-xl border border-navy-100">
        <!-- Header row skeleton -->
        <div class="bg-surface px-4 h-[42px]" />
        <!-- Row skeletons -->
        <div class="bg-white divide-y divide-navy-50">
          <div v-for="n in 8" :key="n" class="flex items-center gap-4 px-4 py-3.5 skeleton-row-enter" :style="{ animationDelay: n * 60 + 'ms' }">
            <div class="h-4 w-28 bg-navy-100 rounded animate-pulse" />
            <div class="h-4 w-36 bg-navy-100 rounded animate-pulse" />
            <div class="h-5 w-24 bg-navy-100 rounded-full animate-pulse" />
            <div class="flex-1" />
            <div class="h-4 w-20 bg-navy-100 rounded animate-pulse hidden md:block" />
            <div class="w-4 h-4 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </div>
    </template>

    <!-- ──── Content ──── -->
    <template v-else>
      <!-- Empty state -->
      <div v-if="logs.length === 0" :class="theme.card.base">
        <div :class="theme.emptyState.wrapper">
          <div :class="theme.emptyState.iconWrap">
            <Shield :class="theme.emptyState.icon" :size="24" />
          </div>
          <p :class="theme.emptyState.title">Geen audit logs gevonden</p>
          <p :class="theme.emptyState.description">
            {{ hasActiveFilters ? 'Pas de filters aan om meer resultaten te zien.' : 'Er zijn nog geen beveiligingsgebeurtenissen gelogd.' }}
          </p>
        </div>
      </div>

      <!-- Table -->
      <div v-else class="overflow-hidden rounded-xl border border-navy-100">
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-navy-200 text-sm table-fixed">
            <colgroup>
              <col style="width: 18%" />
              <col style="width: 22%" />
              <col style="width: 28%" />
              <col style="width: 14%" />
              <col style="width: 18%" />
            </colgroup>
            <thead class="bg-surface text-navy-700 font-semibold">
              <tr>
                <th class="px-4 h-[42px] text-left">Datum</th>
                <th class="px-4 h-[42px] text-left">Gebruiker</th>
                <th class="px-4 h-[42px] text-left">Actie</th>
                <th class="px-4 h-[42px] text-left hidden md:table-cell">IP-adres</th>
                <th class="px-4 h-[42px] text-right">Details</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-navy-50">
              <template v-for="log in logs" :key="log.id">
                <tr class="hover:bg-surface transition-colors">
                  <!-- Date -->
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-2">
                      <Clock :size="14" class="shrink-0 text-navy-300" />
                      <div>
                        <p class="text-navy-900 text-xs whitespace-nowrap">{{ formatDate(log.created_at) }}</p>
                        <p v-if="timeAgo(log.created_at)" :class="theme.text.muted" class="text-[10px]">{{ timeAgo(log.created_at) }}</p>
                      </div>
                    </div>
                  </td>

                  <!-- User -->
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-2 min-w-0">
                      <div
                        class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold"
                        :class="log.user_email ? 'bg-accent-50 text-accent-700' : 'bg-navy-50 text-navy-400'"
                      >
                        <User :size="12" v-if="!log.user_email" />
                        <template v-else>{{ log.user_email[0].toUpperCase() }}</template>
                      </div>
                      <span v-if="log.user_email" class="text-navy-900 truncate text-xs">{{ log.user_email }}</span>
                      <span v-else :class="theme.text.muted" class="text-xs">Systeem</span>
                    </div>
                  </td>

                  <!-- Action -->
                  <td class="px-4 py-3">
                    <span :class="[theme.badge.base, actionBadgeStyle(log.action)]" class="inline-flex items-center gap-1.5">
                      <span class="w-1.5 h-1.5 rounded-full" :class="actionDotColor(log.action)" />
                      {{ log.action }}
                    </span>
                  </td>

                  <!-- IP -->
                  <td class="px-4 py-3 hidden md:table-cell">
                    <div v-if="log.ip_address" class="flex items-center gap-1.5">
                      <Globe :size="12" class="text-navy-300 shrink-0" />
                      <span class="font-mono text-xs text-navy-600">{{ log.ip_address }}</span>
                    </div>
                    <span v-else :class="theme.text.muted" class="text-xs">&mdash;</span>
                  </td>

                  <!-- Details toggle -->
                  <td class="px-4 py-3 text-right">
                    <button
                      v-if="log.details"
                      @click="toggleExpand(log.id)"
                      class="inline-flex items-center gap-1 text-xs font-medium text-accent-700 hover:text-accent-800 transition-colors"
                    >
                      <ChevronDown
                        :size="14"
                        class="transition-transform duration-200"
                        :class="expandedId === log.id ? 'rotate-0' : '-rotate-90'"
                      />
                      {{ expandedId === log.id ? 'Verbergen' : 'Tonen' }}
                    </button>
                    <span v-else :class="theme.text.muted" class="text-xs">&mdash;</span>
                  </td>
                </tr>

                <!-- Expanded detail row -->
                <tr v-if="expandedId === log.id && log.details">
                  <td colspan="5" class="px-4 py-3 bg-surface border-t border-navy-100">
                    <pre class="text-xs text-navy-700 font-mono whitespace-pre-wrap bg-white p-3 rounded-lg border border-navy-100 overflow-x-auto">{{ formatDetails(log.details) }}</pre>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-between px-4 py-3 border-t border-navy-200 bg-surface">
          <p :class="theme.text.muted" class="text-xs">
            {{ (currentPage * pageSize + 1).toLocaleString('nl-NL') }}&ndash;{{ Math.min((currentPage + 1) * pageSize, totalLogs).toLocaleString('nl-NL') }}
            van {{ totalLogs.toLocaleString('nl-NL') }}
          </p>
          <div class="flex items-center gap-1">
            <button
              @click="goToPage(currentPage - 1)"
              :disabled="currentPage === 0"
              class="p-1.5 rounded-lg hover:bg-navy-100 text-navy-400 hover:text-navy-700 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft :size="16" />
            </button>
            <template v-for="page in visiblePages" :key="page">
              <button
                @click="goToPage(page)"
                class="w-8 h-8 rounded-lg text-xs font-medium transition-colors"
                :class="page === currentPage
                  ? 'bg-accent-700 text-white'
                  : 'text-navy-600 hover:bg-navy-100'"
              >
                {{ page + 1 }}
              </button>
            </template>
            <button
              @click="goToPage(currentPage + 1)"
              :disabled="currentPage >= totalPages - 1"
              class="p-1.5 rounded-lg hover:bg-navy-100 text-navy-400 hover:text-navy-700 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight :size="16" />
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
@keyframes skeletonFadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.skeleton-row-enter {
  opacity: 0;
  animation: skeletonFadeIn 0.3s ease forwards;
}
</style>
