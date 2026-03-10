<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Rocket, CheckCircle2, Circle, ChevronRight,
  Database, Settings, Users, GraduationCap, CalendarDays, ClipboardCheck, Receipt,
  ArrowUpDown, ArrowUp, ArrowDown,
} from 'lucide-vue-next'
import { theme } from '@/theme'
import { getOnboardingOverview, type OnboardingItem } from '@/api/platform/operations'

const router = useRouter()
const items = ref<OnboardingItem[]>([])
const loading = ref(true)
const error = ref('')
const sortColumn = ref<string>('')
const sortDirection = ref<'asc' | 'desc'>('asc')

onMounted(async () => {
  try {
    items.value = await getOnboardingOverview()
  } catch {
    error.value = 'Kon onboarding gegevens niet laden'
  } finally {
    loading.value = false
  }
})

function handleSort(col: string) {
  if (sortColumn.value === col) {
    if (sortDirection.value === 'desc') {
      sortDirection.value = 'asc'
    } else {
      sortColumn.value = ''
    }
  } else {
    sortColumn.value = col
    sortDirection.value = 'desc'
  }
}

const sortedItems = computed(() => {
  if (!sortColumn.value) return items.value

  const copy = [...items.value]
  const dir = sortDirection.value === 'asc' ? 1 : -1
  copy.sort((a, b) => {
    switch (sortColumn.value) {
      case 'name': return a.tenant_name.localeCompare(b.tenant_name) * dir
      case 'date': return (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()) * dir
      case 'completion': return (a.completion_pct - b.completion_pct) * dir
      default: return 0
    }
  })
  return copy
})

// ─── Summary stats ───
const totalCount = computed(() => items.value.length)
const completeCount = computed(() => items.value.filter(i => i.completion_pct === 100).length)
const inProgressCount = computed(() => items.value.filter(i => i.completion_pct > 0 && i.completion_pct < 100).length)
const notStartedCount = computed(() => items.value.filter(i => i.completion_pct === 0).length)
const avgCompletion = computed(() => {
  if (!items.value.length) return 0
  return Math.round(items.value.reduce((s, i) => s + i.completion_pct, 0) / items.value.length)
})

// ─── Step config ───
interface StepDef { key: string; label: string; icon: object }
const stepDefs: StepDef[] = [
  { key: 'is_provisioned', label: 'Database', icon: Database },
  { key: 'has_settings', label: 'Instellingen', icon: Settings },
  { key: 'has_members', label: 'Leden', icon: Users },
  { key: 'has_students', label: 'Leerlingen', icon: GraduationCap },
  { key: 'has_schedule', label: 'Rooster', icon: CalendarDays },
  { key: 'has_attendance', label: 'Aanwezigheid', icon: ClipboardCheck },
  { key: 'has_billing_plan', label: 'Facturatie', icon: Receipt },
]

const stepLabels: Record<string, string> = Object.fromEntries(stepDefs.map(s => [s.key, s.label]))

function progressColor(pct: number): string {
  if (pct === 100) return 'bg-green-500'
  if (pct >= 70) return 'bg-accent-700'
  if (pct >= 40) return 'bg-yellow-500'
  return 'bg-red-400'
}

function progressRing(pct: number): string {
  if (pct === 100) return 'ring-green-200'
  if (pct >= 70) return 'ring-accent-200'
  if (pct >= 40) return 'ring-yellow-200'
  return 'ring-red-200'
}

function goToTenant(item: OnboardingItem) {
  router.push({ name: 'platform-org-detail', params: { tenantId: item.tenant_id } })
}

