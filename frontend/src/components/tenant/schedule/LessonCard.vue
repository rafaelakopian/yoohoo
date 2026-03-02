<script setup lang="ts">
import { Clock, User, CheckCircle, XCircle, ArrowRight, Calendar } from 'lucide-vue-next'
import type { CalendarDayEntry, LessonStatus } from '@/types/models'

defineProps<{
  lesson: CalendarDayEntry
}>()

defineEmits<{
  click: [lesson: CalendarDayEntry]
}>()

const statusConfig: Record<LessonStatus, { label: string; class: string }> = {
  scheduled: { label: 'Gepland', class: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200' },
  completed: { label: 'Voltooid', class: 'bg-green-50 text-green-700 ring-1 ring-green-200' },
  cancelled: { label: 'Geannuleerd', class: 'bg-red-50 text-red-700 ring-1 ring-red-200' },
  rescheduled: { label: 'Verplaatst', class: 'bg-yellow-50 text-yellow-700 ring-1 ring-yellow-200' },
}

function formatTime(time: string): string {
  return time.substring(0, 5)
}
</script>

<template>
  <div
    class="p-3 rounded-lg border border-navy-100 bg-white hover:shadow-sm transition-shadow cursor-pointer"
    @click="$emit('click', lesson)"
  >
    <div class="flex items-center justify-between mb-1.5">
      <div class="flex items-center gap-1.5 text-sm font-medium text-navy-900">
        <User :size="14" />
        {{ lesson.student_name }}
      </div>
      <span
        :class="['px-2 py-0.5 rounded-full text-xs font-medium', statusConfig[lesson.status].class]"
      >
        {{ statusConfig[lesson.status].label }}
      </span>
    </div>
    <div class="flex items-center gap-3 text-xs text-body">
      <span class="flex items-center gap-1">
        <Clock :size="12" />
        {{ formatTime(lesson.start_time) }}
      </span>
      <span>{{ lesson.duration_minutes }} min</span>
    </div>
  </div>
</template>
