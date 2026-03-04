<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  UserRound,
  Building2,
  CalendarDays,
  ClipboardCheck,
  Users,
  CalendarOff,
  Bell,
} from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { orgPath } from '@/router/routes'
import { studentsApi } from '@/api/tenant/students'
import { calendarApi } from '@/api/tenant/schedule'
import { theme } from '@/theme'

const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()

const studentCount = ref<number | null>(null)
const todayLessons = ref<number | null>(null)
const loading = ref(true)

const quickLinks = computed(() => [
  { label: 'Leerlingen', to: orgPath('students'), icon: Users, color: 'bg-primary-50 text-primary-600' },
  { label: 'Rooster', to: orgPath('schedule'), icon: CalendarDays, color: 'bg-accent-50 text-accent-600' },
  { label: 'Aanwezigheid', to: orgPath('attendance'), icon: ClipboardCheck, color: 'bg-green-50 text-green-600' },
  { label: 'Vakanties', to: orgPath('holidays'), icon: CalendarOff, color: 'bg-yellow-50 text-yellow-600' },
  { label: 'Notificaties', to: orgPath('notifications'), icon: Bell, color: 'bg-red-50 text-red-600' },
])

onMounted(async () => {
  loading.value = true
  try {
    const [studentsRes, calendarRes] = await Promise.allSettled([
      studentsApi.list({ per_page: 1 }),
      calendarApi.getWeek(getMonday(new Date())),
    ])

    if (studentsRes.status === 'fulfilled') {
      studentCount.value = studentsRes.value.total
    }
    if (calendarRes.status === 'fulfilled') {
      const today = new Date().toISOString().split('T')[0]
      todayLessons.value = calendarRes.value.lessons.filter(
        (l) => l.lesson_date === today
      ).length
    }
  } finally {
    loading.value = false
  }
})

function getMonday(date: Date): string {
  const d = new Date(date)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  d.setDate(diff)
  return d.toISOString().split('T')[0]
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h2 :class="theme.text.h2">Dashboard</h2>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <div :class="theme.card.padded" class="flex items-center gap-4">
        <div class="w-10 h-10 rounded-lg bg-navy-50 flex items-center justify-center flex-shrink-0">
          <UserRound :size="20" class="text-navy-600" />
        </div>
        <div>
          <p :class="theme.text.body">Welkom</p>
          <p :class="[theme.text.h3, 'mt-1']">
            {{ authStore.user?.full_name }}
          </p>
        </div>
      </div>
      <div :class="theme.card.padded" class="flex items-center gap-4">
        <div class="w-10 h-10 rounded-lg bg-navy-50 flex items-center justify-center flex-shrink-0">
          <Building2 :size="20" class="text-navy-600" />
        </div>
        <div>
          <p :class="theme.text.body">Organisatie</p>
          <p :class="[theme.text.h3, 'mt-1']">
            {{ tenantStore.currentTenant?.name ?? '—' }}
          </p>
        </div>
      </div>
      <div :class="theme.card.padded" class="flex items-center gap-4">
        <div class="w-10 h-10 rounded-lg bg-primary-50 flex items-center justify-center flex-shrink-0">
          <Users :size="20" class="text-primary-600" />
        </div>
        <div>
          <p :class="theme.text.body">Leerlingen</p>
          <p :class="theme.text.h2" class="mt-1">
            {{ loading ? '...' : (studentCount ?? '—') }}
          </p>
        </div>
      </div>
    </div>

    <!-- Today info -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
      <div :class="theme.card.padded" class="flex items-center gap-4">
        <div class="w-10 h-10 rounded-lg bg-accent-50 flex items-center justify-center flex-shrink-0">
          <CalendarDays :size="20" class="text-accent-600" />
        </div>
        <div>
          <p :class="theme.text.body">Lessen vandaag</p>
          <p :class="theme.text.h2" class="mt-1">
            {{ loading ? '...' : (todayLessons ?? '—') }}
          </p>
        </div>
      </div>
    </div>

    <!-- Quick links -->
    <div :class="theme.card.base">
      <div :class="theme.list.sectionHeader">
        <h3 :class="theme.text.h3">Snelkoppelingen</h3>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-5 gap-4 p-6">
        <router-link
          v-for="link in quickLinks"
          :key="link.to"
          :to="link.to"
          class="flex flex-col items-center gap-2 p-4 rounded-xl hover:bg-surface transition-colors"
        >
          <div
            :class="['w-12 h-12 rounded-xl flex items-center justify-center', link.color]"
          >
            <component :is="link.icon" :size="24" />
          </div>
          <span class="text-sm font-medium text-navy-900">{{ link.label }}</span>
        </router-link>
      </div>
    </div>
  </div>
</template>
