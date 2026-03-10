<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { platformBillingApi } from '@/api/platform/billing'
import { sendDunningReminders } from '@/api/platform/finance'
import { formatCents } from '@/types/billing'
import type { BillingInvoice } from '@/types/billing'
import { usePermissions } from '@/composables/usePermissions'
import IconButton from '@/components/ui/IconButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import {
  Receipt, User, Users, Building2, Banknote, Calendar, Bell,
  ChevronDown, ChevronRight, ArrowUp, ArrowDown, ArrowUpDown,
  X, Zap, CheckCircle, Send, AlertTriangle, Clock,
  FileText, CircleDollarSign, Hourglass,
  ExternalLink,
} from 'lucide-vue-next'
import { theme } from '@/theme'

const { hasPermission } = usePermissions()

// ─── Data ───
const invoices = ref<BillingInvoice[]>([])
const total = ref(0)
const loading = ref(true)
const error = ref('')
const actionFeedback = ref('')
const actionError = ref('')
const expandedId = ref<string | null>(null)

// ─── Summary stats ───
const paidCount = computed(() => invoices.value.filter(i => i.status === 'paid').length)
const openCount = computed(() => invoices.value.filter(i => i.status === 'open' || i.status === 'overdue').length)
const overdueCount = computed(() => invoices.value.filter(i => i.status === 'overdue').length)
const totalOutstandingCents = computed(() =>
  invoices.value
    .filter(i => i.status === 'open' || i.status === 'overdue')
    .reduce((s, i) => s + i.total_cents, 0)
)
const totalPaidCents = computed(() =>
  invoices.value
    .filter(i => i.status === 'paid')
    .reduce((s, i) => s + i.total_cents, 0)
)

// ─── Confirm modals ───
const markPaidModal = ref(false)
const dunningModal = ref(false)
const actionTarget = ref<BillingInvoice | null>(null)

function promptMarkPaid(inv: BillingInvoice) {
  actionTarget.value = inv
  markPaidModal.value = true
}

function promptDunning(inv: BillingInvoice) {
  actionTarget.value = inv
  dunningModal.value = true
}

function cancelModal() {
  markPaidModal.value = false
  dunningModal.value = false
  actionTarget.value = null
}

// ─── Column definitions ───
interface Column {
  key: string
  label: string
  width: string
  icon?: object
  sortable?: boolean
  hiddenMobile?: boolean
  align?: 'left' | 'center' | 'right'
}

const columns: Column[] = [
  { key: 'expand', label: '', width: '4%' },
  { key: 'created_at', label: 'Datum', width: '13%', icon: Calendar, sortable: true },
  { key: 'invoice_number', label: 'Factuurnr', width: '15%', icon: Receipt },
  { key: 'recipient_name', label: 'Organisatie / Ontvanger', width: '26%', icon: Building2, sortable: true, hiddenMobile: true },
  { key: 'total_cents', label: 'Bedrag', width: '18%', icon: Banknote, sortable: true, align: 'right' },
  { key: 'dunning_count', label: 'Herinn.', width: '10%', icon: Bell, sortable: true, hiddenMobile: true },
]

const actionsWidth = '12%'

// ─── Sorting ───
const sortColumn = ref<string>('')
const sortDirection = ref<'asc' | 'desc'>('desc')

function handleSort(key: string) {
  if (sortColumn.value === key) {
    if (sortDirection.value === 'desc') {
      sortDirection.value = 'asc'
    } else {
      sortColumn.value = ''
    }
  } else {
    sortColumn.value = key
    sortDirection.value = 'desc'
  }
}

// ─── Column search ───
const searchableKeys = ['invoice_number', 'recipient_name']
const searchFilters = reactive<Record<string, string>>({
  invoice_number: '',
  recipient_name: '',
})
const activeSearch = ref<string | null>(null)
const searchInputRefs = reactive<Record<string, HTMLInputElement | null>>({})
const headerRefs = reactive<Record<string, HTMLElement | null>>({})
const columnWidths = reactive<Record<string, number>>({})

function activateSearch(key: string) {
  if (!searchableKeys.includes(key)) return
  if (headerRefs[key]) columnWidths[key] = headerRefs[key]!.offsetWidth
  activeSearch.value = key
  nextTick(() => { searchInputRefs[key]?.focus() })
}

function deactivateSearch() {
  activeSearch.value = null
}

function clearAndDeactivate(key: string) {
  searchFilters[key] = ''
  activeSearch.value = null
}

function handleClickOutside(event: MouseEvent) {
  if (activeSearch.value && !(event.target as HTMLElement).closest('th')) {
    activeSearch.value = null
  }
}

