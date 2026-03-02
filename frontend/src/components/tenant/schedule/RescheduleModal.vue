<script setup lang="ts">
import { ref } from 'vue'
import { X, ArrowRight } from 'lucide-vue-next'
import { theme } from '@/theme'
import { lessonApi } from '@/api/tenant/schedule'
import type { CalendarDayEntry } from '@/types/models'

const props = defineProps<{
  lesson: CalendarDayEntry
}>()

const emit = defineEmits<{
  close: []
  rescheduled: []
}>()

const loading = ref(false)
const error = ref<string | null>(null)
const newDate = ref('')
const newTime = ref('')
const reason = ref('')

async function handleReschedule() {
  if (!newDate.value || !newTime.value) return

  loading.value = true
  error.value = null

  try {
    await lessonApi.reschedule(props.lesson.id, {
      new_date: newDate.value,
      new_time: newTime.value + ':00',
      reason: reason.value || undefined,
    })
    emit('rescheduled')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Verplaatsen mislukt'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-xl w-full max-w-sm">
      <div class="flex items-center justify-between p-6 border-b border-navy-100">
        <h3 :class="theme.text.h3">Les verplaatsen</h3>
        <button @click="$emit('close')" class="p-1 rounded hover:bg-surface">
          <X :size="18" />
        </button>
      </div>

      <form @submit.prevent="handleReschedule" class="p-6 space-y-4">
        <p class="text-sm text-body">
          Verplaats de les van <strong>{{ lesson.student_name }}</strong>
          op {{ lesson.lesson_date }} om {{ lesson.start_time.substring(0, 5) }}.
        </p>

        <div v-if="error" :class="theme.alert.error">{{ error }}</div>

        <div :class="theme.form.group">
          <label :class="theme.form.label">Nieuwe datum</label>
          <input v-model="newDate" type="date" :class="theme.form.input" required />
        </div>

        <div :class="theme.form.group">
          <label :class="theme.form.label">Nieuwe tijd</label>
          <input v-model="newTime" type="time" :class="theme.form.input" required />
        </div>

        <div :class="theme.form.group">
          <label :class="theme.form.label">Reden (optioneel)</label>
          <input v-model="reason" :class="theme.form.input" placeholder="Bijv. docent afwezig" />
        </div>

        <div class="flex justify-end gap-3 pt-2">
          <button type="button" @click="$emit('close')" class="px-4 py-2 text-sm text-body hover:text-navy-900">
            Annuleren
          </button>
          <button type="submit" :class="theme.btn.primarySm" :disabled="loading">
            <ArrowRight :size="14" class="inline mr-1" />
            {{ loading ? 'Verplaatsen...' : 'Verplaatsen' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
