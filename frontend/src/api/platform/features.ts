import apiClient from '@/api/client'
import type { FeatureCatalogEntry, TenantFeatureStatusItem } from '@/types/billing'

export const featureCatalogApi = {
  async getCatalog(): Promise<FeatureCatalogEntry[]> {
    const response = await apiClient.get<FeatureCatalogEntry[]>('/platform/features/catalog')
    return response.data
  },

  async getCatalogItem(featureName: string): Promise<FeatureCatalogEntry> {
    const response = await apiClient.get<FeatureCatalogEntry>(
      `/platform/features/catalog/${featureName}`
    )
    return response.data
  },

  async upsertCatalogItem(
    featureName: string,
    data: Omit<FeatureCatalogEntry, 'id' | 'feature_name'>
  ): Promise<FeatureCatalogEntry> {
    const response = await apiClient.put<FeatureCatalogEntry>(
      `/platform/features/catalog/${featureName}`,
      data
    )
    return response.data
  },

  async getTenantFeatures(tenantId: string): Promise<TenantFeatureStatusItem[]> {
    const response = await apiClient.get<TenantFeatureStatusItem[]>(
      `/platform/orgs/${tenantId}/features`
    )
    return response.data
  },

  async forceOn(tenantId: string, featureName: string): Promise<void> {
    await apiClient.post(`/platform/orgs/${tenantId}/features/${featureName}/force-on`)
  },

  async forceOff(tenantId: string, featureName: string, reason?: string): Promise<void> {
    await apiClient.post(`/platform/orgs/${tenantId}/features/${featureName}/force-off`, {
      reason: reason || null,
    })
  },

  async liftForceOff(tenantId: string, featureName: string): Promise<void> {
    await apiClient.post(`/platform/orgs/${tenantId}/features/${featureName}/lift`)
  },

  async resetTrial(tenantId: string, featureName: string): Promise<void> {
    await apiClient.post(`/platform/orgs/${tenantId}/features/${featureName}/reset-trial`)
  },

  async extendTrial(tenantId: string, featureName: string, extraDays: number): Promise<void> {
    await apiClient.post(`/platform/orgs/${tenantId}/features/${featureName}/extend-trial`, {
      extra_days: extraDays,
    })
  },

  async overrideFeature(
    tenantId: string,
    featureName: string,
    data: { trial_days?: number; retention_days?: number }
  ): Promise<void> {
    await apiClient.put(
      `/platform/orgs/${tenantId}/features/${featureName}/override`,
      data
    )
  },
}
