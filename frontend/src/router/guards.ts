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

    // 5. Clear tenant context when entering platform-only routes
    // (mirrors sidebar "Terug naar platform" behavior for all navigation paths)
    if ((to.meta.requiresPlatformAccess || to.meta.requiresSuperAdmin) && tenantStore.currentTenantId) {
      tenantStore.clearTenant()
    }

    // 5a. Platform access with permission-based routing
    if (to.meta.requiresPlatformAccess) {
      const user = authStore.user
      if (!user) return { name: 'login' }

      // Superadmin always has full platform access
      if (!user.is_superadmin) {
        // Non-superadmin with platform permissions
        if (authStore.hasPlatformAccess) {
          // Check specific permission if required on this route
          const requiredPerms = to.meta.requiresAnyPermission as string[] | undefined
          if (requiredPerms?.length) {
            const perms = new Set(user.platform_permissions ?? [])
            if (!requiredPerms.some((p) => perms.has(p))) {
              return { name: 'platform' }
            }
          }
        } else {
          return { path: '/' }
        }
      }
    }

    // 5b. Superadmin-only check (legacy, for routes not yet migrated to requiresPlatformAccess)
    if (to.meta.requiresSuperAdmin && !authStore.user?.is_superadmin) {
      return { path: '/' }
    }

    // 6. Subscription status check for tenant routes
    if (to.meta.requiresTenant && to.params.slug && tenantStore.subscriptionStatus) {
      const PAUSED_ALLOWED_ROUTES = [
        'org-billing', 'org-billing-invoices', 'org-billing-plans',
        'org-billing-students', 'org-upgrade', 'org-subscription-paused',
      ]
      const isInactive = ['paused', 'cancelled', 'expired'].includes(
        tenantStore.subscriptionStatus,
      )
      if (isInactive && !PAUSED_ALLOWED_ROUTES.includes(to.name as string)) {
        return { name: 'org-subscription-paused', params: { slug: to.params.slug } }
      }
    }

    // 7. Slug resolution for org routes
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

      // Verify membership for ALL users (including superadmin)
      // Superadmin must use impersonation to access tenant data
      const memberTenantIds = authStore.user?.memberships?.map((m) => m.tenant_id) ?? []
      if (!memberTenantIds.includes(tenant.id)) {
        return { name: 'not-found' }
      }

      // 7. Permission check for tenant routes
      const requiredPerms = to.meta.requiresAnyPermission as string[] | undefined
      if (requiredPerms) {
        const membership = authStore.user?.memberships?.find((m) => m.tenant_id === tenant.id)
        const userPerms = new Set(membership?.permissions ?? [])
        if (!requiredPerms.some((p) => userPerms.has(p))) {
          return { name: 'not-found' }
        }
      }
    }
  })
}
