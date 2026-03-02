import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'

export function usePermissions() {
  const authStore = useAuthStore()
  const tenantStore = useTenantStore()

  const currentMembership = computed(() => {
    if (!authStore.user?.memberships || !tenantStore.currentTenantId) return null
    return authStore.user.memberships.find(
      (m) => m.tenant_id === tenantStore.currentTenantId
    ) ?? null
  })

  const effectivePermissions = computed<Set<string>>(() => {
    if (authStore.user?.is_superadmin) {
      // Superadmin has all permissions — return empty set, checks bypass via isSuperAdmin
      return new Set<string>()
    }
    const platformPerms = authStore.user?.platform_permissions ?? []
    const tenantPerms = currentMembership.value?.permissions ?? []
    return new Set([...platformPerms, ...tenantPerms])
  })

  const currentGroups = computed(() => {
    return currentMembership.value?.groups ?? []
  })

  function hasPermission(permission: string): boolean {
    if (authStore.user?.is_superadmin) return true
    return effectivePermissions.value.has(permission)
  }

  function hasAnyPermission(...permissions: string[]): boolean {
    if (authStore.user?.is_superadmin) return true
    return permissions.some((p) => effectivePermissions.value.has(p))
  }

  function hasAllPermissions(...permissions: string[]): boolean {
    if (authStore.user?.is_superadmin) return true
    return permissions.every((p) => effectivePermissions.value.has(p))
  }

  return {
    currentMembership,
    effectivePermissions,
    currentGroups,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
  }
}
