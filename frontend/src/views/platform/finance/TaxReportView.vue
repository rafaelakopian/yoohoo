<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  FileSpreadsheet, FileText, Calculator, Receipt,
  ChevronLeft, ChevronRight, Banknote, Percent,
} from 'lucide-vue-next'
import { getTaxReport, type TaxReport } from '@/api/platform/finance'
import { useAuthStore } from '@/stores/auth'
import { theme } from '@/theme'

const authStore = useAuthStore()
const currentYear = new Date().getFullYear()
const currentQuarter = Math.ceil((new Date().getMonth() + 1) / 3)

const year = ref(currentYear)
const quarter = ref(currentQuarter)
const data = ref<TaxReport | null>(null)
const loading = ref(true)
const error = ref('')

function fmt(cents: number): string {
  return new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' }).format(cents / 100)
}

const quarterLabel = computed(() => {
  const labels: Record<number, string> = {
    1: 'jan \u2013 mrt',
    2: 'apr \u2013 jun',
    3: 'jul \u2013 sep',
    4: 'okt \u2013 dec',
  }
  return `Q${quarter.value} ${year.value} (${labels[quarter.value]})`
})

// Navigate quarters
function prevQuarter() {
  if (quarter.value === 1) {
    quarter.value = 4
    year.value--
  } else {
    quarter.value--
  }
}

function nextQuarter() {
  if (quarter.value === 4) {
    quarter.value = 1
    year.value++
  } else {
    quarter.value++
  }
}

const isCurrentPeriod = computed(() => year.value === currentYear && quarter.value === currentQuarter)
const isFuture = computed(() => year.value > currentYear || (year.value === currentYear && quarter.value > currentQuarter))

