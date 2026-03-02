import apiClient, { tenantUrl } from '../client'
import type {
  TuitionPlan,
  StudentBilling,
  TuitionInvoice,
} from '@/types/billing'

interface PaginatedList<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

export const tuitionBillingApi = {
  // Plans
  async listPlans(activeOnly = true): Promise<TuitionPlan[]> {
    const response = await apiClient.get<TuitionPlan[]>(tenantUrl('/tuition/plans'), {
      params: { active_only: activeOnly },
    })
    return response.data
  },

  async createPlan(data: Partial<TuitionPlan>): Promise<TuitionPlan> {
    const response = await apiClient.post<TuitionPlan>(tenantUrl('/tuition/plans'), data)
    return response.data
  },

  async updatePlan(id: string, data: Partial<TuitionPlan>): Promise<TuitionPlan> {
    const response = await apiClient.put<TuitionPlan>(tenantUrl(`/tuition/plans/${id}`), data)
    return response.data
  },

  async deactivatePlan(id: string): Promise<TuitionPlan> {
    const response = await apiClient.delete<TuitionPlan>(tenantUrl(`/tuition/plans/${id}`))
    return response.data
  },

  // Student Billing
  async listStudentBilling(params?: {
    student_id?: string
    skip?: number
    limit?: number
  }): Promise<StudentBilling[]> {
    const response = await apiClient.get<StudentBilling[]>(tenantUrl('/tuition/student-billing'), {
      params,
    })
    return response.data
  },

  async getStudentBilling(studentId: string): Promise<StudentBilling | null> {
    const response = await apiClient.get<StudentBilling | null>(
      tenantUrl(`/tuition/student-billing/${studentId}`)
    )
    return response.data
  },

  async createStudentBilling(data: Partial<StudentBilling>): Promise<StudentBilling> {
    const response = await apiClient.post<StudentBilling>(tenantUrl('/tuition/student-billing'), data)
    return response.data
  },

  async updateStudentBilling(
    id: string,
    data: Partial<StudentBilling>
  ): Promise<StudentBilling> {
    const response = await apiClient.put<StudentBilling>(
      tenantUrl(`/tuition/student-billing/${id}`),
      data
    )
    return response.data
  },

  // Invoices
  async listInvoices(params?: {
    student_billing_id?: string
    status?: string
    skip?: number
    limit?: number
  }): Promise<PaginatedList<TuitionInvoice>> {
    const response = await apiClient.get<PaginatedList<TuitionInvoice>>(tenantUrl('/tuition/invoices'), {
      params,
    })
    return response.data
  },

  async generateInvoices(data: {
    period_start: string
    period_end: string
    student_billing_ids?: string[]
  }): Promise<TuitionInvoice[]> {
    const response = await apiClient.post<TuitionInvoice[]>(
      tenantUrl('/tuition/invoices/generate'),
      data
    )
    return response.data
  },

  async sendInvoice(id: string): Promise<TuitionInvoice> {
    const response = await apiClient.post<TuitionInvoice>(tenantUrl(`/tuition/invoices/${id}/send`))
    return response.data
  },

  async getInvoice(id: string): Promise<TuitionInvoice> {
    const response = await apiClient.get<TuitionInvoice>(tenantUrl(`/tuition/invoices/${id}`))
    return response.data
  },
}
