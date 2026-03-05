<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Search,
  Plus,
  Play,
  Trash2,
  Music,
  Eye,
  Shield,
  GraduationCap,
  Mail,
  UserCog,
} from 'lucide-vue-next'
import { theme } from '@/theme'
import { adminApi, type AdminTenantItem, type AdminTenantDetail, type AdminMembershipInfo } from '@/api/platform/admin'
import { orgsApi } from '@/api/platform/orgs'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { usePermissions } from '@/composables/usePermissions'
import type { Tenant } from '@/types/models'
import IconButton from '@/components/ui/IconButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'

const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()
const { hasPermission } = usePermissions()

const canViewOrgs = computed(() => hasPermission('platform.view_orgs'))
const canManageOrgs = computed(() => hasPermission('platform.manage_orgs'))

// Unified list — admin gets extra fields, non-admin gets basic Tenant objects
const tenants = ref<AdminTenantItem[]>([])
const loading = ref(true)
const searchQuery = ref('')
const error = ref('')

const showCreateForm = ref(false)
const newTenantName = ref('')
const newTenantSlug = ref('')
const createError = ref('')

const deleteModal = ref(false)
const deletingTenant = ref<AdminTenantItem | null>(null)
const deleteError = ref('')

// Owner transfer
const ownerModal = ref(false)
const ownerTenant = ref<AdminTenantItem | null>(null)
const ownerMembers = ref<AdminMembershipInfo[]>([])
const ownerSelectedId = ref<string>('')
const ownerLoading = ref(false)
const ownerError = ref('')

const filteredTenants = computed(() => {
  if (!searchQuery.value) return tenants.value
  const q = searchQuery.value.toLowerCase()
  return tenants.value.filter(
    (t) => t.name.toLowerCase().includes(q) || t.slug.toLowerCase().includes(q)
  )
})

onMounted(async () => {
  await fetchTenants()

  // Non-admin with exactly 1 provisioned org → auto-select
  if (!canViewOrgs.value) {
    const selectable = tenants.value.filter((t) => t.is_provisioned)
    if (selectable.length === 1) {
      await handleSelect(selectable[0])
    }
  }
})

async function fetchTenants() {
  loading.value = true
  try {
    if (canViewOrgs.value) {
      // Admin: use admin API for extra info (owner, member count)
      tenants.value = await adminApi.getTenants()
    } else {
      // Non-admin: use regular API, map to same shape
      const list = await orgsApi.list()
      tenants.value = list.map((t) => ({
        ...t,
        owner_name: null,
        member_count: 0,
      }))
    }
  } catch {
    error.value = 'Kon organisaties niet laden'
  } finally {
    loading.value = false
  }
}

function generateSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

function onNameInput() {
  newTenantSlug.value = generateSlug(newTenantName.value)
}

async function createTenant() {
  createError.value = ''
  try {
    await orgsApi.create({
      name: newTenantName.value,
      slug: newTenantSlug.value,
    })
    showCreateForm.value = false
    newTenantName.value = ''
    newTenantSlug.value = ''
    await fetchTenants()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    createError.value = err.response?.data?.detail ?? 'Aanmaken mislukt'
  }
}

async function handleProvision(tenantId: string) {
  try {
    await orgsApi.provision(tenantId)
    await fetchTenants()
  } catch {
    // Handled silently
  }
}

function handleDelete(tenant: AdminTenantItem) {
  deletingTenant.value = tenant
  deleteError.value = ''
  deleteModal.value = true
}

async function confirmDelete(password: string) {
  if (!deletingTenant.value) return

  deleteError.value = ''
  try {
    await orgsApi.delete(deletingTenant.value.id, password)
    deleteModal.value = false
    deletingTenant.value = null
    await fetchTenants()
  } catch (e: unknown) {
    const err = e as { response?: { status?: number } }
    if (err.response?.status === 401) {
      deleteError.value = 'Wachtwoord onjuist'
    } else {
      deleteModal.value = false
      deletingTenant.value = null
    }
  }
}

async function openOwnerModal(tenant: AdminTenantItem) {
  ownerTenant.value = tenant
  ownerMembers.value = []
  ownerSelectedId.value = ''
  ownerError.value = ''
  ownerLoading.value = true
  ownerModal.value = true
  try {
    const detail = await adminApi.getTenantDetail(tenant.id)
    ownerMembers.value = detail.memberships.filter(m => m.is_active)
  } catch {
    ownerError.value = 'Kon leden niet laden'
  } finally {
    ownerLoading.value = false
  }
}

async function confirmTransferOwnership() {
  if (!ownerTenant.value || !ownerSelectedId.value) return
  ownerError.value = ''
  try {
    const result = await adminApi.transferOwnership(ownerTenant.value.id, ownerSelectedId.value)
    ownerTenant.value.owner_name = result.owner_name
    ownerModal.value = false
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ownerError.value = err.response?.data?.detail ?? 'Fout bij overdragen eigenaarschap'
  }
}

async function goToInvitations(tenant: AdminTenantItem) {
  await tenantStore.fetchTenants()
  const t = tenantStore.tenants.find((t) => t.id === tenant.id)
  if (t) {
    await tenantStore.selectTenant(t)
    router.push(`/org/${t.slug}/users`)
  }
}

