<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { adminApi } from '@/api/platform/admin'
import type { PlatformStaffItem } from '@/api/platform/admin'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import IconButton from '@/components/ui/IconButton.vue'
import { Shield, ShieldCheck, Users, ShieldOff, UserPlus, X } from 'lucide-vue-next'
import { theme } from '@/theme'
import { useAuthStore } from '@/stores/auth'
import { extractError, validationMessage } from '@/utils/errors'
import { isValidEmail } from '@/utils/validators'

const authStore = useAuthStore()
const currentUserId = computed(() => authStore.user?.id)
const isSuperAdmin = computed(() => authStore.user?.is_superadmin === true)

const users = ref<PlatformStaffItem[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const successMessage = ref<string | null>(null)

const superadminCount = computed(() => users.value.filter(u => u.is_superadmin).length)
const expandedBadge = ref<string | null>(null)

function isMe(user: PlatformStaffItem): boolean {
  return user.id === currentUserId.value
}

function canToggleSuperAdmin(user: PlatformStaffItem): boolean {
  if (isMe(user) && user.is_superadmin) return false
  if (user.is_superadmin && superadminCount.value <= 1) return false
  return true
}

onMounted(async () => {
  try {
    users.value = await adminApi.getPlatformUsers()
  } catch {
    error.value = 'Kon platform gebruikers niet laden'
  } finally {
    loading.value = false
  }
})

const superadminModal = ref(false)
const superadminTarget = ref<PlatformStaffItem | null>(null)
const superadminLoading = ref(false)
const superadminError = ref('')

function promptToggleSuperAdmin(user: PlatformStaffItem) {
  if (!canToggleSuperAdmin(user)) return
  superadminTarget.value = user
  superadminError.value = ''
  superadminModal.value = true
}

async function confirmToggleSuperAdmin() {
  if (!superadminTarget.value) return
  superadminLoading.value = true
  try {
    await adminApi.toggleSuperAdmin(
      superadminTarget.value.id,
      !superadminTarget.value.is_superadmin,
    )
    superadminModal.value = false
    superadminTarget.value = null
    users.value = await adminApi.getPlatformUsers()
  } catch (e: unknown) {
    superadminError.value = extractError(e, 'save')
  } finally {
    superadminLoading.value = false
  }
}

// Invite modal
const inviteModal = ref(false)
const inviteEmail = ref('')
const inviteSubmitting = ref(false)
const inviteError = ref('')

function openInviteModal() {
  inviteEmail.value = ''
  inviteError.value = ''
  inviteModal.value = true
}

async function handleInvite() {
  inviteError.value = ''
  if (!inviteEmail.value) return

  if (!isValidEmail(inviteEmail.value)) {
    inviteError.value = validationMessage('email')
    return
  }

  inviteSubmitting.value = true
  try {
    const result = await adminApi.invitePlatformUser(inviteEmail.value)
    inviteModal.value = false
    successMessage.value = result.message
    setTimeout(() => { successMessage.value = null }, 5000)
  } catch (e: unknown) {
    inviteError.value = extractError(e, 'invite')
  } finally {
    inviteSubmitting.value = false
  }
}

function formatDate(date: string | null) {
  if (!date) return '—'
  return new Date(date).toLocaleDateString('nl-NL', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-2">
        <Users class="w-6 h-6 text-navy-700" />
        <h2 :class="theme.text.h2">Platform gebruikers</h2>
      </div>
      <button v-if="isSuperAdmin" @click="openInviteModal" :class="theme.btn.addInline">
        <span :class="theme.btn.addInlineIcon"><UserPlus :size="14" /></span>
        Uitnodigen
      </button>
    </div>

    <div v-if="successMessage" :class="[theme.alert.success, 'mb-4']">{{ successMessage }}</div>
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <div v-if="loading" :class="theme.list.empty">
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <div v-else :class="theme.card.base">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-navy-100 text-left">
              <th class="px-6 py-3 font-medium text-navy-700">Gebruiker</th>
              <th class="px-6 py-3 font-medium text-navy-700">Groepen</th>
              <th class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">
                Aangemaakt
              </th>
              <th class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">
                Laatste login
              </th>
              <th class="px-6 py-3 font-medium text-navy-700">Status</th>
              <th class="px-6 py-3 font-medium text-navy-700 text-right">Acties</th>
            </tr>
          </thead>
          <tbody :class="theme.list.divider">
            <tr v-if="users.length === 0">
              <td colspan="6" :class="theme.list.empty">
                <p :class="theme.text.muted">Geen platform gebruikers gevonden.</p>
              </td>
            </tr>
            <tr
              v-for="user in users"
              :key="user.id"
              class="hover:bg-surface transition-colors"
            >
              <td class="px-6 py-4">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-lg bg-primary-50 flex items-center
                              justify-center flex-shrink-0">
                    <Users :size="14" class="text-primary-600" />
                  </div>
                  <div v-if="isMe(user)">
                    <div class="flex items-center gap-1.5">
                      <p class="text-base italic text-navy-300">You</p>
                      <button
                        v-if="user.is_superadmin"
                        @click.stop="expandedBadge = expandedBadge === user.id ? null : user.id"
                        :class="[
                          theme.chip.base,
                          expandedBadge === user.id ? [theme.chip.expanded, theme.chip.variant.purple.bg] : '',
                        ]"
                        :title="expandedBadge === user.id ? '' : 'Superadmin'"
                      >
                        <ShieldCheck :size="14" :class="[theme.chip.icon, theme.chip.variant.purple.text]" />
                        <span
                          :class="[theme.chip.label, theme.chip.variant.purple.text]"
                          :style="{ maxWidth: expandedBadge === user.id ? '100px' : '0', opacity: expandedBadge === user.id ? 1 : 0 }"
                        >Superadmin</span>
                      </button>
                    </div>
                  </div>
                  <div v-else>
                    <div class="flex items-center gap-1.5">
                      <p :class="theme.text.h4">{{ user.full_name }}</p>
                      <button
                        v-if="user.is_superadmin"
                        @click.stop="expandedBadge = expandedBadge === user.id ? null : user.id"
                        :class="[
                          theme.chip.base,
                          expandedBadge === user.id ? [theme.chip.expanded, theme.chip.variant.purple.bg] : '',
                        ]"
                        :title="expandedBadge === user.id ? '' : 'Superadmin'"
                      >
                        <ShieldCheck :size="14" :class="[theme.chip.icon, theme.chip.variant.purple.text]" />
                        <span
                          :class="[theme.chip.label, theme.chip.variant.purple.text]"
                          :style="{ maxWidth: expandedBadge === user.id ? '100px' : '0', opacity: expandedBadge === user.id ? 1 : 0 }"
                        >Superadmin</span>
                      </button>
                    </div>
                    <p class="text-xs text-body">{{ user.email }}</p>
                  </div>
                </div>
              </td>
              <td class="px-6 py-4">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-if="user.is_superadmin"
                    :class="[theme.badge.base, theme.badge.error]"
                  >
                    Superadmin
                  </span>
                  <span
                    v-for="group in user.platform_groups"
                    :key="group.id"
                    :class="[theme.badge.base, theme.badge.info]"
                  >
                    {{ group.name }}
                  </span>
                  <span
                    v-if="!user.is_superadmin && user.platform_groups.length === 0"
                    :class="[theme.badge.base, theme.badge.default]"
                  >
                    Geen groep
                  </span>
                </div>
              </td>
              <td class="px-6 py-4 hidden md:table-cell">
                <span :class="theme.text.muted">{{ formatDate(user.created_at) }}</span>
              </td>
              <td class="px-6 py-4 hidden md:table-cell">
                <span :class="theme.text.muted">{{ formatDate(user.last_login_at) }}</span>
              </td>
              <td class="px-6 py-4">
                <span :class="[theme.badge.base,
                  user.is_active ? theme.badge.success : theme.badge.default]">
                  {{ user.is_active ? 'Actief' : 'Inactief' }}
                </span>
              </td>
              <td class="px-6 py-4" @click.stop>
                <div class="flex items-center justify-end gap-1">
                  <IconButton
                    :variant="user.is_superadmin ? 'danger' : 'accent'"
                    :disabled="!canToggleSuperAdmin(user)"
                    :title="!canToggleSuperAdmin(user)
                      ? (isMe(user) ? 'Je kunt je eigen superadmin niet intrekken' : 'De laatste superadmin kan niet worden verwijderd')
                      : (user.is_superadmin ? 'Superadmin intrekken' : 'Superadmin toekennen')"
                    :class="{ 'pointer-events-none': !canToggleSuperAdmin(user) }"
                    @click="promptToggleSuperAdmin(user)"
                  >
                    <ShieldOff v-if="user.is_superadmin" :size="16" />
                    <Shield v-else :size="16" />
                  </IconButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <ConfirmModal
    :open="superadminModal"
    :title="superadminTarget?.is_superadmin
      ? 'Superadmin intrekken'
      : 'Superadmin toekennen'"
    :message="superadminTarget?.is_superadmin
      ? `Superadmin-rechten van '${superadminTarget?.full_name}' intrekken?`
      : `LET OP: Het toekennen van superadmin aan '${superadminTarget?.full_name}' verwijdert alle organisatie-lidmaatschappen. Doorgaan?`"
    :confirm-label="superadminTarget?.is_superadmin ? 'Intrekken' : 'Toekennen'"
    variant="danger"
    :loading="superadminLoading"
    :error="superadminError"
    @confirm="confirmToggleSuperAdmin"
    @cancel="superadminModal = false; superadminTarget = null"
  />

  <!-- Invite modal -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="inviteModal" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="fixed inset-0 bg-black/40" @click="inviteModal = false" />
        <div class="relative bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 :class="theme.text.h3">Platformgebruiker uitnodigen</h3>
            <button @click="inviteModal = false" class="text-navy-400 hover:text-navy-700">
              <X :size="20" />
            </button>
          </div>

          <form @submit.prevent="handleInvite" class="space-y-4">
            <div>
              <label :class="theme.form.label">E-mailadres</label>
              <input
                v-model="inviteEmail"
                type="email"
                required
                :class="[theme.form.input, 'w-full']"
                placeholder="naam@voorbeeld.nl"
                autocomplete="off"
              />
            </div>

            <div v-if="inviteError" :class="theme.alert.error">{{ inviteError }}</div>

            <div class="flex justify-end gap-2">
              <button type="button" @click="inviteModal = false" :class="theme.btn.secondarySm">
                Annuleren
              </button>
              <button
                type="submit"
                :disabled="inviteSubmitting || !inviteEmail"
                :class="theme.btn.primarySm"
              >
                {{ inviteSubmitting ? 'Versturen...' : 'Uitnodiging versturen' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
