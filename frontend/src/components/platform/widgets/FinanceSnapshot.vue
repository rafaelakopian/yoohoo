<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { getRevenueOverview, getOutstandingPayments, type RevenueOverview, type OutstandingPayments } from '@/api/platform/finance'
import { formatCents } from '@/types/billing'
import { TrendingUp, TrendingDown, Minus, CircleDollarSign, ExternalLink } from 'lucide-vue-next'
import { theme } from '@/theme'

const overview = ref<RevenueOverview | null>(null)
const outstanding = ref<OutstandingPayments | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const [ov, os] = await Promise.all([
      getRevenueOverview(),
      getOutstandingPayments(),
    ])
    overview.value = ov
    outstanding.value = os
  } catch {
    // Silently handle — widget shows empty state
  } finally {
    loading.value = false
  }
})

const overdueCount = computed(() => {
  if (!outstanding.value?.buckets) return 0
  return outstanding.value.buckets.reduce((sum, b) => sum + b.count, 0)
})

const growthIcon = computed(() => {
  if (!overview.value?.growth_percent) return Minus
  return overview.value.growth_percent > 0 ? TrendingUp : TrendingDown
})

const growthColor = computed(() => {
  if (!overview.value?.growth_percent) return 'text-navy-400'
  return overview.value.growth_percent > 0 ? 'text-green-600' : 'text-red-600'
})
</script>

<template>
  <div :class="theme.card.base" class="overflow-hidden flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between px-5 pt-5 pb-3">
      <div class="flex items-center gap-2">
        <CircleDollarSign :size="18" class="text-navy-400" />
        <h3 :class="theme.text.h3">Finance overzicht</h3>
      </div>
      <RouterLink to="/platform/finance/revenue" class="flex items-center gap-1 text-xs font-medium text-accent-700 hover:text-accent-800 transition-colors">
        Details <ExternalLink :size="12" />
      </RouterLink>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="px-5 pb-5 space-y-4">
      <div v-for="n in 4" :key="n" class="flex items-center justify-between animate-pulse">
        <div class="h-3.5 w-16 bg-navy-100 rounded" />
        <div class="h-5 w-24 bg-navy-100 rounded" />
      </div>
    </div>

    <!-- Content -->
    <div v-else class="flex-1 divide-y divide-navy-50">
      <!-- MRR -->
      <div class="flex items-center justify-between px-5 py-3">
        <span :class="theme.text.muted" class="text-sm">MRR</span>
        <span class="text-lg font-bold text-navy-900">{{ formatCents(overview?.mrr_cents ?? 0) }}</span>
      </div>

      <!-- ARR -->
      <div class="flex items-center justify-between px-5 py-3">
        <span :class="theme.text.muted" class="text-sm">ARR</span>
        <span class="text-lg font-bold text-navy-900">{{ formatCents(overview?.arr_cents ?? 0) }}</span>
      </div>

      <!-- Outstanding -->
      <div class="flex items-center justify-between px-5 py-3">
        <span :class="theme.text.muted" class="text-sm">Openstaand</span>
        <div class="flex items-center gap-2">
          <span class="text-lg font-bold text-navy-900">{{ formatCents(outstanding?.total_outstanding_cents ?? 0) }}</span>
          <span v-if="overdueCount > 0" :class="[theme.badge.base, theme.badge.warning]" class="text-[10px]">
            {{ overdueCount }}
          </span>
        </div>
      </div>

      <!-- Growth -->
      <div v-if="overview?.growth_percent != null" class="flex items-center justify-between px-5 py-3">
        <span :class="theme.text.muted" class="text-sm">Groei</span>
        <div class="flex items-center gap-1.5" :class="growthColor">
          <component :is="growthIcon" :size="16" />
          <span class="text-lg font-bold">
            {{ overview.growth_percent > 0 ? '+' : '' }}{{ overview.growth_percent.toFixed(1) }}%
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
