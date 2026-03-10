<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  PackageOpen, Plus, Pencil, CheckCircle2, Circle,
  GraduationCap, Users, CalendarDays, BellRing,
  Receipt, Handshake, BarChart3, Code, Palette, HeadsetIcon,
  ChevronDown, Infinity, Clock, Shield, X,
} from 'lucide-vue-next'
import { platformBillingApi } from '@/api/platform/billing'
import type { PlatformPlan } from '@/types/billing'
import { formatCents } from '@/types/billing'
import { theme } from '@/theme'

const plans = ref<PlatformPlan[]>([])
const loading = ref(true)
const error = ref('')
const success = ref('')
const saving = ref<string | null>(null)
const editingPlan = ref<PlatformPlan | null>(null)
const editFeatures = ref<Record<string, { enabled: boolean; trial_days: number | null; data_retention_days: number | null }>>({})

// Create plan
const showCreateForm = ref(false)
const creating = ref(false)
const createForm = ref({
  name: '',
  slug: '',
  description: '',
  price_cents: 0,
  interval: 'monthly' as 'monthly' | 'yearly',
  max_students: null as number | null,
  max_teachers: null as number | null,
})

function autoSlug() {
  createForm.value.slug = createForm.value.name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

function resetCreateForm() {
  createForm.value = { name: '', slug: '', description: '', price_cents: 0, interval: 'monthly', max_students: null, max_teachers: null }
  showCreateForm.value = false
}

async function createPlan() {
  if (!createForm.value.name || !createForm.value.slug) return
  creating.value = true
  error.value = ''
  try {
    await platformBillingApi.createPlan({
      ...createForm.value,
      description: createForm.value.description || undefined,
      max_students: createForm.value.max_students || undefined,
      max_teachers: createForm.value.max_teachers || undefined,
    })
    resetCreateForm()
    flashSuccess('Plan aangemaakt')
    await loadPlans()
  } catch {
    error.value = 'Aanmaken mislukt'
  } finally {
    creating.value = false
  }
}

const featureLabels: Record<string, string> = {
  student_management: 'Leerlingbeheer',
  attendance: 'Aanwezigheid',
  schedule: 'Rooster',
  notifications: 'Notificaties',
  billing: 'Facturatie',
  collaborations: 'Samenwerkingen',
  reporting: 'Rapportage',
  api_access: 'API Toegang',
  custom_branding: 'Eigen Huisstijl',
  priority_support: 'Prioriteit Support',
}

const featureIcons: Record<string, object> = {
  student_management: GraduationCap,
  attendance: CheckCircle2,
  schedule: CalendarDays,
  notifications: BellRing,
  billing: Receipt,
  collaborations: Handshake,
  reporting: BarChart3,
  api_access: Code,
  custom_branding: Palette,
  priority_support: HeadsetIcon,
}

const baseFeatures = ['student_management', 'attendance', 'schedule', 'notifications']
const expandableFeatures = ['billing', 'collaborations', 'reporting', 'api_access', 'custom_branding', 'priority_support']

async function loadPlans() {
  try {
    plans.value = await platformBillingApi.listPlans(false)
  } catch {
    error.value = 'Kon plannen niet laden'
  } finally {
    loading.value = false
  }
}

function startEdit(plan: PlatformPlan) {
  editingPlan.value = plan
  const features = plan.features || {}
  const ef: typeof editFeatures.value = {}
  for (const name of [...baseFeatures, ...expandableFeatures]) {
    const f = (features as Record<string, any>)[name] || {}
    ef[name] = {
      enabled: f.enabled ?? baseFeatures.includes(name),
      trial_days: f.trial_days ?? null,
      data_retention_days: f.data_retention_days ?? null,
    }
  }
  editFeatures.value = ef
}

function cancelEdit() {
  editingPlan.value = null
  editFeatures.value = {}
}

async function saveFeatures() {
  if (!editingPlan.value) return
  saving.value = editingPlan.value.id
  try {
    await platformBillingApi.updatePlan(editingPlan.value.id, {
      features: editFeatures.value,
    })
    await loadPlans()
    cancelEdit()
    flashSuccess('Features opgeslagen')
  } catch {
    error.value = 'Opslaan mislukt'
  } finally {
    saving.value = null
  }
}

function featureCount(plan: PlatformPlan): number {
  if (!plan.features) return 0
  const f = plan.features as Record<string, any>
  return Object.values(f).filter((v: any) => v?.enabled).length
}

function flashSuccess(msg: string) {
  success.value = msg
  setTimeout(() => { success.value = '' }, 3000)
}

function priceLabel(plan: PlatformPlan): string {
  if (plan.price_cents === 0) return 'Gratis'
  return `${formatCents(plan.price_cents)}/${plan.interval === 'monthly' ? 'mo' : 'jr'}`
}

onMounted(loadPlans)

// Skeleton
const skeletonCards = Array.from({ length: 3 }, (_, i) => i)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <PackageOpen class="w-6 h-6 text-navy-700" />
        <h2 :class="theme.text.h2">Pakketbeheer</h2>
      </div>
      <button @click="showCreateForm = !showCreateForm" :class="theme.btn.addInline">
        <span :class="theme.btn.addInlineIcon"><Plus :size="14" /></span>
        Nieuw plan
      </button>
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
      <div v-if="success" :class="theme.alert.success">{{ success }}</div>
    </Transition>
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <!-- ─── Create form ─── -->
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div v-if="showCreateForm" :class="theme.card.base" class="overflow-hidden">
        <div class="flex items-center justify-between px-4 md:px-6 py-3 bg-surface border-b border-navy-100">
          <h3 :class="theme.text.h4">Nieuw plan aanmaken</h3>
          <button class="p-1 rounded hover:bg-navy-100 text-navy-400 hover:text-navy-700 transition-colors" @click="resetCreateForm">
            <X :size="16" />
          </button>
        </div>
        <form @submit.prevent="createPlan" class="p-4 md:p-6">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label :class="theme.form.label">Naam *</label>
              <input v-model="createForm.name" @input="autoSlug" :class="theme.form.input" placeholder="Bijv. Starter" required />
            </div>
            <div>
              <label :class="theme.form.label">Slug *</label>
              <input v-model="createForm.slug" :class="theme.form.input" placeholder="bijv. starter" required pattern="^[a-z0-9-]+$" />
            </div>
            <div class="md:col-span-2">
              <label :class="theme.form.label">Beschrijving</label>
              <input v-model="createForm.description" :class="theme.form.input" placeholder="Optioneel" />
            </div>
            <div>
              <label :class="theme.form.label">Prijs (centen) *</label>
              <input v-model.number="createForm.price_cents" type="number" min="0" :class="theme.form.input" placeholder="0 = gratis" required />
            </div>
            <div>
              <label :class="theme.form.label">Interval *</label>
              <select v-model="createForm.interval" :class="theme.form.input">
                <option value="monthly">Maandelijks</option>
                <option value="yearly">Jaarlijks</option>
              </select>
            </div>
            <div>
              <label :class="theme.form.label">Max leerlingen</label>
              <input v-model.number="createForm.max_students" type="number" min="0" :class="theme.form.input" placeholder="Onbeperkt" />
            </div>
            <div>
              <label :class="theme.form.label">Max docenten</label>
              <input v-model.number="createForm.max_teachers" type="number" min="0" :class="theme.form.input" placeholder="Onbeperkt" />
            </div>
          </div>
          <div class="flex gap-2 mt-5 pt-4 border-t border-navy-100">
            <button type="submit" :class="theme.btn.primary" :disabled="creating || !createForm.name || !createForm.slug">
              {{ creating ? 'Aanmaken...' : 'Plan aanmaken' }}
            </button>
            <button type="button" :class="theme.btn.ghost" @click="resetCreateForm">Annuleren</button>
          </div>
        </form>
      </div>
    </Transition>

    <!-- ──── Loading Skeleton ──── -->
    <template v-if="loading">
      <div class="space-y-4">
        <div v-for="i in skeletonCards" :key="i" :class="theme.card.base" class="overflow-hidden skeleton-card" :style="{ animationDelay: i * 100 + 'ms' }">
          <div class="p-4 md:p-6">
            <div class="flex items-center justify-between mb-4">
              <div class="space-y-2">
                <div class="h-6 w-32 bg-navy-100 rounded animate-pulse" />
                <div class="h-4 w-48 bg-navy-100 rounded animate-pulse" />
              </div>
              <div class="h-8 w-28 bg-navy-100 rounded animate-pulse" />
            </div>
            <div class="flex gap-2">
              <div v-for="j in 5" :key="j" class="h-6 w-20 bg-navy-100 rounded-full animate-pulse" />
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ──── Empty state ──── -->
    <div v-else-if="plans.length === 0 && !showCreateForm" :class="theme.emptyState.wrapper">
      <div :class="theme.emptyState.iconWrap">
        <PackageOpen :size="24" :class="theme.emptyState.icon" />
      </div>
      <p :class="theme.emptyState.title">Geen plannen gevonden</p>
      <p :class="theme.emptyState.description">Maak je eerste abonnementsplan aan met de knop hierboven.</p>
    </div>

    <!-- ──── Plan Cards ──── -->
    <div v-else class="space-y-4">
      <div
        v-for="plan in plans"
        :key="plan.id"
        :class="theme.card.base"
        class="overflow-hidden transition-shadow"
        :class2="editingPlan?.id === plan.id ? 'ring-2 ring-accent-200 shadow-md' : ''"
      >
        <!-- Plan header -->
        <div class="flex items-start justify-between p-4 md:p-6"
          :class="editingPlan?.id === plan.id ? 'bg-accent-50/30 border-b border-navy-100' : ''"
        >
          <div class="flex items-start gap-3">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              :class="plan.is_active ? 'bg-accent-50' : 'bg-navy-100'"
            >
              <PackageOpen :size="20" :class="plan.is_active ? 'text-accent-700' : 'text-navy-400'" />
            </div>
            <div>
              <div class="flex items-center gap-2">
                <h3 :class="theme.text.h3">{{ plan.name }}</h3>
                <span v-if="!plan.is_active" :class="[theme.badge.base, theme.badge.warning]">Inactief</span>
              </div>
              <div class="flex items-center gap-3 mt-0.5">
                <span class="text-lg font-bold text-accent-700">{{ priceLabel(plan) }}</span>
                <span :class="theme.text.muted" class="text-sm">&middot;</span>
                <span :class="theme.text.muted" class="text-sm">{{ featureCount(plan) }} features actief</span>
              </div>
              <p v-if="plan.description" :class="theme.text.muted" class="text-sm mt-1">{{ plan.description }}</p>
              <!-- Limits -->
              <div class="flex items-center gap-3 mt-2 text-xs" :class="theme.text.muted">
                <span class="flex items-center gap-1">
                  <GraduationCap :size="12" />
                  {{ plan.max_students ?? '\u221E' }} leerlingen
                </span>
                <span class="flex items-center gap-1">
                  <Users :size="12" />
                  {{ plan.max_teachers ?? '\u221E' }} docenten
                </span>
              </div>
            </div>
          </div>
          <button
            v-if="editingPlan?.id !== plan.id"
            :class="theme.btn.ghost"
            class="shrink-0"
            @click="startEdit(plan)"
          >
            <Pencil :size="14" class="mr-1.5" />
            Features
          </button>
        </div>

        <!-- Feature chips (collapsed view) -->
        <div v-if="editingPlan?.id !== plan.id && plan.features" class="px-4 md:px-6 pb-4 md:pb-6">
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="name in [...baseFeatures, ...expandableFeatures]"
              :key="name"
              class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors"
              :class="(plan.features as Record<string, any>)?.[name]?.enabled || baseFeatures.includes(name)
                ? 'bg-green-50 text-green-700'
                : 'bg-navy-50 text-navy-400'
              "
            >
              <component :is="featureIcons[name]" :size="12" />
              {{ featureLabels[name] }}
            </span>
          </div>
        </div>

        <!-- ─── Feature editor (expanded) ─── -->
        <div v-if="editingPlan?.id === plan.id" class="p-4 md:p-6">
          <!-- Base features -->
          <div class="mb-5">
            <div class="flex items-center gap-2 mb-3">
              <Shield :size="14" class="text-navy-400" />
              <p class="text-xs font-semibold text-navy-700 uppercase tracking-wide">Base features (altijd aan)</p>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
              <div
                v-for="name in baseFeatures"
                :key="name"
                class="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-50"
              >
                <component :is="featureIcons[name]" :size="14" class="text-green-600 shrink-0" />
                <span class="text-sm text-green-700 font-medium">{{ featureLabels[name] }}</span>
              </div>
            </div>
          </div>

          <!-- Expandable features -->
          <div>
            <div class="flex items-center gap-2 mb-3">
              <Plus :size="14" class="text-navy-400" />
              <p class="text-xs font-semibold text-navy-700 uppercase tracking-wide">Uitbreidbare features</p>
            </div>
            <div class="space-y-2">
              <div
                v-for="name in expandableFeatures"
                :key="name"
                class="flex items-center gap-4 px-3 py-2.5 rounded-lg border transition-colors"
                :class="editFeatures[name]?.enabled ? 'bg-green-50/50 border-green-200' : 'bg-white border-navy-100'"
              >
                <!-- Toggle + name -->
                <label class="flex items-center gap-2.5 min-w-[140px] cursor-pointer">
                  <input
                    type="checkbox"
                    v-model="editFeatures[name].enabled"
                    class="rounded border-navy-300 text-accent-700 focus:ring-accent-200"
                  />
                  <component :is="featureIcons[name]" :size="14" :class="editFeatures[name]?.enabled ? 'text-green-600' : 'text-navy-300'" />
                  <span class="text-sm font-medium" :class="editFeatures[name]?.enabled ? 'text-navy-900' : 'text-navy-500'">
                    {{ featureLabels[name] }}
                  </span>
                </label>

                <!-- Trial days -->
                <div class="flex items-center gap-1.5 ml-auto">
                  <Clock :size="12" class="text-navy-300" />
                  <span :class="theme.text.muted" class="text-xs hidden md:inline">Trial</span>
                  <input
                    type="number"
                    v-model.number="editFeatures[name].trial_days"
                    min="0"
                    :class="[theme.form.input, 'w-16 !py-1 text-xs text-center']"
                    placeholder="\u2014"
                  />
                  <span :class="theme.text.muted" class="text-xs hidden md:inline">d</span>
                </div>

                <!-- Retention days -->
                <div class="flex items-center gap-1.5">
                  <Infinity :size="12" class="text-navy-300" />
                  <span :class="theme.text.muted" class="text-xs hidden md:inline">Retentie</span>
                  <input
                    type="number"
                    v-model.number="editFeatures[name].data_retention_days"
                    min="0"
                    :class="[theme.form.input, 'w-16 !py-1 text-xs text-center']"
                    placeholder="\u221E"
                  />
                  <span :class="theme.text.muted" class="text-xs hidden md:inline">d</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex gap-2 mt-5 pt-4 border-t border-navy-100">
            <button
              :class="theme.btn.primary"
              :disabled="saving === editingPlan.id"
              @click="saveFeatures"
            >
              {{ saving === editingPlan.id ? 'Opslaan...' : 'Opslaan' }}
            </button>
            <button :class="theme.btn.ghost" @click="cancelEdit">Annuleren</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes skeletonFadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.skeleton-card {
  opacity: 0;
  animation: skeletonFadeIn 0.3s ease forwards;
}
</style>
