<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ListChecks, Plus } from 'lucide-vue-next'
import { theme } from '@/theme'
import PageHeader from '@/components/shared/PageHeader.vue'
import SkeletonLoader from '@/components/shared/SkeletonLoader.vue'
import EmptyState from '@/components/shared/EmptyState.vue'
import { useBillingStore } from '@/stores/billing'
import { formatCents } from '@/types/billing'
import type { TuitionPlan } from '@/types/billing'

const billing = useBillingStore()
const showForm = ref(false)
const editingPlan = ref<TuitionPlan | null>(null)
const loading = ref(true)

const form = ref({
  name: '',
  description: '',
  amount_cents: 0,
  frequency: 'monthly',
  lesson_duration_minutes: 30,
})

const frequencyLabels: Record<string, string> = {
  per_lesson: 'Per les',
  weekly: 'Wekelijks',
  monthly: 'Maandelijks',
  quarterly: 'Per kwartaal',
  semester: 'Per semester',
  yearly: 'Jaarlijks',
}

onMounted(async () => {
  await billing.fetchPlans(false)
  loading.value = false
})

function openCreate() {
  editingPlan.value = null
  form.value = { name: '', description: '', amount_cents: 0, frequency: 'monthly', lesson_duration_minutes: 30 }
  showForm.value = true
}

function openEdit(plan: TuitionPlan) {
  editingPlan.value = plan
  form.value = {
    name: plan.name,
    description: plan.description || '',
    amount_cents: plan.amount_cents,
    frequency: plan.frequency,
    lesson_duration_minutes: plan.lesson_duration_minutes || 30,
  }
  showForm.value = true
}

async function handleSubmit() {
  try {
    if (editingPlan.value) {
      await billing.updatePlan(editingPlan.value.id, form.value)
    } else {
      await billing.createPlan(form.value)
    }
    showForm.value = false
  } catch (e: any) {
    billing.error = e.response?.data?.detail || 'Opslaan mislukt'
  }
}

async function handleDeactivate(id: string) {
  if (confirm('Weet je zeker dat je dit plan wilt deactiveren?')) {
    await billing.deactivatePlan(id)
  }
}
</script>

<template>
  <div>
    <PageHeader :icon="ListChecks" title="Lesgeldplannen" description="Tariefstructuren voor leerlingen">
      <template #actions>
        <button :class="theme.btn.addInline" @click="openCreate">
          <span :class="theme.btn.addInlineIcon"><Plus :size="14" /></span>
          Nieuw plan
        </button>
      </template>
    </PageHeader>

    <div v-if="billing.error" :class="theme.alert.error">{{ billing.error }}</div>

    <!-- Plan form -->
    <div v-if="showForm" :class="theme.card.form" class="mt-6">
      <h3 :class="theme.text.h3">{{ editingPlan ? 'Plan bewerken' : 'Nieuw plan' }}</h3>
      <form @submit.prevent="handleSubmit" class="mt-4 space-y-4">
        <div>
          <label :class="theme.form.label">Naam</label>
          <input v-model="form.name" :class="theme.form.input" required />
        </div>
        <div>
          <label :class="theme.form.label">Beschrijving</label>
          <input v-model="form.description" :class="theme.form.input" />
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label :class="theme.form.label">Bedrag (in centen)</label>
            <input v-model.number="form.amount_cents" type="number" :class="theme.form.input" required min="0" />
          </div>
          <div>
            <label :class="theme.form.label">Frequentie</label>
            <select v-model="form.frequency" :class="theme.form.input">
              <option v-for="(label, key) in frequencyLabels" :key="key" :value="key">{{ label }}</option>
            </select>
          </div>
          <div>
            <label :class="theme.form.label">Lesduur (minuten)</label>
            <input v-model.number="form.lesson_duration_minutes" type="number" :class="theme.form.input" min="1" />
          </div>
        </div>
        <div class="flex gap-3">
          <button type="submit" :class="theme.btn.primary">Opslaan</button>
          <button type="button" :class="theme.btn.ghost" @click="showForm = false">Annuleren</button>
        </div>
      </form>
    </div>

    <!-- Loading -->
    <SkeletonLoader v-if="loading" variant="list" :rows="3" class="mt-6" />

    <!-- Empty -->
    <EmptyState
      v-else-if="billing.plans.length === 0"
      :icon="ListChecks"
      title="Geen lesgeldplannen"
      description="Maak een nieuw tarievenplan aan voor je leerlingen."
      actionLabel="Nieuw plan"
      @action="openCreate"
    />

    <!-- Plans list -->
    <div v-else class="mt-6 space-y-3 fade-in-up">
      <div
        v-for="plan in billing.plans"
        :key="plan.id"
        :class="[theme.card.padded, !plan.is_active ? 'opacity-50' : '']"
      >
        <div class="flex items-center justify-between gap-4">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <h3 :class="theme.text.h4">{{ plan.name }}</h3>
              <span :class="[theme.badge.base, plan.is_active ? theme.badge.success : theme.badge.default]">
                {{ plan.is_active ? 'Actief' : 'Inactief' }}
              </span>
            </div>
            <p :class="theme.text.muted" class="text-sm mt-1">
              {{ formatCents(plan.amount_cents) }} / {{ frequencyLabels[plan.frequency] || plan.frequency }}
              <span v-if="plan.lesson_duration_minutes"> &middot; {{ plan.lesson_duration_minutes }} min</span>
            </p>
            <p v-if="plan.description" :class="theme.text.body" class="mt-1">{{ plan.description }}</p>
          </div>
          <div class="flex gap-2 flex-shrink-0">
            <button :class="theme.btn.ghost" @click="openEdit(plan)">Bewerken</button>
            <button
              v-if="plan.is_active"
              :class="theme.btn.dangerOutline"
              @click="handleDeactivate(plan.id)"
            >
              Deactiveren
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
