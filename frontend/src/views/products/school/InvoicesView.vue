<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { theme } from '@/theme'
import { useBillingStore } from '@/stores/billing'
import { formatCents } from '@/types/billing'
import PaymentStatusBadge from '@/components/products/school/billing/PaymentStatusBadge.vue'

const billing = useBillingStore()
const loading = ref(true)
const statusFilter = ref<string>('')
const showGenerateForm = ref(false)

const generateForm = ref({
  period_start: '',
  period_end: '',
})

onMounted(async () => {
  await billing.fetchInvoices()
  loading.value = false
})

async function applyFilter() {
  loading.value = true
  await billing.fetchInvoices({
    status: statusFilter.value || undefined,
  })
  loading.value = false
}

async function handleGenerate() {
  try {
    await billing.generateInvoices({
      period_start: new Date(generateForm.value.period_start).toISOString(),
      period_end: new Date(generateForm.value.period_end).toISOString(),
    })
    showGenerateForm.value = false
  } catch (e: any) {
    billing.error = e.response?.data?.detail || 'Facturen genereren mislukt'
  }
}

async function handleSend(id: string) {
  if (confirm('Wil je deze factuur verzenden?')) {
    try {
      await billing.sendInvoice(id)
    } catch (e: any) {
      billing.error = e.response?.data?.detail || 'Verzenden mislukt'
    }
  }
}
</script>

<template>
  <div>
      <div :class="theme.pageHeader.row">
        <div>
          <h2 :class="theme.text.h2">Facturen</h2>
          <p :class="theme.text.subtitle">Lesgeld facturen beheren</p>
        </div>
        <button :class="theme.btn.primary" @click="showGenerateForm = !showGenerateForm">
          Facturen genereren
        </button>
      </div>

      <div v-if="billing.error" :class="theme.alert.error" class="mt-4">
        {{ billing.error }}
      </div>

      <!-- Generate form -->
      <div v-if="showGenerateForm" :class="theme.card.form" class="mt-6">
        <h2 :class="theme.text.h3">Facturen genereren</h2>
        <form @submit.prevent="handleGenerate" class="mt-4 grid grid-cols-2 gap-4">
          <div>
            <label :class="theme.form.label">Periode start</label>
            <input v-model="generateForm.period_start" type="date" :class="theme.form.input" required />
          </div>
          <div>
            <label :class="theme.form.label">Periode einde</label>
            <input v-model="generateForm.period_end" type="date" :class="theme.form.input" required />
          </div>
          <div class="col-span-2 flex gap-3">
            <button type="submit" :class="theme.btn.primary">Genereren</button>
            <button type="button" :class="theme.btn.ghost" @click="showGenerateForm = false">Annuleren</button>
          </div>
        </form>
      </div>

      <!-- Filter -->
      <div class="mt-6 flex gap-3 items-center">
        <select v-model="statusFilter" :class="theme.form.input" class="w-48" @change="applyFilter">
          <option value="">Alle statussen</option>
          <option value="draft">Concept</option>
          <option value="sent">Verzonden</option>
          <option value="paid">Betaald</option>
          <option value="overdue">Achterstallig</option>
          <option value="cancelled">Geannuleerd</option>
        </select>
      </div>

      <!-- Invoice table -->
      <div v-if="loading" class="mt-8 text-center">
        <p :class="theme.text.muted">Laden...</p>
      </div>

      <div v-else class="mt-4 overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr :class="theme.list.sectionHeader">
              <th class="text-left py-2 px-3">Nummer</th>
              <th class="text-left py-2 px-3">Leerling</th>
              <th class="text-left py-2 px-3">Betaler</th>
              <th class="text-left py-2 px-3">Periode</th>
              <th class="text-right py-2 px-3">Bedrag</th>
              <th class="text-left py-2 px-3">Status</th>
              <th class="text-left py-2 px-3">Acties</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="inv in billing.invoices" :key="inv.id" :class="theme.list.item">
              <td class="py-2 px-3 font-mono text-xs">{{ inv.invoice_number }}</td>
              <td class="py-2 px-3">{{ inv.student_name }}</td>
              <td class="py-2 px-3">{{ inv.payer_name }}</td>
              <td class="py-2 px-3 text-xs">
                {{ new Date(inv.period_start).toLocaleDateString('nl-NL') }} -
                {{ new Date(inv.period_end).toLocaleDateString('nl-NL') }}
              </td>
              <td class="py-2 px-3 text-right">{{ formatCents(inv.total_cents, inv.currency) }}</td>
              <td class="py-2 px-3">
                <PaymentStatusBadge :status="inv.status" />
              </td>
              <td class="py-2 px-3">
                <button
                  v-if="inv.status === 'draft'"
                  :class="theme.btn.link"
                  @click="handleSend(inv.id)"
                >
                  Verzenden
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <p v-if="billing.invoices.length === 0" :class="theme.list.empty" class="mt-4">
          Geen facturen gevonden.
        </p>
      </div>
  </div>
</template>