// ─── Filtered + sorted ───
const filtered = computed(() => {
  let list = invoices.value

  const inv = searchFilters.invoice_number?.toLowerCase()
  const rec = searchFilters.recipient_name?.toLowerCase()

  if (inv || rec) {
    list = list.filter(i => {
      if (inv && !i.invoice_number.toLowerCase().includes(inv)) return false
      if (rec && !i.recipient_name.toLowerCase().includes(rec)) return false
      return true
    })
  }

  return list
})

const sorted = computed(() => {
  if (!sortColumn.value) return filtered.value

  const list = [...filtered.value]
  const dir = sortDirection.value === 'asc' ? 1 : -1
  list.sort((a, b) => {
    switch (sortColumn.value) {
      case 'total_cents': return (a.total_cents - b.total_cents) * dir
      case 'dunning_count': return (a.dunning_count - b.dunning_count) * dir
      case 'recipient_name': return a.recipient_name.localeCompare(b.recipient_name) * dir
      case 'created_at': return (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()) * dir
      default: return 0
    }
  })
  return list
})

// ─── Due date urgency ───
function dueUrgency(inv: BillingInvoice): { color: string; pct: number; label: string } | null {
  if (inv.status === 'paid' || inv.status === 'cancelled' || inv.status === 'refunded') return null
  if (!inv.due_date) return null

  const now = Date.now()
  const due = new Date(inv.due_date).getTime()
  const created = new Date(inv.created_at).getTime()
  const totalSpan = due - created
  const elapsed = now - created
  const daysLeft = Math.ceil((due - now) / 86400000)

  // Fill: how much of the time period has elapsed (capped at 100%)
  const pct = totalSpan > 0 ? Math.min(Math.round((elapsed / totalSpan) * 100), 100) : 100

  if (daysLeft < 0) {
    const overdueDays = Math.abs(daysLeft)
    return { color: 'bg-red-400', pct: 100, label: `${overdueDays}d te laat` }
  }
  if (daysLeft <= 3) return { color: 'bg-red-400', pct, label: `${daysLeft}d` }
  if (daysLeft <= 7) return { color: 'bg-orange-400', pct, label: `${daysLeft}d` }
  if (daysLeft <= 14) return { color: 'bg-yellow-400', pct, label: `${daysLeft}d` }
  return { color: 'bg-navy-200', pct, label: `${daysLeft}d` }
}

// ─── Status distribution ───
const statusDistribution = computed(() => {
  const counts: Record<string, number> = { paid: 0, open: 0, overdue: 0, other: 0 }
  for (const inv of invoices.value) {
    if (inv.status === 'paid') counts.paid++
    else if (inv.status === 'open') counts.open++
    else if (inv.status === 'overdue') counts.overdue++
    else counts.other++
  }
  const t = invoices.value.length || 1
  return {
    paid: { count: counts.paid, pct: Math.round((counts.paid / t) * 100) },
    open: { count: counts.open, pct: Math.round((counts.open / t) * 100) },
    overdue: { count: counts.overdue, pct: Math.round((counts.overdue / t) * 100) },
    other: { count: counts.other, pct: Math.round((counts.other / t) * 100) },
  }
})

// ─── Top outstanding debtors ───
const topDebtors = computed(() => {
  const map = new Map<string, { name: string; orgName: string | null; total: number; count: number }>()
  for (const inv of invoices.value.filter(i => i.status === 'open' || i.status === 'overdue')) {
    const key = inv.tenant_id || inv.recipient_email
    const existing = map.get(key) || { name: inv.recipient_name, orgName: inv.tenant_name, total: 0, count: 0 }
    existing.total += inv.total_cents
    existing.count++
    map.set(key, existing)
  }
  return [...map.values()].sort((a, b) => b.total - a.total).slice(0, 5)
})

// ─── Date range ───
const dateRange = computed(() => {
  if (invoices.value.length === 0) return ''
  const dates = invoices.value.map(i => new Date(i.created_at).getTime())
  const min = new Date(Math.min(...dates))
  const max = new Date(Math.max(...dates))
  const fmt = (d: Date) => d.toLocaleDateString('nl-NL', { month: 'short', year: 'numeric' })
  if (fmt(min) === fmt(max)) return fmt(min)
  return `${fmt(min)} – ${fmt(max)}`
})

function timeAgo(dt: string): string {
  const diff = Date.now() - new Date(dt).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return 'zojuist'
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}u geleden`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days}d geleden`
  return ''
}

// ─── Skeleton ───
const skeletonWidths = ['70%', '85%', '60%', '75%', '50%', '45%', '60px']
const skeletonRows = Array.from({ length: 8 }, (_, i) => ({
  id: i,
  cells: columns.map((_, c) => skeletonWidths[(i + c) % skeletonWidths.length]),
}))

// ─── Helpers ───
function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

const statusLabels: Record<string, string> = {
  draft: 'Concept',
  open: 'Open',
  paid: 'Betaald',
  overdue: 'Te laat',
  cancelled: 'Geannuleerd',
  refunded: 'Terugbetaald',
}

