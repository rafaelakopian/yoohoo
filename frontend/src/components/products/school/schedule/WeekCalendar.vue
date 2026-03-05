<script setup lang="ts">
import { computed } from 'vue'
import type { CalendarDayEntry, Holiday } from '@/types/models'
import LessonCard from './LessonCard.vue'

const props = defineProps<{
  weekStart: string
  weekEnd: string
  lessons: CalendarDayEntry[]
  holidays: Holiday[]
}>()

defineEmits<{
  lessonClick: [lesson: CalendarDayEntry]
}>()

const dayNames = ['Maandag', 'Dinsdag', 'Woensdag', 'Donderdag', 'Vrijdag', 'Zaterdag', 'Zondag']

const days = computed(() => {
  const result = []
  const start = new Date(props.weekStart + 'T00:00:00')

  for (let i = 0; i < 7; i++) {
    const d = new Date(start)
    d.setDate(d.getDate() + i)
    const dateStr = d.toISOString().split('T')[0]

    const dayLessons = props.lessons
      .filter((l) => l.lesson_date === dateStr)
      .sort((a, b) => a.start_time.localeCompare(b.start_time))

    const dayHolidays = props.holidays.filter(
      (h) => h.start_date <= dateStr && h.end_date >= dateStr
    )

    result.push({
      name: dayNames[i],
      date: dateStr,
      dayNum: d.getDate(),
      lessons: dayLessons,
      holidays: dayHolidays,
      isToday: dateStr === new Date().toISOString().split('T')[0],
    })
  }
  return result
})
</script>

<template>
  <div class="overflow-x-auto">
  <div class="grid grid-cols-7 gap-px bg-navy-100 rounded-xl overflow-hidden border border-navy-100 min-w-[700px]">
    <!-- Headers -->
    <div
      v-for="day in days"
      :key="day.date"
      :class="[
        'px-3 py-2 text-center bg-white',
        day.isToday ? 'bg-accent-50' : '',
      ]"
    >
      <p class="text-xs font-medium text-muted">{{ day.name }}</p>
      <p
        :class="[
          'text-lg font-semibold',
          day.isToday ? 'text-accent-700' : 'text-navy-900',
        ]"
      >
        {{ day.dayNum }}
      </p>
    </div>

    <!-- Content cells -->
    <div
      v-for="day in days"
      :key="'c-' + day.date"
      :class="[
        'min-h-[120px] p-2 bg-white space-y-2',
        day.isToday ? 'bg-accent-50/30' : '',
      ]"
    >
      <!-- Holiday badge -->
      <div
        v-for="h in day.holidays"
        :key="h.id"
        class="px-2 py-1 rounded bg-yellow-50 text-yellow-700 text-xs font-medium"
      >
        {{ h.name }}
      </div>

      <!-- Lessons -->
      <LessonCard
        v-for="lesson in day.lessons"
        :key="lesson.id"
        :lesson="lesson"
        @click="$emit('lessonClick', lesson)"
      />

      <!-- Empty state -->
      <p
        v-if="day.lessons.length === 0 && day.holidays.length === 0"
        class="text-xs text-muted text-center pt-4"
      >
        —
      </p>
    </div>
  </div>
  </div>
</template>
