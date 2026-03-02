import apiClient from '../client'
import type { Tenant, TenantSettings } from '@/types/models'

export const schoolsApi = {
  async create(data: { name: string; slug: string }): Promise<Tenant> {
    const response = await apiClient.post<Tenant>('/schools/', data)
    return response.data
  },

  async list(): Promise<Tenant[]> {
    const response = await apiClient.get<Tenant[]>('/schools/')
    return response.data
  },

  async get(id: string): Promise<Tenant> {
    const response = await apiClient.get<Tenant>(`/schools/${id}`)
    return response.data
  },

  async provision(id: string): Promise<Tenant> {
    const response = await apiClient.post<Tenant>(`/schools/${id}/provision`)
    return response.data
  },

  async delete(id: string, password: string): Promise<Tenant> {
    const response = await apiClient.delete<Tenant>(`/schools/${id}`, {
      data: { password },
    })
    return response.data
  },

  async getSettings(id: string): Promise<TenantSettings> {
    const response = await apiClient.get<TenantSettings>(`/schools/${id}/settings`)
    return response.data
  },

  async updateSettings(id: string, data: Partial<TenantSettings>): Promise<TenantSettings> {
    const response = await apiClient.put<TenantSettings>(`/schools/${id}/settings`, data)
    return response.data
  },
}