const statusDots: Record<string, string> = {
  draft: 'bg-navy-400',
  open: 'bg-accent-600',
  paid: 'bg-green-500',
  overdue: 'bg-red-500',
  cancelled: 'bg-yellow-500',
  refunded: 'bg-yellow-500',
}

function statusBadge(status: string): string {
  const map: Record<string, string> = {
    draft: theme.badge.default,
    open: theme.badge.info,
    paid: theme.badge.success,
    overdue: theme.badge.error,
    cancelled: theme.badge.warning,
    refunded: theme.badge.warning,
  }
  return map[status] ?? theme.badge.default
}

function formatDate(dt: string | null): string {
  if (!dt) return '\u2014'
  return new Date(dt).toLocaleDateString('nl-NL', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function formatDateTime(dt: string | null): string {
  if (!dt) return '\u2014'
  return new Date(dt).toLocaleString('nl-NL', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function alignClass(col: Column): string {
  if (col.align === 'right') return 'text-right'
  if (col.align === 'center') return 'text-center'
  return 'text-left'
}

// ─── API ───
async function load() {
  loading.value = true
  error.value = ''
  try {
    const result = await platformBillingApi.listInvoices({ invoice_type: 'platform', limit: 100 })
    invoices.value = result.items
    total.value = result.total
  } catch {
    error.value = 'Kon facturen niet laden'
  } finally {
    loading.value = false
  }
}

async function confirmMarkPaid() {
  if (!actionTarget.value) return
  const invoice = actionTarget.value
  actionFeedback.value = ''
  actionError.value = ''
  try {
    const updated = await platformBillingApi.markInvoicePaid(invoice.id)
    const idx = invoices.value.findIndex(i => i.id === invoice.id)
    if (idx !== -1) invoices.value[idx] = updated
    actionFeedback.value = `Factuur ${invoice.invoice_number} als betaald gemarkeerd`
    setTimeout(() => { actionFeedback.value = '' }, 4000)
  } catch {
    actionError.value = 'Kon factuur niet als betaald markeren'
  } finally {
    cancelModal()
  }
}

async function confirmDunning() {
  if (!actionTarget.value) return
  const invoice = actionTarget.value
  actionFeedback.value = ''
  actionError.value = ''
  try {
    const result = await sendDunningReminders({ invoice_id: invoice.id })
    actionFeedback.value = result.sent > 0
      ? `Herinnering verstuurd voor ${invoice.invoice_number}`
      : 'Geen herinnering verstuurd (mogelijk al recent verzonden)'
    setTimeout(() => { actionFeedback.value = '' }, 4000)
    await load()
  } catch {
    actionError.value = 'Kon herinnering niet versturen'
  } finally {
    cancelModal()
  }
}

onMounted(() => {
  load()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Receipt class="w-6 h-6 text-navy-700" />
        <h2 :class="theme.text.h2">Facturen</h2>
      </div>
      <span v-if="!loading && !error" :class="theme.text.muted" class="text-sm">
        {{ total }} facturen
      </span>
    </div>

    <!-- Alerts -->
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="actionFeedback" :class="theme.alert.success">{{ actionFeedback }}</div>
    </Transition>
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>
    <div v-if="actionError" :class="theme.alert.error">{{ actionError }}</div>

    <!-- ──── Loading Skeleton ──── -->
    <template v-if="loading">
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

      <!-- Insight widgets skeleton -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div :class="theme.card.base" class="overflow-hidden skeleton-card" style="animation-delay: 400ms">
          <div class="px-5 pt-5 pb-3 flex items-center gap-2">
            <div class="h-4 w-4 bg-navy-100 rounded animate-pulse" />
            <div class="h-5 w-28 bg-navy-100 rounded animate-pulse" />
          </div>
          <div class="px-5 pb-5 space-y-4">
            <div v-for="n in 2" :key="n" class="space-y-1.5">
              <div class="flex items-center justify-between">
                <div class="h-3.5 w-16 bg-navy-100 rounded animate-pulse" />
                <div class="h-3.5 w-20 bg-navy-100 rounded animate-pulse" />
              </div>
              <div class="h-2 bg-navy-100 rounded-full animate-pulse" :style="{ width: `${70 - n * 20}%` }" />
            </div>
          </div>
        </div>
        <div :class="theme.card.base" class="overflow-hidden lg:col-span-2 skeleton-card" style="animation-delay: 480ms">
          <div class="px-5 pt-5 pb-3 flex items-center gap-2">
            <div class="h-4 w-4 bg-navy-100 rounded animate-pulse" />
            <div class="h-5 w-36 bg-navy-100 rounded animate-pulse" />
          </div>
          <div class="px-5 pb-5 space-y-3">
            <div v-for="n in 4" :key="n" class="flex items-center gap-3 animate-pulse">
              <div class="w-7 h-7 bg-navy-100 rounded-full shrink-0" />
              <div class="flex-1 space-y-1">
                <div class="h-3.5 bg-navy-100 rounded" :style="{ width: `${50 + n * 8}%` }" />
                <div class="h-3 w-16 bg-navy-50 rounded" />
              </div>
              <div class="h-3.5 w-20 bg-navy-100 rounded shrink-0" />
            </div>
          </div>
        </div>
      </div>

      <!-- Table skeleton -->
      <div class="overflow-x-auto rounded-xl border border-navy-100">
        <table class="min-w-full table-fixed">
          <thead class="bg-surface">
            <tr><th :colspan="columns.length + 1" class="h-[46px]" /></tr>
          </thead>
          <tbody class="bg-white divide-y divide-navy-50">
            <tr
              v-for="row in skeletonRows"
              :key="'skeleton-' + row.id"
              class="skeleton-row-enter"
              :style="{ animationDelay: (row.id + 4) * 50 + 'ms' }"
            >
              <td v-for="(w, ci) in row.cells" :key="ci" class="px-4 py-4">
                <div class="h-4 bg-navy-100 rounded animate-pulse" :style="{ width: w }" />
              </td>
              <td class="px-4 py-4">
                <div class="h-4 bg-navy-100 rounded animate-pulse" style="width: 60px" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ──── Loaded Content ──── -->
    <template v-else-if="invoices.length > 0">
      <!-- ─── Summary Cards ─── -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <!-- Total invoices -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.default]">
            <FileText :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ total }}</p>
            <p :class="theme.stat.label">Totaal</p>
          </div>
        </div>

        <!-- Paid -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.green]">
            <CheckCircle :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value" class="!text-green-600">{{ paidCount }}</p>
            <p :class="theme.stat.label">Betaald</p>
            <p :class="theme.stat.sub">{{ formatCents(totalPaidCents) }}</p>
          </div>
        </div>

        <!-- Open/overdue -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, overdueCount > 0 ? theme.stat.iconVariant.red : theme.stat.iconVariant.accent]">
            <Hourglass :size="20" />
          </div>
          <div>
            <p :class="[theme.stat.value, overdueCount > 0 ? '!text-red-500' : '']">{{ openCount }}</p>
            <p :class="theme.stat.label">Openstaand</p>
            <p v-if="overdueCount > 0" class="text-xs text-red-500 mt-0.5">{{ overdueCount }} achterstallig</p>
          </div>
        </div>

        <!-- Outstanding amount -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.accent]">
            <CircleDollarSign :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ formatCents(totalOutstandingCents) }}</p>
            <p :class="theme.stat.label">Te ontvangen</p>
          </div>
        </div>
      </div>

      <!-- ─── Top Outstanding Debtors ─── -->
      <div>
        <div :class="theme.card.base" class="overflow-hidden flex flex-col">
          <div class="flex items-center justify-between px-5 pt-5 pb-3">
            <div class="flex items-center gap-2">
              <Users :size="18" class="text-navy-400" />
              <h3 :class="theme.text.h3">Hoogste openstaand</h3>
            </div>
            <RouterLink to="/platform/finance/outstanding" class="flex items-center gap-1 text-xs font-medium text-accent-700 hover:text-accent-800 transition-colors">
              Overzicht <ExternalLink :size="12" />
            </RouterLink>
          </div>

          <!-- Empty -->
          <div v-if="topDebtors.length === 0" class="flex-1 flex items-center justify-center px-5 pb-5">
            <div class="text-center py-4">
              <CheckCircle :size="20" class="text-green-400 mx-auto mb-1.5" />
              <p :class="theme.text.muted" class="text-sm">Geen openstaande facturen</p>
            </div>
          </div>

          <!-- Debtor list -->
          <div v-else class="flex-1 divide-y divide-navy-50">
            <div
              v-for="(debtor, idx) in topDebtors"
              :key="idx"
              class="flex items-center gap-3 px-5 py-3"
            >
              <!-- Avatar -->
              <div
                class="w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold bg-accent-50 text-accent-700"
              >
                {{ (debtor.orgName || debtor.name)[0]?.toUpperCase() }}
              </div>
              <!-- Name + count -->
              <div class="flex-1 min-w-0">
                <p class="text-sm text-navy-900 font-medium truncate">{{ debtor.orgName || debtor.name }}</p>
                <p :class="theme.text.muted" class="text-xs">
                  <template v-if="debtor.orgName">{{ debtor.name }} &middot; </template>
                  {{ debtor.count }} factuur{{ debtor.count === 1 ? '' : 'en' }}
                </p>
              </div>
              <!-- Bar + amount -->
              <div class="flex items-center gap-2.5 shrink-0">
                <div class="w-20 h-1.5 rounded-full overflow-hidden bg-navy-100 hidden md:block">
                  <div
                    class="h-full rounded-full transition-all duration-700"
                    :class="debtor.total > (topDebtors[0]?.total ?? 0) * 0.7 ? 'bg-red-400' : 'bg-orange-300'"
                    :style="{ width: Math.round((debtor.total / (topDebtors[0]?.total || 1)) * 100) + '%' }"
                  />
                </div>
                <span class="text-sm font-bold text-navy-900 w-24 text-right">{{ formatCents(debtor.total) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Table ─── -->
      <div class="overflow-x-auto rounded-xl border border-navy-100">
        <table class="min-w-full divide-y divide-navy-200 text-sm table-fixed">
          <colgroup>
            <col v-for="col in columns" :key="'col-' + col.key" :style="{ width: col.width }" />
            <col :style="{ width: actionsWidth }" />
          </colgroup>

          <!-- Header -->
          <thead class="bg-surface text-navy-700 font-semibold">
            <tr>
              <th
                v-for="col in columns"
                :key="col.key"
                :ref="(el: any) => { if (el) headerRefs[col.key] = el }"
                class="px-4 h-[46px] select-none"
                :class="[
                  alignClass(col),
                  searchableKeys.includes(col.key) || col.sortable ? 'cursor-pointer' : '',
                  col.hiddenMobile ? 'hidden md:table-cell' : '',
                ]"
                :style="columnWidths[col.key] ? { width: columnWidths[col.key] + 'px', minWidth: columnWidths[col.key] + 'px' } : {}"
                @click.stop="searchableKeys.includes(col.key) ? activateSearch(col.key) : col.sortable ? handleSort(col.key) : undefined"
              >
                <!-- Search active -->
                <div v-if="activeSearch === col.key" class="flex items-center gap-1">
                  <input
                    :ref="(el: any) => { if (el) searchInputRefs[col.key] = el }"
                    v-model="searchFilters[col.key]"
                    type="text"
                    :placeholder="col.label"
                    class="w-full px-2 py-1 text-sm font-normal border border-navy-200 rounded focus:outline-none focus:border-accent-700 focus:ring-1 focus:ring-accent-200"
                    @click.stop
                    @keydown.escape="deactivateSearch()"
                    @keydown.enter="deactivateSearch()"
                  />
                  <button
                    v-if="searchFilters[col.key]"
                    class="text-navy-300 hover:text-navy-600 shrink-0"
                    @click.stop="clearAndDeactivate(col.key)"
                  >
                    <X class="w-3.5 h-3.5" />
                  </button>
                </div>

                <!-- Normal header -->
                <div v-else class="flex items-center gap-1" :class="{ 'justify-end': col.align === 'right', 'justify-center': col.align === 'center' }">
                  <component
                    :is="col.icon"
                    v-if="col.icon && !searchFilters[col.key]"
                    class="w-3.5 h-3.5 text-navy-300 shrink-0"
                  />
                  <span v-if="!searchFilters[col.key]">{{ col.label }}</span>
                  <!-- Active search chip -->
                  <span
                    v-else
                    class="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full text-xs font-medium bg-accent-50 text-accent-700 cursor-pointer"
                    @click.stop="activateSearch(col.key)"
                  >
                    {{ searchFilters[col.key] }}
                    <button
                      class="text-accent-700 hover:text-red-500 transition-colors"
                      @click.stop="clearAndDeactivate(col.key)"
                    >
                      <X class="w-3 h-3" />
                    </button>
                  </span>
                  <!-- Sort button -->
                  <button
                    v-if="col.sortable"
                    class="shrink-0 p-0.5 rounded hover:bg-navy-100 transition-colors"
                    :class="[
                      sortColumn === col.key ? 'text-accent-700' : 'text-navy-300',
                      col.align !== 'right' ? 'ml-auto' : '',
                    ]"
                    @click.stop="handleSort(col.key)"
                  >
                    <ArrowUp v-if="sortColumn === col.key && sortDirection === 'asc'" class="w-3.5 h-3.5" />
                    <ArrowDown v-else-if="sortColumn === col.key && sortDirection === 'desc'" class="w-3.5 h-3.5" />
                    <ArrowUpDown v-else class="w-3.5 h-3.5" />
                  </button>
                </div>
              </th>
              <!-- Actions header -->
              <th class="px-4 h-[46px] text-left">
                <div class="flex items-center gap-1">
                  <Zap class="w-3.5 h-3.5 text-navy-300 shrink-0" />
                  <span>Acties</span>
                </div>
              </th>
            </tr>
            <!-- Status distribution row -->
            <tr>
              <th :colspan="columns.length + 1" class="p-0">
                <div class="flex items-center gap-3 px-4 py-1.5 bg-white border-t border-navy-50">
                  <div class="flex-1 h-1.5 rounded-full overflow-hidden flex bg-navy-100">
                    <div
                      v-if="statusDistribution.paid.pct > 0"
                      class="h-full bg-green-400 transition-all duration-500"
                      :style="{ width: statusDistribution.paid.pct + '%' }"
                    />
                    <div
                      v-if="statusDistribution.open.pct > 0"
                      class="h-full bg-accent-400 transition-all duration-500"
                      :style="{ width: statusDistribution.open.pct + '%' }"
                    />
                    <div
                      v-if="statusDistribution.overdue.pct > 0"
                      class="h-full bg-red-400 transition-all duration-500"
                      :style="{ width: statusDistribution.overdue.pct + '%' }"
                    />
                    <div
                      v-if="statusDistribution.other.pct > 0"
                      class="h-full bg-navy-300 transition-all duration-500"
                      :style="{ width: statusDistribution.other.pct + '%' }"
                    />
                  </div>
                  <div class="flex items-center gap-2.5 shrink-0">
                    <span v-if="statusDistribution.paid.count > 0" class="flex items-center gap-1 text-[10px] font-medium text-green-700">
                      <span class="w-1.5 h-1.5 rounded-full bg-green-400" />
                      {{ statusDistribution.paid.count }}
                    </span>
                    <span v-if="statusDistribution.open.count > 0" class="flex items-center gap-1 text-[10px] font-medium text-accent-700">
                      <span class="w-1.5 h-1.5 rounded-full bg-accent-400" />
                      {{ statusDistribution.open.count }}
                    </span>
                    <span v-if="statusDistribution.overdue.count > 0" class="flex items-center gap-1 text-[10px] font-medium text-red-700">
                      <span class="w-1.5 h-1.5 rounded-full bg-red-400" />
                      {{ statusDistribution.overdue.count }}
                    </span>
                  </div>
                </div>
              </th>
            </tr>
          </thead>

          <!-- Empty state -->
          <tbody v-if="sorted.length === 0" class="bg-white">
            <tr>
              <td :colspan="columns.length + 1" class="text-center py-12">
                <p :class="theme.text.muted">Geen facturen gevonden</p>
              </td>
            </tr>
          </tbody>

          <!-- Data rows -->
          <tbody v-else class="bg-white divide-y divide-navy-50">
            <template v-for="inv in sorted" :key="inv.id">
              <tr
                class="hover:bg-surface transition-colors cursor-pointer group"
                :class="inv.status === 'overdue' ? 'bg-red-50/30' : ''"
                @click="toggleExpand(inv.id)"
              >
                <!-- Expand chevron -->
                <td class="px-4 py-3">
                  <ChevronDown
                    :size="16"
                    class="transition-transform duration-200 text-navy-200 group-hover:text-accent-700"
                    :class="expandedId === inv.id ? 'rotate-0 text-accent-700' : '-rotate-90'"
                  />
                </td>
                <!-- Date -->
                <td class="px-4 py-3">
                  <span class="text-xs text-navy-700 block">{{ formatDate(inv.created_at) }}</span>
                  <span v-if="timeAgo(inv.created_at)" :class="theme.text.muted" class="text-[10px]">{{ timeAgo(inv.created_at) }}</span>
                </td>
                <!-- Invoice number -->
                <td class="px-4 py-3">
                  <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-navy-50 font-mono text-xs text-navy-700">
                    <Receipt :size="11" class="text-navy-400" />
                    {{ inv.invoice_number }}
                  </span>
                </td>
                <!-- Organisation / Recipient -->
                <td class="px-4 py-3 hidden md:table-cell">
                  <div class="flex items-center gap-2.5 min-w-0">
                    <div class="w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold bg-accent-50 text-accent-700">
                      {{ (inv.tenant_name || inv.recipient_name)[0]?.toUpperCase() }}
                    </div>
                    <div class="min-w-0">
                      <p v-if="inv.tenant_name" class="text-sm text-navy-900 font-medium truncate">{{ inv.tenant_name }}</p>
                      <p class="text-navy-500 truncate" :class="inv.tenant_name ? 'text-xs' : 'text-sm text-navy-900'">{{ inv.recipient_name }}</p>
                    </div>
                  </div>
                </td>
                <!-- Amount + due date urgency bar -->
                <td class="px-4 py-3 text-right">
                  <span class="font-semibold text-navy-900">{{ formatCents(inv.total_cents) }}</span>
                  <div v-if="dueUrgency(inv)" class="mt-1.5 flex items-center gap-1.5 justify-end">
                    <div class="flex-1 max-w-[80px] h-1.5 rounded-full overflow-hidden bg-navy-100">
                      <div
                        class="h-full rounded-full transition-all duration-700"
                        :class="dueUrgency(inv)!.color"
                        :style="{ width: dueUrgency(inv)!.pct + '%' }"
                      />
                    </div>
                    <span
                      class="text-[10px] font-medium w-[45px] text-right"
                      :class="dueUrgency(inv)!.color.includes('red') ? 'text-red-600' : dueUrgency(inv)!.color.includes('orange') ? 'text-orange-600' : dueUrgency(inv)!.color.includes('yellow') ? 'text-yellow-600' : 'text-navy-400'"
                    >{{ dueUrgency(inv)!.label }}</span>
                  </div>
                  <div v-else-if="inv.status === 'paid'" class="mt-1 flex items-center gap-1 justify-end">
                    <CheckCircle :size="10" class="text-green-400" />
                    <span class="text-[10px] text-green-600 font-medium">Voldaan</span>
                  </div>
                </td>
                <!-- Dunning count -->
                <td class="px-4 py-3 hidden md:table-cell">
                  <div v-if="inv.dunning_count > 0" class="flex items-center gap-1">
                    <div class="flex gap-0.5">
                      <span
                        v-for="n in Math.min(inv.dunning_count, 3)"
                        :key="n"
                        class="w-2 h-2 rounded-full"
                        :class="n <= 1 ? 'bg-yellow-400' : n === 2 ? 'bg-orange-400' : 'bg-red-400'"
                      />
                    </div>
                    <span class="font-medium text-navy-900 text-xs ml-0.5">{{ inv.dunning_count }}x</span>
                  </div>
                  <span v-else :class="theme.text.muted" class="text-xs">&mdash;</span>
                </td>
                <!-- Actions -->
                <td class="px-4 py-3" @click.stop>
                  <div class="flex items-center gap-1">
                    <IconButton
                      v-if="(inv.status === 'open' || inv.status === 'overdue') && hasPermission('billing.manage')"
                      variant="success"
                      title="Als betaald markeren"
                      @click="promptMarkPaid(inv)"
                    >
                      <CheckCircle :size="14" />
                    </IconButton>
                    <IconButton
                      v-if="(inv.status === 'open' || inv.status === 'overdue') && hasPermission('finance.manage_dunning')"
                      variant="warning"
                      title="Herinnering versturen"
                      @click="promptDunning(inv)"
                    >
                      <Send :size="14" />
                    </IconButton>
                  </div>
                </td>
              </tr>

              <!-- Expanded detail -->
              <tr v-if="expandedId === inv.id">
                <td :colspan="columns.length + 1" class="p-0">
                  <div class="bg-surface border-t border-navy-100 px-5 py-5">
                    <div class="flex flex-col lg:flex-row gap-5">

                      <!-- Left: Organisatie & Ontvanger card -->
                      <div class="bg-white rounded-xl border border-navy-100 p-4 lg:w-1/3">
                        <div class="flex items-center gap-3 mb-3">
                          <div class="w-9 h-9 rounded-full bg-accent-50 flex items-center justify-center text-sm font-bold text-accent-700">
                            {{ (inv.tenant_name || inv.recipient_name)[0]?.toUpperCase() }}
                          </div>
                          <div class="min-w-0">
                            <p v-if="inv.tenant_name" class="font-semibold text-navy-900 truncate">{{ inv.tenant_name }}</p>
                            <p class="text-navy-700 truncate" :class="inv.tenant_name ? 'text-xs' : 'font-semibold text-navy-900'">{{ inv.recipient_name }}</p>
                            <p class="text-xs text-muted truncate">{{ inv.recipient_email }}</p>
                          </div>
                        </div>
                        <div class="space-y-2 text-sm">
                          <div v-if="inv.recipient_address">
                            <p class="text-xs text-muted mb-0.5">Adres</p>
                            <p class="text-navy-700 text-xs whitespace-pre-line leading-relaxed">{{ inv.recipient_address }}</p>
                          </div>
                        </div>
                      </div>

                      <!-- Center: Bedragen card -->
                      <div class="bg-white rounded-xl border border-navy-100 p-4 lg:w-1/3">
                        <p class="text-xs font-semibold text-navy-700 uppercase tracking-wide mb-3">Bedragen</p>
                        <div class="space-y-2.5">
                          <div class="flex items-center justify-between text-sm">
                            <span class="text-muted">Subtotaal</span>
                            <span class="text-navy-900">{{ formatCents(inv.subtotal_cents) }}</span>
                          </div>
                          <div class="flex items-center justify-between text-sm">
                            <span class="text-muted">BTW</span>
                            <span class="text-navy-900">{{ formatCents(inv.tax_cents) }}</span>
                          </div>
                          <div class="flex items-center justify-between text-sm pt-2.5 border-t border-navy-100">
                            <span class="font-semibold text-navy-900">Totaal</span>
                            <span class="font-bold text-lg text-navy-900">{{ formatCents(inv.total_cents) }}</span>
                          </div>
                        </div>
                        <div v-if="inv.due_date" class="mt-3 pt-3 border-t border-navy-50 flex items-center justify-between text-sm">
                          <span class="text-muted flex items-center gap-1"><AlertTriangle :size="12" /> Vervaldatum</span>
                          <span class="font-medium text-navy-900">{{ formatDate(inv.due_date) }}</span>
                        </div>
                      </div>

                      <!-- Right: Status & Timeline card -->
                      <div class="bg-white rounded-xl border border-navy-100 p-4 lg:w-1/3">
                        <p class="text-xs font-semibold text-navy-700 uppercase tracking-wide mb-3">Status & Tijdlijn</p>
                        <div class="space-y-3">
                          <!-- Created -->
                          <div class="flex items-start gap-2.5">
                            <div class="mt-0.5 w-5 h-5 rounded-full bg-navy-50 flex items-center justify-center shrink-0">
                              <Calendar :size="11" class="text-navy-400" />
                            </div>
                            <div>
                              <p class="text-xs text-muted">Aangemaakt</p>
                              <p class="text-sm text-navy-900">{{ formatDateTime(inv.created_at) }}</p>
                            </div>
                          </div>
                          <!-- Paid -->
                          <div class="flex items-start gap-2.5">
                            <div class="mt-0.5 w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                              :class="inv.paid_at ? 'bg-green-50' : 'bg-navy-50'"
                            >
                              <CheckCircle :size="11" :class="inv.paid_at ? 'text-green-500' : 'text-navy-300'" />
                            </div>
                            <div>
                              <p class="text-xs text-muted">Betaald op</p>
                              <p class="text-sm" :class="inv.paid_at ? 'text-green-700 font-medium' : 'text-navy-400'">{{ formatDateTime(inv.paid_at) }}</p>
                            </div>
                          </div>
                          <!-- Dunning -->
                          <div class="flex items-start gap-2.5">
                            <div class="mt-0.5 w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                              :class="inv.dunning_count > 0 ? 'bg-yellow-50' : 'bg-navy-50'"
                            >
                              <Bell :size="11" :class="inv.dunning_count > 0 ? 'text-yellow-500' : 'text-navy-300'" />
                            </div>
                            <div>
                              <p class="text-xs text-muted">Herinneringen</p>
                              <p class="text-sm text-navy-900">
                                <template v-if="inv.dunning_count > 0">
                                  <span class="font-medium">{{ inv.dunning_count }}x</span>
                                  <span class="text-muted"> &middot; laatst {{ formatDateTime(inv.dunning_last_sent_at) }}</span>
                                </template>
                                <span v-else class="text-navy-400">Geen</span>
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>

                    </div>

                    <!-- Description (full width) -->
                    <div v-if="inv.description" class="mt-4 bg-white rounded-xl border border-navy-100 p-4">
                      <p class="text-xs font-semibold text-navy-700 uppercase tracking-wide mb-1.5">Omschrijving</p>
                      <p class="text-sm text-navy-700 leading-relaxed">{{ inv.description }}</p>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <!-- Footer -->
        <div class="py-2.5 px-4 border-t border-navy-100 bg-surface text-center">
          <span :class="theme.text.muted" class="text-xs">{{ sorted.length }} van {{ total }} facturen</span>
        </div>
      </div>
    </template>

    <!-- ──── Empty state (no invoices at all) ──── -->
    <div v-else-if="!error" :class="theme.emptyState.wrapper">
      <div :class="theme.emptyState.iconWrap">
        <Receipt :class="theme.emptyState.icon" :size="24" />
      </div>
      <p :class="theme.emptyState.title">Geen facturen</p>
      <p :class="theme.emptyState.description">Er zijn nog geen facturen aangemaakt.</p>
    </div>

    <!-- Mark paid confirmation -->
    <ConfirmModal
      :open="markPaidModal"
      title="Factuur als betaald markeren"
      :message="`Weet je zeker dat je factuur ${actionTarget?.invoice_number ?? ''} als betaald wilt markeren?`"
      confirm-label="Markeer als betaald"
      variant="accent"
      @confirm="confirmMarkPaid"
      @cancel="cancelModal"
    />

    <!-- Send dunning confirmation -->
    <ConfirmModal
      :open="dunningModal"
      title="Herinnering versturen"
      :message="`Wilt u een betalingsherinnering versturen voor factuur ${actionTarget?.invoice_number ?? ''}?${actionTarget && actionTarget.dunning_count > 0 ? ` Er zijn al ${actionTarget.dunning_count} herinnering(en) verstuurd.` : ''}`"
      confirm-label="Verstuur herinnering"
      variant="primary"
      @confirm="confirmDunning"
      @cancel="cancelModal"
    />
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