async function handleSelect(tenant: AdminTenantItem) {
  await tenantStore.fetchTenants()
  const t = tenantStore.tenants.find((t) => t.id === tenant.id)
  if (t) {
    await tenantStore.selectTenant(t)
    router.push(`/org/${t.slug}/dashboard`)
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('nl-NL', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}
</script>

<template>
  <div>
    <div v-if="canViewOrgs || tenants.length > 0" class="mb-6">
      <div class="flex items-center gap-3">
        <h2 :class="theme.text.h2">{{ canViewOrgs ? 'Organisaties' : 'Uw organisaties' }}</h2>
        <button
          v-if="canManageOrgs"
          @click="showCreateForm = !showCreateForm"
          :class="theme.btn.addInline"
        >
          <span :class="theme.btn.addInlineIcon"><Plus :size="14" /></span>
          Toevoegen
        </button>
      </div>
      <p :class="[theme.text.body, 'mt-1']">
        {{ canViewOrgs ? 'Beheer alle organisaties op het platform' : 'Selecteer een organisatie om mee te werken' }}
      </p>
    </div>

    <!-- Create form (manage permission required) -->
    <div v-if="showCreateForm && canManageOrgs" :class="[theme.card.padded, 'mb-6']">
      <form @submit.prevent="createTenant" class="flex flex-col md:flex-row gap-4 md:items-end">
        <div class="flex-1">
          <label :class="theme.form.label">Naam</label>
          <input
            v-model="newTenantName"
            @input="onNameInput"
            type="text"
            required
            :class="theme.form.input"
            placeholder="Muziekschool Amsterdam (voorbeeld)"
          />
        </div>
        <div class="flex-1">
          <label :class="theme.form.label">Slug</label>
          <input
            v-model="newTenantSlug"
            type="text"
            required
            pattern="[a-z0-9][-a-z0-9]*[a-z0-9]"
            :class="theme.form.input"
            placeholder="muziekschool-amsterdam"
          />
        </div>
        <button type="submit" :class="['px-6', theme.btn.primarySm]">
          Aanmaken
        </button>
      </form>
      <div v-if="createError" :class="theme.alert.errorInline">{{ createError }}</div>
    </div>

    <!-- Loading state for non-admin -->
    <div v-if="loading && !canViewOrgs" :class="theme.list.empty">
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <!-- Empty state for non-admin users with no orgs -->
    <div v-else-if="!loading && tenants.length === 0 && !canViewOrgs" :class="theme.card.form">
      <div class="flex flex-col items-center gap-4 text-center">
        <div class="w-16 h-16 rounded-full bg-navy-50 flex items-center justify-center">
          <Mail :size="32" class="text-navy-600" />
        </div>
        <div>
          <h3 :class="[theme.text.h3, 'mb-2']">Nog geen organisatie gekoppeld</h3>
          <p :class="[theme.text.body, 'max-w-md']">
            Je bent nog niet uitgenodigd voor een organisatie.
            Vraag een beheerder om je een uitnodiging te sturen via e-mail.
          </p>
        </div>
        <router-link to="/auth/account" :class="[theme.btn.primary, 'mt-2']">
          Mijn Profiel Beheren
        </router-link>
      </div>
    </div>

    <!-- Search (only when there are orgs or user has view permission) -->
    <div v-if="tenants.length > 0 || canViewOrgs" :class="[theme.card.base, 'mb-4']">
      <div class="p-4">
        <div class="relative">
          <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-body" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Zoek op naam of slug..."
            :class="[theme.form.input, 'pl-10']"
          />
        </div>
      </div>
    </div>

    <!-- Schools table -->
    <div v-if="tenants.length > 0 || canViewOrgs" :class="theme.card.base">
      <div v-if="loading" :class="theme.list.empty">
        <p :class="theme.text.muted">Laden...</p>
      </div>

      <div v-else-if="filteredTenants.length === 0" :class="theme.list.empty">
        <div class="flex flex-col items-center gap-4 py-4">
          <div class="w-16 h-16 rounded-full bg-navy-50 flex items-center justify-center">
            <GraduationCap :size="32" class="text-navy-600" />
          </div>
          <div>
            <p :class="[theme.text.h4, 'mb-1']">Geen organisaties gevonden</p>
            <p :class="theme.text.muted">
              {{ canViewOrgs ? 'Maak uw eerste organisatie aan om te beginnen.' : 'Geen resultaten voor uw zoekopdracht.' }}
            </p>
          </div>
        </div>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-navy-100 text-left">
              <th class="px-6 py-3 font-medium text-navy-700">Organisatie</th>
              <th class="px-6 py-3 font-medium text-navy-700">Status</th>
              <th v-if="canViewOrgs" class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">Eigenaar</th>
              <th v-if="canViewOrgs" class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">Leden</th>
              <th v-if="canViewOrgs" class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">Aangemaakt</th>
              <th class="px-6 py-3 font-medium text-navy-700 text-right">Acties</th>
            </tr>
          </thead>
          <tbody :class="theme.list.divider">
            <tr v-for="tenant in filteredTenants" :key="tenant.id" class="hover:bg-surface transition-colors">
              <td class="px-6 py-4">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-lg bg-primary-50 flex items-center justify-center flex-shrink-0">
                    <Music :size="14" class="text-primary-600" />
                  </div>
                  <div>
                    <p :class="theme.text.h4">{{ tenant.name }}</p>
                    <p class="text-xs text-body">{{ tenant.slug }}</p>
                  </div>
                </div>
              </td>
              <td class="px-6 py-4">
                <span
                  :class="[
                    theme.badge.base,
                    tenant.is_provisioned ? theme.badge.success : theme.badge.warning
                  ]"
                >
                  {{ tenant.is_provisioned ? 'Actief' : 'Niet ingericht' }}
                </span>
              </td>
              <td v-if="canViewOrgs" class="px-6 py-4 hidden md:table-cell">
                <button
                  v-if="canManageOrgs"
                  class="text-body hover:text-accent-700 transition-colors underline decoration-dotted underline-offset-2 cursor-pointer"
                  @click="openOwnerModal(tenant)"
                >{{ tenant.owner_name ?? 'Geen eigenaar' }}</button>
                <span v-else class="text-body">{{ tenant.owner_name ?? '-' }}</span>
              </td>
              <td v-if="canViewOrgs" class="px-6 py-4 text-body hidden md:table-cell">{{ tenant.member_count }}</td>
              <td v-if="canViewOrgs" class="px-6 py-4 text-body hidden md:table-cell">{{ formatDate(tenant.created_at) }}</td>
              <td class="px-6 py-4">
                <div class="flex items-center justify-end gap-1">
                  <IconButton
                    v-if="!tenant.is_provisioned && canManageOrgs"
                    variant="accent"
                    title="Inrichten"
                    @click="handleProvision(tenant.id)"
                  >
                    <Play :size="16" />
                  </IconButton>
                  <IconButton
                    v-if="tenant.is_provisioned"
                    variant="accent"
                    title="Naar organisatie"
                    @click="handleSelect(tenant)"
                  >
                    <Eye :size="16" />
                  </IconButton>
                  <IconButton
                    v-if="tenant.is_provisioned && canViewOrgs"
                    variant="accent"
                    title="Groepen beheren"
                    @click="router.push(`/platform/orgs/${tenant.id}/groups`)"
                  >
                    <Shield :size="16" />
                  </IconButton>
                  <IconButton
                    v-if="canManageOrgs"
                    variant="danger"
                    title="Verwijderen"
                    @click="handleDelete(tenant)"
                  >
                    <Trash2 :size="16" />
                  </IconButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Owner transfer modal -->
    <Teleport to="body">
      <div v-if="ownerModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30" @click.self="ownerModal = false">
        <div class="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
          <h3 :class="theme.text.h3" class="mb-4">Eigenaar wijzigen</h3>
          <p :class="[theme.text.body, 'mb-4']">
            Selecteer een lid van <strong>{{ ownerTenant?.name }}</strong> als nieuwe eigenaar.
          </p>

          <div v-if="ownerError" :class="[theme.alert.error, 'mb-4']">{{ ownerError }}</div>

          <div v-if="ownerLoading" :class="theme.text.muted" class="py-4 text-center">Laden...</div>

          <div v-else-if="ownerMembers.length === 0" class="py-4 text-center space-y-3">
            <p :class="theme.text.muted">Geen leden gevonden.</p>
            <button
              v-if="ownerTenant?.is_provisioned"
              :class="theme.btn.primarySm"
              class="inline-flex items-center gap-1"
              @click="ownerModal = false; goToInvitations(ownerTenant!)"
            >
              <Plus :size="14" />
              Gebruiker uitnodigen
            </button>
          </div>

          <div v-else class="space-y-4">
            <div>
              <label :class="theme.form.label">Nieuwe eigenaar</label>
              <select v-model="ownerSelectedId" :class="theme.form.input">
                <option value="" disabled>Selecteer een lid...</option>
                <option v-for="m in ownerMembers" :key="m.user_id" :value="m.user_id">
                  {{ m.full_name }} ({{ m.email }})
                </option>
              </select>
            </div>

            <div class="flex gap-3 justify-end">
              <button type="button" @click="ownerModal = false" :class="theme.btn.link">Annuleren</button>
              <button
                :disabled="!ownerSelectedId"
                @click="confirmTransferOwnership"
                :class="theme.btn.primary"
              >Overdragen</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <ConfirmModal
      :open="deleteModal"
      title="Organisatie verwijderen"
      :message="
        deletingTenant?.is_provisioned
          ? `De organisatie '${deletingTenant?.name}' en de bijbehorende database met alle gegevens worden permanent verwijderd.`
          : `De organisatie '${deletingTenant?.name}' wordt verwijderd.`
      "
      confirm-label="Verwijderen"
      variant="danger"
      require-confirm-check
      :require-password="deletingTenant?.is_provisioned ?? false"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="deleteModal = false; deleteError = ''"
    />
  </div>
</template>
