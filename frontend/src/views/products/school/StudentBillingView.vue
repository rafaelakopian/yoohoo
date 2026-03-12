<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { theme } from '@/theme'
import PageHeader from '@/components/shared/PageHeader.vue'
import SkeletonLoader from '@/components/shared/SkeletonLoader.vue'
import { useBillingStore } from '@/stores/billing'
import { formatCents } from '@/types/billing'
import PaymentStatusBadge from '@/components/products/school/billing/PaymentStatusBadge.vue'

const billing = useBillingStore()
const loading = ref(true)

onMounted(async () => {
  await Promise.all([billing.fetchStudentBillings(), billing.fetchPlans()])
  loading.value = false
})

function getPlanName(planId: string): string {
  const plan = billing.plans.find((p) => p.id === planId)
  return plan ? plan.name : 'Onbekend plan'
}

function getPlanAmount(planId: string): number {
  const plan = billing.plans.find((p) => p.id === planId)
  return plan ? plan.amount_cents : 0
}
</script>

<template>
  <div>
      <PageHeader title="Leerling facturatie" description="Facturatieconfiguratie per leerling" />

      <SkeletonLoader v-if="loading" variant="table" :rows="5" />

      <div v-else class="mt-6 overflow-x-auto fade-in-up">
        <table class="w-full text-sm">
          <thead>
            <tr :class="theme.list.sectionHeader">
              <th class="text-left py-2 px-3">Betaler</th>
              <th class="text-left py-2 px-3">E-mail</th>
              <th class="text-left py-2 px-3">Plan</th>
              <th class="text-right py-2 px-3">Bedrag</th>
              <th class="text-left py-2 px-3">Korting</th>
              <th class="text-left py-2 px-3">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="sb in billing.studentBillings" :key="sb.id" :class="theme.list.item">
              <td class="py-2 px-3">{{ sb.payer_name }}</td>
              <td class="py-2 px-3">{{ sb.payer_email }}</td>
              <td class="py-2 px-3">{{ getPlanName(sb.tuition_plan_id) }}</td>
              <td class="py-2 px-3 text-right">
                {{ formatCents(sb.custom_amount_cents || getPlanAmount(sb.tuition_plan_id)) }}
              </td>
              <td class="py-2 px-3">
                {{ sb.discount_percent ? `${sb.discount_percent}%` : '-' }}
              </td>
              <td class="py-2 px-3">
                <PaymentStatusBadge :status="sb.status" />
              </td>
            </tr>
          </tbody>
        </table>

        <p v-if="billing.studentBillings.length === 0" :class="theme.list.empty" class="mt-4">
          Geen leerlingen met facturatie-instelling gevonden.
        </p>
      </div>
  </div>
</template>
