import apiClient from '../client'
import type { Tenant, TenantSettings } from '@/types/models'

export const orgsApi = {
  async create(data: { name: string; slug: string }): Promise<Tenant> {
    const response = await apiClient.post<Tenant>('/platform/orgs/', data)
    return response.data
  },

  async list(): Promise<Tenant[]> {
    const response = await apiClient.get<Tenant[]>('/platform/orgs/')
    return response.data
  },

  async get(id: string): Promise<Tenant> {
    const response = await apiClient.get<Tenant>(`/platform/orgs/${id}`)
    return response.data
  },

  async provision(id: string): Promise<Tenant> {
    const response = await apiClient.post<Tenant>(`/platform/orgs/${id}/provision`)
    return response.data
  },

  async delete(id: string, password: string): Promise<Tenant> {
    const response = await apiClient.delete<Tenant>(`/platform/orgs/${id}`, {
      data: { password },
    })
    return response.data
  },

  async checkSlug(slug: string): Promise<{ slug: string; available: boolean }> {
    const response = await apiClient.get<{ slug: string; available: boolean }>('/platform/orgs/check-slug', { params: { slug } })
    return response.data
  },

  async selfServiceCreate(data: { name: string; slug: string; plan_id: string }): Promise<Tenant> {
    const response = await apiClient.post<Tenant>('/platform/orgs/self-service', data)
    return response.data
  },

  async getSettings(id: string): Promise<TenantSettings> {
    const response = await apiClient.get<TenantSettings>(`/platform/orgs/${id}/settings`)
    return response.data
  },

  async updateSettings(id: string, data: Partial<TenantSettings>): Promise<TenantSettings> {
    const response = await apiClient.put<TenantSettings>(`/platform/orgs/${id}/settings`, data)
    return response.data
  },
}
