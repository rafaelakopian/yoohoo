<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTenantStore } from '@/stores/tenant'
import { useBrandingStore } from '@/stores/branding'
import { useAuthStore } from '@/stores/auth'
import { platformBillingApi } from '@/api/products/school/billing'
import { featuresApi } from '@/api/products/school/features'
import { formatCents } from '@/types/billing'
import type { BillingInvoice } from '@/types/billing'
import PaymentStatusBadge from '@/components/products/school/billing/PaymentStatusBadge.vue'
import { theme } from '@/theme'
import { PauseCircle, XCircle, Clock, Mail, Phone, CheckCircle, ArrowRight } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const tenantStore = useTenantStore()
const branding = useBrandingStore()
const authStore = useAuthStore()

const invoices = ref<BillingInvoice[]>([])
const loading = ref(true)
const error = ref('')
const payingInvoiceId = ref<string | null>(null)
const successMessage = ref('')
const polling = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const status = computed(() => tenantStore.subscriptionStatus ?? 'paused')
const planName = computed(() => tenantStore.subscriptionPlanName)
const slug = computed(() => route.params.slug as string)
const firstName = computed(() => {
  const name = authStore.user?.full_name?.split(' ')[0] ?? ''
  // Skip if it looks like a username (contains digits or special chars)
  if (!name || /\d/.test(name) || name.length > 20) return ''
  return name
})

const totalOpenCents = computed(() =>
  invoices.value.reduce((sum, inv) => sum + inv.total_cents, 0),
)

const allPaidButStillPaused = computed(
  () => status.value === 'paused' && !loading.value && invoices.value.length === 0,
)

const statusConfig = computed(() => {
  switch (status.value) {
    case 'paused':
      if (allPaidButStillPaused.value) {
        return {
          icon: PauseCircle,
          iconBg: 'bg-amber-100',
          iconClass: 'text-amber-500',
          title: 'Even op pauze',
          text: 'Je account is momenteel niet actief. Hieronder vind je meer informatie.',
        }
      }
      return {
        icon: PauseCircle,
        iconBg: 'bg-amber-100',
        iconClass: 'text-amber-500',
        title: 'Even op pauze',
        text: 'Er staat een openstaande betaling open. Zodra deze is voldaan, wordt je account automatisch hervat en kun je direct weer verder.',
      }
    case 'cancelled':
      return {
        icon: XCircle,
        iconBg: 'bg-red-100',
        iconClass: 'text-red-400',
        title: 'Abonnement gestopt',
        text: 'Je abonnement is beëindigd. Geen zorgen — al je gegevens staan veilig bewaard. Neem contact met ons op om weer te starten.',
      }
    case 'expired':
      return {
        icon: Clock,
        iconBg: 'bg-red-100',
        iconClass: 'text-red-400',
        title: 'Abonnement verlopen',
        text: 'Je abonnement is verlopen. Je gegevens blijven bewaard. Neem contact op om je account te verlengen.',
      }
    default:
      return {
        icon: PauseCircle,
        iconBg: 'bg-amber-100',
        iconClass: 'text-amber-500',
        title: 'Account niet actief',
        text: 'Neem contact op met ons team voor meer informatie.',
      }
  }
})

const showContact = computed(() => ['cancelled', 'expired'].includes(status.value))

