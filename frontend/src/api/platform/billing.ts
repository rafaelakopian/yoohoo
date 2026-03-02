import apiClient from '../client'
import type {
  PlatformPlan,
  PlatformSubscription,
  ProviderConfig,
  BillingInvoice,
  BillingPayment,
} from '@/types/billing'

interface PaginatedList<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

export const platformBillingApi = {
  // Plans
  async listPlans(activeOnly = true): Promise<PlatformPlan[]> {
    const response = await apiClient.get<PlatformPlan[]>('/billing/plans', {
      params: { active_only: activeOnly },
    })
    return response.data
  },

  async createPlan(data: Partial<PlatformPlan>): Promise<PlatformPlan> {
    const response = await apiClient.post<PlatformPlan>('/billing/plans', data)
    return response.data
  },

  async updatePlan(id: string, data: Partial<PlatformPlan>): Promise<PlatformPlan> {
    const response = await apiClient.put<PlatformPlan>(`/billing/plans/${id}`, data)
    return response.data
  },

  // Subscriptions
  async getSubscription(tenantId: string): Promise<PlatformSubscription | null> {
    const response = await apiClient.get<PlatformSubscription | null>(
      `/billing/subscriptions/${tenantId}`
    )
    return response.data
  },

  async createSubscription(
    tenantId: string,
    data: { plan_id: string; status?: string }
  ): Promise<PlatformSubscription> {
    const response = await apiClient.post<PlatformSubscription>(
      `/billing/subscriptions/${tenantId}`,
      data
    )
    return response.data
  },

  async updateSubscription(
    tenantId: string,
    data: Partial<PlatformSubscription>
  ): Promise<PlatformSubscription> {
    const response = await apiClient.put<PlatformSubscription>(
      `/billing/subscriptions/${tenantId}`,
      data
    )
    return response.data
  },

  async cancelSubscription(tenantId: string): Promise<PlatformSubscription> {
    const response = await apiClient.post<PlatformSubscription>(
      `/billing/subscriptions/${tenantId}/cancel`
    )
    return response.data
  },

  // Providers
  async getProviders(tenantId: string): Promise<ProviderConfig[]> {
    const response = await apiClient.get<ProviderConfig[]>(
      `/billing/providers/${tenantId}`
    )
    return response.data
  },

  async configureProvider(
    tenantId: string,
    data: {
      provider_type: string
      api_key: string
      api_secret?: string
      webhook_secret?: string
      is_default?: boolean
    }
  ): Promise<ProviderConfig> {
    const response = await apiClient.post<ProviderConfig>(
      `/billing/providers/${tenantId}`,
      data
    )
    return response.data
  },

  async updateProvider(
    tenantId: string,
    providerId: string,
    data: Partial<{
      api_key: string
      api_secret: string
      webhook_secret: string
      is_default: boolean
      is_active: boolean
    }>
  ): Promise<ProviderConfig> {
    const response = await apiClient.put<ProviderConfig>(
      `/billing/providers/${tenantId}/${providerId}`,
      data
    )
    return response.data
  },

  // Invoices
  async listInvoices(params?: {
    tenant_id?: string
    status?: string
    skip?: number
    limit?: number
  }): Promise<PaginatedList<BillingInvoice>> {
    const response = await apiClient.get<PaginatedList<BillingInvoice>>('/billing/invoices', {
      params,
    })
    return response.data
  },

  async getInvoice(id: string): Promise<BillingInvoice> {
    const response = await apiClient.get<BillingInvoice>(`/billing/invoices/${id}`)
    return response.data
  },

  // Payments
  async listPayments(params?: {
    tenant_id?: string
    invoice_id?: string
    skip?: number
    limit?: number
  }): Promise<PaginatedList<BillingPayment>> {
    const response = await apiClient.get<PaginatedList<BillingPayment>>('/billing/payments', {
      params,
    })
    return response.data
  },

  async refundPayment(
    paymentId: string,
    data?: { amount_cents?: number; description?: string }
  ): Promise<BillingPayment> {
    const response = await apiClient.post<BillingPayment>(
      `/billing/payments/${paymentId}/refund`,
      data || {}
    )
    return response.data
  },
}
