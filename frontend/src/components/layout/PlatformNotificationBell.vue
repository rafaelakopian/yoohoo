<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { Bell, Check, CheckCheck, Inbox } from 'lucide-vue-next'
import { usePlatformNotificationStore } from '@/stores/platformNotification'
import { useAuthStore } from '@/stores/auth'
import { theme } from '@/theme'
import { PLATFORM } from '@/router/routes'

const store = usePlatformNotificationStore()
const authStore = useAuthStore()
const open = ref(false)

const showBell = computed(() => authStore.isAuthenticated)

function toggle() {
  open.value = !open.value
  if (open.value) {
    store.fetchInbox()
  }
}

function close() {
  open.value = false
}

function handleMarkRead(id: string) {
  store.markRead(id)
}

function handleMarkAllRead() {
  store.markAllRead()
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)

  if (diffMin < 1) return 'zojuist'
  if (diffMin < 60) return `${diffMin}m geleden`
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return `${diffHours}u geleden`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d geleden`
  return d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })
}

function severityDot(severity: string): string {
  switch (severity) {
    case 'critical': return 'bg-red-500'
    case 'warning': return 'bg-yellow-500'
    default: return 'bg-accent-500'
  }
}

onMounted(() => {
  if (showBell.value) store.startPolling()
})

onUnmounted(() => {
  store.stopPolling()
})

defineExpose({ close })
</script>

<template>
  <div v-if="showBell" class="relative">
    <button
      @click="toggle"
      class="relative p-2 rounded-lg text-navy-500 hover:bg-navy-50 hover:text-navy-700 transition-colors"
    >
      <Bell :size="18" />
      <span
        v-if="store.unreadCount > 0"
        class="absolute top-0.5 right-0.5 min-w-[16px] h-4 px-1 bg-primary-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center"
      >
        {{ store.unreadCount > 99 ? '99+' : store.unreadCount }}
      </span>
    </button>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 scale-95 -translate-y-1"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 -translate-y-1"
    >
      <div
        v-if="open"
        class="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-navy-100 z-50"
      >
        <!-- Header -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-navy-100">
          <span class="text-sm font-semibold text-navy-900">Platformmeldingen</span>
          <button
            v-if="store.unreadCount > 0"
            @click="handleMarkAllRead"
            class="flex items-center gap-1 text-xs text-accent-700 hover:text-accent-800 font-medium transition-colors"
          >
            <CheckCheck :size="12" />
            Alles gelezen
          </button>
        </div>

        <!-- Notification list -->
        <div class="max-h-80 overflow-y-auto divide-y divide-navy-50">
          <div
            v-for="notif in store.inboxItems"
            :key="notif.id"
            :class="[
              'px-4 py-3 cursor-pointer hover:bg-surface transition-colors',
              !notif.is_read ? 'bg-accent-50/30' : ''
            ]"
            @click="handleMarkRead(notif.id)"
          >
            <div class="flex items-start gap-2">
              <span
                :class="['w-2 h-2 rounded-full mt-1.5 shrink-0', severityDot(notif.severity)]"
              />
              <div class="flex-1 min-w-0">
                <p :class="['text-sm truncate', notif.is_read ? 'text-body' : 'text-navy-900 font-medium']">
                  {{ notif.title }}
                </p>
                <p class="text-xs text-muted mt-0.5 line-clamp-2">{{ notif.message }}</p>
                <p class="text-xs text-muted mt-1">{{ formatTime(notif.created_at) }}</p>
              </div>
              <Check v-if="notif.is_read" :size="12" class="text-green-500 mt-1 shrink-0" />
            </div>
          </div>

          <!-- Empty state -->
          <div v-if="store.inboxItems.length === 0" class="py-8 text-center">
            <Inbox :size="24" class="mx-auto text-navy-300 mb-2" />
            <p class="text-sm text-muted">Geen meldingen</p>
          </div>
        </div>

        <!-- Footer -->
        <div class="px-4 py-2 border-t border-navy-100 text-center">
          <router-link
            :to="`${PLATFORM}/notifications/inbox`"
            @click="close"
            :class="theme.btn.link"
          >
            Alle meldingen bekijken
          </router-link>
        </div>
      </div>
    </Transition>

    <!-- Click outside to close -->
    <div v-if="open" class="fixed inset-0 z-40" @click="close" />
  </div>
</template>
