import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/platform/auth'
import type { User } from '@/types/models'
import router from '@/router'

/** Read a token from whatever storage it's in. */
function _readToken(key: string): string | null {
  const sessionType = localStorage.getItem('auth_session_type') ?? 'persistent'
  if (sessionType === 'session') {
    return sessionStorage.getItem(key) ?? localStorage.getItem(key)
  }
  return localStorage.getItem(key) ?? sessionStorage.getItem(key)
}

/** Store tokens in the correct storage based on session type. */
function _storeTokens(access: string, refresh: string, type: 'session' | 'persistent') {
  const storage = type === 'persistent' ? localStorage : sessionStorage
  // Clear from the other storage
  const otherStorage = type === 'persistent' ? sessionStorage : localStorage
  otherStorage.removeItem('access_token')
  otherStorage.removeItem('refresh_token')
  // Set in correct storage
  storage.setItem('access_token', access)
  storage.setItem('refresh_token', refresh)
  localStorage.setItem('auth_session_type', type)
}

/** Clear tokens from both storages. */
function _clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  sessionStorage.removeItem('access_token')
  sessionStorage.removeItem('refresh_token')
  localStorage.removeItem('auth_session_type')
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(_readToken('access_token'))
  const refreshToken = ref<string | null>(_readToken('refresh_token'))
  const loading = ref(false)
  const error = ref<string | null>(null)
  const registeredEmail = ref<string | null>(null)

  // 2FA state
  const twoFactorToken = ref<string | null>(null)
  const twoFactorEmail = ref<string | null>(null)
  const available2FAMethods = ref<string[]>([])

  // Email verification state
  const requiresEmailVerification = ref(false)

  // Impersonation state
  const impersonatedBy = ref<string | null>(sessionStorage.getItem('impersonated_by'))
  const impersonationTargetName = ref<string | null>(sessionStorage.getItem('impersonation_target_name'))
  const impersonationTargetEmail = ref<string | null>(sessionStorage.getItem('impersonation_target_email'))
  const impersonationExpiresAt = ref<string | null>(sessionStorage.getItem('impersonation_expires_at'))
  const originalAccessToken = ref<string | null>(sessionStorage.getItem('original_access_token'))
  const originalRefreshToken = ref<string | null>(sessionStorage.getItem('original_refresh_token'))

  const isAuthenticated = computed(() => !!accessToken.value)
  const isImpersonating = computed(() => !!impersonatedBy.value)
  const hasPlatformAccess = computed(() => {
    if (user.value?.is_superadmin) return true
    return (user.value?.platform_permissions?.length ?? 0) > 0
  })
  const requires2FA = computed(() => !!twoFactorToken.value)

  async function login(email: string, password: string, rememberMe: boolean = false) {
    loading.value = true
    error.value = null
    requiresEmailVerification.value = false

    try {
      const response = await authApi.login(email, password, rememberMe)

      // Check if 2FA is required
      if (response.requires_2fa && response.two_factor_token) {
        twoFactorToken.value = response.two_factor_token
        twoFactorEmail.value = email
        available2FAMethods.value = response.available_2fa_methods ?? []
        return
      }

      // Check if email verification is required (magic link sent)
      if (response.requires_email_verification) {
        requiresEmailVerification.value = true
        return
      }

      // Normal login (no 2FA, no email verification)
      const sessionType = rememberMe ? 'persistent' : 'session'
      _handleTokens(response.access_token!, response.refresh_token!, sessionType)

      await fetchUser()
      await _routeAfterLogin()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      error.value = err.response?.data?.detail ?? 'Login failed'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function verify2FA(code: string, method: string = 'totp', verificationId?: string) {
    if (!twoFactorToken.value) return
    loading.value = true
    error.value = null

    try {
      const tokens = await authApi.verify2FA(twoFactorToken.value, code, method, verificationId)
      twoFactorToken.value = null
      twoFactorEmail.value = null
      available2FAMethods.value = []

      _handleTokens(tokens.access_token, tokens.refresh_token, 'persistent')

      await fetchUser()
      await _routeAfterLogin()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      error.value = err.response?.data?.detail ?? 'Ongeldige code'
      throw e
    } finally {
      loading.value = false
    }
  }

  function _handleTokens(access: string, refresh: string, type: 'session' | 'persistent') {
    accessToken.value = access
    refreshToken.value = refresh
    _storeTokens(access, refresh, type)
  }

  async function _routeAfterLogin() {
    const memberships = user.value?.memberships ?? []
    const _hasPlatformAccess = user.value?.is_superadmin ||
      (user.value?.platform_permissions?.length ?? 0) > 0

    // Platform user (superadmin / platform permissions) → always platform dashboard
    if (_hasPlatformAccess) {
      await router.push('/platform')
      return
    }

    // Auto-select tenant if user has exactly 1 membership
    if (memberships.length === 1) {
      const { useTenantStore } = await import('@/stores/tenant')
      const tenantStore = useTenantStore()
      await tenantStore.fetchTenants()
      const tenant = tenantStore.tenants.find((t) => t.id === memberships[0].tenant_id)
      if (tenant?.is_provisioned) {
        await tenantStore.selectTenant(tenant)
        await router.push(`/org/${tenant.slug}/dashboard`)
        return
      }
    }

    await router.push('/welcome')
  }

  async function register(email: string, password: string, fullName: string) {
    loading.value = true
    error.value = null

    try {
      await authApi.register({ email, password, full_name: fullName })
      registeredEmail.value = email
      await router.push('/auth/register-success')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      error.value = err.response?.data?.detail ?? 'Registration failed'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchUser() {
    if (!accessToken.value) return

    try {
      user.value = await authApi.me()
    } catch {
      logout()
    }
  }

  async function logout() {
    if (refreshToken.value) {
      try {
        await authApi.logout(refreshToken.value)
      } catch {
        // Ignore errors during logout
      }
    }

    user.value = null
    accessToken.value = null
    refreshToken.value = null
    twoFactorToken.value = null
    twoFactorEmail.value = null
    available2FAMethods.value = []
    requiresEmailVerification.value = false
    _clearTokens()
    localStorage.removeItem('tenant_id')
    localStorage.removeItem('tenant_slug')
    await router.push('/auth/login')
  }

  async function startImpersonation(response: {
    access_token: string
    target_user_email: string
    target_user_name: string
    expires_at: string
    impersonated_by: string
  }) {
    // Save current tokens
    originalAccessToken.value = accessToken.value
    originalRefreshToken.value = refreshToken.value
    sessionStorage.setItem('original_access_token', accessToken.value ?? '')
    sessionStorage.setItem('original_refresh_token', refreshToken.value ?? '')

    // Set impersonation state
    impersonatedBy.value = response.impersonated_by
    impersonationTargetName.value = response.target_user_name
    impersonationTargetEmail.value = response.target_user_email
    impersonationExpiresAt.value = response.expires_at
    sessionStorage.setItem('impersonated_by', response.impersonated_by)
    sessionStorage.setItem('impersonation_target_name', response.target_user_name)
    sessionStorage.setItem('impersonation_target_email', response.target_user_email)
    sessionStorage.setItem('impersonation_expires_at', response.expires_at)

    // Replace tokens (no refresh for impersonation)
    accessToken.value = response.access_token
    refreshToken.value = null
    sessionStorage.setItem('access_token', response.access_token)
    sessionStorage.removeItem('refresh_token')
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')

    // Fetch impersonated user
    await fetchUser()
  }

  async function stopImpersonation() {
    // Restore original tokens
    const origAccess = originalAccessToken.value
    const origRefresh = originalRefreshToken.value

    // Clear impersonation state
    impersonatedBy.value = null
    impersonationTargetName.value = null
    impersonationTargetEmail.value = null
    impersonationExpiresAt.value = null
    originalAccessToken.value = null
    originalRefreshToken.value = null
    sessionStorage.removeItem('impersonated_by')
    sessionStorage.removeItem('impersonation_target_name')
    sessionStorage.removeItem('impersonation_target_email')
    sessionStorage.removeItem('impersonation_expires_at')
    sessionStorage.removeItem('original_access_token')
    sessionStorage.removeItem('original_refresh_token')

    // Restore tokens
    if (origAccess && origRefresh) {
      const sessionType = localStorage.getItem('auth_session_type') as 'session' | 'persistent' ?? 'persistent'
      _handleTokens(origAccess, origRefresh, sessionType)
      await fetchUser()
    }

    await router.push('/platform')
  }

  return {
    user,
    accessToken,
    refreshToken,
    loading,
    error,
    registeredEmail,
    twoFactorToken,
    twoFactorEmail,
    available2FAMethods,
    requiresEmailVerification,
    isAuthenticated,
    isImpersonating,
    hasPlatformAccess,
    requires2FA,
    impersonatedBy,
    impersonationTargetName,
    impersonationTargetEmail,
    impersonationExpiresAt,
    login,
    verify2FA,
    register,
    fetchUser,
    logout,
    startImpersonation,
    stopImpersonation,
    _handleTokens,
    _routeAfterLogin,
  }
})
