import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { ORG } from './routes'

export function setupGuards(router: Router) {
  router.beforeEach(async (to) => {
    const authStore = useAuthStore()
    const tenantStore = useTenantStore()

    // 1. Try to restore session if we have a token but no user
    if (authStore.accessToken && !authStore.user) {
      try {
        await authStore.fetchUser()
      } catch {
        // Token invalid, will redirect to login
      }
    }

    const requiresAuth = to.meta.requiresAuth !== false

    // 2. Smart root redirect
    if (to.name === 'root') {
      if (!authStore.isAuthenticated) {
        return { name: 'login' }
      }

      const memberships = authStore.user?.memberships ?? []

      // Platform user (superadmin / platform permissions) → always platform
      if (authStore.hasPlatformAccess) {
        return { name: 'platform' }
      }

      // Auto-select if exactly 1 membership
      if (memberships.length === 1) {
        if (tenantStore.tenants.length === 0) {
          await tenantStore.fetchTenants()
        }
        const tenant = tenantStore.tenants.find((t) => t.id === memberships[0].tenant_id)
        if (tenant?.is_provisioned) {
          await tenantStore.selectTenant(tenant)
          return { name: 'org-dashboard', params: { slug: tenant.slug } }
        }
      }

      // Default: welcome (org selection or empty state)
      return { name: 'welcome' }
    }

    // 3. Auth check
    if (requiresAuth && !authStore.isAuthenticated) {
      return { name: 'login' }
    }

    // 4. Redirect authenticated users away from login/register
    if (!requiresAuth && authStore.isAuthenticated && (to.name === 'login' || to.name === 'register')) {
      return { path: '/' }
    }

    // 5. Platform access check (superadmin only for admin routes)
    if (to.meta.requiresSuperAdmin && !authStore.user?.is_superadmin) {
      return { path: '/' }
    }

    // 6. Slug resolution for org routes
    if (to.meta.requiresTenant && to.path.startsWith(`${ORG}/`)) {
      const slug = to.params.slug as string | undefined

      if (!slug) {
        return { name: 'welcome' }
      }

      // Ensure tenants are loaded
      if (tenantStore.tenants.length === 0) {
        await tenantStore.fetchTenants()
      }

      // Resolve slug to tenant
      const tenant = tenantStore.findBySlug(slug)

      if (!tenant) {
        return { name: 'welcome' }
      }

      // Switch tenant if different one is currently selected
      if (tenantStore.currentTenantId !== tenant.id) {
        await tenantStore.selectTenant(tenant)
      }

      // Verify membership for non-platform users
      if (!authStore.hasPlatformAccess) {
        const memberTenantIds = authStore.user?.memberships?.map((m) => m.tenant_id) ?? []
        if (!memberTenantIds.includes(tenant.id)) {
          return { name: 'not-found' }
        }
      }

      // 7. Permission check for tenant routes
      const requiredPerms = to.meta.requiresAnyPermission as string[] | undefined
      if (requiredPerms && !authStore.user?.is_superadmin) {
        const membership = authStore.user?.memberships?.find((m) => m.tenant_id === tenant.id)
        const userPerms = new Set(membership?.permissions ?? [])
        if (!requiredPerms.some((p) => userPerms.has(p))) {
          return { name: 'not-found' }
        }
      }
    }
  })
}
