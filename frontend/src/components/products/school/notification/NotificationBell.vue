<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Bell, Check } from 'lucide-vue-next'
import { useNotificationStore } from '@/stores/notification'
import { useTenantStore } from '@/stores/tenant'
import { orgPath } from '@/router/routes'

const store = useNotificationStore()
const tenantStore = useTenantStore()
const open = ref(false)

function toggle() {
  open.value = !open.value
  if (open.value) {
    store.fetchInApp()
  }
}

function close() {
  open.value = false
}

async function handleMarkAllRead() {
  await store.markAllRead()
}

async function handleMarkRead(id: string) {
  await store.markRead(id)
}

onMounted(() => {
  store.startPolling()
})

onUnmounted(() => {
  store.stopPolling()
})

defineExpose({ close })
</script>

<template>
  <div v-if="tenantStore.hasTenant" class="relative">
    <button
      @click="toggle"
      class="relative p-2 rounded-lg text-navy-300 hover:bg-navy-800 hover:text-white transition-colors"
      title="Meldingen"
    >
      <Bell :size="18" />
      <span
        v-if="store.unreadCount > 0"
        class="absolute top-1 right-1 min-w-[16px] h-4 px-1 bg-primary-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center"
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
        <div class="px-4 py-3 border-b border-navy-100 flex items-center justify-between">
          <p class="text-sm font-semibold text-navy-900">Meldingen</p>
          <button
            v-if="store.unreadCount > 0"
            @click="handleMarkAllRead"
            class="text-xs text-accent-700 hover:text-accent-800 font-medium flex items-center gap-1"
          >
            <Check :size="12" />
            Alles gelezen
          </button>
        </div>

        <div v-if="store.inAppNotifications.length === 0" class="px-4 py-8 text-center">
          <Bell :size="24" class="mx-auto text-navy-200 mb-2" />
          <p class="text-sm text-muted">Geen meldingen</p>
        </div>

        <div v-else class="max-h-80 overflow-y-auto divide-y divide-navy-50">
          <div
            v-for="notif in store.inAppNotifications"
            :key="notif.id"
            :class="['px-4 py-3 cursor-pointer hover:bg-surface transition-colors', !notif.is_read ? 'bg-accent-50/30' : '']"
            @click="handleMarkRead(notif.id)"
          >
            <div class="flex items-start justify-between gap-2">
              <p :class="['text-sm', notif.is_read ? 'text-body' : 'text-navy-900 font-medium']">
                {{ notif.title }}
              </p>
              <span v-if="!notif.is_read" class="mt-1.5 w-2 h-2 bg-accent-700 rounded-full flex-shrink-0"></span>
            </div>
            <p class="text-xs text-muted mt-0.5 line-clamp-2">{{ notif.message }}</p>
            <p class="text-[10px] text-muted mt-1">
              {{ new Date(notif.created_at).toLocaleString('nl-NL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) }}
            </p>
          </div>
        </div>

        <div class="px-4 py-2 border-t border-navy-100 text-center">
          <router-link
            :to="orgPath('notifications')"
            @click="close"
            class="text-xs text-accent-700 hover:text-accent-800 font-medium"
          >
            Alle instellingen bekijken
          </router-link>
        </div>
      </div>
    </Transition>

    <!-- Click outside to close -->
    <div
      v-if="open"
      class="fixed inset-0 z-40"
      @click="close"
    />
  </div>
</template>
