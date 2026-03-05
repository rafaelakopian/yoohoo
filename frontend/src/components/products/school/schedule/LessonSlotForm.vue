<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { X } from 'lucide-vue-next'
import { theme } from '@/theme'
import { slotApi } from '@/api/products/school/schedule'
import apiClient from '@/api/client'

const props = defineProps<{
  slotId?: string
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const loading = ref(false)
const error = ref<string | null>(null)
const students = ref<{ id: string; first_name: string; last_name: string | null }[]>([])

const form = ref({
  student_id: '',
  day_of_week: 1,
  start_time: '14:00',
  duration_minutes: 30,
  location: '',
  is_active: true,
})

const dayOptions = [
  { value: 1, label: 'Maandag' },
  { value: 2, label: 'Dinsdag' },
  { value: 3, label: 'Woensdag' },
  { value: 4, label: 'Donderdag' },
  { value: 5, label: 'Vrijdag' },
  { value: 6, label: 'Zaterdag' },
  { value: 7, label: 'Zondag' },
]

onMounted(async () => {
  // Load students for dropdown
  try {
    const resp = await apiClient.get('/students/', { params: { per_page: 100, active: true } })
    students.value = resp.data.items
  } catch {
    // ignore
  }

  // Load existing slot for editing
  if (props.slotId) {
    try {
      const slot = await slotApi.get(props.slotId)
      form.value = {
        student_id: slot.student_id,
        day_of_week: slot.day_of_week,
        start_time: slot.start_time.substring(0, 5),
        duration_minutes: slot.duration_minutes,
        location: slot.location || '',
        is_active: slot.is_active,
      }
    } catch {
      error.value = 'Kon lesslot niet laden'
    }
  }
})

async function handleSubmit() {
  loading.value = true
  error.value = null

  try {
    const data = {
      ...form.value,
      start_time: form.value.start_time + ':00',
      location: form.value.location || undefined,
    }

    if (props.slotId) {
      const { student_id, ...updateData } = data
      await slotApi.update(props.slotId, updateData)
    } else {
      await slotApi.create(data)
    }
    emit('saved')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Opslaan mislukt'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-xl w-full max-w-md">
      <div class="flex items-center justify-between p-6 border-b border-navy-100">
        <h3 :class="theme.text.h3">{{ slotId ? 'Lesslot bewerken' : 'Nieuw lesslot' }}</h3>
        <button @click="$emit('close')" class="p-1 rounded hover:bg-surface">
          <X :size="18" />
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="p-6 space-y-4">
        <div v-if="error" :class="theme.alert.error">{{ error }}</div>

        <div v-if="!slotId" :class="theme.form.group">
          <label :class="theme.form.label">Leerling</label>
          <select v-model="form.student_id" :class="theme.form.input" required>
            <option value="" disabled>Selecteer leerling</option>
            <option v-for="s in students" :key="s.id" :value="s.id">
              {{ s.first_name }} {{ s.last_name || '' }}
            </option>
          </select>
        </div>

        <div :class="theme.form.group">
          <label :class="theme.form.label">Dag</label>
          <select v-model.number="form.day_of_week" :class="theme.form.input">
            <option v-for="d in dayOptions" :key="d.value" :value="d.value">{{ d.label }}</option>
          </select>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div :class="theme.form.group">
            <label :class="theme.form.label">Tijd</label>
            <input v-model="form.start_time" type="time" :class="theme.form.input" required />
          </div>
          <div :class="theme.form.group">
            <label :class="theme.form.label">Duur (min)</label>
            <input v-model.number="form.duration_minutes" type="number" min="15" max="120" step="15" :class="theme.form.input" />
          </div>
        </div>

        <div :class="theme.form.group">
          <label :class="theme.form.label">Locatie</label>
          <input v-model="form.location" :class="theme.form.input" placeholder="Optioneel" />
        </div>

        <div class="flex items-center gap-2">
          <input v-model="form.is_active" type="checkbox" id="is_active" class="rounded" />
          <label for="is_active" class="text-sm text-navy-700">Actief</label>
        </div>

        <div class="flex justify-end gap-3 pt-2">
          <button type="button" @click="$emit('close')" class="px-4 py-2 text-sm text-body hover:text-navy-900">
            Annuleren
          </button>
          <button type="submit" :class="theme.btn.primarySm" :disabled="loading">
            {{ loading ? 'Opslaan...' : 'Opslaan' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
