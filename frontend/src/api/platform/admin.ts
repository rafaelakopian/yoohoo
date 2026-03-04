import apiClient from '../client'

export interface PlatformStats {
  total_tenants: number
  active_tenants: number
  provisioned_tenants: number
  total_users: number
  active_users: number
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
  role: string
  is_active: boolean
}

export interface AdminTenantDetail extends AdminTenantItem {
  settings: Record<string, unknown> | null
  memberships: AdminMembershipInfo[]
}

export interface AdminUserItem {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_superadmin: boolean
  email_verified: boolean
  membership_count: number
  created_at: string
}

export interface AdminGroupSummary {
  id: string
  name: string
  slug: string
}

export interface AdminUserMembership {
  tenant_id: string
  tenant_name: string
  tenant_slug: string
  role: string | null
  is_active: boolean
  groups: AdminGroupSummary[]
}

export interface AdminUserDetail extends AdminUserItem {
  totp_enabled: boolean
  last_login_at: string | null
  memberships: AdminUserMembership[]
}

export interface PaginatedUserList {
  items: AdminUserItem[]
  total: number
  skip: number
  limit: number
}

export interface AdminUserUpdate {
  full_name?: string
  email?: string
  is_active?: boolean
  email_verified?: boolean
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

export const adminApi = {
  async getStats(): Promise<PlatformStats> {
    const response = await apiClient.get<PlatformStats>('/admin/stats')
    return response.data
  },

  async getTenants(): Promise<AdminTenantItem[]> {
    const response = await apiClient.get<AdminTenantItem[]>('/admin/orgs')
    return response.data
  },

  async getTenantDetail(id: string): Promise<AdminTenantDetail> {
    const response = await apiClient.get<AdminTenantDetail>(`/admin/orgs/${id}/detail`)
    return response.data
  },

  async getUsers(params?: {
    search?: string
    is_active?: boolean
    skip?: number
    limit?: number
  }): Promise<PaginatedUserList> {
    const response = await apiClient.get<PaginatedUserList>('/admin/users', { params })
    return response.data
  },

  async getUserDetail(id: string): Promise<AdminUserDetail> {
    const response = await apiClient.get<AdminUserDetail>(`/admin/users/${id}`)
    return response.data
  },

  async updateUser(id: string, data: AdminUserUpdate): Promise<AdminUserDetail> {
    const response = await apiClient.patch<AdminUserDetail>(`/admin/users/${id}`, data)
    return response.data
  },

  async toggleSuperAdmin(id: string, value: boolean): Promise<void> {
    await apiClient.put(`/admin/users/${id}/superadmin`, { is_superadmin: value })
  },

  async resetUser2FA(userId: string): Promise<AdminUserDetail> {
    const response = await apiClient.post<AdminUserDetail>(`/admin/users/${userId}/reset-2fa`)
    return response.data
  },

  async addMembership(tenantId: string, userId: string, role: string): Promise<void> {
    await apiClient.post(`/admin/orgs/${tenantId}/memberships`, {
      user_id: userId,
      role,
    })
  },

  async removeMembership(tenantId: string, userId: string): Promise<void> {
    await apiClient.delete(`/admin/orgs/${tenantId}/memberships/${userId}`)
  },

  async transferOwnership(tenantId: string, userId: string | null): Promise<{ owner_name: string | null }> {
    const response = await apiClient.put<{ owner_name: string | null }>(
      `/admin/orgs/${tenantId}/owner`,
      { user_id: userId },
    )
    return response.data
  },

  async getAuditLogs(params?: {
    user_id?: string
    action?: string
    date_from?: string
    date_to?: string
    skip?: number
    limit?: number
  }): Promise<PaginatedAuditLogs> {
    const response = await apiClient.get<PaginatedAuditLogs>('/admin/audit-logs', { params })
    return response.data
  },

  // --- Permission Groups per Tenant ---

  async getTenantGroups(tenantId: string): Promise<AdminPermissionGroup[]> {
    const response = await apiClient.get<AdminPermissionGroup[]>(`/admin/orgs/${tenantId}/groups`)
    return response.data
  },

  async createTenantGroup(tenantId: string, data: AdminGroupCreateData): Promise<AdminPermissionGroup> {
    const response = await apiClient.post<AdminPermissionGroup>(`/admin/orgs/${tenantId}/groups`, data)
    return response.data
  },

  async updateTenantGroup(tenantId: string, groupId: string, data: AdminGroupUpdateData): Promise<AdminPermissionGroup> {
    const response = await apiClient.put<AdminPermissionGroup>(`/admin/orgs/${tenantId}/groups/${groupId}`, data)
    return response.data
  },

  async deleteTenantGroup(tenantId: string, groupId: string): Promise<void> {
    await apiClient.delete(`/admin/orgs/${tenantId}/groups/${groupId}`)
  },

  async getTenantGroupUsers(tenantId: string, groupId: string): Promise<AdminGroupUser[]> {
    const response = await apiClient.get<AdminGroupUser[]>(`/admin/orgs/${tenantId}/groups/${groupId}/users`)
    return response.data
  },

  async assignUserToTenantGroup(tenantId: string, groupId: string, userId: string): Promise<void> {
    await apiClient.post(`/admin/orgs/${tenantId}/groups/${groupId}/users`, { user_id: userId })
  },

  async removeUserFromTenantGroup(tenantId: string, groupId: string, userId: string): Promise<void> {
    await apiClient.delete(`/admin/orgs/${tenantId}/groups/${groupId}/users/${userId}`)
  },

  async getPermissionRegistry(): Promise<{ modules: ModulePermissions[] }> {
    const response = await apiClient.get<{ modules: ModulePermissions[] }>('/permissions/registry')
    return response.data
  },

  // --- Platform Groups ---

  async getPlatformGroups(): Promise<AdminPermissionGroup[]> {
    const response = await apiClient.get<AdminPermissionGroup[]>('/admin/platform-groups')
    return response.data
  },

  async createPlatformGroup(data: AdminGroupCreateData): Promise<AdminPermissionGroup> {
    const response = await apiClient.post<AdminPermissionGroup>('/admin/platform-groups', data)
    return response.data
  },

  async updatePlatformGroup(groupId: string, data: AdminGroupUpdateData): Promise<AdminPermissionGroup> {
    const response = await apiClient.put<AdminPermissionGroup>(`/admin/platform-groups/${groupId}`, data)
    return response.data
  },

  async deletePlatformGroup(groupId: string): Promise<void> {
    await apiClient.delete(`/admin/platform-groups/${groupId}`)
  },

  async getPlatformGroupUsers(groupId: string): Promise<AdminGroupUser[]> {
    const response = await apiClient.get<AdminGroupUser[]>(`/admin/platform-groups/${groupId}/users`)
    return response.data
  },

  async assignUserToPlatformGroup(groupId: string, userId: string): Promise<void> {
    await apiClient.post(`/admin/platform-groups/${groupId}/users`, { user_id: userId })
  },

  async removeUserFromPlatformGroup(groupId: string, userId: string): Promise<void> {
    await apiClient.delete(`/admin/platform-groups/${groupId}/users/${userId}`)
  },
}
