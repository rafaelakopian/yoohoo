import { ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  TuitionPlan,
  StudentBilling,
  TuitionInvoice,
} from '@/types/billing'
import { tuitionBillingApi } from '@/api/tenant/billing'

export const useBillingStore = defineStore('billing', () => {
  const plans = ref<TuitionPlan[]>([])
  const studentBillings = ref<StudentBilling[]>([])
  const invoices = ref<TuitionInvoice[]>([])
  const invoiceTotal = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchPlans(activeOnly = true) {
    loading.value = true
    try {
      plans.value = await tuitionBillingApi.listPlans(activeOnly)
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Kon plannen niet laden'
    } finally {
      loading.value = false
    }
  }

  async function createPlan(data: Partial<TuitionPlan>) {
    const plan = await tuitionBillingApi.createPlan(data)
    plans.value.push(plan)
    return plan
  }

  async function updatePlan(id: string, data: Partial<TuitionPlan>) {
    const updated = await tuitionBillingApi.updatePlan(id, data)
    const idx = plans.value.findIndex((p) => p.id === id)
    if (idx >= 0) plans.value[idx] = updated
    return updated
  }

  async function deactivatePlan(id: string) {
    const deactivated = await tuitionBillingApi.deactivatePlan(id)
    const idx = plans.value.findIndex((p) => p.id === id)
    if (idx >= 0) plans.value[idx] = deactivated
    return deactivated
  }

  async function fetchStudentBillings(studentId?: string) {
    loading.value = true
    try {
      studentBillings.value = await tuitionBillingApi.listStudentBilling(
        studentId ? { student_id: studentId } : undefined
      )
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Kon facturatiegegevens niet laden'
    } finally {
      loading.value = false
    }
  }

  async function fetchInvoices(params?: {
    student_billing_id?: string
    status?: string
    skip?: number
    limit?: number
  }) {
    loading.value = true
    try {
      const result = await tuitionBillingApi.listInvoices(params)
      invoices.value = result.items
      invoiceTotal.value = result.total
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Kon facturen niet laden'
    } finally {
      loading.value = false
    }
  }

  async function generateInvoices(data: {
    period_start: string
    period_end: string
    student_billing_ids?: string[]
  }) {
    const generated = await tuitionBillingApi.generateInvoices(data)
    invoices.value.unshift(...generated)
    return generated
  }

  async function sendInvoice(id: string) {
    const sent = await tuitionBillingApi.sendInvoice(id)
    const idx = invoices.value.findIndex((i) => i.id === id)
    if (idx >= 0) invoices.value[idx] = sent
    return sent
  }

  function resetState() {
    plans.value = []
    studentBillings.value = []
    invoices.value = []
    invoiceTotal.value = 0
    error.value = null
  }

  return {
    plans,
    studentBillings,
    invoices,
    invoiceTotal,
    loading,
    error,
    fetchPlans,
    createPlan,
    updatePlan,
    deactivatePlan,
    fetchStudentBillings,
    fetchInvoices,
    generateInvoices,
    sendInvoice,
    resetState,
  }
})
