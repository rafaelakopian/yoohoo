<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { adminApi, type PlatformStats } from '@/api/platform/admin'
import { getOutstandingPayments, type OutstandingPayments } from '@/api/platform/finance'
import { getJobMonitor, type JobQueueSummary } from '@/api/platform/operations'
import { formatCents } from '@/types/billing'
import { usePermissions } from '@/composables/usePermissions'
import { useBrandingStore } from '@/stores/branding'
import {
  StatCard, PulseBar, ActivityFeed, FinanceSnapshot
} from '@/components/platform/widgets'
import type { PulseItem } from '@/components/platform/widgets'
import {
  LayoutDashboard, Building2, CreditCard, AlertTriangle,
  Workflow, Clock,
} from 'lucide-vue-next'
import { theme } from '@/theme'

const branding = useBrandingStore()
const { hasPermission } = usePermissions()

const stats = ref<PlatformStats | null>(null)
const jobSummary = ref<JobQueueSummary | null>(null)
const outstanding = ref<OutstandingPayments | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const fetches: Promise<unknown>[] = [adminApi.getStats()]

    if (hasPermission('operations.view_jobs'))
      fetches.push(getJobMonitor())
    if (hasPermission('finance.view_dashboard'))
      fetches.push(getOutstandingPayments())

    const results = await Promise.all(fetches)
    stats.value = results[0] as PlatformStats

    let idx = 1
    if (hasPermission('operations.view_jobs'))
      jobSummary.value = (results[idx++] as JobQueueSummary) ?? null
    if (hasPermission('finance.view_dashboard'))
      outstanding.value = (results[idx++] as OutstandingPayments) ?? null
  } catch {
    // Handled silently
  } finally {
    loading.value = false
  }
})

const overdueCount = computed(() => {
  if (!outstanding.value?.buckets) return 0
  return outstanding.value.buckets.reduce((sum, b) => sum + b.count, 0)
})

function pluralize(n: number, singular: string, plural: string) {
  return `${n} ${n === 1 ? singular : plural}`
}

const pulseItems = computed<PulseItem[]>(() => {
  const items: PulseItem[] = []

  if (hasPermission('operations.view_jobs') && jobSummary.value && jobSummary.value.failed_count > 0)
    items.push({
      severity: 'error',
      message: `${pluralize(jobSummary.value.failed_count, 'achtergrondtaak', 'achtergrondtaken')} gefaald`,
      to: '/platform/operations/jobs',
    })

  if (hasPermission('finance.view_dashboard') && overdueCount.value > 0)
    items.push({
      severity: 'warning',
      message: `${pluralize(overdueCount.value, 'openstaande factuur', 'openstaande facturen')}`,
      to: '/platform/finance/outstanding',
    })

  if (items.length === 0)
    items.push({ severity: 'ok', message: 'Alle systemen operationeel' })

  return items
})

function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Goedemorgen'
  if (h < 18) return 'Goedemiddag'
  return 'Goedenavond'
}

