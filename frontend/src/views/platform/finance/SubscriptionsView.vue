<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { platformBillingApi } from '@/api/platform/billing'
import { formatCents } from '@/types/billing'
import type { SubscriptionOverviewItem, ResumeMode } from '@/types/billing'
import { usePermissions } from '@/composables/usePermissions'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import { StatCard } from '@/components/platform/widgets'
import IconButton from '@/components/ui/IconButton.vue'
import {
  CreditCard, Building2, Banknote, Calendar, Receipt, Zap, Package,
  ChevronDown, ArrowUp, ArrowDown, ArrowUpDown, X,
  Pause, Play, XCircle, CheckCircle, Clock, PauseCircle,
} from 'lucide-vue-next'
import { theme } from '@/theme'

const { hasPermission } = usePermissions()

// ─── Data ───
const items = ref<SubscriptionOverviewItem[]>([])
const total = ref(0)
const loading = ref(true)
const error = ref('')
const actionFeedback = ref('')
const actionError = ref('')
const expandedId = ref<string | null>(null)

// ─── Column definitions ───
interface Column {
  key: string
  label: string
  width: string
  icon?: object
  sortable?: boolean
  searchable?: boolean
  hiddenMobile?: boolean
  align?: 'left' | 'center' | 'right'
}

const columns: Column[] = [
  { key: 'expand', label: '', width: '4%' },
  { key: 'tenant_name', label: 'Organisatie', width: '24%', icon: Building2, sortable: true, searchable: true },
  { key: 'plan_name', label: 'Plan', width: '14%', icon: Package, sortable: true, searchable: true, hiddenMobile: true },
  { key: 'status', label: 'Status', width: '12%', align: 'center' },
  { key: 'plan_price_cents', label: 'Prijs /mnd', width: '13%', icon: Banknote, sortable: true, align: 'right' },
  { key: 'next_invoice_date', label: 'Volg. factuur', width: '13%', icon: Calendar, sortable: true, hiddenMobile: true },
  { key: 'total_invoiced_cents', label: 'Gefactureerd', width: '12%', icon: Receipt, hiddenMobile: true, align: 'right' },
]

const actionsWidth = '8%'
const searchableKeys = columns.filter(c => c.searchable).map(c => c.key)

// ─── Filters ───
const statusFilter = ref<string>('all')

const statusOptions = [
  { value: 'all', label: 'Alle' },
  { value: 'active', label: 'Actief' },
  { value: 'trialing', label: 'Proef' },
  { value: 'paused', label: 'Gepauzeerd' },
  { value: 'past_due', label: 'Achterstallig' },
  { value: 'cancelled', label: 'Opgezegd' },
]

