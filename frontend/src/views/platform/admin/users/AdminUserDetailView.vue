<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Pencil, UserMinus, UserX, UserCheck, ShieldOff } from 'lucide-vue-next'
import { theme } from '@/theme'
import { adminApi, type AdminUserDetail, type AdminUserUpdate } from '@/api/platform/admin'
import BackLink from '@/components/ui/BackLink.vue'
import IconButton from '@/components/ui/IconButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'

const route = useRoute()
const userId = route.params.userId as string

const user = ref<AdminUserDetail | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

// Edit mode
const editing = ref(false)
const editForm = ref<AdminUserUpdate>({})
const editLoading = ref(false)
const editError = ref('')

// Modals
const toggleActiveModal = ref(false)
const removeMembershipModal = ref(false)
const removingMembership = ref<{ tenantId: string; tenantName: string } | null>(null)
const reset2faModal = ref(false)
const reset2faLoading = ref(false)
const reset2faError = ref('')

onMounted(async () => {
  await loadUser()
})

async function loadUser() {
  loading.value = true
  try {
    user.value = await adminApi.getUserDetail(userId)
  } catch {
    error.value = 'Gebruiker niet gevonden'
  } finally {
    loading.value = false
  }
}

function startEdit() {
  if (!user.value) return
  editForm.value = {
    full_name: user.value.full_name,
    email: user.value.email,
    is_active: user.value.is_active,
    email_verified: user.value.email_verified,
  }
  editError.value = ''
  editing.value = true
}

async function saveEdit() {
  if (!user.value) return
  editLoading.value = true
  editError.value = ''
  try {
    user.value = await adminApi.updateUser(user.value.id, editForm.value)
    editing.value = false
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    editError.value = err.response?.data?.detail ?? 'Er is een fout opgetreden'
  } finally {
    editLoading.value = false
  }
}

async function confirmToggleActive() {
  if (!user.value) return
  editLoading.value = true
  try {
    user.value = await adminApi.updateUser(user.value.id, {
      is_active: !user.value.is_active,
    })
  } catch {
    // Handled silently
  } finally {
    editLoading.value = false
    toggleActiveModal.value = false
  }
}

function promptRemoveMembership(tenantId: string, tenantName: string) {
  removingMembership.value = { tenantId, tenantName }
  removeMembershipModal.value = true
}

async function confirmRemoveMembership() {
  if (!removingMembership.value || !user.value) return
  try {
    await adminApi.removeMembership(removingMembership.value.tenantId, user.value.id)
    user.value.memberships = user.value.memberships.filter(
      (m) => m.tenant_id !== removingMembership.value!.tenantId,
    )
  } catch {
    // Handled silently
  } finally {
    removeMembershipModal.value = false
    removingMembership.value = null
  }
}

