<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { featuresApi } from '@/api/products/school/features'
import type { FeatureStatusItem } from '@/types/billing'
import { formatCents } from '@/types/billing'
import { theme } from '@/theme'
import { Lock, Unlock, Clock, AlertTriangle, CheckCircle } from 'lucide-vue-next'

const features = ref<FeatureStatusItem[]>([])
const loading = ref(true)
const error = ref('')
const trialLoading = ref<string | null>(null)
const trialMessage = ref('')

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

async function loadFeatures() {
  try {
    const resp = await featuresApi.listFeatures()
    features.value = resp.features
  } catch {
    error.value = 'Kon features niet laden'
  } finally {
    loading.value = false
  }
}

async function startTrial(featureName: string) {
  trialLoading.value = featureName
  trialMessage.value = ''
  try {
    const resp = await featuresApi.startTrial(featureName)
    trialMessage.value = resp.message
    await loadFeatures()
  } catch (e: any) {
    trialMessage.value = e.response?.data?.detail || 'Kan proefperiode niet starten'
  } finally {
    trialLoading.value = null
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })
}

const expandableFeatures = computed(() =>
  features.value.filter(f => !['student_management', 'attendance', 'schedule', 'notifications'].includes(f.name))
)

const baseFeatures = computed(() =>
  features.value.filter(f => ['student_management', 'attendance', 'schedule', 'notifications'].includes(f.name))
)

onMounted(loadFeatures)
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <h2 :class="theme.text.h2">Features &amp; Upgrades</h2>
    <p :class="[theme.text.muted, 'mt-1 mb-6']">
      Bekijk welke features beschikbaar zijn in uw pakket en start proefperiodes.
    </p>

    <div v-if="error" :class="[theme.alert.error, 'mb-4']">{{ error }}</div>
    <div v-if="trialMessage" :class="[theme.alert.success, 'mb-4']">{{ trialMessage }}</div>

    <div v-if="loading" :class="theme.text.muted">Laden...</div>

    <template v-else>
      <!-- Base features (always on) -->
      <div :class="[theme.card.padded, 'mb-6']">
        <h2 :class="[theme.text.h3, 'mb-3']">Standaard features</h2>
        <div class="space-y-2">
          <div v-for="f in baseFeatures" :key="f.name" class="flex items-center gap-3">
            <CheckCircle :size="18" class="text-green-600 shrink-0" />
            <span :class="theme.text.body">{{ featureLabels[f.name] || f.name }}</span>
          </div>
        </div>
      </div>

      <!-- Expandable features -->
      <div class="space-y-3">
        <div
          v-for="f in expandableFeatures"
          :key="f.name"
          :class="theme.card.padded"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-3">
              <component
                :is="f.access.is_force_blocked ? AlertTriangle : (f.access.allowed ? Unlock : (f.access.in_retention ? AlertTriangle : Lock))"
                :size="20"
                :class="f.access.is_force_blocked ? 'text-red-500 mt-0.5' : (f.access.allowed ? 'text-green-600 mt-0.5' : (f.access.in_retention ? 'text-amber-500 mt-0.5' : 'text-navy-300 mt-0.5'))"
              />
              <div>
                <h3 :class="theme.text.h4">{{ featureLabels[f.name] || f.name }}</h3>

                <!-- Status badges -->
                <div class="flex items-center gap-2 mt-1">
                  <span v-if="f.access.is_force_blocked" :class="[theme.badge.base, theme.badge.error]">
                    Niet beschikbaar
                  </span>
                  <span v-else-if="f.access.is_force_enabled" :class="[theme.badge.base, theme.badge.success]">
                    Actief
                  </span>
                  <span v-else-if="f.access.allowed && !f.access.in_trial" :class="[theme.badge.base, theme.badge.success]">
                    Actief
                  </span>
                  <span v-else-if="f.access.in_trial" :class="[theme.badge.base, theme.badge.info]">
                    <Clock :size="12" class="inline mr-1" />
                    Proefperiode t/m {{ formatDate(f.access.trial_expires_at) }}
                  </span>
                  <span v-else-if="f.access.in_retention" :class="[theme.badge.base, theme.badge.warning]">
                    Retentieperiode
                  </span>
                  <span v-else :class="[theme.badge.base, theme.badge.default]">
                    Niet beschikbaar
                  </span>
                </div>

                <!-- Force blocked message -->
                <p v-if="f.access.is_force_blocked" :class="[theme.text.muted, 'text-xs mt-1']">
                  {{ f.access.force_off_reason || 'Deze functie is tijdelijk niet beschikbaar. Neem contact op met de beheerder.' }}
                </p>
                <!-- Reason if denied -->
                <p v-else-if="!f.access.allowed && f.access.reason" :class="[theme.text.muted, 'text-xs mt-1']">
                  {{ f.access.reason }}
                </p>
              </div>
            </div>

            <div class="shrink-0">
              <!-- Trial button -->
              <button
                v-if="f.access.trial_available && !f.access.allowed"
                :class="theme.btn.primarySm"
                :disabled="trialLoading === f.name"
                @click="startTrial(f.name)"
              >
                {{ trialLoading === f.name ? 'Starten...' : `${f.access.trial_days} dagen proberen` }}
              </button>
            </div>
          </div>

          <!-- Upgrade plans -->
          <div v-if="!f.access.allowed && f.access.upgrade_plans.length > 0" class="mt-3 pt-3 border-t border-navy-100">
            <p :class="[theme.text.muted, 'text-xs mb-2']">Beschikbaar in:</p>
            <div class="flex gap-2 flex-wrap">
              <span
                v-for="p in f.access.upgrade_plans"
                :key="p.id"
                :class="[theme.badge.base, theme.badge.info]"
              >
                {{ p.name }} — {{ formatCents(p.price_cents) }}/{{ p.interval === 'monthly' ? 'mnd' : 'jr' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
