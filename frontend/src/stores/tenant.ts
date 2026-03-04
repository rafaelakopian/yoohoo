import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { orgsApi } from '@/api/platform/orgs'
import { fetchTeachers } from '@/api/tenant/members'
import { useAuthStore } from '@/stores/auth'
import type { Tenant, TenantSettings, Member } from '@/types/models'

export const useTenantStore = defineStore('tenant', () => {
  const tenants = ref<Tenant[]>([])
  const currentTenant = ref<Tenant | null>(null)
  const currentSettings = ref<TenantSettings | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Members cache (for dropdowns)
  const cachedTeachers = ref<Member[]>([])
  const teachersCacheSlug = ref<string | null>(null)

  const currentTenantId = computed(() => currentTenant.value?.id ?? null)
  const currentSlug = computed(() => currentTenant.value?.slug ?? null)
  const hasTenant = computed(() => !!currentTenant.value)

  const authStore = useAuthStore()

  /** Tenants where user is a full member (own orgs). */
  const myOrgs = computed(() => {
    const fullIds = authStore.user?.memberships
      ?.filter((m) => m.membership_type !== 'collaboration')
      .map((m) => m.tenant_id) ?? []
    return tenants.value.filter((t) => fullIds.includes(t.id) && t.is_provisioned)
  })

  /** Tenants where user is a collaborator. */
  const myCollaborations = computed(() => {
    const collabIds = authStore.user?.memberships
      ?.filter((m) => m.membership_type === 'collaboration')
      .map((m) => m.tenant_id) ?? []
    return tenants.value.filter((t) => collabIds.includes(t.id) && t.is_provisioned)
  })

  /** Whether the currently selected tenant is a collaboration workspace. */
  const isCurrentCollaboration = computed(() => {
    if (!currentTenant.value) return false
    const membership = authStore.user?.memberships?.find(
      (m) => m.tenant_id === currentTenant.value?.id,
    )
    return membership?.membership_type === 'collaboration'
  })

  async function restoreTenant() {
    const savedId = localStorage.getItem('tenant_id')
    if (!savedId || currentTenant.value) return

    // Try to find tenant in already-loaded list
    if (tenants.value.length > 0) {
      const found = tenants.value.find((t) => t.id === savedId)
      if (found) {
        currentTenant.value = found
        try {
          currentSettings.value = await orgsApi.getSettings(found.id)
        } catch {
          // Settings might not exist yet
        }
        return
      }
    }

    // Otherwise fetch tenant by ID
    try {
      const tenant = await orgsApi.get(savedId)
      currentTenant.value = tenant
      try {
        currentSettings.value = await orgsApi.getSettings(tenant.id)
      } catch {
        // Settings might not exist yet
      }
    } catch {
      // Saved tenant no longer valid
      localStorage.removeItem('tenant_id')
    }
  }

  async function fetchTenants() {
    loading.value = true
    error.value = null

    try {
      tenants.value = await orgsApi.list()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      error.value = err.response?.data?.detail ?? 'Failed to load tenants'
    } finally {
      loading.value = false
    }
  }

  function findBySlug(slug: string): Tenant | undefined {
    return tenants.value.find((t) => t.slug === slug)
  }

  async function selectTenant(tenant: Tenant) {
    currentTenant.value = tenant
    localStorage.setItem('tenant_id', tenant.id)
    localStorage.setItem('tenant_slug', tenant.slug)

    // Reset tenant-scoped stores to prevent data leakage between tenants
    const { useNotificationStore } = await import('@/stores/notification')
    useNotificationStore().resetState()

    try {
      currentSettings.value = await orgsApi.getSettings(tenant.id)
    } catch {
      // Settings might not exist yet
    }
  }

  async function createTenant(name: string, slug: string) {
    loading.value = true
    error.value = null

    try {
      const tenant = await orgsApi.create({ name, slug })
      tenants.value.push(tenant)
      return tenant
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      error.value = err.response?.data?.detail ?? 'Failed to create tenant'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function provisionTenant(id: string) {
    loading.value = true
    error.value = null

    try {
      const tenant = await orgsApi.provision(id)
      const idx = tenants.value.findIndex((t) => t.id === id)
      if (idx !== -1) tenants.value[idx] = tenant
      if (currentTenant.value?.id === id) currentTenant.value = tenant
      return tenant
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      error.value = err.response?.data?.detail ?? 'Failed to provision tenant'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteTenant(id: string, password: string) {
    loading.value = true
    error.value = null
    try {
      await orgsApi.delete(id, password)
      tenants.value = tenants.value.filter((t) => t.id !== id)
      if (currentTenant.value?.id === id) clearTenant()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      error.value = err.response?.data?.detail ?? 'Failed to delete tenant'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function getTeachers(): Promise<Member[]> {
    const slug = currentTenant.value?.slug
    if (!slug) return []

    // Return cached if same tenant
    if (teachersCacheSlug.value === slug && cachedTeachers.value.length > 0) {
      return cachedTeachers.value
    }

    try {
      cachedTeachers.value = await fetchTeachers()
      teachersCacheSlug.value = slug
    } catch {
      cachedTeachers.value = []
    }
    return cachedTeachers.value
  }

  function clearTeachersCache() {
    cachedTeachers.value = []
    teachersCacheSlug.value = null
  }

  function clearTenant() {
    currentTenant.value = null
    currentSettings.value = null
    clearTeachersCache()
    localStorage.removeItem('tenant_id')
    localStorage.removeItem('tenant_slug')
  }

  return {
    tenants,
    currentTenant,
    currentSettings,
    currentTenantId,
    currentSlug,
    loading,
    error,
    hasTenant,
    myOrgs,
    myCollaborations,
    isCurrentCollaboration,
    cachedTeachers,
    fetchTenants,
    restoreTenant,
    findBySlug,
    selectTenant,
    createTenant,
    provisionTenant,
    deleteTenant,
    clearTenant,
    getTeachers,
    clearTeachersCache,
  }
})
