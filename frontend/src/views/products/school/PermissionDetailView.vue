<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Pencil, Trash2, UserMinus } from 'lucide-vue-next'
import { theme } from '@/theme'
import { orgPath } from '@/router/routes'
import { permissionsApi, type GroupUser } from '@/api/products/school/permissions'
import { membersApi } from '@/api/products/school/members'
import type { Member } from '@/types/school'
import type { PermissionGroup } from '@/types/auth'
import BackLink from '@/components/ui/BackLink.vue'
import SkeletonLoader from '@/components/shared/SkeletonLoader.vue'
import GroupFormModal, { type GroupFormData } from '@/components/ui/GroupFormModal.vue'
import IconButton from '@/components/ui/IconButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import { usePermissions } from '@/composables/usePermissions'
import { usePermissionRegistry } from '@/composables/usePermissionRegistry'

const { hasPermission } = usePermissions()

const route = useRoute()
const router = useRouter()
const groupId = route.params.groupId as string

const { registry, load: loadRegistry } = usePermissionRegistry()
const group = ref<PermissionGroup | null>(null)
const groupUsers = ref<GroupUser[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const showModal = ref(false)
const deleteModal = ref(false)
const assignError = ref<string | null>(null)
const removeUserModal = ref(false)
const removingUser = ref<GroupUser | null>(null)

// Member search for user assignment
const memberQuery = ref('')
const memberSearchResults = ref<Member[]>([])
const searching = ref(false)
let searchTimeout: ReturnType<typeof setTimeout> | null = null

watch(memberQuery, (val) => {
  if (searchTimeout) clearTimeout(searchTimeout)
  if (val.length < 2) {
    memberSearchResults.value = []
    return
  }
  searchTimeout = setTimeout(async () => {
    searching.value = true
    try {
      const resp = await membersApi.list({ q: val, limit: 10 })
      memberSearchResults.value = resp.items
    } finally {
      searching.value = false
    }
  }, 300)
})

onMounted(async () => {
  await Promise.all([loadGroup(), loadRegistry()])
  loading.value = false
})

async function loadGroup() {
  try {
    group.value = await permissionsApi.getGroup(groupId)
    groupUsers.value = await permissionsApi.listGroupUsers(groupId)
  } catch {
    error.value = 'Groep niet gevonden'
  }
}

async function handleSave(data: GroupFormData) {
  try {
    await permissionsApi.updateGroup(groupId, {
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
    await permissionsApi.deleteGroup(groupId)
    router.push(orgPath('permissions'))
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Fout bij verwijderen'
    deleteModal.value = false
  }
}

async function assignUser(userId: string) {
  if (!userId) return
  assignError.value = null
  try {
    await permissionsApi.assignUser(groupId, userId)
    memberQuery.value = ''
    memberSearchResults.value = []
    group.value = await permissionsApi.getGroup(groupId)
    groupUsers.value = await permissionsApi.listGroupUsers(groupId)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    assignError.value = err.response?.data?.detail ?? 'Fout bij toewijzen'
  }
}

function promptRemoveUser(user: GroupUser) {
  removingUser.value = user
  removeUserModal.value = true
}

async function confirmRemoveUser() {
  if (!removingUser.value) return
  try {
    await permissionsApi.removeUser(groupId, removingUser.value.user_id)
    removeUserModal.value = false
    removingUser.value = null
    group.value = await permissionsApi.getGroup(groupId)
    groupUsers.value = await permissionsApi.listGroupUsers(groupId)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    assignError.value = err.response?.data?.detail ?? 'Fout bij verwijderen'
    removeUserModal.value = false
  }
}
</script>

<template>
  <div>
    <SkeletonLoader v-if="loading" variant="list" :rows="6" />

    <div v-else-if="error && !group" :class="theme.alert.error">{{ error }}</div>

    <template v-else-if="group">
      <div :class="theme.pageHeader.rowResponsive" class="fade-in-up">
        <div class="flex items-center gap-3">
          <BackLink :to="orgPath('permissions')" />
          <h2 :class="theme.text.h2">{{ group.name }}</h2>
        </div>
        <div v-if="hasPermission('org_settings.edit')" class="flex gap-2">
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

        <!-- Assign user form -->
        <div v-if="hasPermission('org_settings.edit')" class="p-4 border-b border-navy-100">
          <div class="relative">
            <input
              v-model="memberQuery"
              type="text"
              :class="[theme.form.input, 'w-full']"
              placeholder="Zoek op naam of e-mailadres..."
              autocomplete="off"
            />

            <!-- Backdrop -->
            <div
              v-if="memberSearchResults.length > 0"
              class="fixed inset-0 z-40"
              @click="memberSearchResults = []"
            />

            <!-- Dropdown -->
            <Transition
              enter-active-class="transition duration-150 ease-out"
              enter-from-class="opacity-0 scale-95 -translate-y-1"
              enter-to-class="opacity-100 scale-100 translate-y-0"
              leave-active-class="transition duration-100 ease-in"
              leave-from-class="opacity-100 scale-100 translate-y-0"
              leave-to-class="opacity-0 scale-95 -translate-y-1"
            >
              <div
                v-if="memberSearchResults.length > 0"
                class="absolute left-0 right-0 mt-1 bg-white rounded-lg shadow-lg
                       border border-navy-100 py-1 z-50 overflow-hidden"
              >
                <button
                  v-for="result in memberSearchResults"
                  :key="result.user_id"
                  class="w-full text-left px-4 py-2.5 text-sm hover:bg-surface
                         transition-colors flex items-center gap-2"
                  @click="assignUser(result.user_id)"
                >
                  <span :class="theme.text.h4">{{ result.full_name }}</span>
                  <span v-if="result.email" :class="theme.text.muted">{{ result.email }}</span>
                </button>
              </div>
            </Transition>
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
            <IconButton v-if="hasPermission('org_settings.edit')" variant="danger" title="Verwijderen uit groep" @click="promptRemoveUser(u)">
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
