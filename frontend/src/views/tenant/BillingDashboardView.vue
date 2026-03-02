<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { theme } from '@/theme'
import { useBillingStore } from '@/stores/billing'
import { formatCents } from '@/types/billing'
import PaymentStatusBadge from '@/components/tenant/billing/PaymentStatusBadge.vue'
import { orgPath } from '@/router/routes'

const billing = useBillingStore()
const loading = ref(true)

onMounted(async () => {
  await Promise.all([
    billing.fetchPlans(),
    billing.fetchInvoices({ limit: 10 }),
    billing.fetchStudentBillings(),
  ])
  loading.value = false
})
</script>

<template>
  <div :class="theme.page.bg">
    <div class="max-w-6xl mx-auto px-4 py-8">
      <h1 :class="theme.text.h1">Facturatie</h1>
      <p :class="theme.text.subtitle">Overzicht lesgeld en facturen</p>

      <div v-if="loading" class="mt-8 text-center">
        <p :class="theme.text.muted">Laden...</p>
      </div>

      <div v-else class="mt-8 grid gap-6 md:grid-cols-3">
        <!-- Stats cards -->
        <div :class="theme.card.padded">
          <p :class="theme.text.muted">Actieve plannen</p>
          <p class="text-2xl font-bold mt-1">{{ billing.plans.length }}</p>
          <router-link :to="orgPath('billing/plans')" :class="theme.btn.link">
            Beheren
          </router-link>
        </div>

        <div :class="theme.card.padded">
          <p :class="theme.text.muted">Actieve leerlingen</p>
          <p class="text-2xl font-bold mt-1">
            {{ billing.studentBillings.filter(sb => sb.status === 'active').length }}
          </p>
          <router-link :to="orgPath('billing/students')" :class="theme.btn.link">
            Beheren
          </router-link>
        </div>

        <div :class="theme.card.padded">
          <p :class="theme.text.muted">Openstaande facturen</p>
          <p class="text-2xl font-bold mt-1">
            {{ billing.invoices.filter(i => ['draft', 'sent', 'overdue'].includes(i.status)).length }}
          </p>
          <router-link :to="orgPath('billing/invoices')" :class="theme.btn.link">
            Bekijken
          </router-link>
        </div>
      </div>

      <!-- Recent invoices -->
      <div v-if="!loading && billing.invoices.length > 0" class="mt-8">
        <h2 :class="theme.text.h3">Recente facturen</h2>
        <div class="mt-4 overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr :class="theme.list.sectionHeader">
                <th class="text-left py-2 px-3">Nummer</th>
                <th class="text-left py-2 px-3">Leerling</th>
                <th class="text-left py-2 px-3">Bedrag</th>
                <th class="text-left py-2 px-3">Status</th>
                <th class="text-left py-2 px-3">Datum</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="inv in billing.invoices.slice(0, 10)"
                :key="inv.id"
                :class="theme.list.item"
              >
                <td class="py-2 px-3 font-mono text-xs">{{ inv.invoice_number }}</td>
                <td class="py-2 px-3">{{ inv.student_name }}</td>
                <td class="py-2 px-3">{{ formatCents(inv.total_cents, inv.currency) }}</td>
                <td class="py-2 px-3">
                  <PaymentStatusBadge :status="inv.status" />
                </td>
                <td class="py-2 px-3">
                  {{ new Date(inv.created_at).toLocaleDateString('nl-NL') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
