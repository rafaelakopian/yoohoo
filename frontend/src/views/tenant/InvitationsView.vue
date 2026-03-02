<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus, RefreshCw, X } from 'lucide-vue-next'
import IconButton from '@/components/ui/IconButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import { invitationsApi } from '@/api/tenant/invitations'
import type { InvitationWithStatus, BulkInvitationResponse } from '@/api/tenant/invitations'
import { permissionsApi } from '@/api/tenant/permissions'
import { useTenantStore } from '@/stores/tenant'
import { theme } from '@/theme'
import { orgPath } from '@/router/routes'
import RouteTabs from '@/components/ui/RouteTabs.vue'
import type { PermissionGroup } from '@/types/auth'
import { usePermissions } from '@/composables/usePermissions'

const { hasPermission } = usePermissions()

import { COLLABORATION_LABEL } from '@/constants/collaboration'

const tenantTabs = [
  { label: 'Gebruikers', to: orgPath('users') },
  { label: COLLABORATION_LABEL, to: orgPath('collaborations') },
  { label: 'Groepen & Rechten', to: orgPath('permissions') },
]

const tenantStore = useTenantStore()

const invitations = ref<InvitationWithStatus[]>([])
const groups = ref<PermissionGroup[]>([])
const loading = ref(false)
const error = ref('')

// Status filter
const statusFilter = ref<string>('pending')
const statusOptions = [
  { value: 'pending', label: 'Openstaand' },
  { value: 'accepted', label: 'Geaccepteerd' },
  { value: 'revoked', label: 'Ingetrokken' },
  { value: 'expired', label: 'Verlopen' },
]

// Invite modal (unified single + bulk)
const showModal = ref(false)
const inviteEmails = ref('')
const inviteGroupId = ref<string>('')
const inviteCreating = ref(false)
const inviteError = ref('')
const inviteResult = ref<BulkInvitationResponse | null>(null)

function openInviteModal() {
  inviteEmails.value = ''
  inviteError.value = ''
  inviteResult.value = null
  showModal.value = true
}

function closeInviteModal() {
  showModal.value = false
  inviteResult.value = null
  inviteError.value = ''
}

async function loadInvitations() {
  if (!tenantStore.currentTenant) return
  loading.value = true
  error.value = ''
  try {
    invitations.value = await invitationsApi.list(
      tenantStore.currentTenant.id,
      statusFilter.value || undefined
    )
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Kon uitnodigingen niet laden'
  } finally {
    loading.value = false
  }
}

async function loadGroups() {
  try {
    groups.value = await permissionsApi.listGroups()
    if (groups.value.length > 0 && !inviteGroupId.value) {
      inviteGroupId.value = groups.value[0].id
    }
  } catch {
    // non-critical
  }
}

async function handleInvite() {
  if (!tenantStore.currentTenant) return
  inviteError.value = ''
  inviteResult.value = null

  const emails = inviteEmails.value
    .split('\n')
    .map(e => e.trim())
    .filter(e => e.length > 0)

  if (emails.length === 0) {
    inviteError.value = 'Vul minimaal één e-mailadres in'
    return
  }
  if (emails.length > 50) {
    inviteError.value = 'Maximaal 50 e-mailadressen per keer'
    return
  }

  inviteCreating.value = true
  try {
    inviteResult.value = await invitationsApi.createBulk(
      tenantStore.currentTenant.id,
      emails,
      inviteGroupId.value || null
    )
    if (inviteResult.value.failed === 0) {
      closeInviteModal()
    }
    await loadInvitations()
  } catch (e: any) {
    inviteError.value = e.response?.data?.detail || 'Fout bij versturen uitnodigingen'
  } finally {
    inviteCreating.value = false
  }
}

async function handleResend(id: string) {
  if (!tenantStore.currentTenant) return
  try {
    await invitationsApi.resend(tenantStore.currentTenant.id, id)
    await loadInvitations()
  } catch {
    // silent
  }
}

// Revoke confirmation
const revokeModal = ref(false)
const revokingId = ref<string | null>(null)

function promptRevoke(id: string) {
  revokingId.value = id
  revokeModal.value = true
}

async function confirmRevoke() {
  if (!tenantStore.currentTenant || !revokingId.value) return
  try {
    await invitationsApi.revoke(tenantStore.currentTenant.id, revokingId.value)
    invitations.value = invitations.value.filter(i => i.id !== revokingId.value)
  } catch {
    // silent
  } finally {
    revokeModal.value = false
    revokingId.value = null
  }
}

function getRoleLabel(inv: InvitationWithStatus): string {
  if (inv.group_name) return inv.group_name
  if (inv.role) {
    const labels: Record<string, string> = {
      school_admin: 'Schoolbeheerder',
      teacher: 'Docent',
      parent: 'Ouder',
    }
    return labels[inv.role] || inv.role
  }
  return 'Lid'
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: 'Openstaand',
    accepted: 'Geaccepteerd',
    revoked: 'Ingetrokken',
    expired: 'Verlopen',
  }
  return labels[status] || status
}

function getStatusBadge(status: string): string {
  const badges: Record<string, string> = {
    pending: theme.badge.warning,
    accepted: theme.badge.success,
    revoked: theme.badge.error,
    expired: theme.badge.default,
  }
  return badges[status] || theme.badge.default
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('nl-NL')
}

