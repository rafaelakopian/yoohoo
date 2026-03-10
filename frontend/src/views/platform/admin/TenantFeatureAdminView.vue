<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { theme } from '@/theme'
import { featureCatalogApi } from '@/api/platform/features'
import type { TenantFeatureStatusItem } from '@/types/billing'

const route = useRoute()
const tenantId = route.params.tenantId as string
const slug = route.params.slug as string

const features = ref<TenantFeatureStatusItem[]>([])
const loading = ref(true)
const error = ref('')
const actionMsg = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    features.value = await featureCatalogApi.getTenantFeatures(tenantId)
  } catch {
    error.value = 'Fout bij laden van features.'
  } finally {
    loading.value = false
  }
}

async function doAction(action: () => Promise<void>, successMsg: string) {
  error.value = ''
  actionMsg.value = ''
  try {
    await action()
    actionMsg.value = successMsg
    await load()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Actie mislukt.'
  }
}

function statusLabel(item: TenantFeatureStatusItem): string {
  if (item.access.is_force_blocked) return 'Geblokkeerd'
  if (item.access.is_force_enabled) return 'Force-on'
  if (item.access.in_trial) return 'Proefperiode'
  if (item.access.in_retention) return 'Retentie'
  if (item.access.allowed) return 'Actief'
  return 'Niet beschikbaar'
}

function statusBadge(item: TenantFeatureStatusItem): string {
  if (item.access.is_force_blocked) return theme.badge.error
  if (item.access.is_force_enabled) return theme.badge.info
  if (item.access.in_trial) return theme.badge.warning
  if (item.access.in_retention) return theme.badge.warning
  if (item.access.allowed) return theme.badge.success
  return theme.badge.default
}

const extendDays = ref<Record<string, number>>({})
const forceOffReason = ref<Record<string, string>>({})

onMounted(load)
</script>

<template>
  <div :class="theme.page.bg">
    <div class="max-w-6xl mx-auto px-4 py-8">
      <div :class="theme.pageHeader.row">
        <div>
          <h1 :class="theme.text.h1">Feature Beheer</h1>
          <p :class="theme.text.subtitle">Per-tenant feature overrides voor {{ slug || tenantId }}</p>
        </div>
      </div>

      <div v-if="error" :class="theme.alert.error" class="mb-4">{{ error }}</div>
      <div v-if="actionMsg" :class="theme.alert.success" class="mb-4">{{ actionMsg }}</div>

      <div v-if="loading" :class="theme.text.muted">Laden...</div>

      <div v-else class="space-y-4">
        <div v-for="f in features" :key="f.feature_name" :class="theme.card.padded">
          <div class="flex items-center justify-between mb-3">
            <div>
              <h3 :class="theme.text.h3">{{ f.catalog?.display_name || f.feature_name }}</h3>
              <span :class="theme.text.muted" class="text-sm">{{ f.feature_name }}</span>
            </div>
            <span :class="[theme.badge.base, statusBadge(f)]">{{ statusLabel(f) }}</span>
          </div>

          <!-- Trial info -->
          <div v-if="f.trial" :class="theme.text.body" class="mb-2">
            Status: {{ f.trial.status }}
            <template v-if="f.trial.trial_expires_at"> · Verloopt: {{ new Date(f.trial.trial_expires_at).toLocaleDateString('nl-NL') }}</template>
            <template v-if="f.trial.reset_count > 0"> · Resets: {{ f.trial.reset_count }}</template>
          </div>

          <!-- Override info -->
          <div v-if="f.override" :class="theme.text.body" class="mb-2">
            <template v-if="f.override.force_off">Geblokkeerd: {{ f.override.force_off_reason || '(geen reden)' }}</template>
            <template v-if="f.override.force_on">Handmatig geactiveerd</template>
            <template v-if="f.override.trial_days">Trial override: {{ f.override.trial_days }}d</template>
            <template v-if="f.override.retention_days"> · Retentie override: {{ f.override.retention_days }}d</template>
          </div>

          <!-- Actions -->
          <div class="flex flex-wrap items-center gap-2 mt-3">
            <!-- Force on/off -->
            <template v-if="f.access.is_force_blocked">
              <button :class="theme.btn.secondarySm" @click="doAction(() => featureCatalogApi.liftForceOff(tenantId, f.feature_name), 'Blokkade opgeheven')">
                Deblokkeren
              </button>
            </template>
            <template v-else-if="f.access.is_force_enabled">
              <button :class="theme.btn.ghost" @click="doAction(() => featureCatalogApi.liftForceOff(tenantId, f.feature_name), 'Force-on opgeheven')">
                Force-on opheffen
              </button>
            </template>
            <template v-else>
              <button :class="theme.btn.secondarySm" @click="doAction(() => featureCatalogApi.forceOn(tenantId, f.feature_name), 'Feature geactiveerd')">
                Force on
              </button>
              <div class="flex items-center gap-1">
                <input v-model="forceOffReason[f.feature_name]" :class="theme.form.input" class="!py-1.5 text-sm w-40" placeholder="Reden..." />
                <button
                  :class="theme.btn.dangerOutline"
                  @click="doAction(() => featureCatalogApi.forceOff(tenantId, f.feature_name, forceOffReason[f.feature_name]), 'Feature geblokkeerd')"
                >
                  Blokkeren
                </button>
              </div>
            </template>

            <!-- Trial actions -->
            <template v-if="f.trial">
              <button :class="theme.btn.ghost" @click="doAction(() => featureCatalogApi.resetTrial(tenantId, f.feature_name), 'Trial gereset')">
                Reset trial
              </button>
              <div v-if="f.trial.status === 'trialing'" class="flex items-center gap-1">
                <input v-model.number="extendDays[f.feature_name]" type="number" :class="theme.form.input" class="!py-1.5 text-sm w-20" placeholder="Dagen" />
                <button
                  :class="theme.btn.ghost"
                  :disabled="!extendDays[f.feature_name]"
                  @click="doAction(() => featureCatalogApi.extendTrial(tenantId, f.feature_name, extendDays[f.feature_name] || 0), 'Trial verlengd')"
                >
                  Verleng
                </button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
