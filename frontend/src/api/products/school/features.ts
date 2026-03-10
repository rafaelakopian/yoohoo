import apiClient, { tenantUrl } from '@/api/client'
import type { FeatureStatusResponse, SubscriptionStatusResponse, TrialStartResponse } from '@/types/billing'

export const featuresApi = {
  async listFeatures(): Promise<FeatureStatusResponse> {
    const response = await apiClient.get<FeatureStatusResponse>(tenantUrl('/features'))
    return response.data
  },

  async startTrial(featureName: string): Promise<TrialStartResponse> {
    const response = await apiClient.post<TrialStartResponse>(
      tenantUrl(`/features/${featureName}/trial`)
    )
    return response.data
  },

  async getSubscriptionStatus(): Promise<SubscriptionStatusResponse> {
    const response = await apiClient.get<SubscriptionStatusResponse>(tenantUrl('/subscription-status'))
    return response.data
  },
}