function daysOverdue(dueDate: string | null): number | null {
  if (!dueDate) return null
  const due = new Date(dueDate)
  const now = new Date()
  const diff = Math.floor((now.getTime() - due.getTime()) / (1000 * 60 * 60 * 24))
  return diff > 0 ? diff : null
}

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('nl-NL', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

async function loadInvoices() {
  loading.value = true
  error.value = ''
  try {
    invoices.value = await platformBillingApi.getPlatformInvoices('open,overdue')
  } catch {
    error.value = 'Kon facturen niet laden'
  } finally {
    loading.value = false
  }
}

async function payInvoice(invoiceId: string) {
  payingInvoiceId.value = invoiceId
  error.value = ''
  try {
    const result = await platformBillingApi.createInvoicePayment(invoiceId)
    if (result.checkout_url) {
      window.location.href = result.checkout_url
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Kon betaallink niet aanmaken'
  } finally {
    payingInvoiceId.value = null
  }
}

async function pollSubscriptionStatus() {
  polling.value = true
  let attempts = 0
  const maxAttempts = 10

  pollTimer = setInterval(async () => {
    attempts++
    try {
      const data = await featuresApi.getSubscriptionStatus()
      if (data.status !== 'paused') {
        stopPolling()
        tenantStore.subscriptionStatus = data.status
        tenantStore.subscriptionPlanName = data.plan_name
        router.push({ name: 'org-dashboard', params: { slug: slug.value } })
        return
      }
    } catch {
      // Ignore polling errors
    }

    if (attempts >= maxAttempts) {
      stopPolling()
      successMessage.value =
        'Je betaling is ontvangen. Het kan een moment duren voordat je account hervat wordt. Je ontvangt een bevestiging per e-mail.'
    }
  }, 3000)
}

function stopPolling() {
  polling.value = false
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  await loadInvoices()

  if (route.query.payment === 'success') {
    successMessage.value = 'Betaling ontvangen! Je account wordt automatisch hervat.'
    pollSubscriptionStatus()
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="w-full max-w-2xl mx-auto px-4 py-12 md:py-16">

    <!-- Hero: logo + greeting + status -->
    <div class="text-center mb-10">
      <!-- Logo -->
      <div v-if="branding.currentLogo" class="flex justify-center mb-6">
        <div class="w-20 h-20 overflow-hidden shadow-md bg-white rounded-full">
          <img :src="branding.currentLogo" alt="Logo" class="w-full h-full object-cover" />
        </div>
      </div>

      <!-- Status icon (fallback als geen logo) -->
      <div v-else class="flex justify-center mb-6">
        <div :class="['w-20 h-20 rounded-full flex items-center justify-center', statusConfig.iconBg]">
          <component :is="statusConfig.icon" :size="36" :class="statusConfig.iconClass" />
        </div>
      </div>

      <h1 :class="[theme.text.h1, 'mb-2']">
        {{ firstName ? `Hoi ${firstName}` : statusConfig.title }}
      </h1>
      <p :class="[theme.text.muted, 'text-base max-w-md mx-auto']">
        {{ statusConfig.text }}
      </p>

      <!-- Plan badge -->
      <div v-if="planName" class="mt-4">
        <span :class="[theme.badge.base, theme.badge.default]">
          {{ planName }}
        </span>
      </div>
    </div>

    <!-- Success toast -->
    <div
      v-if="successMessage"
      class="mb-6 p-4 bg-green-50 border border-green-200 rounded-xl flex items-center gap-3"
    >
      <CheckCircle :size="20" class="text-green-600 shrink-0" />
      <span class="text-sm text-green-700 flex-1">{{ successMessage }}</span>
      <span
        v-if="polling"
        class="inline-block w-4 h-4 border-2 border-green-500 border-t-transparent rounded-full animate-spin shrink-0"
      />
    </div>

    <!-- Error -->
    <div v-if="error" :class="[theme.alert.error, 'mb-6']">{{ error }}</div>

    <!-- Openstaande facturen -->
    <div :class="[theme.card.base, 'mb-6 overflow-hidden']">
      <div class="p-5 md:p-6 border-b border-navy-100">
        <h2 :class="theme.text.h3">Openstaande facturen</h2>
        <p v-if="invoices.length > 0" :class="[theme.text.muted, 'text-sm mt-1']">
          Betaal je openstaande facturen om direct weer aan de slag te gaan.
        </p>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="p-10 text-center">
        <div class="inline-block w-6 h-6 border-2 border-navy-200 border-t-accent-700 rounded-full animate-spin mb-3" />
        <p :class="theme.text.muted">Facturen laden...</p>
      </div>

      <!-- Alles betaald maar nog paused -->
      <div v-else-if="allPaidButStillPaused" class="p-6 md:p-8">
        <div class="flex items-start gap-4 p-5 bg-green-50 border border-green-200 rounded-xl">
          <div class="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center shrink-0">
            <CheckCircle :size="20" class="text-green-600" />
          </div>
          <div>
            <p class="font-medium text-green-800 mb-1">Alles lijkt in orde</p>
            <p class="text-sm text-green-700">
              Als je denkt dat je onterecht op deze pagina bent beland, neem dan contact op met de
              <a href="mailto:support@yoohoo.nl" class="underline font-medium hover:text-green-900">beheerder</a>.
            </p>
          </div>
        </div>
      </div>

      <!-- Facturen kaarten (mobiel) / tabel (desktop) -->
      <template v-else-if="invoices.length > 0">
        <!-- Mobiel: kaarten -->
        <div class="md:hidden divide-y divide-navy-50">
          <div v-for="inv in invoices" :key="inv.id" class="p-4">
            <div class="flex items-center justify-between mb-2">
              <span :class="theme.text.h4">{{ inv.invoice_number }}</span>
              <PaymentStatusBadge :status="inv.status" />
            </div>
            <p v-if="inv.description" :class="[theme.text.muted, 'text-sm mb-2']">
              {{ inv.description }}
            </p>
            <div class="flex items-center justify-between mb-1">
              <span :class="theme.text.muted">Bedrag</span>
              <span :class="theme.text.h4">{{ formatCents(inv.total_cents, inv.currency) }}</span>
            </div>
            <div v-if="inv.due_date" class="flex items-center justify-between mb-3">
              <span :class="theme.text.muted">Vervaldatum</span>
              <span :class="theme.text.body">
                {{ formatDate(inv.due_date) }}
                <span v-if="daysOverdue(inv.due_date)" class="text-red-600 text-xs ml-1">
                  ({{ daysOverdue(inv.due_date) }}d te laat)
                </span>
              </span>
            </div>
            <button
              :class="[theme.btn.primary, 'w-full flex items-center justify-center gap-2']"
              :disabled="payingInvoiceId === inv.id"
              @click="payInvoice(inv.id)"
            >
              <template v-if="payingInvoiceId === inv.id">Laden...</template>
              <template v-else>
                Betaal nu
                <ArrowRight :size="16" />
              </template>
            </button>
          </div>
        </div>

        <!-- Desktop: tabel -->
        <div class="hidden md:block">
          <div :class="theme.table.wrapper">
            <table :class="theme.table.base">
              <thead :class="theme.table.thead">
                <tr>
                  <th :class="theme.table.th">Factuurnummer</th>
                  <th :class="theme.table.th">Omschrijving</th>
                  <th :class="[theme.table.th, theme.table.thRight]">Bedrag</th>
                  <th :class="[theme.table.th, theme.table.thCenter]">Status</th>
                  <th :class="theme.table.th">Vervaldatum</th>
                  <th :class="[theme.table.th, theme.table.thRight]">Actie</th>
                </tr>
              </thead>
              <tbody :class="theme.table.tbody">
                <tr v-for="inv in invoices" :key="inv.id" :class="theme.table.row">
                  <td :class="[theme.table.td, theme.table.tdBold]">{{ inv.invoice_number }}</td>
                  <td :class="[theme.table.td, theme.table.tdMuted]">
                    {{ inv.description || '-' }}
                  </td>
                  <td :class="[theme.table.td, theme.table.tdRight, theme.table.tdBold]">
                    {{ formatCents(inv.total_cents, inv.currency) }}
                  </td>
                  <td :class="[theme.table.td, theme.table.tdCenter]">
                    <PaymentStatusBadge :status="inv.status" />
                    <span
                      v-if="daysOverdue(inv.due_date)"
                      class="block text-xs text-red-600 mt-0.5"
                    >
                      {{ daysOverdue(inv.due_date) }}d te laat
                    </span>
                  </td>
                  <td :class="[theme.table.td, theme.table.tdMuted]">
                    {{ formatDate(inv.due_date) }}
                  </td>
                  <td :class="[theme.table.td, theme.table.tdRight]">
                    <button
                      :class="[theme.btn.primarySm, 'inline-flex items-center gap-1.5']"
                      :disabled="payingInvoiceId === inv.id"
                      @click="payInvoice(inv.id)"
                    >
                      <template v-if="payingInvoiceId === inv.id">Laden...</template>
                      <template v-else>
                        Betaal nu
                        <ArrowRight :size="14" />
                      </template>
                    </button>
                  </td>
                </tr>
              </tbody>
              <tfoot :class="theme.table.tfoot">
                <tr>
                  <td :class="theme.table.tfootCell" colspan="2">Totaal openstaand</td>
                  <td :class="[theme.table.tfootCell, 'text-right']">
                    {{ formatCents(totalOpenCents) }}
                  </td>
                  <td colspan="3" />
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        <!-- Mobiel totaal -->
        <div class="md:hidden p-4 bg-navy-50 border-t border-navy-100 flex items-center justify-between">
          <span class="font-bold text-navy-900">Totaal openstaand</span>
          <span class="font-bold text-navy-900">{{ formatCents(totalOpenCents) }}</span>
        </div>
      </template>

      <!-- Geen facturen, geen paused status -->
      <div v-else class="p-8 text-center">
        <p :class="theme.text.muted">Geen openstaande facturen gevonden.</p>
      </div>
    </div>

    <!-- Contact sectie (cancelled / expired) -->
    <div v-if="showContact" :class="[theme.card.padded, 'text-center']">
      <h3 :class="[theme.text.h3, 'mb-2']">We helpen je graag</h3>
      <p :class="[theme.text.muted, 'mb-5 max-w-sm mx-auto']">
        Neem gerust contact op — we zoeken samen naar een oplossing.
      </p>
      <div class="flex flex-col sm:flex-row gap-3 justify-center">
        <a
          href="mailto:support@yoohoo.nl"
          :class="[theme.btn.secondary, 'inline-flex items-center justify-center gap-2']"
        >
          <Mail :size="16" />
          Stuur een bericht
        </a>
        <a
          href="tel:+31850000000"
          :class="[theme.btn.ghost, 'inline-flex items-center justify-center gap-2']"
        >
          <Phone :size="16" />
          Bel ons
        </a>
      </div>
      <p :class="[theme.text.muted, 'text-xs mt-5']">
        Je gegevens worden bewaard — er gaat niets verloren.
      </p>
    </div>

    <!-- Hulp nodig (paused, met facturen) -->
    <div v-if="status === 'paused' && invoices.length > 0" class="text-center mt-2">
      <p :class="[theme.text.muted, 'text-sm']">
        Hulp nodig? Neem contact op via
        <a href="mailto:support@yoohoo.nl" :class="theme.link.primary">support@yoohoo.nl</a>
      </p>
    </div>
  </div>
</template>