function formatDate(d: string | null) {
  if (!d) return '\u2014'
  return new Date(d).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

function timeAgo(d: string | null) {
  if (!d) return ''
  const diff = Date.now() - new Date(d).getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'vandaag'
  if (days === 1) return 'gisteren'
  if (days < 30) return `${days} dagen geleden`
  const months = Math.floor(days / 30)
  return months === 1 ? '1 maand geleden' : `${months} maanden geleden`
}

// ─── Skeleton ───
const skeletonRows = Array.from({ length: 5 }, (_, i) => i)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Rocket class="w-6 h-6 text-navy-700" />
        <h2 :class="theme.text.h2">Onboarding</h2>
      </div>
      <span v-if="!loading && !error" :class="theme.text.muted" class="text-sm">
        {{ totalCount }} organisaties
      </span>
    </div>

    <!-- Error -->
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <!-- Loading skeleton -->
    <template v-if="loading">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" :class="theme.card.padded">
          <div class="h-4 w-20 bg-navy-100 rounded animate-pulse mb-2" />
          <div class="h-7 w-12 bg-navy-100 rounded animate-pulse" />
        </div>
      </div>
      <div class="overflow-x-auto rounded-xl border border-navy-100">
        <table class="min-w-full table-fixed">
          <thead class="bg-surface"><tr><th :colspan="10" class="h-[46px]" /></tr></thead>
          <tbody class="bg-white divide-y divide-navy-50">
            <tr v-for="n in skeletonRows" :key="n" class="skeleton-row-enter" :style="{ animationDelay: n * 50 + 'ms' }">
              <td v-for="c in 10" :key="c" class="px-4 py-4">
                <div class="h-4 bg-navy-100 rounded animate-pulse" :style="{ width: ['70%','50%','30%','40%','30%','30%','30%','30%','60%','40%'][c-1] }" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <template v-else-if="items.length > 0">
      <!-- Summary cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div :class="theme.card.padded" class="text-center">
          <p :class="theme.text.muted" class="text-xs mb-1">Gemiddeld</p>
          <div class="relative inline-flex items-center justify-center w-14 h-14">
            <svg class="w-14 h-14 -rotate-90" viewBox="0 0 56 56">
              <circle cx="28" cy="28" r="24" fill="none" stroke-width="4" class="stroke-navy-100" />
              <circle cx="28" cy="28" r="24" fill="none" stroke-width="4" stroke-linecap="round"
                :class="avgCompletion === 100 ? 'stroke-green-500' : avgCompletion >= 50 ? 'stroke-accent-700' : 'stroke-red-400'"
                :stroke-dasharray="`${avgCompletion * 1.508} 150.8`"
              />
            </svg>
            <span class="absolute text-sm font-bold text-navy-900">{{ avgCompletion }}%</span>
          </div>
        </div>
        <div :class="theme.card.padded" class="text-center">
          <p :class="theme.text.muted" class="text-xs mb-1">Voltooid</p>
          <p class="text-2xl font-bold text-green-600">{{ completeCount }}</p>
        </div>
        <div :class="theme.card.padded" class="text-center">
          <p :class="theme.text.muted" class="text-xs mb-1">Bezig</p>
          <p class="text-2xl font-bold text-accent-700">{{ inProgressCount }}</p>
        </div>
        <div :class="theme.card.padded" class="text-center">
          <p :class="theme.text.muted" class="text-xs mb-1">Niet gestart</p>
          <p class="text-2xl font-bold" :class="notStartedCount > 0 ? 'text-red-500' : 'text-navy-900'">{{ notStartedCount }}</p>
        </div>
      </div>

      <!-- Table -->
      <div class="overflow-x-auto rounded-xl border border-navy-100">
        <table class="min-w-full divide-y divide-navy-200 text-sm table-fixed">
          <colgroup>
            <col style="width: 22%" />
            <col v-for="s in stepDefs" :key="s.key" style="width: 8%" />
            <col style="width: 18%" />
            <col style="width: 4%" />
          </colgroup>

          <thead class="bg-surface text-navy-700 font-semibold">
            <tr>
              <th class="px-4 h-[46px] text-left cursor-pointer select-none" @click="handleSort('name')">
                <div class="flex items-center gap-1">
                  <span>Organisatie</span>
                  <button class="ml-auto shrink-0 p-0.5 rounded hover:bg-navy-100 transition-colors"
                    :class="sortColumn === 'name' ? 'text-accent-700' : 'text-navy-300'"
                    @click.stop="handleSort('name')"
                  >
                    <ArrowUp v-if="sortColumn === 'name' && sortDirection === 'asc'" class="w-3.5 h-3.5" />
                    <ArrowDown v-else-if="sortColumn === 'name' && sortDirection === 'desc'" class="w-3.5 h-3.5" />
                    <ArrowUpDown v-else class="w-3.5 h-3.5" />
                  </button>
                </div>
              </th>
              <th
                v-for="s in stepDefs" :key="s.key"
                class="px-2 h-[46px] text-center hidden md:table-cell"
                :title="s.label"
              >
                <div class="flex flex-col items-center gap-0.5">
                  <component :is="s.icon" class="w-3.5 h-3.5 text-navy-300" />
                  <span class="text-[10px] text-navy-400 font-medium leading-tight">{{ s.label }}</span>
                </div>
              </th>
              <th class="px-4 h-[46px] text-right cursor-pointer select-none" @click="handleSort('completion')">
                <div class="flex items-center gap-1 justify-end">
                  <span>Voortgang</span>
                  <button class="shrink-0 p-0.5 rounded hover:bg-navy-100 transition-colors"
                    :class="sortColumn === 'completion' ? 'text-accent-700' : 'text-navy-300'"
                    @click.stop="handleSort('completion')"
                  >
                    <ArrowUp v-if="sortColumn === 'completion' && sortDirection === 'asc'" class="w-3.5 h-3.5" />
                    <ArrowDown v-else-if="sortColumn === 'completion' && sortDirection === 'desc'" class="w-3.5 h-3.5" />
                    <ArrowUpDown v-else class="w-3.5 h-3.5" />
                  </button>
                </div>
              </th>
              <th class="px-2 h-[46px]" />
            </tr>
          </thead>

          <tbody class="bg-white divide-y divide-navy-50">
            <tr
              v-for="item in sortedItems"
              :key="item.tenant_id"
              class="hover:bg-surface transition-colors cursor-pointer group"
              @click="goToTenant(item)"
            >
              <!-- Org info -->
              <td class="px-4 py-3">
                <p class="font-medium text-navy-900 truncate">{{ item.tenant_name }}</p>
                <p :class="theme.text.muted" class="text-xs mt-0.5">
                  {{ formatDate(item.created_at) }}
                  <span v-if="item.last_step_at" class="ml-1">&middot; {{ timeAgo(item.last_step_at) }}</span>
                </p>
              </td>

              <!-- Step checks -->
              <td
                v-for="s in stepDefs" :key="s.key"
                class="px-2 py-3 text-center hidden md:table-cell"
              >
                <CheckCircle2
                  v-if="(item as any)[s.key]"
                  :size="18"
                  class="text-green-500 inline-block"
                />
                <Circle v-else :size="18" class="text-navy-200 inline-block" />
              </td>

              <!-- Progress -->
              <td class="px-4 py-3">
                <div class="flex items-center gap-2 justify-end">
                  <div class="w-full max-w-[100px] h-2 rounded-full overflow-hidden ring-1" :class="progressRing(item.completion_pct)" style="background: var(--color-surface, #f6f7fa)">
                    <div
                      class="h-full rounded-full transition-all duration-500"
                      :class="progressColor(item.completion_pct)"
                      :style="{ width: `${item.completion_pct}%` }"
                    />
                  </div>
                  <span class="text-xs font-semibold w-9 text-right" :class="item.completion_pct === 100 ? 'text-green-600' : 'text-navy-700'">
                    {{ item.completion_pct }}%
                  </span>
                </div>
                <!-- Missing steps on mobile -->
                <div v-if="item.missing_steps.length > 0" class="flex gap-1 flex-wrap justify-end mt-1.5 md:hidden">
                  <span
                    v-for="ms in item.missing_steps" :key="ms"
                    class="text-[10px] px-1.5 py-0.5 rounded-full bg-red-50 text-red-600 ring-1 ring-red-200"
                  >{{ stepLabels[ms] ?? ms }}</span>
                </div>
              </td>

              <!-- Arrow -->
              <td class="px-2 py-3 text-center">
                <ChevronRight :size="16" class="text-navy-200 group-hover:text-accent-700 transition-colors inline-block" />
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Empty state -->
        <div v-if="sortedItems.length === 0" class="py-12 text-center">
          <p :class="theme.text.muted">Geen organisaties gevonden</p>
        </div>

        <!-- Footer -->
        <div v-else class="py-3 text-center border-t border-navy-100" :class="theme.text.muted">
          {{ sortedItems.length }} organisaties
        </div>
      </div>
    </template>

    <!-- Empty state (no orgs at all) -->
    <div v-else :class="theme.emptyState.wrapper">
      <div :class="theme.emptyState.iconWrap">
        <Rocket :class="theme.emptyState.icon" :size="24" />
      </div>
      <p :class="theme.emptyState.title">Geen organisaties</p>
      <p :class="theme.emptyState.description">Er zijn nog geen organisaties aangemaakt om te onboarden.</p>
    </div>
  </div>
</template>

<style scoped>
@keyframes skeletonFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.skeleton-row-enter {
  opacity: 0;
  animation: skeletonFadeIn 0.3s ease forwards;
}
</style>
