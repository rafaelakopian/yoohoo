<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Activity, ChevronDown, Clock, AlertTriangle,
  CheckCircle2, XCircle, RefreshCw, Filter, Timer,
  Hash, Calendar, Play, Square, RotateCcw,
} from 'lucide-vue-next'
import { theme } from '@/theme'
import { getJobMonitor, type JobInfo, type JobQueueSummary } from '@/api/platform/operations'

const summary = ref<JobQueueSummary | null>(null)
const loading = ref(true)
const error = ref('')
const autoRefresh = ref(true)
const functionFilter = ref('')
const statusFilter = ref<string>('all')
const expandedJobId = ref<string | null>(null)

// Date filter defaults: last 30 days
function toDateStr(d: Date): string {
  return d.toISOString().slice(0, 10)
}
const now = new Date()
const thirtyDaysAgo = new Date(now)
thirtyDaysAgo.setDate(now.getDate() - 30)
const dateFrom = ref(toDateStr(thirtyDaysAgo))
const dateTo = ref(toDateStr(now))

let interval: ReturnType<typeof setInterval> | null = null

async function fetchData() {
  try {
    const params: Record<string, string> = {}
    if (dateFrom.value) params.date_from = dateFrom.value + 'T00:00:00Z'
    if (dateTo.value) params.date_to = dateTo.value + 'T23:59:59Z'
    summary.value = await getJobMonitor(params)
    error.value = ''
  } catch {
    error.value = 'Kon job status niet laden'
  } finally {
    loading.value = false
  }
}

watch([dateFrom, dateTo], () => {
  fetchData()
})

function startAutoRefresh() {
  stopAutoRefresh()
  if (autoRefresh.value) {
    interval = setInterval(fetchData, 10_000)
  }
}

function stopAutoRefresh() {
  if (interval) {
    clearInterval(interval)
    interval = null
  }
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) startAutoRefresh()
  else stopAutoRefresh()
}

function toggleExpand(jobId: string | null) {
  if (!jobId) return
  expandedJobId.value = expandedJobId.value === jobId ? null : jobId
}

function setStatusFromBlock(status: string) {
  statusFilter.value = statusFilter.value === status ? 'all' : status
}

const filteredJobs = computed(() => {
  if (!summary.value) return []
  let jobs = summary.value.jobs

  if (functionFilter.value) {
    jobs = jobs.filter((j) => j.function === functionFilter.value)
  }

  if (statusFilter.value !== 'all') {
    jobs = jobs.filter((j) => j.status === statusFilter.value)
  }

  return jobs
})

const uniqueFunctions = computed(() => {
  if (!summary.value) return []
  const fns = new Set(summary.value.jobs.map((j) => j.function))
  return Array.from(fns).sort()
})

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: 'In wacht',
    deferred: 'Uitgesteld',
    in_progress: 'Actief',
    complete: 'Klaar',
    failed: 'Mislukt',
  }
  return labels[status] ?? status
}

function statusDotColor(status: string): string {
  const dots: Record<string, string> = {
    queued: 'bg-navy-400',
    deferred: 'bg-yellow-400',
    in_progress: 'bg-accent-500',
    complete: 'bg-green-500',
    failed: 'bg-red-500',
  }
  return dots[status] ?? 'bg-navy-300'
}

