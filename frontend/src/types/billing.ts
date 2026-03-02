// Platform billing types

export interface PlatformPlan {
  id: string
  name: string
  slug: string
  description: string | null
  price_cents: number
  currency: string
  interval: 'monthly' | 'yearly'
  max_students: number | null
  max_teachers: number | null
  features: Record<string, unknown> | null
  is_active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface PlatformSubscription {
  id: string
  tenant_id: string
  plan_id: string
  status: 'trialing' | 'active' | 'past_due' | 'cancelled' | 'expired'
  provider_subscription_id: string | null
  current_period_start: string | null
  current_period_end: string | null
  trial_end: string | null
  cancelled_at: string | null
  plan: PlatformPlan | null
  created_at: string
  updated_at: string
}

export interface ProviderConfig {
  id: string
  tenant_id: string
  provider_type: 'mollie' | 'stripe'
  is_active: boolean
  is_default: boolean
  provider_account_id: string | null
  supported_methods: string[] | null
  extra_config: Record<string, unknown> | null
  has_api_key: boolean
  has_api_secret: boolean
  has_webhook_secret: boolean
  created_at: string
  updated_at: string
}

export interface BillingInvoice {
  id: string
  invoice_number: string
  invoice_type: 'platform' | 'tuition'
  tenant_id: string
  subscription_id: string | null
  recipient_name: string
  recipient_email: string
  recipient_address: string | null
  subtotal_cents: number
  tax_cents: number
  total_cents: number
  currency: string
  status: 'draft' | 'open' | 'paid' | 'overdue' | 'cancelled' | 'refunded'
  description: string | null
  line_items: unknown[] | null
  due_date: string | null
  paid_at: string | null
  created_at: string
  updated_at: string
}

export interface BillingPayment {
  id: string
  invoice_id: string
  tenant_id: string
  provider_type: 'mollie' | 'stripe'
  provider_payment_id: string
  amount_cents: number
  currency: string
  status: 'pending' | 'processing' | 'paid' | 'failed' | 'cancelled' | 'expired' | 'refunded' | 'partially_refunded'
  payment_method: string | null
  failure_reason: string | null
  refund_amount_cents: number
  paid_at: string | null
  created_at: string
  updated_at: string
}

// Tenant tuition billing types

export interface TuitionPlan {
  id: string
  name: string
  description: string | null
  amount_cents: number
  currency: string
  frequency: 'per_lesson' | 'weekly' | 'monthly' | 'quarterly' | 'semester' | 'yearly'
  lesson_duration_minutes: number | null
  is_active: boolean
  extra_config: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface StudentBilling {
  id: string
  student_id: string
  tuition_plan_id: string
  payer_user_id: string | null
  payer_name: string
  payer_email: string
  status: 'active' | 'paused' | 'cancelled'
  custom_amount_cents: number | null
  discount_percent: number | null
  billing_start_date: string | null
  billing_end_date: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface TuitionInvoice {
  id: string
  invoice_number: string
  student_billing_id: string
  central_invoice_id: string | null
  payer_name: string
  payer_email: string
  student_name: string
  period_start: string
  period_end: string
  subtotal_cents: number
  discount_cents: number
  total_cents: number
  currency: string
  status: 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled'
  description: string | null
  line_items: unknown[] | null
  due_date: string | null
  sent_at: string | null
  paid_at: string | null
  checkout_url: string | null
  created_at: string
  updated_at: string
}

// Helper type for formatting
export function formatCents(cents: number, currency = 'EUR'): string {
  return new Intl.NumberFormat('nl-NL', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}
