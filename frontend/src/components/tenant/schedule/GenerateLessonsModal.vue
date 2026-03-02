<script setup lang="ts">
import { ref } from 'vue'
import { X, Zap } from 'lucide-vue-next'
import { theme } from '@/theme'
import { lessonApi } from '@/api/tenant/schedule'
import type { GenerateLessonsResponse } from '@/types/models'

const emit = defineEmits<{
  close: []
  generated: [result: GenerateLessonsResponse]
}>()

const loading = ref(false)
const error = ref<string | null>(null)

const startDate = ref('')
const endDate = ref('')

async function handleGenerate() {
  if (!startDate.value || !endDate.value) return

  loading.value = true
  error.value = null

  try {
    const result = await lessonApi.generate(startDate.value, endDate.value)
    emit('generated', result)
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Genereren mislukt'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-xl w-full max-w-sm">
      <div class="flex items-center justify-between p-6 border-b border-navy-100">
        <h3 :class="theme.text.h3">Lessen genereren</h3>
        <button @click="$emit('close')" class="p-1 rounded hover:bg-surface">
          <X :size="18" />
        </button>
      </div>

      <form @submit.prevent="handleGenerate" class="p-6 space-y-4">
        <p class="text-sm text-body">
          Genereer lessen op basis van de actieve lesslots. Vakanties en bestaande lessen worden overgeslagen.
        </p>

        <div v-if="error" :class="theme.alert.error">{{ error }}</div>

        <div :class="theme.form.group">
          <label :class="theme.form.label">Startdatum</label>
          <input v-model="startDate" type="date" :class="theme.form.input" required />
        </div>

        <div :class="theme.form.group">
          <label :class="theme.form.label">Einddatum</label>
          <input v-model="endDate" type="date" :class="theme.form.input" required />
        </div>

        <div class="flex justify-end gap-3 pt-2">
          <button type="button" @click="$emit('close')" class="px-4 py-2 text-sm text-body hover:text-navy-900">
            Annuleren
          </button>
          <button type="submit" :class="theme.btn.primarySm" :disabled="loading">
            <Zap :size="14" class="inline mr-1" />
            {{ loading ? 'Genereren...' : 'Genereren' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
