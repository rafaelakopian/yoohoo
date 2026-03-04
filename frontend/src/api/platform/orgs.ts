import apiClient from '../client'
import type { Tenant, TenantSettings } from '@/types/models'

export const orgsApi = {
  async create(data: { name: string; slug: string }): Promise<Tenant> {
    const response = await apiClient.post<Tenant>('/orgs/', data)
    return response.data
  },

  async list(): Promise<Tenant[]> {
    const response = await apiClient.get<Tenant[]>('/orgs/')
    return response.data
  },

  async get(id: string): Promise<Tenant> {
    const response = await apiClient.get<Tenant>(`/orgs/${id}`)
    return response.data
  },

  async provision(id: string): Promise<Tenant> {
    const response = await apiClient.post<Tenant>(`/orgs/${id}/provision`)
    return response.data
  },

  async delete(id: string, password: string): Promise<Tenant> {
    const response = await apiClient.delete<Tenant>(`/orgs/${id}`, {
      data: { password },
    })
    return response.data
  },

  async getSettings(id: string): Promise<TenantSettings> {
    const response = await apiClient.get<TenantSettings>(`/orgs/${id}/settings`)
    return response.data
  },

  async updateSettings(id: string, data: Partial<TenantSettings>): Promise<TenantSettings> {
    const response = await apiClient.put<TenantSettings>(`/orgs/${id}/settings`, data)
    return response.data
  },
}
