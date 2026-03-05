<script setup lang="ts">
import type { NotificationPreference } from '@/types/models'

const props = defineProps<{
  preference: NotificationPreference
}>()

const emit = defineEmits<{
  update: [field: string, value: boolean]
}>()

const typeLabels: Record<string, { label: string; description: string }> = {
  lesson_reminder: {
    label: 'Lesherinnering',
    description: 'Herinnering een dag voor de les',
  },
  absence_alert: {
    label: 'Afwezigheidsmelding',
    description: 'Melding bij afwezigheid of ziekmelding',
  },
  schedule_change: {
    label: 'Roosterwijziging',
    description: 'Melding bij annulering of verplaatsing van les',
  },
  attendance_report: {
    label: 'Aanwezigheidsoverzicht',
    description: 'Periodiek overzicht van aanwezigheid',
  },
}

const info = typeLabels[props.preference.notification_type] || {
  label: props.preference.notification_type,
  description: '',
}
</script>

<template>
  <div class="py-4 flex items-start justify-between gap-4">
    <div class="flex-1">
      <div class="flex items-center gap-3">
        <p class="font-medium text-navy-900 text-sm">{{ info.label }}</p>
        <label class="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            :checked="preference.is_enabled"
            @change="emit('update', 'is_enabled', !preference.is_enabled)"
            class="sr-only peer"
          />
          <div class="w-9 h-5 bg-navy-200 peer-focus:ring-2 peer-focus:ring-accent-200 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-accent-700"></div>
        </label>
      </div>
      <p class="text-xs text-muted mt-0.5">{{ info.description }}</p>
    </div>

    <div v-if="preference.is_enabled" class="flex items-center gap-4 text-xs">
      <label class="flex items-center gap-1.5 cursor-pointer">
        <input
          type="checkbox"
          :checked="preference.send_to_guardian"
          @change="emit('update', 'send_to_guardian', !preference.send_to_guardian)"
          class="rounded text-accent-700 focus:ring-accent-200"
        />
        <span class="text-body">Ouder</span>
      </label>
      <label class="flex items-center gap-1.5 cursor-pointer">
        <input
          type="checkbox"
          :checked="preference.send_to_teacher"
          @change="emit('update', 'send_to_teacher', !preference.send_to_teacher)"
          class="rounded text-accent-700 focus:ring-accent-200"
        />
        <span class="text-body">Docent</span>
      </label>
      <label class="flex items-center gap-1.5 cursor-pointer">
        <input
          type="checkbox"
          :checked="preference.send_to_admin"
          @change="emit('update', 'send_to_admin', !preference.send_to_admin)"
          class="rounded text-accent-700 focus:ring-accent-200"
        />
        <span class="text-body">Admin</span>
      </label>
    </div>
  </div>
</template>