const timeLabel = computed(() => {
  return new Date().toLocaleDateString('nl-NL', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <LayoutDashboard class="w-6 h-6 text-navy-700" />
        <h2 :class="theme.text.h2">Dashboard</h2>
      </div>
      <span :class="theme.text.muted" class="text-sm flex items-center gap-1">
        <Clock :size="13" />
        {{ timeLabel }}
      </span>
    </div>

    <!-- Pulse Bar -->
    <PulseBar :items="pulseItems" />

    <!-- ──── Stat Cards ──── -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <!-- Skeleton cards while loading -->
      <template v-if="loading">
        <div v-for="i in 4" :key="i" :class="theme.stat.card" class="skeleton-card" :style="{ animationDelay: i * 80 + 'ms' }">
          <div :class="theme.stat.iconWrap" class="bg-navy-50">
            <div class="w-5 h-5 rounded bg-navy-100 animate-pulse" />
          </div>
          <div class="flex-1 space-y-1.5">
            <div class="h-7 w-16 bg-navy-100 rounded animate-pulse" />
            <div class="h-3.5 w-20 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </template>

      <!-- Live cards -->
      <template v-else>
        <StatCard
          v-if="hasPermission('platform.view_orgs')"
          label="Organisaties"
          :value="stats?.active_tenants ?? '\u2014'"
          :sub="`${stats?.provisioned_tenants ?? 0} ingericht`"
          :icon="Building2"
          variant="primary"
          to="/platform/orgs"
        />
        <StatCard
          v-if="hasPermission('billing.view')"
          label="Abonnementen"
          :value="stats?.active_subscriptions ?? '\u2014'"
          :sub="stats ? `${formatCents(stats.mrr_cents)} /maand` : ''"
          :icon="CreditCard"
          variant="accent"
          to="/platform/billing"
        />
        <StatCard
          v-if="hasPermission('finance.view_dashboard')"
          label="Openstaand"
          :value="outstanding ? formatCents(outstanding.total_outstanding_cents) : '\u2014'"
          :sub="pluralize(overdueCount, 'factuur', 'facturen')"
          :icon="AlertTriangle"
          variant="red"
          to="/platform/finance/outstanding"
        />
        <StatCard
          v-if="hasPermission('operations.view_jobs')"
          label="Achtergrondtaken"
          :value="jobSummary?.failed_count === 0 ? 'Alles OK' : `${jobSummary?.failed_count ?? '\u2014'} gefaald`"
          :icon="Workflow"
          :variant="(jobSummary?.failed_count ?? 0) > 0 ? 'red' : 'green'"
          to="/platform/operations/jobs"
        />
      </template>
    </div>

    <!-- ──── Two-Column Grid ──── -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- Loading skeletons -->
      <template v-if="loading">
        <div :class="theme.card.base" class="overflow-hidden skeleton-card" style="animation-delay: 400ms">
          <div class="px-5 pt-5 pb-3 flex items-center gap-2">
            <div class="h-4 w-4 bg-navy-100 rounded animate-pulse" />
            <div class="h-5 w-32 bg-navy-100 rounded animate-pulse" />
          </div>
          <div class="px-5 pb-5 space-y-3">
            <div v-for="n in 4" :key="n" class="flex items-center gap-3">
              <div class="w-7 h-7 bg-navy-50 rounded-full animate-pulse" />
              <div class="flex-1 space-y-1">
                <div class="h-3.5 bg-navy-100 rounded animate-pulse" :style="{ width: `${60 + n * 5}%` }" />
                <div class="h-3 w-1/3 bg-navy-50 rounded animate-pulse" />
              </div>
            </div>
          </div>
        </div>
        <div :class="theme.card.base" class="overflow-hidden skeleton-card" style="animation-delay: 480ms">
          <div class="px-5 pt-5 pb-3 flex items-center gap-2">
            <div class="h-4 w-4 bg-navy-100 rounded animate-pulse" />
            <div class="h-5 w-32 bg-navy-100 rounded animate-pulse" />
          </div>
          <div class="px-5 pb-5 space-y-4">
            <div v-for="n in 4" :key="n" class="flex items-center justify-between">
              <div class="h-3.5 w-14 bg-navy-100 rounded animate-pulse" />
              <div class="h-5 w-20 bg-navy-100 rounded animate-pulse" />
            </div>
          </div>
        </div>
      </template>

      <!-- Live widgets -->
      <template v-else>
        <ActivityFeed
          v-if="hasPermission('platform.view_audit_logs')"
          :max-items="5"
        />
        <FinanceSnapshot
          v-if="hasPermission('finance.view_dashboard')"
        />
      </template>
    </div>
  </div>
</template>

<style scoped>
@keyframes skeletonFadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.skeleton-card {
  opacity: 0;
  animation: skeletonFadeIn 0.3s ease forwards;
}
</style>