async function confirmReset2FA() {
  if (!user.value) return
  reset2faLoading.value = true
  reset2faError.value = ''
  try {
    user.value = await adminApi.resetUser2FA(user.value.id)
    reset2faModal.value = false
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    reset2faError.value = err.response?.data?.detail ?? 'Er is een fout opgetreden'
  } finally {
    reset2faLoading.value = false
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('nl-NL', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function roleLabel(role: string): string {
  const labels: Record<string, string> = {
    super_admin: 'Super Admin',
    org_admin: 'Beheerder',
    teacher: 'Docent',
    parent: 'Ouder',
  }
  return labels[role] ?? role
}
</script>

<template>
  <div>
    <div v-if="loading" :class="theme.list.empty">
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <div v-else-if="error && !user" :class="theme.alert.error">{{ error }}</div>

    <template v-else-if="user">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-3">
          <BackLink to="/platform/users" />
          <div>
            <h2 :class="theme.text.h2">{{ user.full_name }}</h2>
            <p :class="[theme.text.body, 'mt-1']">{{ user.email }}</p>
          </div>
        </div>
        <div class="flex gap-2">
          <button
            v-if="!editing"
            @click="startEdit"
            :class="[theme.btn.secondarySm, 'flex items-center gap-1.5']"
          >
            <Pencil :size="14" />
            Bewerken
          </button>
          <button
            @click="toggleActiveModal = true"
            class="px-4 py-2 rounded-lg text-sm transition-colors"
            :class="user.is_active
              ? 'text-red-600 hover:bg-red-50'
              : 'text-green-600 hover:bg-green-50'"
          >
            <UserX v-if="user.is_active" :size="14" class="inline mr-1" />
            <UserCheck v-else :size="14" class="inline mr-1" />
            {{ user.is_active ? 'Deactiveren' : 'Activeren' }}
          </button>
        </div>
      </div>

      <!-- User info / edit form -->
      <div :class="[theme.card.padded, 'mb-6']">
        <template v-if="!editing">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-6">
            <div>
              <p class="text-xs text-body mb-1">Status</p>
              <div class="flex flex-wrap gap-1.5">
                <span
                  :class="[theme.badge.base, user.is_active ? theme.badge.success : theme.badge.warning]"
                >{{ user.is_active ? 'Actief' : 'Inactief' }}</span>
                <span v-if="user.is_superadmin" :class="[theme.badge.base, theme.badge.info]">Super Admin</span>
                <span v-if="!user.email_verified" :class="[theme.badge.base, theme.badge.warning]">Niet geverifieerd</span>
              </div>
            </div>
            <div>
              <p class="text-xs text-body mb-1">Organisaties</p>
              <p v-if="user.is_superadmin" class="text-sm text-navy-900">Alle (platform)</p>
              <p v-else class="text-sm text-navy-900">{{ user.memberships.length }}</p>
            </div>
            <div>
              <p class="text-xs text-body mb-1">Aangemaakt</p>
              <p class="text-sm text-navy-900">{{ formatDate(user.created_at) }}</p>
            </div>
            <div>
              <p class="text-xs text-body mb-1">2FA</p>
              <div class="flex items-center gap-2">
                <span
                  :class="[theme.badge.base, user.totp_enabled ? theme.badge.success : theme.badge.default]"
                >{{ user.totp_enabled ? 'Ingeschakeld' : 'Uitgeschakeld' }}</span>
                <button
                  v-if="user.totp_enabled"
                  @click="reset2faError = ''; reset2faModal = true"
                  class="text-xs text-red-600 hover:text-red-700 hover:underline"
                >
                  Reset
                </button>
              </div>
            </div>
          </div>
        </template>

        <template v-else>
          <div v-if="editError" :class="[theme.alert.error, 'mb-4']">{{ editError }}</div>
          <form @submit.prevent="saveEdit" class="space-y-4">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label :class="theme.form.label">Naam</label>
                <input v-model="editForm.full_name" type="text" required :class="theme.form.input" />
              </div>
              <div>
                <label :class="theme.form.label">E-mail</label>
                <input v-model="editForm.email" type="email" required :class="theme.form.input" />
              </div>
            </div>
            <div class="flex items-center gap-4">
              <label class="flex items-center gap-2 text-sm text-navy-700 cursor-pointer">
                <input v-model="editForm.is_active" type="checkbox" class="rounded" />
                Actief
              </label>
              <label class="flex items-center gap-2 text-sm text-navy-700 cursor-pointer">
                <input v-model="editForm.email_verified" type="checkbox" class="rounded" />
                Geverifieerd
              </label>
            </div>
            <div class="flex gap-2">
              <button type="submit" :disabled="editLoading" :class="theme.btn.primary">
                {{ editLoading ? 'Opslaan...' : 'Opslaan' }}
              </button>
              <button type="button" @click="editing = false" :class="theme.btn.secondary">
                Annuleren
              </button>
            </div>
          </form>
        </template>
      </div>

      <!-- Memberships (hidden for platform users) -->
      <div :class="theme.card.base">
        <div :class="theme.list.sectionHeader">
          <h3 :class="theme.text.h3">Organisatiekoppelingen</h3>
        </div>

        <div v-if="user.is_superadmin" :class="theme.list.empty">
          <p :class="theme.text.muted">
            Platformgebruikers hebben geen organisatiekoppelingen. Toegang tot organisaties verloopt via het admin panel.
          </p>
        </div>
        <template v-else>
          <div v-if="user.memberships.length === 0" :class="theme.list.empty">
            <p :class="theme.text.muted">Geen koppelingen</p>
          </div>
          <div v-else :class="theme.list.divider">
            <div
              v-for="m in user.memberships"
              :key="m.tenant_id"
              class="flex items-center justify-between px-6 py-3"
            >
              <div>
                <p class="text-sm font-medium text-navy-900">{{ m.tenant_name }}</p>
                <div class="flex flex-wrap gap-1 mt-0.5">
                  <span
                    v-for="g in m.groups"
                    :key="g.id"
                    :class="[theme.badge.base, theme.badge.info]"
                    class="text-[10px]"
                  >{{ g.name }}</span>
                  <span v-if="m.groups.length === 0 && m.role" class="text-xs text-body">
                    {{ roleLabel(m.role) }}
                  </span>
                </div>
              </div>
              <IconButton
                variant="danger"
                title="Ontkoppelen"
                @click="promptRemoveMembership(m.tenant_id, m.tenant_name)"
              >
                <UserMinus :size="14" />
              </IconButton>
            </div>
          </div>
        </template>
      </div>
    </template>

    <!-- Toggle active confirmation -->
    <ConfirmModal
      :open="toggleActiveModal"
      :title="user?.is_active ? 'Gebruiker deactiveren' : 'Gebruiker activeren'"
      :message="user?.is_active
        ? `Weet je zeker dat je '${user?.full_name ?? ''}' wilt deactiveren? De gebruiker kan niet meer inloggen.`
        : `Weet je zeker dat je '${user?.full_name ?? ''}' wilt activeren?`"
      :confirm-label="user?.is_active ? 'Deactiveren' : 'Activeren'"
      :variant="user?.is_active ? 'danger' : 'accent'"
      @confirm="confirmToggleActive"
      @cancel="toggleActiveModal = false"
    />

    <!-- Remove membership confirmation -->
    <ConfirmModal
      :open="removeMembershipModal"
      title="Organisatiekoppeling verwijderen"
      :message="`Weet je zeker dat je de koppeling met '${removingMembership?.tenantName ?? ''}' wilt verwijderen?`"
      confirm-label="Ontkoppelen"
      variant="danger"
      @confirm="confirmRemoveMembership"
      @cancel="removeMembershipModal = false; removingMembership = null"
    />

    <!-- Reset 2FA confirmation -->
    <ConfirmModal
      :open="reset2faModal"
      title="2FA resetten"
      :message="`Weet je zeker dat je 2FA wilt resetten voor '${user?.full_name ?? ''}'? Alle actieve sessies worden beëindigd en de gebruiker ontvangt een e-mail.`"
      confirm-label="2FA resetten"
      variant="danger"
      :error="reset2faError"
      :loading="reset2faLoading"
      @confirm="confirmReset2FA"
      @cancel="reset2faModal = false; reset2faError = ''"
    />
  </div>
</template>
