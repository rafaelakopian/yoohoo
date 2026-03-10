import apiClient from '../client'
import type { GroupSummary } from '@/types/auth'

export interface PlatformStats {
  total_tenants: number
  active_tenants: number
  provisioned_tenants: number
  active_subscriptions: number
  mrr_cents: number
  total_users: number
  active_users: number
  platform_user_count: number
  platform_group_count: number
}

export interface AdminTenantItem {
  id: string
  name: string
  slug: string
  is_active: boolean
  is_provisioned: boolean
  owner_name: string | null
  member_count: number
  created_at: string
}

export interface AdminMembershipInfo {
  user_id: string
  email: string
  full_name: string
  is_active: boolean
}

export interface AdminTenantDetail extends AdminTenantItem {
  settings: Record<string, unknown> | null
  memberships: AdminMembershipInfo[]
}

export interface AuditLogItem {
  id: string
  user_id: string | null
  user_email: string | null
  action: string
  ip_address: string | null
  details: Record<string, unknown> | null
  created_at: string
}

export interface PaginatedAuditLogs {
  items: AuditLogItem[]
  total: number
  skip: number
  limit: number
}

export interface AdminPermissionGroup {
  id: string
  tenant_id: string | null
  name: string
  slug: string
  description: string | null
  is_default: boolean
  permissions: string[]
  user_count: number
  created_at: string
}

export interface AdminGroupCreateData {
  name: string
  slug: string
  description?: string
  permissions: string[]
}

export interface AdminGroupUpdateData {
  name?: string
  description?: string
  permissions?: string[]
}

export interface AdminGroupUser {
  user_id: string
  email: string
  full_name: string
  assigned_at: string
}

export interface ModulePermissionDef {
  codename: string
  label: string
  description: string
}

export interface ModulePermissions {
  module_name: string
  label: string
  permissions: ModulePermissionDef[]
}

export interface PlatformStaffItem {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_superadmin: boolean
  platform_groups: GroupSummary[]
  created_at: string
  last_login_at: string | null
}

export interface UserSearchResult {
  id: string
  email: string
  full_name: string
}

export const adminApi = {
  async getStats(): Promise<PlatformStats> {
    const response = await apiClient.get<PlatformStats>('/platform/dashboard')
    return response.data
  },

  async getTenantDetail(id: string): Promise<AdminTenantDetail> {
    const response = await apiClient.get<AdminTenantDetail>(`/platform/orgs/${id}/detail`)
    return response.data
  },

  async toggleSuperAdmin(id: string, value: boolean): Promise<void> {
    await apiClient.put(`/platform/access/users/${id}/superadmin`, { is_superadmin: value })
  },

  async addMembership(tenantId: string, userId: string, groupId?: string): Promise<void> {
    await apiClient.post(`/platform/orgs/${tenantId}/memberships`, {
      user_id: userId,
      group_id: groupId,
    })
  },

  async removeMembership(tenantId: string, userId: string): Promise<void> {
    await apiClient.delete(`/platform/orgs/${tenantId}/memberships/${userId}`)
  },

  async transferOwnership(tenantId: string, userId: string | null): Promise<{ owner_name: string | null }> {
    const response = await apiClient.put<{ owner_name: string | null }>(
      `/platform/orgs/${tenantId}/owner`,
      { user_id: userId },
    )
    return response.data
  },

  async getAuditLogs(params?: {
    user_id?: string
    action?: string
    category?: string
    date_from?: string
    date_to?: string
    skip?: number
    limit?: number
  }): Promise<PaginatedAuditLogs> {
    const response = await apiClient.get<PaginatedAuditLogs>('/platform/audit-logs', { params })
    return response.data
  },

  // --- Permission Groups per Tenant ---

  async getTenantGroups(tenantId: string): Promise<AdminPermissionGroup[]> {
    const response = await apiClient.get<AdminPermissionGroup[]>(`/platform/orgs/${tenantId}/groups`)
    return response.data
  },

  async createTenantGroup(tenantId: string, data: AdminGroupCreateData): Promise<AdminPermissionGroup> {
    const response = await apiClient.post<AdminPermissionGroup>(`/platform/orgs/${tenantId}/groups`, data)
    return response.data
  },

  async updateTenantGroup(tenantId: string, groupId: string, data: AdminGroupUpdateData): Promise<AdminPermissionGroup> {
    const response = await apiClient.put<AdminPermissionGroup>(`/platform/orgs/${tenantId}/groups/${groupId}`, data)
    return response.data
  },

  async deleteTenantGroup(tenantId: string, groupId: string): Promise<void> {
    await apiClient.delete(`/platform/orgs/${tenantId}/groups/${groupId}`)
  },

  async getTenantGroupUsers(tenantId: string, groupId: string): Promise<AdminGroupUser[]> {
    const response = await apiClient.get<AdminGroupUser[]>(`/platform/orgs/${tenantId}/groups/${groupId}/users`)
    return response.data
  },

  async assignUserToTenantGroup(tenantId: string, groupId: string, userId: string): Promise<void> {
    await apiClient.post(`/platform/orgs/${tenantId}/groups/${groupId}/users`, { user_id: userId })
  },

  async removeUserFromTenantGroup(tenantId: string, groupId: string, userId: string): Promise<void> {
    await apiClient.delete(`/platform/orgs/${tenantId}/groups/${groupId}/users/${userId}`)
  },

  async getPermissionRegistry(): Promise<{ modules: ModulePermissions[] }> {
    const response = await apiClient.get<{ modules: ModulePermissions[] }>('/platform/access/permissions/registry')
    return response.data
  },

  // --- Platform Groups ---

  async getPlatformGroups(): Promise<AdminPermissionGroup[]> {
    const response = await apiClient.get<AdminPermissionGroup[]>('/platform/access/groups')
    return response.data
  },

  async createPlatformGroup(data: AdminGroupCreateData): Promise<AdminPermissionGroup> {
    const response = await apiClient.post<AdminPermissionGroup>('/platform/access/groups', data)
    return response.data
  },

  async updatePlatformGroup(groupId: string, data: AdminGroupUpdateData): Promise<AdminPermissionGroup> {
    const response = await apiClient.put<AdminPermissionGroup>(`/platform/access/groups/${groupId}`, data)
    return response.data
  },

  async deletePlatformGroup(groupId: string): Promise<void> {
    await apiClient.delete(`/platform/access/groups/${groupId}`)
  },

  async getPlatformGroupUsers(groupId: string): Promise<AdminGroupUser[]> {
    const response = await apiClient.get<AdminGroupUser[]>(`/platform/access/groups/${groupId}/users`)
    return response.data
  },

  async assignUserToPlatformGroup(groupId: string, userId: string): Promise<void> {
    await apiClient.post(`/platform/access/groups/${groupId}/users`, { user_id: userId })
  },

  async removeUserFromPlatformGroup(groupId: string, userId: string): Promise<void> {
    await apiClient.delete(`/platform/access/groups/${groupId}/users/${userId}`)
  },

  async getPlatformUsers(): Promise<PlatformStaffItem[]> {
    const { data } = await apiClient.get<PlatformStaffItem[]>('/platform/access/users')
    return data
  },

  async searchUsers(query: string): Promise<UserSearchResult[]> {
    const { data } = await apiClient.get<UserSearchResult[]>('/platform/access/users/search', {
      params: { q: query },
    })
    return data
  },

  async invitePlatformUser(email: string): Promise<{ message: string }> {
    const { data } = await apiClient.post<{ message: string }>('/platform/access/users/invite', { email })
    return data
  },
}
