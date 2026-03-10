<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  TrendingUp, TrendingDown, Banknote, BarChart3, Wallet,
  Crown, Users, Percent, ChevronDown, Timer, Bell,
} from 'lucide-vue-next'
import { getRevenueOverview, type RevenueOverview } from '@/api/platform/finance'
import { platformBillingApi } from '@/api/platform/billing'
import { formatCents } from '@/types/billing'
import type { BillingInvoice } from '@/types/billing'
import { theme } from '@/theme'

const router = useRouter()
const data = ref<RevenueOverview | null>(null)
const invoices = ref<BillingInvoice[]>([])
const loading = ref(true)
const error = ref('')

function fmt(cents: number): string {
  return new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' }).format(cents / 100)
}

function fmtCompact(cents: number): string {
  const val = cents / 100
  if (val >= 10000) return `€${(val / 1000).toFixed(1)}k`
  return fmt(cents)
}

// ─── Betaalinzicht (from invoices) ───
const paidCount = computed(() => invoices.value.filter(i => i.status === 'paid').length)
const totalInvoiceCount = computed(() => invoices.value.length)
const totalInvoicedCents = computed(() => invoices.value.reduce((s, i) => s + i.total_cents, 0))
const dunningCount = computed(() => invoices.value.filter(i => i.dunning_count > 0).length)
const collectionRate = computed(() => totalInvoiceCount.value > 0 ? Math.round((paidCount.value / totalInvoiceCount.value) * 100) : 0)
const avgPaymentDays = computed(() => {
  const paid = invoices.value.filter(i => i.status === 'paid' && i.paid_at)
  if (paid.length === 0) return null
  const totalDays = paid.reduce((sum, inv) => {
    return sum + (new Date(inv.paid_at!).getTime() - new Date(inv.created_at).getTime()) / 86400000
  }, 0)
  return Math.round(totalDays / paid.length)
})

const statusLabels: Record<string, string> = {
  trialing: 'Proefperiode',
  active: 'Actief',
  past_due: 'Te laat',
  cancelled: 'Geannuleerd',
  expired: 'Verlopen',
}

const statusStyles: Record<string, { dot: string; bg: string; text: string }> = {
  trialing: { dot: 'bg-accent-600', bg: 'bg-accent-50', text: 'text-accent-700' },
  active: { dot: 'bg-green-500', bg: 'bg-green-50', text: 'text-green-700' },
  past_due: { dot: 'bg-yellow-500', bg: 'bg-yellow-50', text: 'text-yellow-700' },
  cancelled: { dot: 'bg-red-500', bg: 'bg-red-50', text: 'text-red-700' },
  expired: { dot: 'bg-navy-400', bg: 'bg-navy-50', text: 'text-navy-600' },
}

const defaultStatusStyle = { dot: 'bg-navy-400', bg: 'bg-navy-50', text: 'text-navy-600' }

// Funnel steps
const funnelSteps = computed(() => {
  if (!data.value) return []
  const f = data.value.funnel
  const max = Math.max(f.registered || 1, 1)
  return [
    { key: 'registered', label: 'Geregistreerd', tooltip: 'Totaal aantal aangemelde organisaties op het platform', count: f.registered ?? 0, pct: 100 },
    { key: 'provisioned', label: 'Ingericht', tooltip: 'Organisaties waarvan de omgeving is aangemaakt en klaar voor gebruik', count: f.provisioned ?? 0, pct: Math.round(((f.provisioned ?? 0) / max) * 100) },
    { key: 'active_subscription', label: 'Actief abonnement', tooltip: 'Organisaties met een lopend, actief abonnement', count: f.active_subscription ?? 0, pct: Math.round(((f.active_subscription ?? 0) / max) * 100) },
    { key: 'paying', label: 'Betalend', tooltip: 'Organisaties die minstens één factuur hebben betaald', count: f.paying ?? 0, pct: Math.round(((f.paying ?? 0) / max) * 100) },
  ]
})

