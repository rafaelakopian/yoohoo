import apiClient, { tenantUrl } from '@/api/client'
import type { ModulePermissions, PermissionGroup } from '@/types/auth'

export interface PermissionRegistryResponse {
  modules: ModulePermissions[]
}

export interface GroupCreateData {
  name: string
  slug: string
  description?: string
  permissions: string[]
}

export interface GroupUpdateData {
  name?: string
  description?: string
  permissions?: string[]
}

export interface GroupUser {
  user_id: string
  email: string
  full_name: string
  assigned_at: string
}

export interface EffectivePermissionsResponse {
  permissions: string[]
  groups: { id: string; name: string; slug: string }[]
}

export const permissionsApi = {
  // Platform-scoped: no tenant context needed
  async getRegistry(): Promise<PermissionRegistryResponse> {
    const response = await apiClient.get<PermissionRegistryResponse>('/platform/access/permissions/registry')
    return response.data
  },

  // Tenant-scoped: use slug-in-URL
  async listGroups(): Promise<PermissionGroup[]> {
    const response = await apiClient.get<PermissionGroup[]>(tenantUrl('/access/groups'))
    return response.data
  },

  async createGroup(data: GroupCreateData): Promise<PermissionGroup> {
    const response = await apiClient.post<PermissionGroup>(tenantUrl('/access/groups'), data)
    return response.data
  },

  async getGroup(groupId: string): Promise<PermissionGroup> {
    const response = await apiClient.get<PermissionGroup>(tenantUrl(`/access/groups/${groupId}`))
    return response.data
  },

  async updateGroup(groupId: string, data: GroupUpdateData): Promise<PermissionGroup> {
    const response = await apiClient.put<PermissionGroup>(tenantUrl(`/access/groups/${groupId}`), data)
    return response.data
  },

  async deleteGroup(groupId: string): Promise<void> {
    await apiClient.delete(tenantUrl(`/access/groups/${groupId}`))
  },

  async listGroupUsers(groupId: string): Promise<GroupUser[]> {
    const response = await apiClient.get<GroupUser[]>(tenantUrl(`/access/groups/${groupId}/users`))
    return response.data
  },

  async assignUser(groupId: string, userId: string): Promise<void> {
    await apiClient.post(tenantUrl(`/access/groups/${groupId}/users`), { user_id: userId })
  },

  async removeUser(groupId: string, userId: string): Promise<void> {
    await apiClient.delete(tenantUrl(`/access/groups/${groupId}/users/${userId}`))
  },

  async getMyPermissions(): Promise<EffectivePermissionsResponse> {
    const response = await apiClient.get<EffectivePermissionsResponse>(tenantUrl('/access/permissions'))
    return response.data
  },
}