// ─── Fetch ───
async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const res = await platformBillingApi.listSubscriptionsOverview({
      page: 1,
      page_size: 100,
    })
    items.value = res.items
    total.value = res.total
  } catch {
    error.value = 'Kon abonnementen niet laden.'
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

function applyFilter(status: string) {
  statusFilter.value = status
}

// ─── Sorting (3-state: neutral → desc → asc → neutral) ───
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
const searchFilters = reactive<Record<string, string>>({
  tenant_name: '',
  plan_name: '',
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

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))

// ─── Filtered + sorted (client-side) ───
const filtered = computed(() => {
  let list = items.value

  // Status filter
  if (statusFilter.value !== 'all') {
    list = list.filter(s => s.status === statusFilter.value)
  }

  // Column search
  const tn = searchFilters.tenant_name?.toLowerCase()
  const pn = searchFilters.plan_name?.toLowerCase()
  if (tn || pn) {
    list = list.filter(s => {
      if (tn && !s.tenant_name.toLowerCase().includes(tn)) return false
      if (pn && !s.plan_name.toLowerCase().includes(pn)) return false
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
      case 'tenant_name': return a.tenant_name.localeCompare(b.tenant_name) * dir
      case 'plan_name': return a.plan_name.localeCompare(b.plan_name) * dir
      case 'plan_price_cents': return (a.plan_price_cents - b.plan_price_cents) * dir
      case 'next_invoice_date': {
        const da = a.next_invoice_date ? new Date(a.next_invoice_date).getTime() : 0
        const db = b.next_invoice_date ? new Date(b.next_invoice_date).getTime() : 0
        return (da - db) * dir
      }
      default: return 0
    }
  })
  return list
})

function alignClass(col: Column): string {
  if (col.align === 'right') return 'text-right'
  if (col.align === 'center') return 'text-center'
  return 'text-left'
}

// ─── Expand ───
function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

// ─── Status helpers ───
function statusBadge(status: string): string {
  switch (status) {
    case 'active': return theme.badge.success
    case 'trialing': return theme.badge.warning
    case 'paused': return theme.badge.default
    case 'past_due': return theme.badge.error
    case 'cancelled': return theme.badge.default
    default: return theme.badge.default
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'active': return 'Actief'
    case 'trialing': return 'Proef'
    case 'paused': return 'Gepauzeerd'
    case 'past_due': return 'Achterstallig'
    case 'cancelled': return 'Opgezegd'
    case 'expired': return 'Verlopen'
    default: return status
  }
}

// ─── Summary stats (always based on full dataset) ───
const activeCount = computed(() => items.value.filter(s => s.status === 'active').length)
const trialingCount = computed(() => items.value.filter(s => s.status === 'trialing').length)
const pausedCount = computed(() => items.value.filter(s => s.status === 'paused').length)
const pastDueCount = computed(() => items.value.filter(s => s.status === 'past_due').length)
const mrrCents = computed(() =>
  items.value
    .filter(s => s.status === 'active' || s.status === 'trialing')
    .reduce((sum, s) => sum + s.plan_price_cents, 0)
)

// ─── Status distribution (for bar in table header, based on visible rows) ───
const statusDistribution = computed(() => {
  const visible = sorted.value
  const t = visible.length || 1
  const ac = visible.filter(s => s.status === 'active').length
  const tr = visible.filter(s => s.status === 'trialing').length
  const pa = visible.filter(s => s.status === 'paused').length
  const pd = visible.filter(s => s.status === 'past_due').length
  return {
    active: { count: ac, pct: (ac / t) * 100 },
    trialing: { count: tr, pct: (tr / t) * 100 },
    paused: { count: pa, pct: (pa / t) * 100 },
    past_due: { count: pd, pct: (pd / t) * 100 },
  }
})

// ─── Actions ───
const pauseModal = ref(false)
const cancelModal = ref(false)
const resumeModal = ref(false)
const actionTarget = ref<SubscriptionOverviewItem | null>(null)
const resumeMode = ref<ResumeMode>('next_month')
const resumeLoading = ref(false)

function promptPause(item: SubscriptionOverviewItem) {
  actionTarget.value = item
  pauseModal.value = true
}

function promptCancel(item: SubscriptionOverviewItem) {
  actionTarget.value = item
  cancelModal.value = true
}

function promptResume(item: SubscriptionOverviewItem) {
  actionTarget.value = item
  resumeMode.value = 'next_month'
  resumeModal.value = true
}

function closeModals() {
  pauseModal.value = false
  cancelModal.value = false
  resumeModal.value = false
  resumeLoading.value = false
  actionTarget.value = null
}

async function confirmPause() {
  if (!actionTarget.value) return
  try {
    await platformBillingApi.pauseSubscription(actionTarget.value.tenant_id)
    actionFeedback.value = `Abonnement van ${actionTarget.value.tenant_name} gepauzeerd.`
    closeModals()
    await fetchData()
  } catch {
    actionError.value = 'Kon abonnement niet pauzeren.'
    closeModals()
  }
}

async function confirmCancel() {
  if (!actionTarget.value) return
  try {
    await platformBillingApi.cancelSubscription(actionTarget.value.tenant_id)
    actionFeedback.value = `Abonnement van ${actionTarget.value.tenant_name} opgezegd.`
    closeModals()
    await fetchData()
  } catch {
    actionError.value = 'Kon abonnement niet opzeggen.'
    closeModals()
  }
}

async function confirmResume() {
  if (!actionTarget.value) return
  resumeLoading.value = true
  try {
    const result = await platformBillingApi.resumeSubscription(
      actionTarget.value.tenant_id,
      resumeMode.value,
    )
    const invoiceMsg = result.invoices_generated > 0
      ? ` (${result.invoices_generated} factuur${result.invoices_generated > 1 ? 'en' : ''} aangemaakt)`
      : ''
    actionFeedback.value = `Abonnement van ${actionTarget.value.tenant_name} hervat${invoiceMsg}.`
    closeModals()
    await fetchData()
  } catch {
    actionError.value = 'Kon abonnement niet hervatten.'
    closeModals()
  }
}

const resumeModeLabels: Record<ResumeMode, { title: string; description: string }> = {
  backfill: {
    title: 'Alle gemiste maanden factureren',
    description: 'Genereert een factuur voor elke maand sinds de pauze.',
  },
  prorata: {
    title: 'Pro-rata huidige maand',
    description: 'Eén factuur voor de resterende dagen van deze maand.',
  },
  next_month: {
    title: 'Vanaf volgende maand',
    description: 'Geen facturen nu — de normale facturatie start volgende maand.',
  },
}


function formatDate(d: string | null): string {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('nl-NL', { day: '2-digit', month: 'short', year: 'numeric' })
}
</script>

<template>
  <div>
    <!-- Header -->
    <div :class="theme.pageHeader.rowResponsive">
      <div class="flex items-center gap-2">
        <CreditCard class="w-6 h-6 text-navy-700" />
        <div>
          <h2 :class="theme.text.h2">Abonnementen</h2>
        </div>
      </div>
    </div>

    <!-- Feedback -->
    <div v-if="actionFeedback" :class="theme.alert.success" class="flex items-center justify-between">
      <span>{{ actionFeedback }}</span>
      <button class="text-green-500 hover:text-green-700" @click="actionFeedback = ''">&times;</button>
    </div>
    <div v-if="actionError" :class="theme.alert.error" class="flex items-center justify-between">
      <span>{{ actionError }}</span>
      <button class="text-red-500 hover:text-red-700" @click="actionError = ''">&times;</button>
    </div>

    <!-- Summary cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <StatCard
        label="Actief"
        :value="activeCount"
        :icon="CheckCircle"
        variant="green"
      />
      <StatCard
        label="Proef"
        :value="trialingCount"
        :icon="Clock"
        variant="accent"
      />
      <StatCard
        label="Gepauzeerd"
        :value="pausedCount"
        :icon="PauseCircle"
        variant="default"
      />
      <StatCard
        label="MRR"
        :value="formatCents(mrrCents)"
        :icon="Banknote"
        variant="primary"
      />
    </div>

    <!-- Status filter pills -->
    <div class="flex flex-wrap gap-2 mb-4">
      <button
        v-for="opt in statusOptions"
        :key="opt.value"
        :class="[
          theme.badge.base,
          statusFilter === opt.value
            ? 'bg-accent-700 text-white ring-1 ring-accent-700'
            : theme.badge.default,
          'cursor-pointer transition-colors hover:opacity-80',
        ]"
        @click="applyFilter(opt.value)"
      >
        {{ opt.label }}
      </button>
    </div>

    <!-- Error state -->
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <!-- Loading -->
    <div v-if="loading" :class="theme.list.empty">
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <!-- Table -->
    <div v-else-if="items.length" class="overflow-x-auto rounded-xl border border-navy-100">
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
            <th class="px-4 h-[46px] text-left hidden md:table-cell">
              <div class="flex items-center gap-1">
                <Zap class="w-3.5 h-3.5 text-navy-300 shrink-0" />
                <span>Acties</span>
              </div>
            </th>
          </tr>
          <!-- Status distribution bar -->
          <tr>
            <th :colspan="columns.length + 1" class="p-0">
              <div class="flex items-center gap-3 px-4 py-1.5 bg-white border-t border-navy-50">
                <div class="flex-1 h-1.5 rounded-full overflow-hidden flex bg-navy-100">
                  <div
                    v-if="statusDistribution.active.pct > 0"
                    class="h-full bg-green-400 transition-all duration-500"
                    :style="{ width: statusDistribution.active.pct + '%' }"
                  />
                  <div
                    v-if="statusDistribution.trialing.pct > 0"
                    class="h-full bg-yellow-400 transition-all duration-500"
                    :style="{ width: statusDistribution.trialing.pct + '%' }"
                  />
                  <div
                    v-if="statusDistribution.paused.pct > 0"
                    class="h-full bg-navy-300 transition-all duration-500"
                    :style="{ width: statusDistribution.paused.pct + '%' }"
                  />
                  <div
                    v-if="statusDistribution.past_due.pct > 0"
                    class="h-full bg-red-400 transition-all duration-500"
                    :style="{ width: statusDistribution.past_due.pct + '%' }"
                  />
                </div>
                <div class="flex items-center gap-2.5 shrink-0">
                  <span v-if="statusDistribution.active.count > 0" class="flex items-center gap-1 text-[10px] font-medium text-green-700">
                    <span class="w-1.5 h-1.5 rounded-full bg-green-400" />
                    {{ statusDistribution.active.count }}
                  </span>
                  <span v-if="statusDistribution.trialing.count > 0" class="flex items-center gap-1 text-[10px] font-medium text-yellow-700">
                    <span class="w-1.5 h-1.5 rounded-full bg-yellow-400" />
                    {{ statusDistribution.trialing.count }}
                  </span>
                  <span v-if="statusDistribution.paused.count > 0" class="flex items-center gap-1 text-[10px] font-medium text-navy-500">
                    <span class="w-1.5 h-1.5 rounded-full bg-navy-300" />
                    {{ statusDistribution.paused.count }}
                  </span>
                  <span v-if="statusDistribution.past_due.count > 0" class="flex items-center gap-1 text-[10px] font-medium text-red-700">
                    <span class="w-1.5 h-1.5 rounded-full bg-red-400" />
                    {{ statusDistribution.past_due.count }}
                  </span>
                </div>
              </div>
            </th>
          </tr>
        </thead>

        <!-- Empty filtered state -->
        <tbody v-if="sorted.length === 0" class="bg-white">
          <tr>
            <td :colspan="columns.length + 1" class="text-center py-12">
              <p :class="theme.text.muted">Geen abonnementen gevonden</p>
            </td>
          </tr>
        </tbody>

        <!-- Data rows -->
        <tbody v-else class="bg-white divide-y divide-navy-50">
          <template v-for="item in sorted" :key="item.subscription_id">
            <tr
              class="hover:bg-surface transition-colors cursor-pointer group"
              :class="item.status === 'past_due' ? 'bg-red-50/30' : ''"
              @click="toggleExpand(item.subscription_id)"
            >
              <!-- Expand chevron -->
              <td class="px-4 py-3">
                <ChevronDown
                  :size="16"
                  class="transition-transform duration-200 text-navy-200 group-hover:text-accent-700"
                  :class="expandedId === item.subscription_id ? 'rotate-0 text-accent-700' : '-rotate-90'"
                />
              </td>

              <!-- Organisation -->
              <td class="px-4 py-3">
                <div class="flex items-center gap-2.5 min-w-0">
                  <div class="w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold bg-accent-50 text-accent-700">
                    {{ item.tenant_name[0]?.toUpperCase() }}
                  </div>
                  <span class="text-sm text-navy-900 font-medium truncate">{{ item.tenant_name }}</span>
                </div>
              </td>

              <!-- Plan -->
              <td class="px-4 py-3 hidden md:table-cell">
                <span class="text-navy-700">{{ item.plan_name }}</span>
              </td>

              <!-- Status -->
              <td class="px-4 py-3 text-center">
                <span :class="[theme.badge.base, statusBadge(item.status)]">
                  {{ statusLabel(item.status) }}
                </span>
              </td>

              <!-- Price -->
              <td class="px-4 py-3 text-right">
                <span class="font-semibold text-navy-900">{{ formatCents(item.plan_price_cents) }}</span>
              </td>

              <!-- Next invoice -->
              <td class="px-4 py-3 hidden md:table-cell">
                <span class="text-xs text-navy-700">{{ item.next_invoice_date ? formatDate(item.next_invoice_date) : '—' }}</span>
              </td>

              <!-- Invoiced total -->
              <td class="px-4 py-3 text-right hidden md:table-cell">
                <span class="text-navy-700">{{ formatCents(item.total_invoiced_cents) }}</span>
                <span v-if="item.invoice_count" class="text-xs text-muted ml-1">({{ item.invoice_count }})</span>
              </td>

              <!-- Actions -->
              <td class="px-4 py-3 hidden md:table-cell" @click.stop>
                <div v-if="hasPermission('platform.manage_orgs')" class="flex items-center gap-1">
                  <IconButton
                    v-if="item.status === 'active' || item.status === 'trialing'"
                    variant="neutral"
                    title="Pauzeren"
                    @click="promptPause(item)"
                  >
                    <Pause :size="14" />
                  </IconButton>
                  <IconButton
                    v-else-if="item.status === 'paused'"
                    variant="success"
                    title="Hervatten"
                    @click="promptResume(item)"
                  >
                    <Play :size="14" />
                  </IconButton>
                  <IconButton
                    v-if="item.status !== 'cancelled'"
                    variant="danger"
                    title="Opzeggen"
                    @click="promptCancel(item)"
                  >
                    <XCircle :size="14" />
                  </IconButton>
                </div>
              </td>
            </tr>

            <!-- Expanded detail -->
            <tr v-if="expandedId === item.subscription_id">
              <td :colspan="columns.length + 1" class="p-0">
                <div class="bg-surface border-t border-navy-100 px-5 py-5">
                  <div class="flex flex-col lg:flex-row gap-5">

                    <!-- Abonnement card -->
                    <div class="bg-white rounded-xl border border-navy-100 p-5 lg:w-1/3">
                      <div class="flex items-center gap-3 mb-4">
                        <div class="w-9 h-9 rounded-full bg-accent-50 flex items-center justify-center text-sm font-bold text-accent-700">
                          {{ item.tenant_name[0]?.toUpperCase() }}
                        </div>
                        <div class="min-w-0">
                          <p class="font-semibold text-navy-900 truncate">{{ item.tenant_name }}</p>
                          <p class="text-xs text-muted">{{ item.plan_name }}</p>
                        </div>
                      </div>
                      <div class="space-y-3 text-sm">
                        <div class="flex items-center justify-between">
                          <span class="text-muted">Prijs</span>
                          <span class="text-navy-900 font-medium">{{ formatCents(item.plan_price_cents) }} /mnd</span>
                        </div>
                        <div class="flex items-center justify-between">
                          <span class="text-muted">Gestart</span>
                          <span class="text-navy-900">{{ formatDate(item.started_at) }}</span>
                        </div>
                        <div v-if="item.cancelled_at" class="flex items-center justify-between">
                          <span class="text-muted">Opgezegd</span>
                          <span class="text-red-600 font-medium">{{ formatDate(item.cancelled_at) }}</span>
                        </div>
                      </div>
                    </div>

                    <!-- Facturatie card -->
                    <div class="bg-white rounded-xl border border-navy-100 p-5 lg:w-1/3">
                      <p class="text-xs font-semibold text-navy-700 uppercase tracking-wide mb-4">Facturatie</p>
                      <div class="space-y-3">
                        <div class="flex items-center justify-between text-sm">
                          <span class="text-muted">Facturen</span>
                          <span class="text-navy-900 font-medium">{{ item.invoice_count }}</span>
                        </div>
                        <div class="flex items-center justify-between text-sm">
                          <span class="text-muted">Totaal gefactureerd</span>
                          <span class="text-navy-900">{{ formatCents(item.total_invoiced_cents) }}</span>
                        </div>
                        <div v-if="item.last_invoice_date" class="flex items-center justify-between text-sm pt-3 border-t border-navy-100">
                          <span class="text-muted">Laatste factuur</span>
                          <span class="text-navy-900">{{ formatDate(item.last_invoice_date) }}</span>
                        </div>
                      </div>
                    </div>

                    <!-- Status card -->
                    <div class="bg-white rounded-xl border border-navy-100 p-5 lg:w-1/3">
                      <p class="text-xs font-semibold text-navy-700 uppercase tracking-wide mb-4">Status</p>
                      <div class="space-y-4">
                        <div class="flex items-start gap-3">
                          <div class="mt-0.5 w-6 h-6 rounded-full flex items-center justify-center shrink-0"
                            :class="item.status === 'active' ? 'bg-green-50' : 'bg-navy-50'"
                          >
                            <CheckCircle :size="13" :class="item.status === 'active' ? 'text-green-500' : 'text-navy-300'" />
                          </div>
                          <div>
                            <p class="text-xs text-muted mb-1">Huidige status</p>
                            <span :class="[theme.badge.base, statusBadge(item.status)]">
                              {{ statusLabel(item.status) }}
                            </span>
                          </div>
                        </div>
                        <div v-if="item.next_invoice_date" class="flex items-start gap-3">
                          <div class="mt-0.5 w-6 h-6 rounded-full bg-navy-50 flex items-center justify-center shrink-0">
                            <Calendar :size="13" class="text-navy-400" />
                          </div>
                          <div>
                            <p class="text-xs text-muted mb-1">Volgende factuur</p>
                            <p class="text-sm text-navy-900">{{ formatDate(item.next_invoice_date) }}</p>
                          </div>
                        </div>
                      </div>

                      <!-- Mobile actions -->
                      <div v-if="hasPermission('platform.manage_orgs')" class="mt-4 pt-3 border-t border-navy-50 flex gap-2 md:hidden">
                        <button
                          v-if="item.status === 'active' || item.status === 'trialing'"
                          :class="theme.btn.ghost"
                          class="text-xs"
                          @click="promptPause(item)"
                        >
                          <Pause :size="14" class="mr-1" /> Pauzeren
                        </button>
                        <button
                          v-else-if="item.status === 'paused'"
                          :class="theme.btn.ghost"
                          class="text-xs"
                          @click="promptResume(item)"
                        >
                          <Play :size="14" class="mr-1" /> Hervatten
                        </button>
                        <button
                          v-if="item.status !== 'cancelled'"
                          :class="theme.btn.dangerOutline"
                          class="text-xs"
                          @click="promptCancel(item)"
                        >
                          <XCircle :size="14" class="mr-1" /> Opzeggen
                        </button>
                      </div>
                    </div>

                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <!-- Footer -->
      <div class="py-2.5 px-4 border-t border-navy-100 bg-surface flex items-center justify-between">
        <span :class="theme.text.muted" class="text-xs">{{ sorted.length }} van {{ total }} abonnementen</span>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!error" :class="theme.emptyState.wrapper">
      <div :class="theme.emptyState.iconWrap">
        <CreditCard :size="24" :class="theme.emptyState.icon" />
      </div>
      <p :class="theme.emptyState.title">Geen abonnementen</p>
      <p :class="theme.emptyState.description">Er zijn nog geen abonnementen aangemaakt.</p>
    </div>

    <!-- Pause modal -->
    <ConfirmModal
      :open="pauseModal"
      title="Abonnement pauzeren"
      :message="`Weet je zeker dat je het abonnement van ${actionTarget?.tenant_name} wilt pauzeren? Er worden geen facturen meer gegenereerd totdat het abonnement wordt hervat.`"
      confirm-label="Pauzeren"
      variant="accent"
      @confirm="confirmPause"
      @cancel="closeModals"
    />

    <!-- Cancel modal -->
    <ConfirmModal
      :open="cancelModal"
      title="Abonnement opzeggen"
      :message="`Weet je zeker dat je het abonnement van ${actionTarget?.tenant_name} wilt opzeggen? Deze actie kan niet ongedaan worden gemaakt.`"
      confirm-label="Opzeggen"
      variant="danger"
      :require-confirm-check="true"
      @confirm="confirmCancel"
      @cancel="closeModals"
    />

    <!-- Resume modal -->
    <Teleport to="body">
      <div
        v-if="resumeModal"
        class="fixed inset-0 z-50 flex items-center justify-center"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/40" @click="closeModals" />

        <!-- Dialog -->
        <div class="relative bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6">
          <h3 :class="theme.text.h3" class="mb-1">Abonnement hervatten</h3>
          <p class="text-sm text-muted mb-5">
            Kies hoe de facturatie voor <span class="font-medium text-navy-900">{{ actionTarget?.tenant_name }}</span> wordt hervat.
          </p>

          <!-- Radio options -->
          <div class="space-y-3 mb-6">
            <label
              v-for="(info, mode) in resumeModeLabels"
              :key="mode"
              class="flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors"
              :class="resumeMode === mode
                ? 'border-accent-700 bg-accent-50/50'
                : 'border-navy-100 hover:border-navy-200'"
            >
              <input
                v-model="resumeMode"
                type="radio"
                :value="mode"
                class="mt-0.5 accent-accent-700"
              />
              <div>
                <p class="text-sm font-medium text-navy-900">{{ info.title }}</p>
                <p class="text-xs text-muted mt-0.5">{{ info.description }}</p>
              </div>
            </label>
          </div>

          <!-- Actions -->
          <div class="flex justify-end gap-3">
            <button :class="theme.btn.secondary" @click="closeModals">Annuleren</button>
            <button
              :class="theme.btn.primary"
              :disabled="resumeLoading"
              @click="confirmResume"
            >
              {{ resumeLoading ? 'Hervatten...' : 'Hervatten' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
