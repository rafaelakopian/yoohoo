<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Check, X, Loader2, Building2, CreditCard, Rocket, CircleCheck } from 'lucide-vue-next'
import { theme } from '@/theme'
import { orgsApi } from '@/api/platform/orgs'
import { platformBillingApi } from '@/api/platform/billing'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { isValidSlug, sanitizeSlug } from '@/utils/validators'
import type { PlatformPlan } from '@/types/billing'
import { formatCents } from '@/types/billing'

const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()

// Wizard state
const step = ref(1)
const error = ref('')

// Step 1: Name + Slug
const name = ref('')
const slug = ref('')
const slugManual = ref(false)
const slugAvailable = ref<boolean | null>(null)
const slugChecking = ref(false)
let slugTimeout: ReturnType<typeof setTimeout> | null = null

// Step 2: Plan
const plans = ref<PlatformPlan[]>([])
const plansLoading = ref(true)
const selectedPlanId = ref('')

const selectedPlan = computed(() => plans.value.find(p => p.id === selectedPlanId.value))

// Step 3: Create
const creating = ref(false)

// Step 1 validation
const step1Valid = computed(() =>
  name.value.trim().length >= 2 &&
  slug.value.length >= 2 &&
  isValidSlug(slug.value) &&
  slugAvailable.value === true
)

function onNameInput() {
  if (!slugManual.value) {
    slug.value = name.value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
  }
}

function onSlugInput(e: Event) {
  slugManual.value = true
  slug.value = sanitizeSlug((e.target as HTMLInputElement).value)
}

watch(slug, (val) => {
  slugAvailable.value = null
  if (slugTimeout) clearTimeout(slugTimeout)
  if (!val || val.length < 2 || !isValidSlug(val)) return

  slugChecking.value = true
  slugTimeout = setTimeout(async () => {
    try {
      const result = await orgsApi.checkSlug(val)
      if (slug.value === val) {
        slugAvailable.value = result.available
      }
    } catch {
      slugAvailable.value = null
    } finally {
      slugChecking.value = false
    }
  }, 400)
})

// Load plans when reaching step 2
async function goToStep2() {
  if (!step1Valid.value) return
  step.value = 2
  if (plans.value.length === 0) {
    plansLoading.value = true
    try {
      plans.value = await platformBillingApi.listPlans(true)
    } catch {
      error.value = 'Kon plannen niet laden'
    } finally {
      plansLoading.value = false
    }
  }
}

function selectPlan(plan: PlatformPlan) {
  selectedPlanId.value = plan.id
}

function formatPrice(plan: PlatformPlan): string {
  if (plan.price_cents === 0) return 'Gratis'
  return formatCents(plan.price_cents)
}

function formatInterval(plan: PlatformPlan): string {
  if (plan.price_cents === 0) return ''
  return plan.interval === 'monthly' ? '/maand' : '/jaar'
}