function statusBadge(status: string): string {
  const badges: Record<string, string> = {
    queued: theme.badge.default,
    deferred: theme.badge.warning,
    in_progress: theme.badge.info,
    complete: theme.badge.success,
    failed: theme.badge.error,
  }
  return badges[status] ?? theme.badge.default
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '\u2014'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatTime(dt: string | null): string {
  if (!dt) return '\u2014'
  return new Date(dt).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDateTime(dt: string | null): string {
  if (!dt) return '\u2014'
  return new Date(dt).toLocaleString('nl-NL', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

const hasActiveFilters = computed(() =>
  functionFilter.value !== '' || statusFilter.value !== 'all'
)

function clearFilters() {
  functionFilter.value = ''
  statusFilter.value = 'all'
}

onMounted(() => {
  fetchData()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-start md:items-center justify-between flex-wrap gap-3">
      <div class="flex items-center gap-2">
        <Activity class="w-6 h-6 text-navy-700" />
        <div>
          <h2 :class="theme.text.h2">Achtergrondtaken</h2>
          <p :class="theme.text.muted" class="text-xs mt-0.5">
            Laatste check: {{ summary ? formatTime(summary.checked_at) : '\u2014' }}
          </p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <label class="flex items-center gap-2 text-sm cursor-pointer select-none" :class="theme.text.body">
          <div
            class="relative w-9 h-5 rounded-full transition-colors duration-200"
            :class="autoRefresh ? 'bg-green-500' : 'bg-navy-200'"
            @click.prevent="toggleAutoRefresh"
          >
            <div
              class="absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200"
              :class="autoRefresh ? 'translate-x-4' : 'translate-x-0.5'"
            />
          </div>
          Auto-refresh
        </label>
        <button :class="theme.btn.ghost" @click="fetchData" :disabled="loading">
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" />
          Ververs
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <!-- ──── Loading Skeleton ──── -->
    <template v-if="loading && !summary">
      <!-- Stat cards skeleton -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" :class="theme.stat.card" class="skeleton-card" :style="{ animationDelay: i * 80 + 'ms' }">
          <div :class="theme.stat.iconWrap" class="bg-navy-50">
            <div class="w-5 h-5 rounded bg-navy-100 animate-pulse" />
          </div>
          <div class="flex-1 space-y-1.5">
            <div class="h-7 w-16 bg-navy-100 rounded animate-pulse" />
            <div class="h-3.5 w-20 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </div>

      <!-- Filter bar skeleton -->
      <div :class="theme.card.base" class="p-4 skeleton-card" style="animation-delay: 400ms">
        <div class="flex gap-4">
          <div class="h-9 w-32 bg-navy-100 rounded-lg animate-pulse" />
          <div class="h-9 w-32 bg-navy-100 rounded-lg animate-pulse" />
          <div class="h-9 w-40 bg-navy-100 rounded-lg animate-pulse" />
          <div class="h-9 w-36 bg-navy-100 rounded-lg animate-pulse" />
        </div>
      </div>

      <!-- List skeleton -->
      <div class="overflow-hidden rounded-xl border border-navy-100">
        <div class="bg-white divide-y divide-navy-50">
          <div v-for="n in 5" :key="n" class="flex items-center gap-4 px-4 py-4 skeleton-row-enter" :style="{ animationDelay: (n + 5) * 60 + 'ms' }">
            <div class="w-4 h-4 bg-navy-100 rounded animate-pulse" />
            <div class="h-4 w-40 bg-navy-100 rounded animate-pulse" />
            <div class="flex-1" />
            <div class="h-5 w-16 bg-navy-100 rounded-full animate-pulse" />
            <div class="h-4 w-14 bg-navy-100 rounded animate-pulse" />
            <div class="h-4 w-16 bg-navy-100 rounded animate-pulse hidden md:block" />
          </div>
        </div>
      </div>
    </template>

    <!-- ──── Loaded Content ──── -->
    <template v-if="summary">
      <!-- ─── Summary Cards ─── -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <!-- Queued -->
        <div
          :class="[theme.stat.card, theme.stat.cardClickable, statusFilter === 'queued' ? 'ring-2 ring-accent-400' : '']"
          @click="setStatusFromBlock('queued')"
        >
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.default]">
            <Clock :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ summary.queued_count }}</p>
            <p :class="theme.stat.label">In wacht</p>
          </div>
        </div>

        <!-- In Progress -->
        <div
          :class="[theme.stat.card, theme.stat.cardClickable, statusFilter === 'in_progress' ? 'ring-2 ring-accent-400' : '']"
          @click="setStatusFromBlock('in_progress')"
        >
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.accent]">
            <Play :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ summary.in_progress_count }}</p>
            <p :class="theme.stat.label">Actief</p>
          </div>
        </div>

        <!-- Complete -->
        <div
          :class="[theme.stat.card, theme.stat.cardClickable, statusFilter === 'complete' ? 'ring-2 ring-accent-400' : '']"
          @click="setStatusFromBlock('complete')"
        >
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.green]">
            <CheckCircle2 :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ summary.complete_count }}</p>
            <p :class="theme.stat.label">Klaar</p>
          </div>
        </div>

        <!-- Failed -->
        <div
          :class="[theme.stat.card, theme.stat.cardClickable, statusFilter === 'failed' ? 'ring-2 ring-accent-400' : '']"
          @click="setStatusFromBlock('failed')"
        >
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.red]">
            <XCircle :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ summary.failed_count }}</p>
            <p :class="theme.stat.label">Mislukt</p>
            <p v-if="summary.failed_count > 0" :class="theme.stat.sub" class="text-red-500">Aandacht vereist</p>
          </div>
        </div>
      </div>

      <!-- ─── Filter Bar ─── -->
      <div :class="theme.card.base" class="p-4">
        <div class="flex flex-wrap items-end gap-3">
          <div>
            <label :class="theme.form.label" class="text-xs">Van</label>
            <input
              v-model="dateFrom"
              type="date"
              :class="theme.form.input"
              class="!w-auto"
            />
          </div>
          <div>
            <label :class="theme.form.label" class="text-xs">Tot</label>
            <input
              v-model="dateTo"
              type="date"
              :class="theme.form.input"
              class="!w-auto"
            />
          </div>
          <div>
            <label :class="theme.form.label" class="text-xs">Functie</label>
            <select
              v-model="functionFilter"
              :class="theme.form.input"
              class="!w-auto min-w-[180px]"
            >
              <option value="">Alle functies</option>
              <option v-for="fn in uniqueFunctions" :key="fn" :value="fn">{{ fn }}</option>
            </select>
          </div>
          <div>
            <label :class="theme.form.label" class="text-xs">Status</label>
            <select
              v-model="statusFilter"
              :class="theme.form.input"
              class="!w-auto min-w-[160px]"
            >
              <option value="all">Alle statussen</option>
              <option value="queued">In wacht</option>
              <option value="deferred">Uitgesteld</option>
              <option value="in_progress">Actief</option>
              <option value="complete">Klaar</option>
              <option value="failed">Mislukt</option>
            </select>
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

      <!-- ─── Jobs List ─── -->
      <div class="overflow-hidden rounded-xl border border-navy-100">
        <!-- Empty state -->
        <div v-if="filteredJobs.length === 0" :class="theme.emptyState.wrapper">
          <div :class="theme.emptyState.iconWrap">
            <Square :class="theme.emptyState.icon" :size="24" />
          </div>
          <p :class="theme.emptyState.title">Geen taken gevonden</p>
          <p :class="theme.emptyState.description">
            {{ hasActiveFilters ? 'Pas de filters aan om meer resultaten te zien.' : 'Er zijn nog geen achtergrondtaken uitgevoerd.' }}
          </p>
        </div>

        <!-- Job rows -->
        <div v-else class="bg-white divide-y divide-navy-50">
          <div
            v-for="job in filteredJobs"
            :key="job.job_id ?? job.function + job.enqueue_time"
          >
            <!-- Job row -->
            <div
              class="flex items-center justify-between px-4 py-3.5 hover:bg-surface transition-colors cursor-pointer"
              @click="toggleExpand(job.job_id)"
            >
              <div class="flex items-center gap-3 min-w-0">
                <ChevronDown
                  :size="16"
                  class="shrink-0 text-navy-400 transition-transform duration-200"
                  :class="expandedJobId === job.job_id ? 'rotate-0' : '-rotate-90'"
                />
                <span :class="theme.text.h4" class="truncate">{{ job.function }}</span>
              </div>
              <div class="flex items-center gap-4 shrink-0">
                <span :class="[theme.badge.base, statusBadge(job.status)]" class="inline-flex items-center gap-1.5">
                  <span class="w-1.5 h-1.5 rounded-full" :class="statusDotColor(job.status)" />
                  {{ statusLabel(job.status) }}
                </span>
                <span :class="theme.text.muted" class="text-xs w-16 text-right font-mono">
                  {{ formatDuration(job.execution_duration_ms) }}
                </span>
                <span :class="theme.text.muted" class="text-xs w-16 text-right hidden md:inline">
                  {{ formatTime(job.enqueue_time) }}
                </span>
              </div>
            </div>

            <!-- Expanded detail -->
            <Transition name="expand">
              <div
                v-if="expandedJobId === job.job_id"
                class="px-4 pb-4 bg-surface border-t border-navy-100"
              >
                <div class="grid grid-cols-2 md:grid-cols-3 gap-4 pt-4 text-sm">
                  <div>
                    <p :class="theme.text.muted" class="text-xs mb-0.5 flex items-center gap-1">
                      <Hash :size="12" /> Job ID
                    </p>
                    <p class="font-mono text-xs text-navy-700 break-all">{{ job.job_id ?? '\u2014' }}</p>
                  </div>
                  <div>
                    <p :class="theme.text.muted" class="text-xs mb-0.5 flex items-center gap-1">
                      <RotateCcw :size="12" /> Pogingen
                    </p>
                    <p class="text-navy-700 font-medium">{{ job.try_count }}</p>
                  </div>
                  <div>
                    <p :class="theme.text.muted" class="text-xs mb-0.5 flex items-center gap-1">
                      <Calendar :size="12" /> Ingepland
                    </p>
                    <p class="text-navy-700">{{ formatDateTime(job.enqueue_time) }}</p>
                  </div>
                  <div>
                    <p :class="theme.text.muted" class="text-xs mb-0.5 flex items-center gap-1">
                      <Play :size="12" /> Gestart
                    </p>
                    <p class="text-navy-700">{{ formatDateTime(job.start_time) }}</p>
                  </div>
                  <div>
                    <p :class="theme.text.muted" class="text-xs mb-0.5 flex items-center gap-1">
                      <CheckCircle2 :size="12" /> Afgerond
                    </p>
                    <p class="text-navy-700">{{ formatDateTime(job.finish_time) }}</p>
                  </div>
                  <div>
                    <p :class="theme.text.muted" class="text-xs mb-0.5 flex items-center gap-1">
                      <Timer :size="12" /> Duur
                    </p>
                    <p class="text-navy-700 font-medium font-mono">{{ formatDuration(job.execution_duration_ms) }}</p>
                  </div>
                </div>

                <!-- Error block -->
                <div v-if="job.error" class="mt-4">
                  <div class="flex items-center gap-1.5 mb-1.5">
                    <AlertTriangle :size="14" class="text-red-500" />
                    <span class="text-xs font-semibold text-red-700">Foutmelding</span>
                  </div>
                  <pre class="p-3 bg-red-50 text-red-700 rounded-lg text-xs overflow-x-auto whitespace-pre-wrap border border-red-100 font-mono">{{ job.error }}</pre>
                </div>
              </div>
            </Transition>
          </div>
        </div>
      </div>

      <!-- Job count footer -->
      <p v-if="filteredJobs.length > 0" :class="theme.text.muted" class="text-xs text-right">
        {{ filteredJobs.length }} {{ filteredJobs.length === 1 ? 'taak' : 'taken' }} weergegeven
      </p>
    </template>
  </div>
</template>

<style scoped>
@keyframes skeletonFadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.skeleton-card,
.skeleton-row-enter {
  opacity: 0;
  animation: skeletonFadeIn 0.3s ease forwards;
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 400px;
}
</style>
