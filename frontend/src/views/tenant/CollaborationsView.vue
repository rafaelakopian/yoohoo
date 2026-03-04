<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Plus, ToggleLeft, ToggleRight } from 'lucide-vue-next'
import { theme } from '@/theme'
import { orgPath } from '@/router/routes'
import { collaborationsApi } from '@/api/tenant/collaborations'
import { permissionsApi } from '@/api/tenant/permissions'
import { useTenantStore } from '@/stores/tenant'
import { usePermissions } from '@/composables/usePermissions'
import { COLLABORATION_LABEL } from '@/constants/collaboration'
import RouteTabs from '@/components/ui/RouteTabs.vue'
import type { Collaborator, PermissionGroup } from '@/types/auth'

const { hasPermission } = usePermissions()
const tenantStore = useTenantStore()

const tenantTabs = [
  { label: 'Gebruikers', to: orgPath('users') },
  { label: COLLABORATION_LABEL, to: orgPath('collaborations') },
  { label: 'Groepen & Rechten', to: orgPath('permissions') },
]

const collaborators = ref<Collaborator[]>([])
const groups = ref<PermissionGroup[]>([])
const loading = ref(false)
const error = ref('')

// Invite modal
const showModal = ref(false)
const inviteEmail = ref('')
const inviteGroupId = ref<string>('')
const inviteCreating = ref(false)
const inviteError = ref('')

const canManage = computed(() => hasPermission('collaborations.manage'))

async function loadCollaborators() {
  loading.value = true
  error.value = ''
  try {
    collaborators.value = await collaborationsApi.list()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Fout bij laden van medewerkers'
  } finally {
    loading.value = false
  }
}

async function loadGroups() {
  try {
    const data = await permissionsApi.listGroups()
    groups.value = data
  } catch {
    // non-critical
  }
}

function openInviteModal() {
  inviteEmail.value = ''
  inviteGroupId.value = ''
  inviteError.value = ''
  showModal.value = true
}

async function sendInvite() {
  if (!inviteEmail.value.trim()) {
    inviteError.value = 'E-mailadres is verplicht.'
    return
  }
  inviteCreating.value = true
  inviteError.value = ''
  try {
    await collaborationsApi.invite({
      email: inviteEmail.value.trim(),
      group_id: inviteGroupId.value || null,
    })
    showModal.value = false
    await loadCollaborators()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    inviteError.value = err.response?.data?.detail ?? 'Fout bij uitnodigen'
  } finally {
    inviteCreating.value = false
  }
}

async function toggleCollaborator(membershipId: string) {
  try {
    const updated = await collaborationsApi.toggle(membershipId)
    const idx = collaborators.value.findIndex((c) => c.membership_id === membershipId)
    if (idx !== -1) collaborators.value[idx] = updated
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Fout bij wijzigen status'
  }
}

onMounted(() => {
  loadCollaborators()
  loadGroups()
})
</script>

<template>
  <div class="max-w-5xl mx-auto">
    <div class="flex items-center justify-between mb-4">
      <h2 :class="theme.text.h2">Toegangsbeheer</h2>
    </div>

    <RouteTabs :tabs="tenantTabs" />

    <div v-if="error" :class="[theme.alert.error, 'mb-4']">{{ error }}</div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <p :class="theme.text.muted">
        Beheer externe medewerkers die samenwerken met je organisatie.
      </p>
      <button v-if="canManage" @click="openInviteModal" :class="theme.btn.primary">
        <Plus :size="16" class="mr-1" />
        Medewerker uitnodigen
      </button>
    </div>

    <!-- Collaborators table -->
    <div v-if="loading" :class="theme.text.muted">Laden...</div>
    <div v-else-if="collaborators.length === 0" :class="[theme.card.padded, 'text-center']">
      <p :class="theme.text.muted">Nog geen externe medewerkers uitgenodigd.</p>
    </div>
    <div v-else :class="theme.card.base" class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-navy-100">
            <th class="text-left p-3 font-medium text-navy-600">Naam</th>
            <th class="text-left p-3 font-medium text-navy-600">E-mail</th>
            <th class="text-left p-3 font-medium text-navy-600">Groep</th>
            <th class="text-left p-3 font-medium text-navy-600">Status</th>
            <th v-if="canManage" class="text-right p-3 font-medium text-navy-600">Actie</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in collaborators"
            :key="c.membership_id"
            class="border-b border-navy-50 last:border-0"
          >
            <td class="p-3">{{ c.full_name }}</td>
            <td class="p-3 text-navy-500">{{ c.email }}</td>
            <td class="p-3">
              <span v-if="c.groups.length > 0">{{ c.groups.map(g => g.name).join(', ') }}</span>
              <span v-else class="text-navy-400">—</span>
            </td>
            <td class="p-3">
              <span
                :class="[theme.badge.base, c.is_active ? theme.badge.success : theme.badge.default]"
              >
                {{ c.is_active ? 'Actief' : 'Inactief' }}
              </span>
            </td>
            <td v-if="canManage" class="p-3 text-right">
              <button
                @click="toggleCollaborator(c.membership_id)"
                :class="theme.btn.ghost"
                :title="c.is_active ? 'Deactiveren' : 'Activeren'"
              >
                <ToggleRight v-if="c.is_active" :size="18" class="text-green-600" />
                <ToggleLeft v-else :size="18" class="text-navy-400" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Invite Modal -->
    <div
      v-if="showModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showModal = false"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h3 :class="[theme.text.h3, 'mb-4']">Medewerker uitnodigen</h3>

        <div class="space-y-4">
          <div>
            <label :class="theme.form.label">E-mailadres</label>
            <input
              v-model="inviteEmail"
              type="email"
              :class="theme.form.input"
              placeholder="medewerker@example.com"
            />
          </div>

          <div>
            <label :class="theme.form.label">Groep (optioneel)</label>
            <select v-model="inviteGroupId" :class="theme.form.input">
              <option value="">Standaard (Medewerker)</option>
              <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
            </select>
          </div>

          <p v-if="inviteError" :class="theme.alert.errorInline">{{ inviteError }}</p>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button @click="showModal = false" :class="theme.btn.secondary">Annuleren</button>
          <button @click="sendInvite" :class="theme.btn.primary" :disabled="inviteCreating">
            {{ inviteCreating ? 'Versturen...' : 'Uitnodigen' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