function stepConversion(idx: number): number {
  if (idx <= 0 || !funnelSteps.value[idx - 1]?.count) return 100
  return Math.round((funnelSteps.value[idx].count / funnelSteps.value[idx - 1].count) * 100)
}

// Total subscriptions for percentage calc
const totalSubscriptions = computed(() => {
  if (!data.value) return 0
  return Object.values(data.value.subscription_counts).reduce((s, c) => s + c, 0)
})

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

function timeAgo(d: string): string {
  const diff = Date.now() - new Date(d).getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'vandaag'
  if (days === 1) return 'gisteren'
  if (days < 30) return `${days} dagen geleden`
  const months = Math.floor(days / 30)
  return months === 1 ? '1 maand geleden' : `${months} maanden geleden`
}

onMounted(async () => {
  try {
    const [overview, invResult] = await Promise.all([
      getRevenueOverview(),
      platformBillingApi.listInvoices({ invoice_type: 'platform', limit: 100 }),
    ])
    data.value = overview
    invoices.value = invResult.items
  } catch {
    error.value = 'Kon financieel overzicht niet laden'
  } finally {
    loading.value = false
  }
})

// Skeleton helpers
const skeletonCards = Array.from({ length: 4 }, (_, i) => i)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <TrendingUp class="w-6 h-6 text-navy-700" />
        <h2 :class="theme.text.h2">Financieel overzicht</h2>
      </div>
      <span v-if="data" :class="theme.text.muted" class="text-sm hidden md:block">
        Laatst bijgewerkt: {{ formatDate(data.generated_at) }}
      </span>
    </div>

    <!-- Error -->
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <!-- ──── Loading Skeleton ──── -->
    <template v-if="loading">
      <!-- KPI skeleton -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in skeletonCards" :key="i" :class="theme.stat.card" class="skeleton-card" :style="{ animationDelay: i * 80 + 'ms' }">
          <div :class="theme.stat.iconWrap" class="bg-navy-50">
            <div class="w-5 h-5 rounded bg-navy-100 animate-pulse" />
          </div>
          <div class="flex-1 space-y-1.5">
            <div class="h-7 w-24 bg-navy-100 rounded animate-pulse" />
            <div class="h-3.5 w-14 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </div>

      <!-- Funnel skeleton -->
      <div :class="theme.card.base" class="overflow-hidden">
        <div class="flex items-center gap-2 px-4 md:px-6 py-3 border-b border-navy-100 bg-surface">
          <div class="h-4 w-4 bg-navy-100 rounded animate-pulse" />
          <div class="h-5 w-32 bg-navy-100 rounded animate-pulse" />
        </div>
        <div class="p-4 md:p-6 flex flex-col items-center gap-2">
          <div v-for="i in 4" :key="i" class="h-9 md:h-10 bg-navy-100 rounded-lg animate-pulse skeleton-card" :style="{ width: `${100 - (i - 1) * 18}%`, animationDelay: (i + 4) * 80 + 'ms' }" />
        </div>
      </div>

      <!-- Table skeleton -->
      <div class="overflow-hidden rounded-xl border border-navy-100">
        <div class="bg-surface px-4 h-[46px] flex items-center">
          <div class="h-4 w-48 bg-navy-100 rounded animate-pulse" />
        </div>
        <div class="bg-white divide-y divide-navy-50">
          <div v-for="n in 5" :key="n" class="flex items-center gap-4 px-4 py-4 skeleton-card" :style="{ animationDelay: (n + 8) * 60 + 'ms' }">
            <div class="w-6 h-6 rounded-full bg-navy-100 animate-pulse shrink-0" />
            <div class="flex-1 space-y-1">
              <div class="h-4 w-32 bg-navy-100 rounded animate-pulse" />
            </div>
            <div class="h-4 w-20 bg-navy-100 rounded animate-pulse hidden md:block" />
            <div class="h-4 w-20 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </div>
    </template>

    <!-- ──── Loaded Content ──── -->
    <template v-else-if="data">
      <!-- ─── KPI Cards ─── -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- MRR -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.accent]">
            <Banknote :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ fmt(data.mrr_cents) }}</p>
            <p :class="theme.stat.label">MRR</p>
          </div>
        </div>

        <!-- ARR -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.primary]">
            <BarChart3 :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ fmt(data.arr_cents) }}</p>
            <p :class="theme.stat.label">ARR</p>
          </div>
        </div>

        <!-- Growth -->
        <div :class="theme.stat.card">
          <div :class="[
            theme.stat.iconWrap,
            data.growth_percent !== null && data.growth_percent >= 0
              ? theme.stat.iconVariant.green
              : theme.stat.iconVariant.red,
          ]">
            <component :is="data.growth_percent !== null && data.growth_percent >= 0 ? TrendingUp : TrendingDown" :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">
              <template v-if="data.growth_percent !== null">
                {{ data.growth_percent > 0 ? '+' : '' }}{{ data.growth_percent }}%
              </template>
              <template v-else>&mdash;</template>
            </p>
            <p :class="theme.stat.label">Groei</p>
          </div>
        </div>

        <!-- Total Revenue -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.green]">
            <Wallet :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ fmtCompact(data.total_revenue_cents) }}</p>
            <p :class="theme.stat.label">Totale omzet</p>
          </div>
        </div>
      </div>

      <!-- ─── Betaalinzicht + Conversion Funnel + Abonnementen ─── -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Betaalinzicht (1/3) -->
        <div :class="theme.card.base" class="overflow-hidden">
          <div class="flex items-center gap-2 px-4 md:px-6 py-3 border-b border-navy-100 bg-surface rounded-t-xl">
            <BarChart3 :size="16" class="text-navy-400" />
            <h3 :class="theme.text.h4">Betaalinzicht</h3>
          </div>
          <div class="divide-y divide-navy-50">
            <div class="flex items-center justify-between px-5 py-3">
              <span :class="theme.text.muted" class="text-sm">Incassograad</span>
              <div class="flex items-center gap-2">
                <div class="w-16 h-1.5 rounded-full overflow-hidden bg-navy-100">
                  <div
                    class="h-full bg-green-400 rounded-full transition-all duration-700"
                    :style="{ width: collectionRate + '%' }"
                  />
                </div>
                <span class="text-sm font-bold text-navy-900">{{ collectionRate }}%</span>
              </div>
            </div>
            <div class="flex items-center justify-between px-5 py-3">
              <div class="flex items-center gap-1.5">
                <Timer :size="13" class="text-navy-300" />
                <span :class="theme.text.muted" class="text-sm">Gem. betaaltijd</span>
              </div>
              <span class="text-sm font-bold text-navy-900">{{ avgPaymentDays !== null ? avgPaymentDays + ' dagen' : '\u2014' }}</span>
            </div>
            <div class="flex items-center justify-between px-5 py-3">
              <span :class="theme.text.muted" class="text-sm">Totaal gefactureerd</span>
              <span class="text-sm font-bold text-navy-900">{{ formatCents(totalInvoicedCents) }}</span>
            </div>
            <div class="flex items-center justify-between px-5 py-3">
              <div class="flex items-center gap-1.5">
                <Bell :size="13" class="text-navy-300" />
                <span :class="theme.text.muted" class="text-sm">Met herinnering</span>
              </div>
              <span class="text-sm font-bold text-navy-900">{{ dunningCount }}</span>
            </div>
          </div>
        </div>

        <!-- Conversie funnel (1/3) -->
        <div :class="theme.card.base" class="overflow-visible">
          <div class="flex items-center gap-2 px-4 md:px-6 py-3 border-b border-navy-100 bg-surface rounded-t-xl">
            <Percent :size="16" class="text-navy-400" />
            <h3 :class="theme.text.h4">Conversie funnel</h3>
          </div>
          <div class="p-4 md:p-6">
            <div class="flex flex-col items-center">
              <template v-for="(step, idx) in funnelSteps" :key="step.key">
                <!-- Step-to-step conversion indicator -->
                <div v-if="idx > 0" class="flex items-center gap-1 py-1.5">
                  <ChevronDown :size="12" class="text-navy-300" />
                  <span
                    class="text-[11px] font-medium"
                    :class="stepConversion(idx) >= 70 ? 'text-green-600' : stepConversion(idx) >= 40 ? 'text-yellow-600' : 'text-red-500'"
                  >{{ stepConversion(idx) }}%</span>
                </div>

                <!-- Funnel bar -->
                <div
                  class="funnel-bar flex items-center justify-between rounded-lg h-9 md:h-10 px-3 md:px-4 shadow-sm cursor-default"
                  :class="[
                    idx === 0 ? 'bg-navy-200 text-navy-800' :
                    idx === 1 ? 'bg-accent-200 text-accent-800' :
                    idx === 2 ? 'bg-accent-700 text-white' :
                    'bg-green-700 text-white'
                  ]"
                  :style="{ width: `${Math.max(step.pct, 30)}%`, animationDelay: `${idx * 100}ms` }"
                  :data-tooltip="step.tooltip"
                >
                  <span class="text-xs md:text-[13px] font-medium truncate">{{ step.label }}</span>
                  <div class="flex items-center gap-1.5 shrink-0 ml-2">
                    <span class="text-sm font-bold">{{ step.count }}</span>
                    <span class="text-[10px] opacity-60 hidden sm:inline">{{ step.pct }}%</span>
                  </div>
                </div>
              </template>
            </div>

            <!-- Total conversion footer -->
            <div class="mt-4 pt-3 border-t border-navy-100 flex items-center justify-center gap-2">
              <span class="text-xs text-navy-400">Totale conversie</span>
              <span class="text-sm font-semibold text-navy-700">
                {{ funnelSteps.length > 0 ? funnelSteps[funnelSteps.length - 1].pct : 0 }}%
              </span>
            </div>
          </div>
        </div>

        <!-- Abonnementen (1/3) -->
        <div :class="theme.card.base" class="overflow-hidden">
          <div class="flex items-center gap-2 px-4 md:px-6 py-3 border-b border-navy-100 bg-surface">
            <Users :size="16" class="text-navy-400" />
            <h3 :class="theme.text.h4">Abonnementen</h3>
            <span :class="[theme.badge.base, theme.badge.default]" class="ml-auto">{{ totalSubscriptions }}</span>
          </div>
          <div class="divide-y divide-navy-50">
            <div
              v-for="(count, status) in data.subscription_counts"
              :key="status"
              class="flex items-center gap-3 px-4 md:px-6 py-3"
            >
              <span class="w-2.5 h-2.5 rounded-full shrink-0" :class="(statusStyles[status] || defaultStatusStyle).dot" />
              <span class="flex-1 text-sm text-navy-700">{{ statusLabels[status] || status }}</span>
              <span class="text-sm font-semibold text-navy-900">{{ count }}</span>
              <span :class="theme.text.muted" class="text-xs w-10 text-right">
                {{ totalSubscriptions > 0 ? Math.round((count / totalSubscriptions) * 100) : 0 }}%
              </span>
            </div>
            <div v-if="Object.keys(data.subscription_counts).length === 0" class="py-8 text-center">
              <p :class="theme.text.muted" class="text-sm">Geen abonnementen</p>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Top Tenants Table ─── -->
      <div class="overflow-hidden rounded-xl border border-navy-100">
        <div class="flex items-center gap-2 px-4 md:px-6 py-3 bg-surface border-b border-navy-100">
          <Crown :size="16" class="text-navy-400" />
          <h3 :class="theme.text.h4">Top 10 organisaties</h3>
          <span :class="theme.text.muted" class="text-xs ml-auto hidden md:block">op lifetime value</span>
        </div>

        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-navy-200 text-sm table-fixed">
            <colgroup>
              <col style="width: 4%" />
              <col style="width: 30%" />
              <col style="width: 18%" />
              <col style="width: 22%" />
              <col style="width: 14%" />
              <col style="width: 12%" />
            </colgroup>
            <thead class="bg-white text-navy-700 font-semibold">
              <tr>
                <th class="px-3 h-[42px] text-center">#</th>
                <th class="px-4 h-[42px] text-left">Organisatie</th>
                <th class="px-4 h-[42px] text-right">MRR</th>
                <th class="px-4 h-[42px] text-right">Lifetime value</th>
                <th class="px-4 h-[42px] text-center hidden md:table-cell">Status</th>
                <th class="px-4 h-[42px] text-right hidden md:table-cell">Sinds</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-navy-50">
              <tr
                v-for="(t, idx) in data.top_tenants"
                :key="t.tenant_id"
                class="hover:bg-surface transition-colors cursor-pointer group"
                @click="router.push({ name: 'platform-org-detail', params: { tenantId: t.tenant_id } })"
              >
                <td class="px-3 py-3 text-center">
                  <span
                    class="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold"
                    :class="idx < 3 ? 'bg-accent-50 text-accent-700' : 'bg-navy-50 text-navy-400'"
                  >{{ idx + 1 }}</span>
                </td>
                <td class="px-4 py-3">
                  <p class="font-medium text-navy-900 truncate">{{ t.tenant_name }}</p>
                  <p :class="theme.text.muted" class="text-xs">{{ t.tenant_slug }}</p>
                </td>
                <td class="px-4 py-3 text-right font-medium text-navy-900">{{ fmt(t.mrr_cents) }}</td>
                <td class="px-4 py-3 text-right">
                  <span class="font-semibold text-navy-900">{{ fmt(t.lifetime_value_cents) }}</span>
                </td>
                <td class="px-4 py-3 text-center hidden md:table-cell">
                  <span
                    :class="[
                      'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
                      (statusStyles[t.subscription_status || ''] || defaultStatusStyle).bg,
                      (statusStyles[t.subscription_status || ''] || defaultStatusStyle).text,
                    ]"
                  >
                    <span class="w-1.5 h-1.5 rounded-full" :class="(statusStyles[t.subscription_status || ''] || defaultStatusStyle).dot" />
                    {{ statusLabels[t.subscription_status || ''] || t.subscription_status || '\u2014' }}
                  </span>
                </td>
                <td class="px-4 py-3 text-right hidden md:table-cell">
                  <span :class="theme.text.muted" class="text-xs">{{ timeAgo(t.since) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Empty state -->
        <div v-if="data.top_tenants.length === 0" class="py-12 text-center bg-white">
          <p :class="theme.text.muted">Nog geen betalende organisaties</p>
        </div>

        <!-- Footer -->
        <div v-else class="py-3 text-center border-t border-navy-100" :class="theme.text.muted">
          {{ data.top_tenants.length }} organisaties
        </div>
      </div>
    </template>

    <!-- ──── Empty state ──── -->
    <div v-else-if="!error" :class="theme.emptyState.wrapper">
      <div :class="theme.emptyState.iconWrap">
        <TrendingUp :class="theme.emptyState.icon" :size="24" />
      </div>
      <p :class="theme.emptyState.title">Geen gegevens</p>
      <p :class="theme.emptyState.description">Financieel overzicht kon niet worden geladen.</p>
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

.funnel-bar {
  position: relative;
  opacity: 0;
  animation: funnelSlideIn 0.4s ease forwards;
}

@keyframes funnelSlideIn {
  from { opacity: 0; transform: translateY(6px) scaleX(0.92); }
  to { opacity: 1; transform: translateY(0) scaleX(1); }
}

/* ── Custom tooltip ── */
.funnel-bar[data-tooltip]::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: calc(100% + 10px);
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  background: #1a2332;
  color: #f1f5f9;
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.4;
  white-space: normal;
  max-width: 220px;
  width: max-content;
  text-align: center;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s ease, transform 0.2s ease;
  z-index: 20;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
}

.funnel-bar[data-tooltip]::before {
  content: '';
  position: absolute;
  bottom: calc(100% + 4px);
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: #1a2332;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s ease;
  z-index: 20;
}

.funnel-bar[data-tooltip]:hover::after {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.funnel-bar[data-tooltip]:hover::before {
  opacity: 1;
}
</style>
