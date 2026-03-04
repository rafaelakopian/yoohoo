export type Role = 'super_admin' | 'org_admin' | 'teacher' | 'parent'

export interface User {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_superadmin: boolean
  email_verified: boolean
  created_at: string
  memberships?: TenantMembership[]
  platform_groups?: GroupSummary[]
  platform_permissions?: string[]
  totp_enabled?: boolean
  backup_codes_remaining?: number
}

export interface GroupSummary {
  id: string
  name: string
  slug: string
}

export interface TenantMembership {
  id: string
  tenant_id: string
  role: Role | null
  is_active: boolean
  membership_type: 'full' | 'collaboration'
  groups: GroupSummary[]
  permissions: string[]
}

export interface PermissionDef {
  codename: string
  label: string
  description: string
}

export interface ModulePermissions {
  module_name: string
  label: string
  permissions: PermissionDef[]
}

export interface PermissionGroup {
  id: string
  tenant_id: string
  name: string
  slug: string
  description: string | null
  is_default: boolean
  permissions: string[]
  user_count: number
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface RegisterResponse {
  id: string
  email: string
  full_name: string
  email_verified: boolean
  message: string
}

export interface MessageResponse {
  message: string
}

export interface LoginResponse {
  access_token: string | null
  refresh_token: string | null
  token_type: string
  requires_2fa: boolean
  two_factor_token: string | null
  requires_email_verification: boolean
  available_2fa_methods: string[]
}

export interface ChangePasswordResponse {
  message: string
  access_token: string
  refresh_token: string
  token_type: string
}

export interface DeviceInfo {
  browser: string
  os: string
  device_type: 'desktop' | 'mobile' | 'tablet'
}

export interface SessionInfo {
  id: string
  created_at: string
  expires_at: string
  last_used_at: string | null
  ip_address: string | null
  user_agent: string | null
  is_current: boolean
  session_type: 'session' | 'persistent'
  device_info: DeviceInfo | null
}

export interface Invitation {
  id: string
  email: string
  role: Role | null
  group_id: string | null
  group_name: string | null
  tenant_id: string
  invited_by_name: string
  expires_at: string
  created_at: string
  invitation_type?: string
}

export interface Collaborator {
  membership_id: string
  user_id: string
  email: string
  full_name: string
  is_active: boolean
  groups: GroupSummary[]
  created_at: string
}

export interface InviteInfo {
  org_name: string
  role: Role | null
  group_name: string | null
  email: string
  inviter_name: string
  is_existing_user: boolean
  invitation_type?: string
}

export interface TwoFactorSetupResponse {
  secret: string
  qr_code_uri: string
}

export interface TwoFactorBackupCodes {
  backup_codes: string[]
  message: string
}
