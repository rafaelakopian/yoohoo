<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Pencil, Trash2, Users, Eye } from 'lucide-vue-next'
import { theme } from '@/theme'
import {
  adminApi,
  type AdminPermissionGroup,
  type ModulePermissions,
} from '@/api/platform/admin'
import type { GroupFormData } from '@/components/ui/GroupFormModal.vue'
import GroupFormModal from '@/components/ui/GroupFormModal.vue'
import IconButton from '@/components/ui/IconButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import RouteTabs from '@/components/ui/RouteTabs.vue'

const platformTabs = [
  { label: 'Gebruikers', to: '/platform/users' },
  { label: 'Groepen', to: '/platform/groups' },
]

const router = useRouter()
const groups = ref<AdminPermissionGroup[]>([])
const registry = ref<ModulePermissions[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

// Create modal
const showModal = ref(false)

// Delete
const deleteGroupModal = ref(false)
const deletingGroup = ref<AdminPermissionGroup | null>(null)

onMounted(async () => {
  await Promise.all([loadGroups(), loadRegistry()])
})

async function loadGroups() {
  loading.value = true
  error.value = null
  try {
    groups.value = await adminApi.getPlatformGroups()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Fout bij laden groepen'
  } finally {
    loading.value = false
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

function openCreate() {
  showModal.value = true
}

async function handleSave(data: GroupFormData) {
  try {
    await adminApi.createPlatformGroup({
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

function promptDeleteGroup(group: AdminPermissionGroup) {
  deletingGroup.value = group
  deleteGroupModal.value = true
}

async function confirmDeleteGroup() {
  if (!deletingGroup.value) return
  try {
    await adminApi.deletePlatformGroup(deletingGroup.value.id)
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
  <div>
    <!-- Header -->
    <div class="mb-6">
      <div class="flex items-center gap-3">
        <h2 :class="theme.text.h2">Toegangsbeheer</h2>
        <button @click="openCreate" :class="theme.btn.addInline">
          <span :class="theme.btn.addInlineIcon"><Plus :size="14" /></span>
          Toevoegen
        </button>
      </div>
    </div>

    <RouteTabs :tabs="platformTabs" />

    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <!-- Groups table -->
    <div :class="theme.card.base">
      <div v-if="loading" :class="theme.list.empty">
        <p :class="theme.text.muted">Laden...</p>
      </div>

      <div v-else-if="groups.length === 0" :class="theme.list.empty">
        <p :class="theme.text.muted">Nog geen platform groepen aangemaakt.</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-navy-100 text-left">
              <th class="px-6 py-3 font-medium text-navy-700">Groep</th>
              <th class="px-6 py-3 font-medium text-navy-700">Rechten</th>
              <th class="px-6 py-3 font-medium text-navy-700">Gebruikers</th>
              <th class="px-6 py-3 font-medium text-navy-700">Type</th>
              <th class="px-6 py-3 font-medium text-navy-700 text-right">Acties</th>
            </tr>
          </thead>
          <tbody :class="theme.list.divider">
            <tr
              v-for="group in groups"
              :key="group.id"
              class="hover:bg-surface transition-colors cursor-pointer"
              @click="router.push(`/platform/groups/${group.id}`)"
            >
              <td class="px-6 py-4">
                <div>
                  <p class="font-medium text-navy-900">{{ group.name }}</p>
                  <p v-if="group.description" class="text-xs text-body mt-0.5">{{ group.description }}</p>
                </div>
              </td>
              <td class="px-6 py-4 text-body">{{ group.permissions.length }}</td>
              <td class="px-6 py-4">
                <div class="flex items-center gap-1 text-body">
                  <Users :size="14" />
                  {{ group.user_count }}
                </div>
              </td>
              <td class="px-6 py-4">
                <span v-if="group.is_default" :class="[theme.badge.base, theme.badge.default]">Standaard</span>
                <span v-else class="text-body">Aangepast</span>
              </td>
              <td class="px-6 py-4">
                <div class="flex items-center justify-end gap-1">
                  <IconButton variant="accent" title="Details" @click.stop="router.push(`/platform/groups/${group.id}`)">
                    <Eye :size="16" />
                  </IconButton>
                  <IconButton
                    v-if="!group.is_default"
                    variant="danger"
                    title="Verwijderen"
                    @click.stop="promptDeleteGroup(group)"
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

    <!-- Delete group confirmation -->
    <ConfirmModal
      :open="deleteGroupModal"
      title="Groep verwijderen"
      :message="`Weet je zeker dat je de groep '${deletingGroup?.name ?? ''}' wilt verwijderen? Alle gebruikerskoppelingen aan deze groep worden ook verwijderd.`"
      confirm-label="Verwijderen"
      variant="danger"
      @confirm="confirmDeleteGroup"
      @cancel="deleteGroupModal = false; deletingGroup = null"
    />

    <!-- Create modal -->
    <GroupFormModal
      :open="showModal"
      :editing-group="null"
      :registry="registry"
      @save="handleSave"
      @close="showModal = false"
    />
  </div>
</template>