// Max bar for visual proportion
const maxTotalCents = computed(() => {
  if (!data.value) return 1
  return Math.max(...data.value.lines.map(l => l.total_cents), 1)
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getTaxReport(year.value, quarter.value)
  } catch {
    error.value = 'Kon BTW rapport niet laden'
  } finally {
    loading.value = false
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

function exportCsv() {
  const token = authStore.accessToken
  fetch(`/api/v1/platform/finance/tax-report/export?year=${year.value}&quarter=${quarter.value}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then(r => r.blob())
    .then(blob => downloadBlob(blob, `btw-rapport-${year.value}-Q${quarter.value}.csv`))
}

function exportPdf() {
  if (!data.value) return
  const lines = data.value.lines
  const totals = data.value.totals
  const rows = lines.map(l =>
    `<tr><td>${l.month}</td><td style="text-align:right">${l.invoice_count}</td><td style="text-align:right">${fmt(l.subtotal_cents)}</td><td style="text-align:right">${fmt(l.tax_cents)}</td><td style="text-align:right">${fmt(l.total_cents)}</td></tr>`
  ).join('')
  const html = `<!DOCTYPE html><html><head><title>BTW Rapport ${year.value} Q${quarter.value}</title><style>body{font-family:sans-serif;padding:40px}table{width:100%;border-collapse:collapse}th,td{padding:8px 12px;border-bottom:1px solid #ddd;text-align:left}th{font-weight:600;background:#f6f7fa}tfoot td{font-weight:700;border-top:2px solid #333}</style></head><body><h1>BTW Rapport ${year.value} Q${quarter.value}</h1><table><thead><tr><th>Maand</th><th style="text-align:right">Facturen</th><th style="text-align:right">Excl. BTW</th><th style="text-align:right">BTW</th><th style="text-align:right">Incl. BTW</th></tr></thead><tbody>${rows}</tbody><tfoot><tr><td>Totaal</td><td style="text-align:right">${totals.invoice_count}</td><td style="text-align:right">${fmt(totals.subtotal_cents)}</td><td style="text-align:right">${fmt(totals.tax_cents)}</td><td style="text-align:right">${fmt(totals.total_cents)}</td></tr></tfoot></table></body></html>`
  const w = window.open('', '_blank')
  if (w) {
    w.document.write(html)
    w.document.close()
    w.print()
  }
}

watch([year, quarter], load)
onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Calculator class="w-6 h-6 text-navy-700" />
        <h2 :class="theme.text.h2">BTW Rapportage</h2>
      </div>
      <div class="flex gap-2">
        <button :class="[theme.export.btn, theme.export.csv]" :disabled="!data || loading" @click="exportCsv">
          <FileSpreadsheet :size="15" :class="theme.export.csvIcon" /> CSV
        </button>
        <button :class="[theme.export.btn, theme.export.pdf]" :disabled="!data || loading" @click="exportPdf">
          <FileText :size="15" :class="theme.export.pdfIcon" /> PDF
        </button>
      </div>
    </div>

    <!-- Period selector -->
    <div :class="theme.card.base" class="overflow-hidden">
      <div class="flex items-center justify-between px-4 md:px-6 py-3">
        <button
          class="p-1.5 rounded-lg hover:bg-navy-100 transition-colors text-navy-400 hover:text-navy-700"
          @click="prevQuarter"
        >
          <ChevronLeft :size="20" />
        </button>
        <div class="text-center">
          <p class="text-lg font-bold text-navy-900">{{ quarterLabel }}</p>
          <p v-if="isCurrentPeriod" class="text-xs text-accent-700 font-medium">Huidig kwartaal</p>
        </div>
        <button
          class="p-1.5 rounded-lg transition-colors"
          :class="isFuture ? 'text-navy-200 cursor-not-allowed' : 'hover:bg-navy-100 text-navy-400 hover:text-navy-700'"
          :disabled="isFuture"
          @click="nextQuarter"
        >
          <ChevronRight :size="20" />
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <!-- ──── Loading Skeleton ──── -->
    <template v-if="loading">
      <!-- Summary cards skeleton -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div v-for="i in 3" :key="i" :class="theme.stat.card" class="skeleton-card" :style="{ animationDelay: i * 80 + 'ms' }">
          <div :class="theme.stat.iconWrap" class="bg-navy-50">
            <div class="w-5 h-5 rounded bg-navy-100 animate-pulse" />
          </div>
          <div class="flex-1 space-y-1.5">
            <div class="h-7 w-24 bg-navy-100 rounded animate-pulse" />
            <div class="h-3.5 w-16 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </div>

      <!-- Table skeleton -->
      <div class="overflow-hidden rounded-xl border border-navy-100">
        <div class="bg-surface px-4 h-[42px]" />
        <div class="bg-white divide-y divide-navy-50">
          <div v-for="n in 3" :key="n" class="flex items-center gap-4 px-4 py-4 skeleton-row-enter" :style="{ animationDelay: (n + 3) * 60 + 'ms' }">
            <div class="h-4 w-20 bg-navy-100 rounded animate-pulse" />
            <div class="flex-1" />
            <div class="h-4 w-12 bg-navy-100 rounded animate-pulse" />
            <div class="h-4 w-20 bg-navy-100 rounded animate-pulse" />
            <div class="h-4 w-20 bg-navy-100 rounded animate-pulse" />
            <div class="h-4 w-20 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </div>
    </template>

    <!-- ──── Loaded Content ──── -->
    <template v-else-if="data">
      <!-- ─── Summary Cards ─── -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- Subtotal (excl. BTW) -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.accent]">
            <Banknote :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ fmt(data.totals.subtotal_cents) }}</p>
            <p :class="theme.stat.label">Excl. BTW</p>
            <p :class="theme.stat.sub">{{ data.totals.invoice_count }} facturen</p>
          </div>
        </div>

        <!-- Tax -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.primary]">
            <Percent :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ fmt(data.totals.tax_cents) }}</p>
            <p :class="theme.stat.label">BTW af te dragen</p>
            <p v-if="data.totals.subtotal_cents > 0" :class="theme.stat.sub">
              {{ Math.round((data.totals.tax_cents / data.totals.subtotal_cents) * 100) }}% effectief tarief
            </p>
          </div>
        </div>

        <!-- Total (incl. BTW) -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.green]">
            <Receipt :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ fmt(data.totals.total_cents) }}</p>
            <p :class="theme.stat.label">Incl. BTW</p>
          </div>
        </div>
      </div>

      <!-- ─── Monthly Breakdown Table ─── -->
      <div class="overflow-hidden rounded-xl border border-navy-100">
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-navy-200 text-sm table-fixed">
            <colgroup>
              <col style="width: 20%" />
              <col style="width: 12%" />
              <col style="width: 22%" />
              <col style="width: 22%" />
              <col style="width: 24%" />
            </colgroup>
            <thead class="bg-surface text-navy-700 font-semibold">
              <tr>
                <th class="px-4 h-[42px] text-left">Maand</th>
                <th class="px-4 h-[42px] text-right">Facturen</th>
                <th class="px-4 h-[42px] text-right">Excl. BTW</th>
                <th class="px-4 h-[42px] text-right">BTW</th>
                <th class="px-4 h-[42px] text-right">Incl. BTW</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-navy-50">
              <tr
                v-for="line in data.lines"
                :key="line.month"
                class="hover:bg-surface transition-colors"
              >
                <td class="px-4 py-3">
                  <div class="flex items-center gap-3">
                    <span class="font-medium text-navy-900">{{ line.month }}</span>
                    <!-- Mini bar -->
                    <div class="hidden md:block flex-1 max-w-[80px] h-1.5 rounded-full overflow-hidden" style="background: var(--color-surface, #f6f7fa)">
                      <div
                        class="h-full rounded-full bg-accent-700 transition-all duration-500"
                        :style="{ width: `${Math.max((line.total_cents / maxTotalCents) * 100, 2)}%` }"
                      />
                    </div>
                  </div>
                </td>
                <td class="px-4 py-3 text-right">
                  <span :class="line.invoice_count > 0 ? 'text-navy-900 font-medium' : 'text-navy-300'">
                    {{ line.invoice_count }}
                  </span>
                </td>
                <td class="px-4 py-3 text-right text-navy-700">{{ fmt(line.subtotal_cents) }}</td>
                <td class="px-4 py-3 text-right text-navy-700">{{ fmt(line.tax_cents) }}</td>
                <td class="px-4 py-3 text-right font-semibold text-navy-900">{{ fmt(line.total_cents) }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="bg-navy-50 border-t-2 border-navy-200">
                <td class="px-4 py-3 font-bold text-navy-900">Totaal</td>
                <td class="px-4 py-3 text-right font-bold text-navy-900">{{ data.totals.invoice_count }}</td>
                <td class="px-4 py-3 text-right font-bold text-navy-900">{{ fmt(data.totals.subtotal_cents) }}</td>
                <td class="px-4 py-3 text-right font-bold text-accent-700">{{ fmt(data.totals.tax_cents) }}</td>
                <td class="px-4 py-3 text-right font-bold text-navy-900">{{ fmt(data.totals.total_cents) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Empty months notice -->
      <div v-if="data.totals.invoice_count === 0" class="text-center py-4">
        <p :class="theme.text.muted" class="text-sm">Geen facturen in dit kwartaal.</p>
      </div>
    </template>

    <!-- ──── Empty state ──── -->
    <div v-else-if="!error" :class="theme.emptyState.wrapper">
      <div :class="theme.emptyState.iconWrap">
        <Calculator :class="theme.emptyState.icon" :size="24" />
      </div>
      <p :class="theme.emptyState.title">Geen rapport beschikbaar</p>
      <p :class="theme.emptyState.description">Het BTW rapport kon niet worden geladen.</p>
    </div>
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
</style>
