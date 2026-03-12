<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Users,
  CalendarDays,
  ClipboardCheck,
  CalendarOff,
  Bell,
  TrendingUp,
  ArrowRight,
} from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { useBrandingStore } from '@/stores/branding'
import { orgPath } from '@/router/routes'
import { studentsApi } from '@/api/products/school/students'
import { calendarApi } from '@/api/products/school/schedule'
import { theme } from '@/theme'

const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()
const branding = useBrandingStore()

const studentCount = ref<number | null>(null)
const todayLessons = ref<number | null>(null)
const loading = ref(true)

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 12) return 'Goedemorgen'
  if (hour < 18) return 'Goedemiddag'
  return 'Goedenavond'
})

const firstName = computed(() => {
  const full = authStore.user?.full_name ?? ''
  return full.split(' ')[0] || full
})

const quickLinks = computed(() => [
  { label: 'Leerlingen', desc: 'Beheer & overzicht', to: orgPath('students'), icon: Users, bg: 'bg-primary-50', iconColor: 'text-primary-600' },
  { label: 'Rooster', desc: 'Planning & lessen', to: orgPath('schedule'), icon: CalendarDays, bg: 'bg-accent-50', iconColor: 'text-accent-600' },
  { label: 'Aanwezigheid', desc: 'Registratie & historie', to: orgPath('attendance'), icon: ClipboardCheck, bg: 'bg-green-50', iconColor: 'text-green-600' },
  { label: 'Vakanties', desc: 'Vrije dagen plannen', to: orgPath('holidays'), icon: CalendarOff, bg: 'bg-yellow-50', iconColor: 'text-yellow-600' },
  { label: 'Notificaties', desc: 'Meldingen & instellingen', to: orgPath('notifications'), icon: Bell, bg: 'bg-red-50', iconColor: 'text-red-600' },
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
    <!-- Hero greeting -->
    <div class="dashboard-hero rounded-2xl p-6 md:p-8 mb-8 relative overflow-hidden fade-in-up">
      <div class="relative z-10 flex items-center gap-5">
        <div v-if="branding.currentLogo" class="hidden md:block">
          <div class="w-[56px] h-[56px] overflow-hidden bg-white/90 shadow-md flex-shrink-0" style="border-radius: 9999px !important">
            <img :src="branding.currentLogo" alt="Logo" class="w-full h-full object-cover" />
          </div>
        </div>
        <div>
          <h2 class="text-xl md:text-2xl font-bold text-white mb-1">{{ greeting }}, {{ firstName }}</h2>
          <p class="text-white/75 text-sm">{{ tenantStore.currentTenant?.name }} — Hier is je overzicht voor vandaag.</p>
        </div>
      </div>
    </div>

    <!-- Stat cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-8 fade-in-up">
      <!-- Leerlingen -->
      <router-link :to="orgPath('students')" class="dashboard-stat-card group">
        <div :class="[theme.card.padded, 'flex items-center gap-4 transition-all duration-200 group-hover:shadow-md']" style="transform: translateY(0); transition: transform 0.2s">
          <div class="w-12 h-12 rounded-xl bg-primary-50 flex items-center justify-center flex-shrink-0">
            <Users :size="22" class="text-primary-600" />
          </div>
          <div class="flex-1 min-w-0">
            <p :class="theme.text.body">Leerlingen</p>
            <div class="flex items-baseline gap-2">
              <p class="text-2xl font-bold text-navy-900 mt-0.5">
                <span v-if="loading" class="inline-block w-10 h-6 bg-navy-50 rounded animate-pulse" />
                <template v-else>{{ studentCount ?? '—' }}</template>
              </p>
              <span class="text-xs text-green-600 font-medium flex items-center gap-0.5">
                <TrendingUp :size="12" /> actief
              </span>
            </div>
          </div>
          <ArrowRight :size="16" class="text-navy-200 group-hover:text-navy-400 transition-colors flex-shrink-0" />
        </div>
      </router-link>

      <!-- Lessen vandaag -->
      <router-link :to="orgPath('schedule')" class="dashboard-stat-card group">
        <div :class="[theme.card.padded, 'flex items-center gap-4 transition-all duration-200 group-hover:shadow-md']">
          <div class="w-12 h-12 rounded-xl bg-accent-50 flex items-center justify-center flex-shrink-0">
            <CalendarDays :size="22" class="text-accent-600" />
          </div>
          <div class="flex-1 min-w-0">
            <p :class="theme.text.body">Lessen vandaag</p>
            <p class="text-2xl font-bold text-navy-900 mt-0.5">
              <span v-if="loading" class="inline-block w-8 h-6 bg-navy-50 rounded animate-pulse" />
              <template v-else>{{ todayLessons ?? '—' }}</template>
            </p>
          </div>
          <ArrowRight :size="16" class="text-navy-200 group-hover:text-navy-400 transition-colors flex-shrink-0" />
        </div>
      </router-link>

      <!-- Aanwezigheid -->
      <router-link :to="orgPath('attendance')" class="dashboard-stat-card group">
        <div :class="[theme.card.padded, 'flex items-center gap-4 transition-all duration-200 group-hover:shadow-md']">
          <div class="w-12 h-12 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
            <ClipboardCheck :size="22" class="text-green-600" />
          </div>
          <div class="flex-1 min-w-0">
            <p :class="theme.text.body">Aanwezigheid</p>
            <p class="text-sm font-medium text-navy-900 mt-1">Registratie bijhouden</p>
          </div>
          <ArrowRight :size="16" class="text-navy-200 group-hover:text-navy-400 transition-colors flex-shrink-0" />
        </div>
      </router-link>
    </div>

    <!-- Quick navigation -->
    <h3 :class="[theme.text.h3, 'mb-4']">Snelkoppelingen</h3>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 fade-in-up">
      <router-link
        v-for="link in quickLinks"
        :key="link.to"
        :to="link.to"
        class="group"
      >
        <div
          :class="[theme.card.padded, 'flex items-center gap-4 transition-all duration-200 group-hover:shadow-md']"
        >
          <div :class="['w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0', link.bg]">
            <component :is="link.icon" :size="20" :class="link.iconColor" />
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold text-navy-900">{{ link.label }}</p>
            <p :class="[theme.text.muted, 'text-xs']">{{ link.desc }}</p>
          </div>
          <ArrowRight :size="16" class="text-navy-200 group-hover:text-navy-400 transition-colors flex-shrink-0" />
        </div>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.dashboard-hero {
  background: linear-gradient(135deg, var(--color-primary-600) 0%, var(--color-accent-700) 100%);
}

.dashboard-stat-card:hover > div {
  transform: translateY(-2px);
}
</style>
