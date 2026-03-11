import axios from 'axios'
import type { TokenResponse } from '@/types/models'

const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

/** Read a token from the correct storage based on session type. */
function readToken(key: string): string | null {
  const sessionType = localStorage.getItem('auth_session_type') ?? 'persistent'
  if (sessionType === 'session') {
    return sessionStorage.getItem(key) ?? localStorage.getItem(key)
  }
  return localStorage.getItem(key) ?? sessionStorage.getItem(key)
}

/** Store tokens in the correct storage, clearing from the other. */
function storeTokens(access: string, refresh: string) {
  const sessionType = localStorage.getItem('auth_session_type') ?? 'persistent'
  const storage = sessionType === 'session' ? sessionStorage : localStorage
  const other = sessionType === 'session' ? localStorage : sessionStorage
  other.removeItem('access_token')
  other.removeItem('refresh_token')
  storage.setItem('access_token', access)
  storage.setItem('refresh_token', refresh)
}

/** Clear tokens from both storages. */
function clearAllTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  sessionStorage.removeItem('access_token')
  sessionStorage.removeItem('refresh_token')
  localStorage.removeItem('auth_session_type')
  localStorage.removeItem('tenant_slug')
}

/** Clear auth state and navigate to login via Vue Router (no page reload). */
async function forceLogout() {
  clearAllTokens()
  const { useAuthStore } = await import('@/stores/auth')
  const auth = useAuthStore()
  auth.user = null
  auth.accessToken = null
  auth.refreshToken = null
  const { default: appRouter } = await import('@/router/index')
  appRouter.push({ name: 'login' })
}

// Request interceptor: attach JWT token
apiClient.interceptors.request.use((config) => {
  const token = readToken('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

/** Build a tenant-scoped API path: /org/{slug}/... */
export function tenantUrl(path: string): string {
  const slug = localStorage.getItem('tenant_slug')
  if (!slug) throw new Error('No tenant context')
  return `/org/${slug}${path}`
}

// Response interceptor: handle 401 and token refresh
let isRefreshing = false
let failedQueue: Array<{
  resolve: (value: unknown) => void
  reject: (reason: unknown) => void
}> = []

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Subscription guard: redirect to upgrade page on paused/inactive subscription
    if (error.response?.status === 403) {
      const detail = error.response.data?.detail
      const code = typeof detail === 'object' ? detail?.code : detail
      if (code === 'subscription_paused' || code === 'subscription_inactive') {
        const slug = typeof detail === 'object' ? detail?.slug : localStorage.getItem('tenant_slug')
        if (slug) {
          // Dynamic import to avoid circular dependency
          const { default: router } = await import('@/router/index')
          const currentRoute = router.currentRoute.value
          // Only redirect if not already on an allowed page
          const allowedRoutes = ['org-billing', 'org-billing-invoices', 'org-billing-plans', 'org-billing-students', 'org-upgrade', 'org-subscription-paused']
          if (!allowedRoutes.includes(currentRoute.name as string)) {
            router.push({ name: 'org-subscription-paused', params: { slug } })
          }
        }
        return Promise.reject(error)
      }
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      // During impersonation: stop impersonation instead of refreshing
      if (sessionStorage.getItem('impersonated_by')) {
        const { useAuthStore } = await import('@/stores/auth')
        const authStore = useAuthStore()
        await authStore.stopImpersonation()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return apiClient(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshTokenValue = readToken('refresh_token')
      if (!refreshTokenValue) {
        isRefreshing = false
        await forceLogout()
        return Promise.reject(error)
      }

      try {
        const { data } = await axios.post<TokenResponse>('/api/v1/auth/refresh', {
          refresh_token: refreshTokenValue,
        })

        storeTokens(data.access_token, data.refresh_token)

        apiClient.defaults.headers.common.Authorization = `Bearer ${data.access_token}`
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`

        processQueue(null, data.access_token)
        return apiClient(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        await forceLogout()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  },
)

export default apiClient
