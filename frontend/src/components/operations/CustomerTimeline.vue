<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { Search, Filter, ChevronDown } from 'lucide-vue-next'
import { theme } from '@/theme'
import {
  getTenantTimeline,
  type TimelineEvent,
  type TimelineParams,
  type Tenant360Member,
} from '@/api/platform/operations'

const props = defineProps<{
  tenantId: string
  members: Tenant360Member[]
}>()

const events = ref<TimelineEvent[]>([])
const totalCount = ref(0)
const hasMore = ref(false)
const loading = ref(true)
const loadingMore = ref(false)

// Filters
const filterCategory = ref('')
const filterUserId = ref('')
const filterSearch = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')
const filtersOpen = ref(false)
const offset = ref(0)
const limit = 50

let searchTimer: ReturnType<typeof setTimeout> | null = null

// Category colors for timeline nodes
const categoryColors: Record<string, string> = {
  login: 'bg-accent-600',
  security: 'bg-amber-500',
  data: 'bg-green-500',
  billing: 'bg-purple-500',
  system: 'bg-navy-400',
}

const activeFilterCount = computed(() => {
  let count = 0
  if (filterCategory.value) count++
  if (filterUserId.value) count++
  if (filterSearch.value) count++
  if (filterDateFrom.value) count++
  if (filterDateTo.value) count++
  return count
})

function buildParams(): TimelineParams {
  const params: TimelineParams = { limit, offset: offset.value }
  if (filterCategory.value) params.category = filterCategory.value
  if (filterUserId.value) params.user_id = filterUserId.value
  if (filterSearch.value && filterSearch.value.length >= 2) params.search = filterSearch.value
  if (filterDateFrom.value) params.date_from = filterDateFrom.value
  if (filterDateTo.value) params.date_to = filterDateTo.value
  return params
}

async function fetchTimeline(append = false) {
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
  }
  try {
    const result = await getTenantTimeline(props.tenantId, buildParams())
    if (append) {
      events.value.push(...result.events)
    } else {
      events.value = result.events
    }
    totalCount.value = result.total_count
    hasMore.value = result.has_more
  } catch {
    if (!append) events.value = []
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function resetAndFetch() {
  offset.value = 0
  fetchTimeline()
}

async function loadMore() {
  offset.value += limit
  await fetchTimeline(true)
}

// Watch filter changes (reset offset)
watch([filterCategory, filterUserId, filterDateFrom, filterDateTo], () => {
  resetAndFetch()
})

watch(filterSearch, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    resetAndFetch()
  }, 300)
})

onMounted(() => fetchTimeline())

function formatTime(d: string) {
  return new Date(d).toLocaleString('nl-NL', { hour: '2-digit', minute: '2-digit' })
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })
}

// Group events by date
const groupedEvents = computed(() => {
  const groups: { date: string; events: TimelineEvent[] }[] = []
  let currentDate = ''
  for (const ev of events.value) {
    const date = new Date(ev.created_at).toISOString().split('T')[0]
    if (date !== currentDate) {
      currentDate = date
      groups.push({ date: ev.created_at, events: [] })
    }
    groups[groups.length - 1].events.push(ev)
  }
  return groups
})
</script>

<template>
  <div :class="theme.card.base">
    <div class="p-4">
      <div class="flex items-center justify-between mb-3">
        <h3 :class="theme.text.h4">Activiteit</h3>
        <!-- Mobile filter toggle -->
        <button
          class="md:hidden"
          :class="theme.btn.ghost"
          @click="filtersOpen = !filtersOpen"
        >
          <Filter :size="16" class="mr-1" />
          Filters
          <span v-if="activeFilterCount > 0" :class="[theme.badge.base, theme.badge.info, 'ml-1']">
            {{ activeFilterCount }}
          </span>
        </button>
      </div>

      <!-- Filters -->
      <div
        :class="{ 'hidden md:flex': !filtersOpen, 'flex': filtersOpen }"
        class="flex-col md:flex-row gap-2 mb-4"
      >
        <select v-model="filterCategory" :class="[theme.form.input, 'text-sm']">
          <option value="">Alle categorieën</option>
          <option value="login">Inloggen</option>
          <option value="security">Beveiliging</option>
          <option value="data">Data</option>
          <option value="billing">Facturatie</option>
          <option value="system">Systeem</option>
        </select>
        <select v-model="filterUserId" :class="[theme.form.input, 'text-sm']">
          <option value="">Alle gebruikers</option>
          <option v-for="m in members" :key="m.user_id" :value="m.user_id">
            {{ m.full_name }}
          </option>
        </select>
        <div class="relative flex-1">
          <Search :size="14" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-body" />
          <input
            v-model="filterSearch"
            type="text"
            placeholder="Zoeken..."
            :class="[theme.form.input, 'pl-8 text-sm']"
          />
        </div>
        <div class="flex gap-2">
          <input
            v-model="filterDateFrom"
            type="date"
            :class="[theme.form.input, 'text-sm']"
            title="Vanaf"
          />
          <input
            v-model="filterDateTo"
            type="date"
            :class="[theme.form.input, 'text-sm']"
            title="Tot"
          />
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="px-4 pb-4">
      <div v-for="i in 4" :key="i" class="flex gap-3 mb-3">
        <div class="w-2.5 h-2.5 rounded-full bg-navy-200 animate-pulse mt-1" />
        <div class="flex-1 space-y-1">
          <div class="h-3 bg-navy-200 rounded animate-pulse w-3/4" />
          <div class="h-2 bg-navy-100 rounded animate-pulse w-1/2" />
        </div>
      </div>
    </div>

    <!-- Timeline -->
    <div v-else-if="events.length > 0" class="px-4 pb-4">
      <div v-for="(group, gi) in groupedEvents" :key="gi">
        <!-- Date header -->
        <div :class="[theme.timeline.dateHeader, 'mb-2 mt-4 first:mt-0']">
          {{ formatDate(group.date) }}
        </div>

        <!-- Events -->
        <div class="relative ml-1">
          <!-- Vertical line -->
          <div :class="[theme.timeline.line, 'absolute left-[4px] top-0 bottom-0']" />

          <div
            v-for="ev in group.events"
            :key="ev.id"
            class="relative pl-6 pb-3 last:pb-0"
          >
            <!-- Node -->
            <div
              :class="[
                theme.timeline.node,
                categoryColors[ev.category] || 'bg-navy-400',
                'absolute left-0 top-1',
              ]"
            />

            <!-- Content -->
            <div class="flex flex-col md:flex-row md:items-baseline md:justify-between gap-0.5">
              <div class="flex-1 min-w-0">
                <span :class="theme.text.muted" class="text-xs w-12 inline-block">
                  {{ formatTime(ev.created_at) }}
                </span>
                <span :class="theme.text.body" class="text-sm">
                  {{ ev.details_summary || ev.action }}
                </span>
              </div>
              <div class="flex items-center gap-2 text-xs" :class="theme.text.muted">
                <span v-if="ev.user_email" class="truncate max-w-[200px]">{{ ev.user_email }}</span>
                <span v-if="ev.ip_address">{{ ev.ip_address }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Load more -->
      <div v-if="hasMore" class="text-center pt-3 border-t border-navy-100 mt-3">
        <button
          :class="theme.btn.ghost"
          :disabled="loadingMore"
          @click="loadMore"
        >
          {{ loadingMore ? 'Laden...' : `Meer laden — ${events.length} van ${totalCount}` }}
        </button>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else :class="[theme.list.empty, 'p-4']">
      Geen activiteit gevonden
    </div>
  </div>
</template>
