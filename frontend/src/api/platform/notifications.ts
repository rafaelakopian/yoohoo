import apiClient from '../client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface NotificationTypeInfo {
  code: string
  label: string
  description: string
  default_severity: string
}

export interface PlatformNotificationItem {
  id: string
  notification_type: string
  title: string
  severity: string
  is_published: boolean
  published_at: string | null
  target_scope: string
  recipient_count: number
  created_at: string
}

export interface PlatformNotificationDetail {
  id: string
  notification_type: string
  title: string
  message: string
  severity: string
  created_by_id: string
  is_published: boolean
  published_at: string | null
  target_scope: string
  target_tenant_ids: string[] | null
  extra_data: Record<string, unknown> | null
  recipient_count: number
  created_at: string
  updated_at: string
}

export interface PaginatedNotifications {
  items: PlatformNotificationItem[]
  total: number
  skip: number
  limit: number
}

export interface InboxItem {
  id: string
  notification_id: string
  notification_type: string
  title: string
  message: string
  severity: string
  is_read: boolean
  read_at: string | null
  created_at: string
}

export interface PaginatedInbox {
  items: InboxItem[]
  total: number
  unread_count: number
}

export interface NotificationPreference {
  id: string | null
  notification_type: string
  type_label: string
  type_description: string
  is_enabled: boolean
  email_enabled: boolean
  extra_recipient_group_ids: string[] | null
}

export interface CreateNotificationData {
  notification_type: string
  title: string
  message: string
  severity?: string
  target_scope?: string
  target_tenant_ids?: string[]
}

export interface UpdateNotificationData {
  title?: string
  message?: string
  severity?: string
  notification_type?: string
  target_scope?: string
  target_tenant_ids?: string[]
}

export interface UpdatePreferenceData {
  is_enabled?: boolean
  email_enabled?: boolean
  extra_recipient_group_ids?: string[]
}

// ---------------------------------------------------------------------------
// Admin API
// ---------------------------------------------------------------------------

export const platformNotifAdminApi = {
  async listTypes(): Promise<NotificationTypeInfo[]> {
    const { data } = await apiClient.get<NotificationTypeInfo[]>('/platform/notifications/types')
    return data
  },

  async create(payload: CreateNotificationData): Promise<PlatformNotificationDetail> {
    const { data } = await apiClient.post<PlatformNotificationDetail>('/platform/notifications', payload)
    return data
  },

  async list(skip = 0, limit = 20): Promise<PaginatedNotifications> {
    const { data } = await apiClient.get<PaginatedNotifications>('/platform/notifications', {
      params: { skip, limit },
    })
    return data
  },

  async get(id: string): Promise<PlatformNotificationDetail> {
    const { data } = await apiClient.get<PlatformNotificationDetail>(`/platform/notifications/${id}`)
    return data
  },

  async update(id: string, payload: UpdateNotificationData): Promise<PlatformNotificationDetail> {
    const { data } = await apiClient.put<PlatformNotificationDetail>(`/platform/notifications/${id}`, payload)
    return data
  },

  async publish(id: string): Promise<{ message: string }> {
    const { data } = await apiClient.put<{ message: string }>(`/platform/notifications/${id}/publish`)
    return data
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/platform/notifications/${id}`)
  },
}

// ---------------------------------------------------------------------------
// User Inbox API
// ---------------------------------------------------------------------------

export const platformNotifInboxApi = {
  async getInbox(skip = 0, limit = 20): Promise<PaginatedInbox> {
    const { data } = await apiClient.get<PaginatedInbox>('/platform/notifications/inbox', {
      params: { skip, limit },
    })
    return data
  },

  async getUnreadCount(): Promise<number> {
    const { data } = await apiClient.get<{ count: number }>('/platform/notifications/unread-count')
    return data.count
  },

  async markRead(recipientId: string): Promise<void> {
    await apiClient.put(`/platform/notifications/${recipientId}/read`)
  },

  async markAllRead(): Promise<void> {
    await apiClient.put('/platform/notifications/read-all')
  },
}

// ---------------------------------------------------------------------------
// Tenant Preferences API (org-scoped)
// ---------------------------------------------------------------------------

export const platformNotifPreferencesApi = {
  async list(slug: string): Promise<NotificationPreference[]> {
    const { data } = await apiClient.get<NotificationPreference[]>(
      `/org/${slug}/notification-preferences`,
    )
    return data
  },

  async update(slug: string, notificationType: string, payload: UpdatePreferenceData): Promise<NotificationPreference> {
    const { data } = await apiClient.put<NotificationPreference>(
      `/org/${slug}/notification-preferences/${notificationType}`,
      payload,
    )
    return data
  },
}
