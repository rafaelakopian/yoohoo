import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/platform/auth'
import type { User } from '@/types/models'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const loading = ref(false)
  const error = ref<string | null>(null)
  const registeredEmail = ref<string | null>(null)

  // 2FA state
  const twoFactorToken = ref<string | null>(null)
  const twoFactorEmail = ref<string | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value)
  const hasPlatformAccess = computed(() => {
    if (user.value?.is_superadmin) return true
    return (user.value?.platform_permissions?.length ?? 0) > 0
  })
  const requires2FA = computed(() => !!twoFactorToken.value)

  async function login(email: string, password: string) {
    loading.value = true
    error.value = null

    try {
      const response = await authApi.login(email, password)

      // Check if 2FA is required
      if (response.requires_2fa && response.two_factor_token) {
        twoFactorToken.value = response.two_factor_token
        twoFactorEmail.value = email
        // Don't navigate — let the LoginView show the 2FA form
        return
      }

      // Normal login (no 2FA)
      accessToken.value = response.access_token
      refreshToken.value = response.refresh_token
      localStorage.setItem('access_token', response.access_token!)
      localStorage.setItem('refresh_token', response.refresh_token!)

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

  async function verify2FA(code: string) {
    if (!twoFactorToken.value) return
    loading.value = true
    error.value = null

    try {
      const tokens = await authApi.verify2FA(twoFactorToken.value, code)
      twoFactorToken.value = null
      twoFactorEmail.value = null

      accessToken.value = tokens.access_token
      refreshToken.value = tokens.refresh_token
      localStorage.setItem('access_token', tokens.access_token)
      localStorage.setItem('refresh_token', tokens.refresh_token)

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
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('tenant_id')
    localStorage.removeItem('tenant_slug')
    await router.push('/auth/login')
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
    isAuthenticated,
    hasPlatformAccess,
    requires2FA,
    login,
    verify2FA,
    register,
    fetchUser,
    logout,
  }
})
