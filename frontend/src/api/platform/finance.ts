import apiClient from '@/api/client'

export interface TenantRevenue {
  tenant_id: string
  tenant_name: string
  tenant_slug: string
  lifetime_value_cents: number
  mrr_cents: number
  subscription_status: string | null
  since: string
}

export interface RevenueOverview {
  mrr_cents: number
  arr_cents: number
  growth_percent: number | null
  total_revenue_cents: number
  top_tenants: TenantRevenue[]
  subscription_counts: Record<string, number>
  funnel: Record<string, number>
  generated_at: string
}

export interface InvoiceAging {
  bucket: string
  days_range: string
  count: number
  total_cents: number
  tenants: string[]
}

export interface OutstandingPayments {
  total_outstanding_cents: number
  buckets: InvoiceAging[]
  generated_at: string
}

export interface TaxReportLine {
  month: string
  invoice_count: number
  subtotal_cents: number
  tax_cents: number
  total_cents: number
}

export interface TaxReport {
  year: number
  quarter: number
  lines: TaxReportLine[]
  totals: TaxReportLine
  generated_at: string
}

export interface DunningCandidate {
  tenant_id: string
  tenant_name: string
  contact_email: string
  invoice_id: string
  invoice_number: string
  amount_cents: number
  days_overdue: number
  reminder_count: number
  last_reminder_sent_at: string | null
}

export interface DunningSendResult {
  sent: number
  skipped: number
}

export async function getRevenueOverview(): Promise<RevenueOverview> {
  const { data } = await apiClient.get('/platform/finance/overview')
  return data
}

export async function getOutstandingPayments(): Promise<OutstandingPayments> {
  const { data } = await apiClient.get('/platform/finance/outstanding')
  return data
}

export async function getTaxReport(year: number, quarter: number): Promise<TaxReport> {
  const { data } = await apiClient.get('/platform/finance/tax-report', { params: { year, quarter } })
  return data
}

export function getTaxReportExportUrl(year: number, quarter: number): string {
  return `/api/v1/platform/finance/tax-report/export?year=${year}&quarter=${quarter}`
}

export async function getDunningCandidates(): Promise<DunningCandidate[]> {
  const { data } = await apiClient.get('/platform/finance/dunning/candidates')
  return data
}

export async function sendDunningReminders(params?: {
  tenant_id?: string
  invoice_id?: string
}): Promise<DunningSendResult> {
  const { data } = await apiClient.post('/platform/finance/dunning/send', null, { params })
  return data
}
