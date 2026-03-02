<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Pencil, Trash2, UserPlus, UserMinus } from 'lucide-vue-next'
import { theme } from '@/theme'
import {
  adminApi,
  type AdminPermissionGroup,
  type AdminGroupUser,
  type ModulePermissions,
} from '@/api/platform/admin'
import BackLink from '@/components/ui/BackLink.vue'
import GroupFormModal, { type GroupFormData } from '@/components/ui/GroupFormModal.vue'
import IconButton from '@/components/ui/IconButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'

const route = useRoute()
const router = useRouter()
const tenantId = route.params.tenantId as string
const groupId = route.params.groupId as string

const group = ref<AdminPermissionGroup | null>(null)
const groupUsers = ref<AdminGroupUser[]>([])
const registry = ref<ModulePermissions[]>([])
const allUsers = ref<{ id: string; email: string; full_name: string }[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const showModal = ref(false)
const deleteModal = ref(false)
const assignEmail = ref('')
const assignError = ref<string | null>(null)
const removeUserModal = ref(false)
const removingUser = ref<AdminGroupUser | null>(null)

onMounted(async () => {
  await Promise.all([loadGroup(), loadRegistry(), loadUsers()])
  loading.value = false
})

async function loadGroup() {
  try {
    const groups = await adminApi.getTenantGroups(tenantId)
    group.value = groups.find((g) => g.id === groupId) ?? null
    if (!group.value) {
      error.value = 'Groep niet gevonden'
      return
    }
    groupUsers.value = await adminApi.getTenantGroupUsers(tenantId, groupId)
  } catch {
    error.value = 'Fout bij laden groep'
  }
}

async function loadRegistry() {
  try {
    const data = await adminApi.getPermissionRegistry()
    registry.value = data.modules
  } catch {
    // non-critical
  }
}

async function loadUsers() {
  try {
    const data = await adminApi.getUsers({ limit: 100 })
    allUsers.value = data.items.map((u) => ({ id: u.id, email: u.email, full_name: u.full_name }))
  } catch {
    // non-critical
  }
}

async function handleSave(data: GroupFormData) {
  try {
    await adminApi.updateTenantGroup(tenantId, groupId, {
      name: data.name,
      description: data.description,
      permissions: data.permissions,
    })
    showModal.value = false
    await loadGroup()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Fout bij opslaan'
  }
}

async function confirmDelete() {
  try {
    await adminApi.deleteTenantGroup(tenantId, groupId)
    router.push(`/platform/schools/${tenantId}/groups`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Fout bij verwijderen'
    deleteModal.value = false
  }
}

async function assignUser() {
  if (!assignEmail.value.trim()) return
  assignError.value = null

  const user = allUsers.value.find((u) => u.email === assignEmail.value.trim())
  if (!user) {
    assignError.value = 'Gebruiker niet gevonden'
    return
  }

  try {
    await adminApi.assignUserToTenantGroup(tenantId, groupId, user.id)
    assignEmail.value = ''
    groupUsers.value = await adminApi.getTenantGroupUsers(tenantId, groupId)
    const groups = await adminApi.getTenantGroups(tenantId)
    group.value = groups.find((g) => g.id === groupId) ?? group.value
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    assignError.value = err.response?.data?.detail ?? 'Fout bij toewijzen'
  }
}

function promptRemoveUser(user: AdminGroupUser) {
  removingUser.value = user
  removeUserModal.value = true
}

async function confirmRemoveUser() {
  if (!removingUser.value) return
  try {
    await adminApi.removeUserFromTenantGroup(tenantId, groupId, removingUser.value.user_id)
    removeUserModal.value = false
    removingUser.value = null
    groupUsers.value = await adminApi.getTenantGroupUsers(tenantId, groupId)
    const groups = await adminApi.getTenantGroups(tenantId)
    group.value = groups.find((g) => g.id === groupId) ?? group.value
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    assignError.value = err.response?.data?.detail ?? 'Fout bij verwijderen'
    removeUserModal.value = false
  }
}
</script>

<template>
  <div>
    <div v-if="loading" :class="theme.list.empty">
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <div v-else-if="error && !group" :class="theme.alert.error">{{ error }}</div>

    <template v-else-if="group">
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-3">
          <BackLink :to="`/platform/schools/${tenantId}/groups`" />
          <h2 :class="theme.text.h2">{{ group.name }}</h2>
        </div>
        <div class="flex gap-2">
          <button @click="showModal = true" :class="[theme.btn.secondarySm, 'flex items-center gap-1.5']">
            <Pencil :size="14" /> Bewerken
          </button>
          <button
            v-if="!group.is_default"
            @click="deleteModal = true"
            :class="theme.btn.dangerOutline"
          >
            <Trash2 :size="14" class="inline mr-1" /> Verwijderen
          </button>
        </div>
      </div>

      <div v-if="error" :class="[theme.alert.error, 'mb-4']">{{ error }}</div>

      <!-- Group info -->
      <div :class="[theme.card.padded, 'mb-6']">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <p class="text-xs text-body mb-1">Beschrijving</p>
            <p class="text-sm text-navy-900">{{ group.description || '—' }}</p>
          </div>
          <div>
            <p class="text-xs text-body mb-1">Slug</p>
            <p class="text-sm text-navy-900">{{ group.slug }}</p>
          </div>
          <div>
            <p class="text-xs text-body mb-1">Type</p>
            <span v-if="group.is_default" :class="[theme.badge.base, theme.badge.default]">Standaard</span>
            <span v-else class="text-sm text-navy-900">Aangepast</span>
          </div>
        </div>
      </div>

      <!-- Permissions -->
      <div :class="[theme.card.base, 'mb-6']">
        <div :class="theme.list.sectionHeader">
          <h3 :class="theme.text.h3">Rechten ({{ group.permissions.length }})</h3>
        </div>
        <div class="p-4">
          <div v-if="group.permissions.length === 0" :class="theme.text.body">Geen rechten toegekend.</div>
          <div v-else class="flex flex-wrap gap-1.5">
            <span v-for="perm in group.permissions" :key="perm" :class="[theme.badge.base, theme.badge.success]" class="text-[11px]">
              {{ perm }}
            </span>
          </div>
        </div>
      </div>

      <!-- Users -->
      <div :class="theme.card.base">
        <div :class="theme.list.sectionHeader">
          <h3 :class="theme.text.h3">Gebruikers ({{ groupUsers.length }})</h3>
        </div>
        <div class="p-4 border-b border-navy-100">
          <div class="flex gap-2">
            <input
              v-model="assignEmail"
              type="email"
              :class="[theme.form.input, 'flex-1']"
              placeholder="E-mailadres van gebruiker..."
              list="user-emails-tenant"
              @keyup.enter="assignUser"
            />
            <datalist id="user-emails-tenant">
              <option v-for="u in allUsers" :key="u.id" :value="u.email">{{ u.full_name }}</option>
            </datalist>
            <button @click="assignUser" :class="[theme.btn.primarySm, 'flex items-center gap-1.5']">
              <UserPlus :size="14" /> Toewijzen
            </button>
          </div>
          <p v-if="assignError" :class="theme.alert.errorInline">{{ assignError }}</p>
        </div>
        <div v-if="groupUsers.length === 0" :class="theme.list.empty">
          <p :class="theme.text.muted">Geen gebruikers in deze groep.</p>
        </div>
        <div v-else :class="theme.list.divider">
          <div v-for="u in groupUsers" :key="u.user_id" class="flex items-center justify-between px-6 py-3">
            <div>
              <p class="text-sm font-medium text-navy-900">{{ u.full_name }}</p>
              <p class="text-xs text-body">{{ u.email }}</p>
            </div>
            <IconButton variant="danger" title="Verwijderen uit groep" @click="promptRemoveUser(u)">
              <UserMinus :size="14" />
            </IconButton>
          </div>
        </div>
      </div>
    </template>

    <GroupFormModal :open="showModal" :editing-group="group" :registry="registry" @save="handleSave" @close="showModal = false" />
    <ConfirmModal :open="deleteModal" title="Groep verwijderen" :message="`Weet je zeker dat je '${group?.name ?? ''}' wilt verwijderen?`" confirm-label="Verwijderen" variant="danger" @confirm="confirmDelete" @cancel="deleteModal = false" />
    <ConfirmModal :open="removeUserModal" title="Gebruiker verwijderen" :message="`Weet je zeker dat je '${removingUser?.full_name ?? ''}' wilt verwijderen uit deze groep?`" confirm-label="Verwijderen" variant="danger" @confirm="confirmRemoveUser" @cancel="removeUserModal = false; removingUser = null" />
  </div>
</template>
