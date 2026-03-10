<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  getOutstandingPayments,
  getDunningCandidates,
  sendDunningReminders,
  type OutstandingPayments,
  type DunningCandidate,
} from '@/api/platform/finance'
import { theme } from '@/theme'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import IconButton from '@/components/ui/IconButton.vue'
import {
  Hourglass, AlertTriangle, Clock, Flame, CircleDollarSign,
  Send, Bell, Building2, Receipt, Calendar, ChevronRight,
} from 'lucide-vue-next'

const router = useRouter()
const data = ref<OutstandingPayments | null>(null)
const candidates = ref<DunningCandidate[]>([])
const loading = ref(true)
const error = ref('')
const sendingDunning = ref(false)
const dunningResult = ref('')
const dunningError = ref('')

// Confirm modal for bulk send
const bulkDunningModal = ref(false)
const singleDunningTarget = ref<DunningCandidate | null>(null)
const singleDunningModal = ref(false)

function fmt(cents: number): string {
  return new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' }).format(cents / 100)
}

const bucketConfig: Record<string, { label: string; icon: object; iconColor: string; variant: string }> = {
  current: { label: 'Actueel', icon: Clock, iconColor: 'text-accent-700', variant: 'accent' },
  late: { label: 'Te laat', icon: AlertTriangle, iconColor: 'text-yellow-600', variant: 'primary' },
  very_late: { label: 'Zeer laat', icon: Hourglass, iconColor: 'text-red-500', variant: 'red' },
  critical: { label: 'Kritiek', icon: Flame, iconColor: 'text-red-600', variant: 'red' },
}

const defaultBucketConfig = { label: 'Onbekend', icon: Clock, iconColor: 'text-navy-400', variant: 'default' }

function bucketVariant(bucket: string): string {
  const v = (bucketConfig[bucket] || defaultBucketConfig).variant
  const map: Record<string, string> = {
    accent: theme.stat.iconVariant.accent,
    primary: 'bg-yellow-50 text-yellow-600',
    red: theme.stat.iconVariant.red,
    default: theme.stat.iconVariant.default,
  }
  return map[v] || theme.stat.iconVariant.default
}

// Total count across all buckets
const totalInvoiceCount = computed(() => {
  if (!data.value) return 0
  return data.value.buckets.reduce((s, b) => s + b.count, 0)
})

// Highest severity bucket
const highestSeverity = computed(() => {
  if (!data.value) return null
  const order = ['critical', 'very_late', 'late', 'current']
  for (const key of order) {
    const bucket = data.value.buckets.find(b => b.bucket === key && b.count > 0)
    if (bucket) return key
  }
  return null
})

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

