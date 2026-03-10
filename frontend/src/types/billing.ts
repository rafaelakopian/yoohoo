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
  status: 'trialing' | 'active' | 'past_due' | 'cancelled' | 'expired' | 'paused'
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
  tenant_name: string | null
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
  dunning_count: number
  dunning_last_sent_at: string | null
  created_at: string
  updated_at: string
}

export interface SubscriptionOverviewItem {
  subscription_id: string
  tenant_id: string
  tenant_name: string
  plan_id: string
  plan_name: string
  plan_price_cents: number
  status: string
  started_at: string
  cancelled_at: string | null
  next_invoice_date: string | null
  last_invoice_date: string | null
  total_invoiced_cents: number
  invoice_count: number
}

export interface SubscriptionOverviewResponse {
  items: SubscriptionOverviewItem[]
  total: number
  page: number
  page_size: number
  pages: number
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

// Feature gating types

export interface FeatureConfig {
  enabled: boolean
  trial_days: number | null
  data_retention_days: number | null
}

export interface FeatureAccess {
  allowed: boolean
  reason: string | null
  in_trial: boolean
  trial_available: boolean
  trial_days: number | null
  trial_expires_at: string | null
  in_retention: boolean
  is_force_blocked: boolean
  is_force_enabled: boolean
  force_off_reason: string | null
  upgrade_plans: { id: string; name: string; slug: string; price_cents: number; interval: string }[]
}

export interface FeatureStatusItem {
  name: string
  config: FeatureConfig
  access: FeatureAccess
}

export interface FeatureStatusResponse {
  features: FeatureStatusItem[]
}

export interface TrialStartResponse {
  feature_name: string
  status: string
  trial_expires_at: string | null
  message: string
}

// Feature catalog types (Fase H-2)

export interface FeatureCatalogEntry {
  id: string
  feature_name: string
  display_name: string
  description: string | null
  benefits: string[] | null
  preview_image_url: string | null
  default_trial_days: number
  default_retention_days: number
  is_active: boolean
}

export interface TenantFeatureOverride {
  trial_days: number | null
  retention_days: number | null
  force_on: boolean
  force_off: boolean
  force_off_reason: string | null
  force_off_since: string | null
  forced_at: string | null
}

export interface TenantFeatureStatusItem {
  feature_name: string
  access: FeatureAccess
  override: TenantFeatureOverride | null
  trial: {
    status: string
    trial_started_at: string | null
    trial_expires_at: string | null
    trial_days_snapshot: number | null
    reset_count: number
    last_reset_at: string | null
  } | null
  catalog: {
    display_name: string
    default_trial_days: number
    default_retention_days: number
    is_active: boolean
  } | null
}

export interface SubscriptionStatusResponse {
  status: string // active/trialing/paused/cancelled/expired/none
  plan_name: string | null
  paused_at: string | null
  cancelled_at: string | null
}

export type ResumeMode = 'backfill' | 'prorata' | 'next_month'

export interface ResumeSubscriptionResponse extends PlatformSubscription {
  invoices_generated: number
}

// Helper type for formatting
export function formatCents(cents: number, currency = 'EUR'): string {
  return new Intl.NumberFormat('nl-NL', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}
