import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { orgsApi } from '@/api/platform/orgs'
import { fetchTeachers } from '@/api/products/school/members'
import { featuresApi } from '@/api/products/school/features'
import { useAuthStore } from '@/stores/auth'
import type { Tenant, TenantSettings, Member } from '@/types/models'

export const useTenantStore = defineStore('tenant', () => {
  const tenants = ref<Tenant[]>([])
  const currentTenant = ref<Tenant | null>(null)
  const currentSettings = ref<TenantSettings | null>(null)
  const subscriptionStatus = ref<string | null>(null)
  const subscriptionPlanName = ref<string | null>(null)
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
        localStorage.setItem('tenant_slug', found.slug)
        try {
          currentSettings.value = await orgsApi.getSettings(found.id)
        } catch {
          // Settings might not exist yet
        }
        await fetchSubscriptionStatus()
        return
      }
    }

    // Otherwise fetch tenant by ID
    try {
      const tenant = await orgsApi.get(savedId)
      currentTenant.value = tenant
      localStorage.setItem('tenant_slug', tenant.slug)
      try {
        currentSettings.value = await orgsApi.getSettings(tenant.id)
      } catch {
        // Settings might not exist yet
      }
      await fetchSubscriptionStatus()
    } catch {
      // Saved tenant no longer valid
      localStorage.removeItem('tenant_id')
    }
  }

  // Deduplication: if a fetch is already in-flight, reuse the same promise
  let _fetchTenantsPromise: Promise<void> | null = null

  async function fetchTenants() {
    if (_fetchTenantsPromise) return _fetchTenantsPromise
    loading.value = true
    error.value = null

    _fetchTenantsPromise = (async () => {
      try {
        tenants.value = await orgsApi.list()
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } } }
        error.value = err.response?.data?.detail ?? 'Failed to load tenants'
      } finally {
        loading.value = false
        _fetchTenantsPromise = null
      }
    })()

    return _fetchTenantsPromise
  }

  function findBySlug(slug: string): Tenant | undefined {
    return tenants.value.find((t) => t.slug === slug)
  }

  let _fetchSubStatusPromise: Promise<void> | null = null

  async function fetchSubscriptionStatus() {
    if (_fetchSubStatusPromise) return _fetchSubStatusPromise

    _fetchSubStatusPromise = (async () => {
      try {
        const data = await featuresApi.getSubscriptionStatus()
        subscriptionStatus.value = data.status
        subscriptionPlanName.value = data.plan_name
      } catch {
        // Subscription status not critical — default to null (allow access)
        subscriptionStatus.value = null
        subscriptionPlanName.value = null
      } finally {
        _fetchSubStatusPromise = null
      }
    })()

    return _fetchSubStatusPromise
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

    // Fetch subscription status for access guard
    await fetchSubscriptionStatus()
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
    subscriptionStatus.value = null
    subscriptionPlanName.value = null
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
    subscriptionStatus,
    subscriptionPlanName,
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
    fetchSubscriptionStatus,
    createTenant,
    provisionTenant,
    deleteTenant,
    clearTenant,
    getTeachers,
    clearTeachersCache,
  }
})
