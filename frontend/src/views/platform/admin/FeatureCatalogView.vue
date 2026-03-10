<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { theme } from '@/theme'
import { featureCatalogApi } from '@/api/platform/features'
import type { FeatureCatalogEntry } from '@/types/billing'

const items = ref<FeatureCatalogEntry[]>([])
const loading = ref(true)
const error = ref('')
const editItem = ref<FeatureCatalogEntry | null>(null)
const showModal = ref(false)

const form = ref({
  display_name: '',
  description: '',
  benefits: [] as string[],
  preview_image_url: '',
  default_trial_days: 14,
  default_retention_days: 90,
  is_active: true,
})
const editFeatureName = ref('')
const saving = ref(false)

async function loadCatalog() {
  loading.value = true
  error.value = ''
  try {
    items.value = await featureCatalogApi.getCatalog()
  } catch {
    error.value = 'Fout bij laden van de feature catalogus.'
  } finally {
    loading.value = false
  }
}

function openEdit(item: FeatureCatalogEntry) {
  editItem.value = item
  editFeatureName.value = item.feature_name
  form.value = {
    display_name: item.display_name,
    description: item.description || '',
    benefits: item.benefits || [],
    preview_image_url: item.preview_image_url || '',
    default_trial_days: item.default_trial_days,
    default_retention_days: item.default_retention_days,
    is_active: item.is_active,
  }
  showModal.value = true
}

function openCreate() {
  editItem.value = null
  editFeatureName.value = ''
  form.value = {
    display_name: '',
    description: '',
    benefits: [],
    preview_image_url: '',
    default_trial_days: 14,
    default_retention_days: 90,
    is_active: true,
  }
  showModal.value = true
}

async function save() {
  if (!editFeatureName.value) return
  saving.value = true
  error.value = ''
  try {
    await featureCatalogApi.upsertCatalogItem(editFeatureName.value, {
      display_name: form.value.display_name,
      description: form.value.description || null,
      benefits: form.value.benefits.length ? form.value.benefits : null,
      preview_image_url: form.value.preview_image_url || null,
      default_trial_days: form.value.default_trial_days,
      default_retention_days: form.value.default_retention_days,
      is_active: form.value.is_active,
    })
    showModal.value = false
    await loadCatalog()
  } catch {
    error.value = 'Fout bij opslaan.'
  } finally {
    saving.value = false
  }
}

onMounted(loadCatalog)
</script>

<template>
  <div :class="theme.page.bg">
    <div class="max-w-5xl mx-auto px-4 py-8">
      <div :class="theme.pageHeader.rowResponsive">
        <div>
          <h1 :class="theme.text.h1">Feature Catalogus</h1>
          <p :class="theme.text.subtitle">Beheer feature definities, proefperiodes en bewaartermijnen.</p>
        </div>
        <button :class="theme.btn.primary" @click="openCreate">+ Feature toevoegen</button>
      </div>

      <div v-if="error" :class="theme.alert.error">{{ error }}</div>

      <div v-if="loading" :class="theme.text.muted">Laden...</div>

      <div v-else-if="items.length === 0" :class="theme.list.empty">
        Geen features in de catalogus. Voeg er een toe.
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="item in items"
          :key="item.id"
          :class="theme.card.padded"
          class="cursor-pointer hover:shadow-md transition-shadow"
          @click="openEdit(item)"
        >
          <div class="flex items-center justify-between">
            <div>
              <h3 :class="theme.text.h3">{{ item.display_name }}</h3>
              <p :class="theme.text.muted" class="text-sm">{{ item.feature_name }}</p>
            </div>
            <div class="flex items-center gap-3">
              <span :class="[theme.badge.base, item.is_active ? theme.badge.success : theme.badge.default]">
                {{ item.is_active ? 'Actief' : 'Inactief' }}
              </span>
              <span :class="theme.text.muted" class="text-sm">
                Trial: {{ item.default_trial_days }}d · Retentie: {{ item.default_retention_days }}d
              </span>
            </div>
          </div>
          <p v-if="item.description" :class="theme.text.body" class="mt-2">{{ item.description }}</p>
        </div>
      </div>

      <!-- Edit/Create Modal -->
      <Teleport to="body">
        <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="showModal = false">
          <div :class="theme.card.form" class="w-full max-w-lg mx-4">
            <h2 :class="theme.text.h2" class="mb-4">
              {{ editItem ? 'Feature bewerken' : 'Nieuwe feature' }}
            </h2>

            <div class="space-y-4">
              <div v-if="!editItem">
                <label :class="theme.form.label">Feature name (slug)</label>
                <input v-model="editFeatureName" :class="theme.form.input" placeholder="billing" />
              </div>
              <div>
                <label :class="theme.form.label">Weergavenaam</label>
                <input v-model="form.display_name" :class="theme.form.input" />
              </div>
              <div>
                <label :class="theme.form.label">Beschrijving</label>
                <textarea v-model="form.description" :class="theme.form.input" rows="3" />
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label :class="theme.form.label">Proefperiode (dagen)</label>
                  <input v-model.number="form.default_trial_days" type="number" :class="theme.form.input" />
                </div>
                <div>
                  <label :class="theme.form.label">Bewaartermijn (dagen)</label>
                  <input v-model.number="form.default_retention_days" type="number" :class="theme.form.input" />
                </div>
              </div>
              <div class="flex items-center gap-2">
                <input id="is_active" v-model="form.is_active" type="checkbox" />
                <label for="is_active" :class="theme.form.label">Actief</label>
              </div>
            </div>

            <div class="flex justify-end gap-3 mt-6">
              <button :class="theme.btn.ghost" @click="showModal = false">Annuleren</button>
              <button :class="theme.btn.primary" :disabled="saving || !editFeatureName" @click="save">
                {{ saving ? 'Opslaan...' : 'Opslaan' }}
              </button>
            </div>
          </div>
        </div>
      </Teleport>
    </div>
  </div>
</template>
