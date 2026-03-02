import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { NotificationPreference, InAppNotification, NotificationLog } from '@/types/models'
import { preferencesApi, inAppApi, logsApi } from '@/api/tenant/notifications'

export const useNotificationStore = defineStore('notification', () => {
  const preferences = ref<NotificationPreference[]>([])
  const inAppNotifications = ref<InAppNotification[]>([])
  const unreadCount = ref(0)
  const logs = ref<NotificationLog[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  let pollInterval: ReturnType<typeof setInterval> | null = null

  async function fetchPreferences() {
    try {
      const result = await preferencesApi.list()
      preferences.value = result.items
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Kon voorkeuren niet laden'
    }
  }

  async function initializePreferences() {
    try {
      const result = await preferencesApi.initialize()
      preferences.value = result.items
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Initialisatie mislukt'
    }
  }

  async function updatePreference(type: string, data: Partial<NotificationPreference>) {
    try {
      const updated = await preferencesApi.update(type as any, data)
      const idx = preferences.value.findIndex((p) => p.notification_type === type)
      if (idx >= 0) preferences.value[idx] = updated
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Bijwerken mislukt'
    }
  }

  async function fetchInApp(unreadOnly = false) {
    try {
      const result = await inAppApi.list({ unread_only: unreadOnly })
      inAppNotifications.value = result.items
    } catch {
      // silently fail
    }
  }

  async function fetchUnreadCount() {
    try {
      unreadCount.value = await inAppApi.getUnreadCount()
    } catch {
      // silently fail
    }
  }

  async function markRead(id: string) {
    try {
      await inAppApi.markRead(id)
      const notif = inAppNotifications.value.find((n) => n.id === id)
      if (notif) notif.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    } catch {
      // silently fail
    }
  }

  async function markAllRead() {
    try {
      await inAppApi.markAllRead()
      inAppNotifications.value.forEach((n) => (n.is_read = true))
      unreadCount.value = 0
    } catch {
      // silently fail
    }
  }

  async function fetchLogs(params?: Record<string, string | number>) {
    loading.value = true
    try {
      const result = await logsApi.list(params as any)
      logs.value = result.items
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Kon logs niet laden'
    } finally {
      loading.value = false
    }
  }

  function startPolling() {
    if (pollInterval) return
    fetchUnreadCount()
    pollInterval = setInterval(fetchUnreadCount, 60_000)
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  function resetState() {
    stopPolling()
    preferences.value = []
    inAppNotifications.value = []
    unreadCount.value = 0
    logs.value = []
    error.value = null
  }

  return {
    preferences,
    inAppNotifications,
    unreadCount,
    logs,
    loading,
    error,
    fetchPreferences,
    initializePreferences,
    updatePreference,
    fetchInApp,
    fetchUnreadCount,
    markRead,
    markAllRead,
    fetchLogs,
    startPolling,
    stopPolling,
    resetState,
  }
})