async function switchStatus(status: string) {
  statusFilter.value = status
  await loadInvitations()
}

onMounted(async () => {
  await Promise.all([loadInvitations(), loadGroups()])
})
</script>

<template>
  <div class="p-6">
    <div class="mb-6">
      <h2 :class="theme.text.h2">Toegangsbeheer</h2>
    </div>

    <RouteTabs :tabs="tenantTabs" />

    <div :class="theme.card.base">
      <div :class="theme.list.sectionHeader">
        <h3 :class="theme.text.h3">Uitnodigingen</h3>
        <button v-if="hasPermission('invitations.manage')" @click="openInviteModal" :class="theme.btn.primarySm" class="flex items-center gap-1">
          <Plus :size="16" />
          Uitnodigen
        </button>
      </div>

      <!-- Status tabs -->
      <div class="flex gap-1 px-4 border-b border-navy-100">
        <button
          v-for="opt in statusOptions"
          :key="opt.value"
          @click="switchStatus(opt.value)"
          class="px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px"
          :class="statusFilter === opt.value
            ? 'border-accent-700 text-accent-700'
            : 'border-transparent text-body hover:text-navy-900'"
        >
          {{ opt.label }}
        </button>
      </div>

      <div v-if="error" :class="[theme.alert.error, 'm-4']">{{ error }}</div>

      <div v-if="loading" class="p-6 text-center" :class="theme.text.muted">Laden...</div>

      <div v-else :class="theme.list.divider">
        <div v-for="inv in invitations" :key="inv.id" :class="theme.list.item">
          <div>
            <div class="flex items-center gap-2">
              <p :class="theme.text.h4">{{ inv.email }}</p>
              <span :class="[theme.badge.base, getStatusBadge(inv.status)]">{{ getStatusLabel(inv.status) }}</span>
            </div>
            <p :class="theme.text.body">
              {{ getRoleLabel(inv) }} &middot;
              Uitgenodigd door {{ inv.invited_by_name }} &middot;
              <template v-if="inv.status === 'accepted' && inv.accepted_at">
                Geaccepteerd {{ formatDate(inv.accepted_at) }}
              </template>
              <template v-else>
                Verloopt {{ formatDate(inv.expires_at) }}
              </template>
            </p>
          </div>
          <div v-if="inv.status === 'pending' && hasPermission('invitations.manage')" class="flex items-center gap-1">
            <IconButton variant="accent" title="Opnieuw versturen" @click="handleResend(inv.id)">
              <RefreshCw :size="14" />
            </IconButton>
            <IconButton variant="danger" title="Intrekken" @click="promptRevoke(inv.id)">
              <X :size="14" />
            </IconButton>
          </div>
        </div>

        <div v-if="invitations.length === 0" :class="theme.list.empty">
          <p :class="theme.text.muted">Geen uitnodigingen gevonden</p>
        </div>
      </div>
    </div>

    <!-- Invite modal (unified single + bulk) -->
    <Teleport to="body">
      <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30" @click.self="closeInviteModal">
        <div class="bg-white rounded-xl p-6 w-full max-w-lg shadow-xl">
          <h3 :class="theme.text.h3" class="mb-4">Uitnodigen</h3>

          <div v-if="inviteError" :class="[theme.alert.error, 'mb-4']">{{ inviteError }}</div>

          <!-- Results for partial failures -->
          <div v-if="inviteResult" class="mb-4 space-y-2">
            <p class="text-sm text-green-700" v-if="inviteResult.created > 0">
              {{ inviteResult.created }} uitnodiging{{ inviteResult.created === 1 ? '' : 'en' }} verstuurd
            </p>
            <div v-for="r in inviteResult.results.filter(r => !r.success)" :key="r.email"
              :class="theme.alert.error">
              {{ r.email }}: {{ r.error }}
            </div>
          </div>

          <form @submit.prevent="handleInvite" class="space-y-4">
            <div>
              <label :class="theme.form.label">E-mailadres(sen)</label>
              <textarea
                v-model="inviteEmails"
                :class="theme.form.input"
                rows="4"
                placeholder="naam@voorbeeld.nl"
                required
              ></textarea>
              <p :class="theme.text.muted" class="mt-1 text-xs">Eén adres per regel. Meerdere adressen worden als bulk verstuurd.</p>
            </div>

            <div>
              <label :class="theme.form.label">Groep</label>
              <select v-model="inviteGroupId" :class="theme.form.input">
                <option v-for="g in groups" :key="g.id" :value="g.id">
                  {{ g.name }}
                </option>
              </select>
            </div>

            <div class="flex gap-3 justify-end">
              <button type="button" @click="closeInviteModal" :class="theme.btn.link">Annuleren</button>
              <button type="submit" :disabled="inviteCreating" :class="theme.btn.primary">
                {{ inviteCreating ? 'Verzenden...' : 'Versturen' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <!-- Revoke confirmation -->
    <ConfirmModal
      :open="revokeModal"
      title="Uitnodiging intrekken"
      message="Weet je zeker dat je deze uitnodiging wilt intrekken? De ontvanger kan de link niet meer gebruiken."
      confirm-label="Intrekken"
      variant="danger"
      @confirm="confirmRevoke"
      @cancel="revokeModal = false; revokingId = null"
    />
  </div>
</template>