async function createOrg() {
  if (!selectedPlan.value) return
  creating.value = true
  error.value = ''
  try {
    const tenant = await orgsApi.selfServiceCreate({
      name: name.value.trim(),
      slug: slug.value,
      plan_id: selectedPlanId.value,
    })
    await authStore.fetchUser()
    await tenantStore.fetchTenants()
    const newTenant = tenantStore.tenants.find(t => t.id === tenant.id)
    if (newTenant) {
      await tenantStore.selectTenant(newTenant)
    }
    router.push(`/org/${tenant.slug}/dashboard`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Aanmaken mislukt. Probeer het opnieuw.'
    creating.value = false
  }
}

const steps = [
  { num: 1, label: 'Organisatie', icon: Building2 },
  { num: 2, label: 'Pakket', icon: CreditCard },
  { num: 3, label: 'Bevestigen', icon: Rocket },
]
</script>

<template>
  <div class="max-w-3xl mx-auto px-4 py-12">
    <!-- Step indicator -->
    <div class="flex items-center justify-center gap-2 mb-10">
      <template v-for="(s, i) in steps" :key="s.num">
        <div class="flex items-center gap-2">
          <div
            class="w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold transition-colors"
            :class="step >= s.num ? 'bg-accent-700 text-white' : 'bg-navy-100 text-navy-400'"
          >
            <component :is="s.icon" :size="16" />
          </div>
          <span
            class="text-sm font-medium hidden sm:inline"
            :class="step >= s.num ? 'text-navy-900' : 'text-muted'"
          >{{ s.label }}</span>
        </div>
        <div
          v-if="i < steps.length - 1"
          class="w-12 h-0.5 mx-1"
          :class="step > s.num ? 'bg-accent-700' : 'bg-navy-100'"
        />
      </template>
    </div>

    <div v-if="error" :class="[theme.alert.error, 'mb-6']">{{ error }}</div>

    <!-- Step 1: Name + Slug -->
    <div v-if="step === 1" :class="theme.card.padded">
      <h2 :class="[theme.text.h2, 'mb-1']">Geef je organisatie een naam</h2>
      <p :class="[theme.text.muted, 'mb-6']">Dit is de naam die je leerlingen en docenten zien.</p>

      <div class="space-y-4">
        <div>
          <label :class="theme.form.label">Organisatienaam</label>
          <input
            v-model="name"
            @input="onNameInput"
            :class="theme.form.input"
            placeholder="Bijv. Muziekschool Amsterdam"
            autofocus
          />
        </div>

        <div>
          <label :class="theme.form.label">URL (slug)</label>
          <div class="relative">
            <input
              :value="slug"
              @input="onSlugInput"
              :class="[theme.form.input, 'pr-10']"
              placeholder="bijv. muziekschool-amsterdam"
            />
            <div class="absolute right-3 top-1/2 -translate-y-1/2">
              <Loader2 v-if="slugChecking" :size="18" class="text-navy-300 animate-spin" />
              <Check v-else-if="slugAvailable === true" :size="18" class="text-green-600" />
              <X v-else-if="slugAvailable === false" :size="18" class="text-red-500" />
            </div>
          </div>
          <p v-if="slug" class="mt-1 text-xs" :class="slugAvailable === false ? 'text-red-500' : 'text-muted'">
            <template v-if="slugAvailable === false">Deze slug is al in gebruik. Kies een andere.</template>
            <template v-else-if="slugAvailable === true">app.yoohoo.nl/org/{{ slug }}</template>
            <template v-else-if="slug.length >= 2 && isValidSlug(slug)">Beschikbaarheid wordt gecontroleerd...</template>
            <template v-else>Alleen kleine letters, cijfers en streepjes. Minimaal 2 tekens.</template>
          </p>
        </div>
      </div>

      <div class="flex justify-end mt-8">
        <button :class="theme.btn.primary" :disabled="!step1Valid" @click="goToStep2">
          Volgende
        </button>
      </div>
    </div>

    <!-- Step 2: Plan selection -->
    <div v-else-if="step === 2">
      <div class="text-center mb-8">
        <h2 :class="[theme.text.h2, 'mb-1']">Kies je pakket</h2>
        <p :class="theme.text.muted">Start gratis en schaal op wanneer je groeit. Geen verborgen kosten.</p>
      </div>

      <div v-if="plansLoading" class="text-center py-12">
        <Loader2 :size="24" class="mx-auto text-navy-300 animate-spin mb-2" />
        <p :class="theme.text.muted">Pakketten laden...</p>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div
          v-for="plan in plans"
          :key="plan.id"
          class="relative rounded-xl border-2 p-6 cursor-pointer transition-all"
          :class="selectedPlanId === plan.id
            ? 'border-accent-700 bg-accent-50/30 shadow-md'
            : 'border-navy-100 bg-white hover:border-navy-200 hover:shadow-sm'"
          @click="selectPlan(plan)"
        >
          <!-- Popular badge -->
          <div
            v-if="plan.sort_order === 1"
            class="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-xs font-semibold bg-accent-700 text-white"
          >
            Populair
          </div>

          <h3 :class="[theme.text.h3, 'mb-2']">{{ plan.name }}</h3>

          <div class="mb-1">
            <span class="text-2xl font-bold text-navy-900">{{ formatPrice(plan) }}</span>
            <span v-if="formatInterval(plan)" class="text-sm text-muted ml-0.5">{{ formatInterval(plan) }}</span>
          </div>

          <p v-if="plan.description" :class="[theme.text.muted, 'text-sm mb-4']">{{ plan.description }}</p>

          <ul class="space-y-2 mt-4">
            <li v-if="plan.max_students !== null" class="flex items-center gap-2 text-sm text-navy-700">
              <CircleCheck :size="16" class="text-green-600 shrink-0" />
              Tot {{ plan.max_students }} leerlingen
            </li>
            <li v-else class="flex items-center gap-2 text-sm text-navy-700">
              <CircleCheck :size="16" class="text-green-600 shrink-0" />
              Onbeperkt leerlingen
            </li>
            <li v-if="plan.max_teachers !== null" class="flex items-center gap-2 text-sm text-navy-700">
              <CircleCheck :size="16" class="text-green-600 shrink-0" />
              Tot {{ plan.max_teachers }} docenten
            </li>
            <li v-else class="flex items-center gap-2 text-sm text-navy-700">
              <CircleCheck :size="16" class="text-green-600 shrink-0" />
              Onbeperkt docenten
            </li>
          </ul>

          <!-- Selected indicator -->
          <div
            v-if="selectedPlanId === plan.id"
            class="absolute top-4 right-4 w-6 h-6 rounded-full bg-accent-700 flex items-center justify-center"
          >
            <Check :size="14" class="text-white" />
          </div>
        </div>
      </div>

      <div class="flex justify-between mt-8">
        <button :class="theme.btn.ghost" @click="step = 1">Terug</button>
        <button :class="theme.btn.primary" :disabled="!selectedPlanId" @click="step = 3">
          Volgende
        </button>
      </div>
    </div>

    <!-- Step 3: Confirmation -->
    <div v-else-if="step === 3" :class="theme.card.padded">
      <h2 :class="[theme.text.h2, 'mb-1']">Bevestig je organisatie</h2>
      <p :class="[theme.text.muted, 'mb-6']">Controleer de gegevens en maak je organisatie aan.</p>

      <div class="space-y-4">
        <div class="flex justify-between py-3 border-b border-navy-100">
          <span :class="theme.text.body">Organisatienaam</span>
          <span class="text-sm font-medium text-navy-900">{{ name }}</span>
        </div>
        <div class="flex justify-between py-3 border-b border-navy-100">
          <span :class="theme.text.body">URL</span>
          <span class="text-sm font-medium text-navy-900">app.yoohoo.nl/org/{{ slug }}</span>
        </div>
        <div class="flex justify-between py-3 border-b border-navy-100">
          <span :class="theme.text.body">Pakket</span>
          <span class="text-sm font-medium text-navy-900">{{ selectedPlan?.name }}</span>
        </div>
        <div class="flex justify-between py-3">
          <span :class="theme.text.body">Prijs</span>
          <span class="text-sm font-medium text-navy-900">
            {{ selectedPlan ? formatPrice(selectedPlan) : '' }}
            {{ selectedPlan ? formatInterval(selectedPlan) : '' }}
          </span>
        </div>
      </div>

      <div class="flex justify-between mt-8">
        <button :class="theme.btn.ghost" @click="step = 2" :disabled="creating">Terug</button>
        <button :class="theme.btn.primary" :disabled="creating" @click="createOrg">
          <Loader2 v-if="creating" :size="16" class="inline mr-1.5 animate-spin" />
          {{ creating ? 'Bezig met aanmaken...' : 'Organisatie aanmaken' }}
        </button>
      </div>
    </div>
  </div>
</template>
