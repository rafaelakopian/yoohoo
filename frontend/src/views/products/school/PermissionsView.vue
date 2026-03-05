<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Trash2, Users, Eye } from 'lucide-vue-next'
import { theme } from '@/theme'
import { orgPath } from '@/router/routes'
import { permissionsApi } from '@/api/products/school/permissions'
import type { PermissionGroup, ModulePermissions } from '@/types/auth'
import type { GroupFormData } from '@/components/ui/GroupFormModal.vue'
import GroupFormModal from '@/components/ui/GroupFormModal.vue'
import IconButton from '@/components/ui/IconButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import RouteTabs from '@/components/ui/RouteTabs.vue'
import { usePermissions } from '@/composables/usePermissions'
import { COLLABORATION_LABEL } from '@/constants/collaboration'

const { hasPermission } = usePermissions()

const tenantTabs = [
  { label: 'Gebruikers', to: orgPath('users') },
  { label: COLLABORATION_LABEL, to: orgPath('collaborations') },
  { label: 'Groepen & Rechten', to: orgPath('permissions') },
]

const router = useRouter()
const groups = ref<PermissionGroup[]>([])
const registry = ref<ModulePermissions[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const showModal = ref(false)
const deleteGroupModal = ref(false)
const deletingGroup = ref<PermissionGroup | null>(null)

onMounted(async () => {
  await Promise.all([loadGroups(), loadRegistry()])
})

async function loadGroups() {
  loading.value = true
  error.value = null
  try {
    groups.value = await permissionsApi.listGroups()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Fout bij laden groepen'
  } finally {
    loading.value = false
  }
}

async function loadRegistry() {
  try {
    const data = await permissionsApi.getRegistry()
    registry.value = data.modules
  } catch {
    // non-critical
  }
}

async function handleSave(data: GroupFormData) {
  try {
    await permissionsApi.createGroup({
      name: data.name,
      slug: data.slug,
      description: data.description || undefined,
      permissions: data.permissions,
    })
    showModal.value = false
    await loadGroups()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Fout bij aanmaken'
  }
}

function promptDeleteGroup(group: PermissionGroup) {
  deletingGroup.value = group
  deleteGroupModal.value = true
}

async function confirmDeleteGroup() {
  if (!deletingGroup.value) return
  try {
    await permissionsApi.deleteGroup(deletingGroup.value.id)
    deleteGroupModal.value = false
    deletingGroup.value = null
    await loadGroups()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Fout bij verwijderen'
    deleteGroupModal.value = false
  }
}
</script>

<template>
  <div class="p-6">
    <div class="mb-6">
      <h2 :class="theme.text.h2">Toegangsbeheer</h2>
    </div>

    <RouteTabs :tabs="tenantTabs" />

    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <div :class="theme.card.base">
      <div :class="theme.list.sectionHeader">
        <h3 :class="theme.text.h3">Groepen & Rechten</h3>
        <button v-if="hasPermission('org_settings.edit')" @click="showModal = true" :class="theme.btn.primarySm" class="flex items-center gap-1">
          <Plus :size="16" />
          Toevoegen
        </button>
      </div>
      <div v-if="loading" :class="theme.list.empty">
        <p :class="theme.text.muted">Laden...</p>
      </div>

      <div v-else-if="groups.length === 0" :class="theme.list.empty">
        <p :class="theme.text.muted">Nog geen groepen aangemaakt.</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-navy-100 text-left">
              <th class="px-6 py-3 font-medium text-navy-700">Groep</th>
              <th class="px-6 py-3 font-medium text-navy-700">Rechten</th>
              <th class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">Gebruikers</th>
              <th class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">Type</th>
              <th class="px-6 py-3 font-medium text-navy-700 text-right">Acties</th>
            </tr>
          </thead>
          <tbody :class="theme.list.divider">
            <tr
              v-for="group in groups"
              :key="group.id"
              class="hover:bg-surface transition-colors cursor-pointer"
              @click="router.push(orgPath(`permissions/${group.id}`))"
            >
              <td class="px-6 py-4">
                <div>
                  <p class="font-medium text-navy-900">{{ group.name }}</p>
                  <p v-if="group.description" class="text-xs text-body mt-0.5">{{ group.description }}</p>
                </div>
              </td>
              <td class="px-6 py-4 text-body">{{ group.permissions.length }}</td>
              <td class="px-6 py-4 hidden md:table-cell">
                <div class="flex items-center gap-1 text-body">
                  <Users :size="14" />
                  {{ group.user_count }}
                </div>
              </td>
              <td class="px-6 py-4 hidden md:table-cell">
                <span v-if="group.is_default" :class="[theme.badge.base, theme.badge.default]">Standaard</span>
                <span v-else class="text-body">Aangepast</span>
              </td>
              <td class="px-6 py-4">
                <div class="flex items-center justify-end gap-1">
                  <IconButton variant="accent" title="Details" @click.stop="router.push(orgPath(`permissions/${group.id}`))">
                    <Eye :size="16" />
                  </IconButton>
                  <IconButton v-if="!group.is_default && hasPermission('org_settings.edit')" variant="danger" title="Verwijderen" @click.stop="promptDeleteGroup(group)">
                    <Trash2 :size="16" />
                  </IconButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <ConfirmModal
      :open="deleteGroupModal"
      title="Groep verwijderen"
      :message="`Weet je zeker dat je '${deletingGroup?.name ?? ''}' wilt verwijderen?`"
      confirm-label="Verwijderen"
      variant="danger"
      @confirm="confirmDeleteGroup"
      @cancel="deleteGroupModal = false; deletingGroup = null"
    />

    <GroupFormModal :open="showModal" :editing-group="null" :registry="registry" @save="handleSave" @close="showModal = false" />
  </div>
</template>
