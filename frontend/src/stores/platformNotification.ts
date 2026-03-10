import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { InboxItem } from '@/api/platform/notifications'
import { platformNotifInboxApi } from '@/api/platform/notifications'

export const usePlatformNotificationStore = defineStore('platformNotification', () => {
  const inboxItems = ref<InboxItem[]>([])
  const unreadCount = ref(0)
  const total = ref(0)
  const loading = ref(false)

  let pollInterval: ReturnType<typeof setInterval> | null = null

  let _pollFailCount = 0

  async function fetchUnreadCount() {
    try {
      unreadCount.value = await platformNotifInboxApi.getUnreadCount()
      _pollFailCount = 0
    } catch {
      _pollFailCount++
      // Stop polling after 3 consecutive failures (auth expired, rate limited, etc.)
      if (_pollFailCount >= 3) stopPolling()
    }
  }

  async function fetchInbox(skip = 0, limit = 20) {
    loading.value = true
    try {
      const result = await platformNotifInboxApi.getInbox(skip, limit)
      inboxItems.value = result.items
      total.value = result.total
      unreadCount.value = result.unread_count
    } catch {
      // silently fail
    } finally {
      loading.value = false
    }
  }

  async function markRead(recipientId: string) {
    try {
      await platformNotifInboxApi.markRead(recipientId)
      const item = inboxItems.value.find(i => i.id === recipientId)
      if (item && !item.is_read) {
        item.is_read = true
        item.read_at = new Date().toISOString()
        unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
    } catch {
      // silently fail
    }
  }

  async function markAllRead() {
    try {
      await platformNotifInboxApi.markAllRead()
      inboxItems.value.forEach(i => {
        i.is_read = true
        i.read_at = i.read_at || new Date().toISOString()
      })
      unreadCount.value = 0
    } catch {
      // silently fail
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
    inboxItems.value = []
    unreadCount.value = 0
    total.value = 0
    loading.value = false
    stopPolling()
  }

  return {
    inboxItems,
    unreadCount,
    total,
    loading,
    fetchUnreadCount,
    fetchInbox,
    markRead,
    markAllRead,
    startPolling,
    stopPolling,
    resetState,
  }
})
