import apiClient, { tenantUrl } from '../client'
import type {
  NotificationPreference,
  NotificationLog,
  InAppNotification,
  NotificationType,
  NotificationStatus,
} from '@/types/models'

interface ListResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

interface PreferenceListResponse {
  items: NotificationPreference[]
}

// --- Preferences ---

export const preferencesApi = {
  async list(): Promise<PreferenceListResponse> {
    const response = await apiClient.get<PreferenceListResponse>(tenantUrl('/notifications/preferences/'))
    return response.data
  },

  async update(
    type: NotificationType,
    data: Partial<NotificationPreference>,
  ): Promise<NotificationPreference> {
    const response = await apiClient.put<NotificationPreference>(
      tenantUrl(`/notifications/preferences/${type}`),
      data,
    )
    return response.data
  },

  async initialize(): Promise<PreferenceListResponse> {
    const response = await apiClient.post<PreferenceListResponse>(
      tenantUrl('/notifications/preferences/initialize'),
    )
    return response.data
  },
}

// --- Logs ---

export const logsApi = {
  async list(params?: {
    page?: number
    per_page?: number
    notification_type?: NotificationType
    status?: NotificationStatus
  }): Promise<ListResponse<NotificationLog>> {
    const response = await apiClient.get<ListResponse<NotificationLog>>(
      tenantUrl('/notifications/logs/'),
      { params },
    )
    return response.data
  },
}

// --- In-App ---

export const inAppApi = {
  async list(params?: {
    page?: number
    per_page?: number
    unread_only?: boolean
  }): Promise<ListResponse<InAppNotification>> {
    const response = await apiClient.get<ListResponse<InAppNotification>>(
      tenantUrl('/notifications/in-app/'),
      { params },
    )
    return response.data
  },

  async getUnreadCount(): Promise<number> {
    const response = await apiClient.get<{ count: number }>(
      tenantUrl('/notifications/in-app/unread-count'),
    )
    return response.data.count
  },

  async markRead(id: string): Promise<InAppNotification> {
    const response = await apiClient.put<InAppNotification>(
      tenantUrl(`/notifications/in-app/${id}/read`),
    )
    return response.data
  },

  async markAllRead(): Promise<{ marked_read: number }> {
    const response = await apiClient.put<{ marked_read: number }>(
      tenantUrl('/notifications/in-app/read-all'),
    )
    return response.data
  },
}
