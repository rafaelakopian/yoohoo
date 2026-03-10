<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  Bell, BellRing, Check, CheckCheck, Inbox,
  ChevronLeft, ChevronRight, ChevronDown,
  AlertTriangle, AlertCircle, Info, Mail, MailOpen,
} from 'lucide-vue-next'
import { usePlatformNotificationStore } from '@/stores/platformNotification'
import { theme } from '@/theme'

const store = usePlatformNotificationStore()
const page = ref(1)
const perPage = 20

onMounted(() => {
  loadPage()
})

function loadPage() {
  store.fetchInbox((page.value - 1) * perPage, perPage)
}

function nextPage() {
  if (page.value * perPage < store.total) {
    page.value++
    loadPage()
  }
}

function prevPage() {
  if (page.value > 1) {
    page.value--
    loadPage()
  }
}

const totalPages = computed(() => Math.ceil(store.total / perPage) || 1)

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'zojuist'
  if (mins < 60) return `${mins}m geleden`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}u geleden`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d geleden`
  return new Date(dateStr).toLocaleDateString('nl-NL', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('nl-NL', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function severityLabel(severity: string): string {
  switch (severity) {
    case 'critical': return 'Kritiek'
    case 'warning': return 'Waarschuwing'
    default: return 'Informatie'
  }
}

function severityBadge(severity: string): string {
  switch (severity) {
    case 'critical': return theme.badge.error
    case 'warning': return theme.badge.warning
    default: return theme.badge.default
  }
}

function severityDot(severity: string): string {
  switch (severity) {
    case 'critical': return 'bg-red-500'
    case 'warning': return 'bg-yellow-500'
    default: return 'bg-navy-400'
  }
}

function severityIcon(severity: string) {
  switch (severity) {
    case 'critical': return AlertCircle
    case 'warning': return AlertTriangle
    default: return Info
  }
}

function severityIconColor(severity: string): string {
  switch (severity) {
    case 'critical': return 'text-red-500'
    case 'warning': return 'text-yellow-500'
    default: return 'text-accent-600'
  }
}

const selectedNotif = ref<string | null>(null)

function toggleExpand(id: string) {
  if (selectedNotif.value === id) {
    selectedNotif.value = null
  } else {
    selectedNotif.value = id
    const item = store.inboxItems.find(i => i.id === id)
    if (item && !item.is_read) {
      store.markRead(id)
    }
  }
}

const visiblePages = computed(() => {
  const total = totalPages.value
  const current = page.value
  const pages: number[] = []
  const start = Math.max(1, current - 2)
  const end = Math.min(total, current + 2)
  for (let i = start; i <= end; i++) pages.push(i)
  return pages
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-accent-50 flex items-center justify-center">
          <BellRing :size="22" class="text-accent-700" />
        </div>
        <div>
          <h2 :class="theme.text.h2">Meldingen</h2>
          <p :class="theme.text.muted" class="text-sm mt-0.5">
            <template v-if="store.unreadCount > 0">
              {{ store.unreadCount }} ongelezen melding{{ store.unreadCount === 1 ? '' : 'en' }}
            </template>
            <template v-else>
              Alle meldingen gelezen
            </template>
          </p>
        </div>
      </div>
      <button
        v-if="store.unreadCount > 0"
        @click="store.markAllRead()"
        :class="theme.btn.ghost"
        class="flex items-center gap-1.5"
      >
        <CheckCheck :size="15" />
        Alles gelezen
      </button>
    </div>

    <!-- ──── Loading Skeleton ──── -->
    <template v-if="store.loading">
      <div class="space-y-3">
        <div v-for="i in 5" :key="i" :class="theme.card.base" class="overflow-hidden skeleton-card" :style="{ animationDelay: i * 80 + 'ms' }">
          <div class="flex items-start gap-3 p-4">
            <div class="w-9 h-9 rounded-xl bg-navy-50 animate-pulse shrink-0" />
            <div class="flex-1 space-y-2 pt-0.5">
              <div class="flex items-center gap-2">
                <div class="h-5 w-20 bg-navy-100 rounded-full animate-pulse" />
              </div>
              <div class="h-4 bg-navy-100 rounded animate-pulse" :style="{ width: `${55 + i * 7}%` }" />
              <div class="h-3 w-24 bg-navy-50 rounded animate-pulse" />
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ──── Empty State ──── -->
    <div v-else-if="store.inboxItems.length === 0" :class="theme.card.base">
      <div :class="theme.emptyState.wrapper">
        <div :class="theme.emptyState.iconWrap">
          <Inbox :size="24" :class="theme.emptyState.icon" />
        </div>
        <p :class="theme.emptyState.title">Geen meldingen</p>
        <p :class="theme.emptyState.description">
          Er zijn nog geen platformmeldingen voor jouw account.
        </p>
      </div>
    </div>

    <!-- ──── Notification List ──── -->
    <template v-else>
      <div class="space-y-2">
        <div
          v-for="notif in store.inboxItems"
          :key="notif.id"
          :class="[
            theme.card.base,
            'overflow-hidden cursor-pointer transition-all duration-200',
            !notif.is_read ? 'ring-2 ring-accent-200 shadow-sm' : 'hover:shadow-sm',
          ]"
          @click="toggleExpand(notif.id)"
        >
          <!-- Main row -->
          <div class="flex items-start gap-3 p-4">
            <!-- Severity icon -->
            <div
              class="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5"
              :class="notif.severity === 'critical' ? 'bg-red-50' : notif.severity === 'warning' ? 'bg-yellow-50' : 'bg-accent-50'"
            >
              <component :is="severityIcon(notif.severity)" :size="18" :class="severityIconColor(notif.severity)" />
            </div>

            <!-- Content -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span :class="[theme.badge.base, severityBadge(notif.severity)]" class="inline-flex items-center gap-1.5">
                  <span class="w-1.5 h-1.5 rounded-full" :class="severityDot(notif.severity)" />
                  {{ severityLabel(notif.severity) }}
                </span>
                <span :class="[theme.badge.base, 'bg-navy-50 text-navy-500 ring-1 ring-navy-100']" class="text-[10px]">
                  {{ notif.notification_type.replace(/_/g, ' ') }}
                </span>
              </div>
              <p
                class="text-sm mt-1.5 leading-snug"
                :class="notif.is_read ? 'text-navy-600' : 'text-navy-900 font-semibold'"
              >
                {{ notif.title }}
              </p>
              <div class="flex items-center gap-3 mt-1.5">
                <span :class="theme.text.muted" class="text-xs">{{ timeAgo(notif.created_at) }}</span>
                <span v-if="notif.is_read" class="flex items-center gap-1 text-[10px] text-green-600">
                  <Check :size="10" />
                  Gelezen
                </span>
              </div>
            </div>

            <!-- Expand chevron -->
            <ChevronDown
              :size="16"
              class="shrink-0 text-navy-300 transition-transform duration-200 mt-1"
              :class="selectedNotif === notif.id ? 'rotate-0' : '-rotate-90'"
            />
          </div>

          <!-- Expanded message -->
          <Transition
            enter-active-class="transition-all duration-200 ease-out"
            enter-from-class="max-h-0 opacity-0"
            enter-to-class="max-h-96 opacity-100"
            leave-active-class="transition-all duration-150 ease-in"
            leave-from-class="max-h-96 opacity-100"
            leave-to-class="max-h-0 opacity-0"
          >
            <div v-if="selectedNotif === notif.id" class="overflow-hidden">
              <div class="mx-4 mb-4 p-4 bg-surface rounded-xl border border-navy-100">
                <div class="flex items-center gap-2 mb-2">
                  <component
                    :is="notif.is_read ? MailOpen : Mail"
                    :size="14"
                    :class="notif.is_read ? 'text-navy-400' : 'text-accent-700'"
                  />
                  <span :class="theme.text.muted" class="text-xs">{{ formatDate(notif.created_at) }}</span>
                </div>
                <div class="text-sm text-navy-700 leading-relaxed whitespace-pre-wrap">{{ notif.message }}</div>
              </div>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="flex items-center justify-between pt-2">
        <p :class="theme.text.muted" class="text-xs">
          {{ ((page - 1) * perPage + 1).toLocaleString('nl-NL') }}&ndash;{{ Math.min(page * perPage, store.total).toLocaleString('nl-NL') }}
          van {{ store.total.toLocaleString('nl-NL') }}
        </p>
        <div class="flex items-center gap-1">
          <button
            @click="prevPage"
            :disabled="page <= 1"
            class="p-1.5 rounded-lg hover:bg-navy-100 text-navy-400 hover:text-navy-700 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronLeft :size="16" />
          </button>
          <template v-for="p in visiblePages" :key="p">
            <button
              @click="page = p; loadPage()"
              class="w-8 h-8 rounded-lg text-xs font-medium transition-colors"
              :class="p === page
                ? 'bg-accent-700 text-white'
                : 'text-navy-600 hover:bg-navy-100'"
            >
              {{ p }}
            </button>
          </template>
          <button
            @click="nextPage"
            :disabled="page >= totalPages"
            class="p-1.5 rounded-lg hover:bg-navy-100 text-navy-400 hover:text-navy-700 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronRight :size="16" />
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
@keyframes skeletonFadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.skeleton-card {
  opacity: 0;
  animation: skeletonFadeIn 0.3s ease forwards;
}
</style>