function formatDateTime(d: string | null) {
  if (!d) return '\u2014'
  return new Date(d).toLocaleString('nl-NL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function daysOverdueColor(days: number): string {
  if (days >= 30) return 'text-red-600 font-bold'
  if (days >= 14) return 'text-red-500 font-semibold'
  if (days >= 7) return 'text-yellow-600 font-medium'
  return 'text-navy-700'
}

function reminderBadge(count: number): string {
  if (count >= 3) return theme.badge.error
  if (count >= 2) return theme.badge.warning
  return theme.badge.default
}

async function load() {
  try {
    const [outstanding, dunning] = await Promise.all([
      getOutstandingPayments(),
      getDunningCandidates(),
    ])
    data.value = outstanding
    candidates.value = dunning
  } catch {
    error.value = 'Kon openstaande betalingen niet laden'
  } finally {
    loading.value = false
  }
}

function promptBulkDunning() {
  bulkDunningModal.value = true
}

function promptSingleDunning(c: DunningCandidate) {
  singleDunningTarget.value = c
  singleDunningModal.value = true
}

function cancelModals() {
  bulkDunningModal.value = false
  singleDunningModal.value = false
  singleDunningTarget.value = null
}

async function confirmBulkDunning() {
  sendingDunning.value = true
  dunningResult.value = ''
  dunningError.value = ''
  try {
    const result = await sendDunningReminders()
    dunningResult.value = `${result.sent} herinnering(en) verstuurd, ${result.skipped} overgeslagen`
    setTimeout(() => { dunningResult.value = '' }, 5000)
    await load()
  } catch {
    dunningError.value = 'Fout bij versturen herinneringen'
  } finally {
    sendingDunning.value = false
    cancelModals()
  }
}

async function confirmSingleDunning() {
  if (!singleDunningTarget.value) return
  const tenantId = singleDunningTarget.value.tenant_id
  sendingDunning.value = true
  dunningResult.value = ''
  dunningError.value = ''
  try {
    const result = await sendDunningReminders({ tenant_id: tenantId })
    dunningResult.value = `${result.sent} herinnering(en) verstuurd, ${result.skipped} overgeslagen`
    setTimeout(() => { dunningResult.value = '' }, 5000)
    await load()
  } catch {
    dunningError.value = 'Fout bij versturen herinneringen'
  } finally {
    sendingDunning.value = false
    cancelModals()
  }
}

onMounted(load)

// Skeleton helpers
const skeletonCards = Array.from({ length: 4 }, (_, i) => i)
const skeletonRows = Array.from({ length: 5 }, (_, i) => i)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Hourglass class="w-6 h-6 text-navy-700" />
        <h2 :class="theme.text.h2">Openstaande betalingen</h2>
      </div>
      <span v-if="data" :class="theme.text.muted" class="text-sm hidden md:block">
        Laatst bijgewerkt: {{ formatDate(data.generated_at) }}
      </span>
    </div>

    <!-- Alerts -->
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="dunningResult" :class="theme.alert.success">{{ dunningResult }}</div>
    </Transition>
    <div v-if="dunningError" :class="theme.alert.error">{{ dunningError }}</div>

    <!-- ──── Loading Skeleton ──── -->
    <template v-if="loading">
      <!-- Total card skeleton -->
      <div :class="theme.card.padded" class="skeleton-card" style="animation-delay: 0ms">
        <div class="flex items-center justify-between">
          <div class="space-y-2">
            <div class="h-4 w-28 bg-navy-100 rounded animate-pulse" />
            <div class="h-8 w-36 bg-navy-100 rounded animate-pulse" />
          </div>
          <div class="h-5 w-20 bg-navy-100 rounded-full animate-pulse" />
        </div>
      </div>

      <!-- Bucket cards skeleton -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in skeletonCards" :key="i" :class="theme.stat.card" class="skeleton-card" :style="{ animationDelay: (i + 1) * 80 + 'ms' }">
          <div :class="theme.stat.iconWrap" class="bg-navy-50">
            <div class="w-5 h-5 rounded bg-navy-100 animate-pulse" />
          </div>
          <div class="flex-1 space-y-1.5">
            <div class="h-7 w-20 bg-navy-100 rounded animate-pulse" />
            <div class="h-3.5 w-24 bg-navy-100 rounded animate-pulse" />
            <div class="h-3 w-16 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </div>

      <!-- Table skeleton -->
      <div class="overflow-hidden rounded-xl border border-navy-100">
        <div class="bg-surface px-4 h-[46px] flex items-center justify-between">
          <div class="h-4 w-36 bg-navy-100 rounded animate-pulse" />
          <div class="h-8 w-40 bg-navy-100 rounded animate-pulse" />
        </div>
        <div class="bg-white divide-y divide-navy-50">
          <div v-for="n in skeletonRows" :key="n" class="flex items-center gap-4 px-4 py-4 skeleton-row-enter" :style="{ animationDelay: (n + 5) * 60 + 'ms' }">
            <div class="flex-1 space-y-1">
              <div class="h-4 w-28 bg-navy-100 rounded animate-pulse" />
              <div class="h-3 w-36 bg-navy-100 rounded animate-pulse" />
            </div>
            <div class="h-4 w-20 bg-navy-100 rounded animate-pulse hidden md:block" />
            <div class="h-4 w-16 bg-navy-100 rounded animate-pulse" />
            <div class="h-6 w-8 bg-navy-100 rounded-full animate-pulse" />
          </div>
        </div>
      </div>
    </template>

    <!-- ──── Loaded Content ──── -->
    <template v-else-if="data">
      <!-- ─── Total Outstanding Hero ─── -->
      <div :class="theme.card.base" class="overflow-hidden">
        <div class="flex items-center justify-between px-4 md:px-6 py-5">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
              :class="highestSeverity === 'critical' || highestSeverity === 'very_late' ? 'bg-red-50' : highestSeverity === 'late' ? 'bg-yellow-50' : 'bg-accent-50'"
            >
              <CircleDollarSign :size="24"
                :class="highestSeverity === 'critical' || highestSeverity === 'very_late' ? 'text-red-500' : highestSeverity === 'late' ? 'text-yellow-600' : 'text-accent-700'"
              />
            </div>
            <div>
              <p :class="theme.text.muted" class="text-xs mb-0.5">Totaal openstaand</p>
              <p class="text-3xl font-bold text-navy-900">{{ fmt(data.total_outstanding_cents) }}</p>
            </div>
          </div>
          <div class="flex flex-col items-end gap-1">
            <span :class="[theme.badge.base, theme.badge.default]">{{ totalInvoiceCount }} facturen</span>
            <span v-if="candidates.length > 0" :class="[theme.badge.base, theme.badge.warning]">
              {{ candidates.length }} dunning
            </span>
          </div>
        </div>
      </div>

      <!-- ─── Aging Buckets ─── -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="bucket in data.buckets" :key="bucket.bucket" :class="theme.stat.card" class="flex-col !items-stretch !gap-0">
          <div class="flex items-center gap-3 mb-3">
            <div :class="[theme.stat.iconWrap, bucketVariant(bucket.bucket)]">
              <component :is="(bucketConfig[bucket.bucket] || defaultBucketConfig).icon" :size="18" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-navy-900">
                {{ (bucketConfig[bucket.bucket] || defaultBucketConfig).label }}
              </p>
              <p :class="theme.text.muted" class="text-xs">{{ bucket.days_range }} dagen</p>
            </div>
          </div>
          <p class="text-xl font-bold text-navy-900 mb-0.5">{{ fmt(bucket.total_cents) }}</p>
          <p :class="theme.text.muted" class="text-xs">{{ bucket.count }} {{ bucket.count === 1 ? 'factuur' : 'facturen' }}</p>
          <!-- Tenant list -->
          <div v-if="bucket.tenants.length > 0" class="mt-3 pt-3 border-t border-navy-100 space-y-1">
            <div v-for="t in bucket.tenants" :key="t" class="flex items-center gap-1.5">
              <Building2 :size="11" class="text-navy-300 shrink-0" />
              <span class="text-xs text-navy-600 truncate">{{ t }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Dunning Candidates Table ─── -->
      <div class="overflow-hidden rounded-xl border border-navy-100">
        <div class="flex items-center justify-between px-4 md:px-6 py-3 bg-surface border-b border-navy-100">
          <div class="flex items-center gap-2">
            <Bell :size="16" class="text-navy-400" />
            <h3 :class="theme.text.h4">Dunning kandidaten</h3>
            <span v-if="candidates.length > 0" :class="[theme.badge.base, theme.badge.warning]">{{ candidates.length }}</span>
          </div>
          <button
            v-if="candidates.length > 0"
            :class="theme.btn.primarySm"
            :disabled="sendingDunning"
            @click="promptBulkDunning"
          >
            <Send :size="14" class="mr-1.5" />
            {{ sendingDunning ? 'Versturen...' : 'Stuur alle herinneringen' }}
          </button>
        </div>

        <!-- Empty -->
        <div v-if="candidates.length === 0" class="py-12 text-center bg-white">
          <div class="w-12 h-12 mx-auto rounded-xl bg-green-50 flex items-center justify-center mb-3">
            <Bell :size="20" class="text-green-500" />
          </div>
          <p class="text-sm font-medium text-navy-900 mb-1">Geen herinneringen nodig</p>
          <p :class="theme.text.muted" class="text-sm">Alle facturen zijn op tijd of al herinnerd.</p>
        </div>

        <!-- Table -->
        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-navy-200 text-sm table-fixed">
            <colgroup>
              <col style="width: 22%" />
              <col style="width: 16%" />
              <col style="width: 14%" />
              <col style="width: 14%" />
              <col style="width: 12%" />
              <col style="width: 14%" class="hidden md:table-column" />
              <col style="width: 8%" />
            </colgroup>
            <thead class="bg-white text-navy-700 font-semibold">
              <tr>
                <th class="px-4 h-[42px] text-left">Organisatie</th>
                <th class="px-4 h-[42px] text-left">Factuurnr</th>
                <th class="px-4 h-[42px] text-right">Bedrag</th>
                <th class="px-4 h-[42px] text-center">Dagen te laat</th>
                <th class="px-4 h-[42px] text-center">Ronde</th>
                <th class="px-4 h-[42px] text-left hidden md:table-cell">Laatste herinnering</th>
                <th class="px-4 h-[42px]" />
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-navy-50">
              <tr
                v-for="c in candidates"
                :key="c.invoice_id"
                class="hover:bg-surface transition-colors group"
              >
                <!-- Tenant -->
                <td class="px-4 py-3">
                  <p class="font-medium text-navy-900 truncate">{{ c.tenant_name }}</p>
                  <p :class="theme.text.muted" class="text-xs truncate">{{ c.contact_email }}</p>
                </td>
                <!-- Invoice number -->
                <td class="px-4 py-3 font-mono text-xs text-navy-700">{{ c.invoice_number }}</td>
                <!-- Amount -->
                <td class="px-4 py-3 text-right font-semibold text-navy-900">{{ fmt(c.amount_cents) }}</td>
                <!-- Days overdue -->
                <td class="px-4 py-3 text-center">
                  <span :class="daysOverdueColor(c.days_overdue)">{{ c.days_overdue }}d</span>
                </td>
                <!-- Reminder round -->
                <td class="px-4 py-3 text-center">
                  <span :class="[theme.badge.base, reminderBadge(c.reminder_count)]">
                    {{ c.reminder_count + 1 }}e
                  </span>
                </td>
                <!-- Last reminder -->
                <td class="px-4 py-3 hidden md:table-cell">
                  <span :class="theme.text.muted" class="text-xs">{{ formatDateTime(c.last_reminder_sent_at) }}</span>
                </td>
                <!-- Action -->
                <td class="px-4 py-3 text-center">
                  <IconButton
                    variant="warning"
                    title="Herinnering versturen"
                    :disabled="sendingDunning"
                    @click="promptSingleDunning(c)"
                  >
                    <Send :size="14" />
                  </IconButton>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Footer -->
        <div v-if="candidates.length > 0" class="py-3 text-center border-t border-navy-100" :class="theme.text.muted">
          {{ candidates.length }} kandidaten
        </div>
      </div>
    </template>

    <!-- ──── Empty state ──── -->
    <div v-else-if="!error" :class="theme.emptyState.wrapper">
      <div :class="theme.emptyState.iconWrap">
        <Hourglass :class="theme.emptyState.icon" :size="24" />
      </div>
      <p :class="theme.emptyState.title">Geen gegevens</p>
      <p :class="theme.emptyState.description">Openstaande betalingen konden niet worden geladen.</p>
    </div>

    <!-- Bulk dunning confirm -->
    <ConfirmModal
      :open="bulkDunningModal"
      title="Alle herinneringen versturen"
      :message="`Weet je zeker dat je betalingsherinneringen wilt versturen naar alle ${candidates.length} kandidaten?`"
      confirm-label="Verstuur alle herinneringen"
      variant="primary"
      :loading="sendingDunning"
      @confirm="confirmBulkDunning"
      @cancel="cancelModals"
    />

    <!-- Single dunning confirm -->
    <ConfirmModal
      :open="singleDunningModal"
      title="Herinnering versturen"
      :message="`Wilt u een betalingsherinnering versturen naar ${singleDunningTarget?.tenant_name ?? ''}?${singleDunningTarget && singleDunningTarget.reminder_count > 0 ? ` Dit is herinnering ${singleDunningTarget.reminder_count + 1}.` : ''}`"
      confirm-label="Verstuur herinnering"
      variant="primary"
      :loading="sendingDunning"
      @confirm="confirmSingleDunning"
      @cancel="cancelModals"
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
