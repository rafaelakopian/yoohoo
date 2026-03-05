import apiClient from '@/api/client'

// --- Shared types ---

export interface TenantSettingsSummary {
  org_name: string | null
  org_email: string | null
  org_phone: string | null
  timezone: string | null
}

export interface AuditEvent {
  action: string
  user_email: string | null
  ip_address: string | null
  created_at: string
}

export interface InvoiceStats {
  sent_count: number
  paid_count: number
  overdue_count: number
  total_outstanding_cents: number
  total_paid_cents: number
}

// --- A1: Tenant Health Dashboard ---

export interface TenantHealthItem {
  id: string
  name: string
  slug: string
  is_active: boolean
  is_provisioned: boolean
  owner_name: string | null
  member_count: number
  created_at: string
  metrics_available: boolean
  student_count: number
  teacher_count: number
  active_invoice_count: number
  last_activity_at: string | null
}

export interface TenantHealthDashboard {
  total_tenants: number
  active_tenants: number
  provisioned_tenants: number
  total_users: number
  active_users: number
  tenants: TenantHealthItem[]
  cached_at: string | null
}

// --- A2: Tenant 360° ---

export interface Tenant360Member {
  user_id: string
  email: string
  full_name: string
  role: string | null
  is_active: boolean
  groups: string[]
  last_login_at: string | null
}

export interface Tenant360Detail {
  id: string
  name: string
  slug: string
  is_active: boolean
  is_provisioned: boolean
  owner_name: string | null
  created_at: string
  settings: TenantSettingsSummary | null
  members: Tenant360Member[]
  metrics_available: boolean
  student_count: number
  active_student_count: number
  teacher_count: number
  lesson_slot_count: number
  attendance_present_count: number
  attendance_total_count: number
  invoice_stats: InvoiceStats
  last_activity_at: string | null
  recent_events: AuditEvent[]
}

// --- A3: User Lookup ---

export interface UserLookupMembership {
  tenant_id: string
  tenant_name: string
  tenant_slug: string
  role: string | null
  groups: string[]
}

export interface UserLookupResult {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_superadmin: boolean
  email_verified: boolean
  totp_enabled: boolean
  last_login_at: string | null
  created_at: string
  memberships: UserLookupMembership[]
  active_sessions: number
}

// --- A4: Onboarding ---

export interface OnboardingItem {
  tenant_id: string
  tenant_name: string
  tenant_slug: string
  created_at: string
  is_provisioned: boolean
  has_settings: boolean
  has_members: boolean
  has_students: boolean
  has_schedule: boolean
  has_attendance: boolean
  has_billing_plan: boolean
  completion_pct: number
  missing_steps: string[]
  last_step_at: string | null
}

// --- API calls ---

export async function getOperationsDashboard(): Promise<TenantHealthDashboard> {
  const { data } = await apiClient.get('/admin/operations/dashboard')
  return data
}

export async function getTenant360(tenantId: string): Promise<Tenant360Detail> {
  const { data } = await apiClient.get(`/admin/operations/tenants/${tenantId}`)
  return data
}

export async function getTenantEvents(
  tenantId: string, offset = 0, limit = 50,
): Promise<AuditEvent[]> {
  const { data } = await apiClient.get(
    `/admin/operations/tenants/${tenantId}/events`,
    { params: { offset, limit } },
  )
  return data
}

export async function lookupUser(query: string): Promise<UserLookupResult[]> {
  const { data } = await apiClient.get('/admin/operations/users/lookup', {
    params: { q: query },
  })
  return data
}

export async function getOnboardingOverview(): Promise<OnboardingItem[]> {
  const { data } = await apiClient.get('/admin/operations/onboarding')
  return data
}
