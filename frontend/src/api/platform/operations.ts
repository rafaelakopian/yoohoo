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
  is_active: boolean
  is_superadmin: boolean
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
  const { data } = await apiClient.get('/platform/operations/dashboard')
  return data
}

export async function getTenant360(tenantId: string): Promise<Tenant360Detail> {
  const { data } = await apiClient.get(`/platform/operations/tenants/${tenantId}`)
  return data
}

export async function getTenantEvents(
  tenantId: string, offset = 0, limit = 50,
): Promise<AuditEvent[]> {
  const { data } = await apiClient.get(
    `/platform/operations/tenants/${tenantId}/events`,
    { params: { offset, limit } },
  )
  return data
}

export async function getOnboardingOverview(): Promise<OnboardingItem[]> {
  const { data } = await apiClient.get('/platform/operations/onboarding')
  return data
}

// --- B4: Support Notes ---

export interface SupportNote {
  id: string
  content: string
  is_pinned: boolean
  created_by_id: string | null
  created_by_name: string
  created_by_email: string
  created_at: string
  updated_at: string | null
}

export async function getTenantNotes(tenantId: string): Promise<SupportNote[]> {
  const { data } = await apiClient.get(`/platform/operations/tenants/${tenantId}/notes`)
  return data
}

export async function createTenantNote(tenantId: string, body: { content: string; is_pinned?: boolean }): Promise<SupportNote> {
  const { data } = await apiClient.post(`/platform/operations/tenants/${tenantId}/notes`, body)
  return data
}

export async function getUserNotes(userId: string): Promise<SupportNote[]> {
  const { data } = await apiClient.get(`/platform/operations/users/${userId}/notes`)
  return data
}

export async function createUserNote(userId: string, body: { content: string; is_pinned?: boolean }): Promise<SupportNote> {
  const { data } = await apiClient.post(`/platform/operations/users/${userId}/notes`, body)
  return data
}

export async function updateNote(noteId: string, body: { content?: string; is_pinned?: boolean }): Promise<SupportNote> {
  const { data } = await apiClient.put(`/platform/operations/notes/${noteId}`, body)
  return data
}

export async function deleteNote(noteId: string): Promise<void> {
  await apiClient.delete(`/platform/operations/notes/${noteId}`)
}

export async function togglePinNote(noteId: string): Promise<SupportNote> {
  const { data } = await apiClient.patch(`/platform/operations/notes/${noteId}/pin`)
  return data
}

// --- B1: Impersonate ---

export interface ImpersonateRequest {
  user_id: string
  reason: string
  tenant_id?: string
}

export interface ImpersonateResponse {
  access_token: string
  target_user_email: string
  target_user_name: string
  expires_at: string
  impersonated_by: string
  impersonation_id: string
}

export async function impersonateUser(data: ImpersonateRequest): Promise<ImpersonateResponse> {
  const { data: result } = await apiClient.post('/platform/operations/impersonate', data)
  return result
}

// --- B3: Customer Timeline ---

export interface TimelineEvent {
  id: string
  action: string
  category: string
  user_email: string | null
  user_id: string | null
  ip_address: string | null
  entity_type: string | null
  entity_id: string | null
  details_summary: string | null
  created_at: string
}

export interface TimelineResponse {
  events: TimelineEvent[]
  total_count: number
  has_more: boolean
}

export interface TimelineParams {
  category?: string
  user_id?: string
  search?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

export async function getTenantTimeline(tenantId: string, params?: TimelineParams): Promise<TimelineResponse> {
  const { data } = await apiClient.get(`/platform/operations/tenants/${tenantId}/timeline`, { params })
  return data
}

// --- Job Monitoring ---

export interface JobInfo {
  job_id: string | null
  function: string
  status: 'queued' | 'deferred' | 'in_progress' | 'complete' | 'failed'
  enqueue_time: string | null
  start_time: string | null
  finish_time: string | null
  execution_duration_ms: number | null
  try_count: number
  success: boolean | null
  error: string | null
}

export interface JobQueueSummary {
  queued_count: number
  in_progress_count: number
  complete_count: number
  failed_count: number
  jobs: JobInfo[]
  checked_at: string
}

export async function getJobMonitor(params?: {
  date_from?: string
  date_to?: string
}): Promise<JobQueueSummary> {
  const { data } = await apiClient.get('/platform/operations/jobs', { params })
  return data
}

// --- B2: Quick Actions ---

export async function forcePasswordReset(userId: string): Promise<void> {
  await apiClient.post(`/platform/operations/users/${userId}/force-password-reset`)
}

export async function toggleUserActive(userId: string, password: string): Promise<{ is_active: boolean }> {
  const { data } = await apiClient.post(`/platform/operations/users/${userId}/toggle-active`, { password })
  return data
}

export async function resendVerificationEmail(userId: string): Promise<void> {
  await apiClient.post(`/platform/operations/users/${userId}/resend-verification`)
}

export async function revokeUserSessions(userId: string): Promise<{ revoked_count: number }> {
  const { data } = await apiClient.post(`/platform/operations/users/${userId}/revoke-sessions`)
  return data
}

export async function disableUser2FA(userId: string, password: string): Promise<void> {
  await apiClient.post(`/platform/operations/users/${userId}/disable-2fa`, { password })
}
