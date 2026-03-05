<script setup lang="ts">
import { ref } from 'vue'
import { KeyRound, UserX, UserCheck, Mail, LogOut, ShieldOff, UserCog } from 'lucide-vue-next'
import { theme } from '@/theme'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import ImpersonateModal from '@/components/ui/ImpersonateModal.vue'
import {
  forcePasswordReset,
  toggleUserActive,
  resendVerificationEmail,
  revokeUserSessions,
  disableUser2FA,
} from '@/api/platform/operations'

export interface QuickActionUser {
  id: string
  email: string
  full_name: string
  is_active: boolean
  email_verified: boolean
  totp_enabled: boolean
  active_sessions: number
}

const props = defineProps<{
  user: QuickActionUser
}>()

const emit = defineEmits<{
  reload: []
}>()

const success = ref('')
const error = ref('')
const loading = ref(false)

// Modal states
const passwordResetModal = ref(false)
const toggleActiveModal = ref(false)
const resendVerifyModal = ref(false)
const revokeSessionsModal = ref(false)
const disable2faModal = ref(false)
const impersonateModal = ref(false)

function flashSuccess(msg: string) {
  success.value = msg
  setTimeout(() => { success.value = '' }, 3000)
}

function clearError() {
  error.value = ''
}

async function handlePasswordReset() {
  loading.value = true
  clearError()
  try {
    await forcePasswordReset(props.user.id)
    passwordResetModal.value = false
    flashSuccess('Wachtwoord reset e-mail verstuurd')
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Er is een fout opgetreden'
  } finally {
    loading.value = false
  }
}

async function handleToggleActive(password: string) {
  loading.value = true
  clearError()
  try {
    await toggleUserActive(props.user.id, password)
    toggleActiveModal.value = false
    flashSuccess(props.user.is_active ? 'Account gedeactiveerd' : 'Account geactiveerd')
    emit('reload')
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Er is een fout opgetreden'
  } finally {
    loading.value = false
  }
}

async function handleResendVerification() {
  loading.value = true
  clearError()
  try {
    await resendVerificationEmail(props.user.id)
    resendVerifyModal.value = false
    flashSuccess('Verificatie-email verstuurd')
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Er is een fout opgetreden'
  } finally {
    loading.value = false
  }
}

async function handleRevokeSessions() {
  loading.value = true
  clearError()
  try {
    const result = await revokeUserSessions(props.user.id)
    revokeSessionsModal.value = false
    flashSuccess(`${result.revoked_count} sessie(s) beëindigd`)
    emit('reload')
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Er is een fout opgetreden'
  } finally {
    loading.value = false
  }
}

async function handleDisable2FA(password: string) {
  loading.value = true
  clearError()
  try {
    await disableUser2FA(props.user.id, password)
    disable2faModal.value = false
    flashSuccess('2FA uitgeschakeld')
    emit('reload')
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Er is een fout opgetreden'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div :class="theme.card.base">
    <h3 :class="[theme.text.h4, 'p-4']">Acties</h3>

    <!-- Success/error alerts -->
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="success" :class="[theme.alert.success, 'mx-4']">{{ success }}</div>
    </Transition>
    <div v-if="error" :class="[theme.alert.error, 'mx-4']">{{ error }}</div>

    <!-- Action items -->
    <div class="divide-y divide-navy-100">
      <!-- Password reset -->
      <div
        :class="theme.action.item"
        @click="clearError(); passwordResetModal = true"
      >
        <KeyRound :size="16" class="shrink-0" />
        <span class="flex-1">Wachtwoord reset versturen</span>
      </div>

      <!-- Toggle active -->
      <div
        :class="user.is_active ? theme.action.itemDanger : theme.action.item"
        @click="clearError(); toggleActiveModal = true"
      >
        <component :is="user.is_active ? UserX : UserCheck" :size="16" class="shrink-0" />
        <span class="flex-1">{{ user.is_active ? 'Account deactiveren' : 'Account activeren' }}</span>
        <span :class="[theme.badge.base, user.is_active ? theme.badge.success : theme.badge.error]">
          {{ user.is_active ? 'Actief' : 'Inactief' }}
        </span>
      </div>

      <!-- Resend verification -->
      <div
        :class="user.email_verified ? theme.action.itemDisabled : theme.action.item"
        @click="!user.email_verified && (clearError(), resendVerifyModal = true)"
      >
        <Mail :size="16" class="shrink-0" />
        <span class="flex-1">Verificatie-email opnieuw</span>
        <span :class="[theme.badge.base, user.email_verified ? theme.badge.success : theme.badge.warning]">
          {{ user.email_verified ? 'Geverifieerd' : 'Niet geverifieerd' }}
        </span>
      </div>

      <!-- Revoke sessions -->
      <div
        :class="theme.action.itemDanger"
        @click="clearError(); revokeSessionsModal = true"
      >
        <LogOut :size="16" class="shrink-0" />
        <span class="flex-1">Alle sessies beëindigen</span>
        <span v-if="user.active_sessions > 0" :class="[theme.badge.base, theme.badge.default]">
          {{ user.active_sessions }} actief
        </span>
      </div>

      <!-- Disable 2FA -->
      <div
        :class="user.totp_enabled ? theme.action.itemDanger : theme.action.itemDisabled"
        @click="user.totp_enabled && (clearError(), disable2faModal = true)"
      >
        <ShieldOff :size="16" class="shrink-0" />
        <span class="flex-1">2FA uitschakelen</span>
        <span :class="[theme.badge.base, user.totp_enabled ? theme.badge.success : theme.badge.default]">
          {{ user.totp_enabled ? '2FA aan' : '2FA uit' }}
        </span>
      </div>

      <!-- Impersonate -->
      <div
        :class="user.is_active ? theme.action.item : theme.action.itemDisabled"
        @click="user.is_active && (clearError(), impersonateModal = true)"
      >
        <UserCog :size="16" class="shrink-0" />
        <span class="flex-1">Inloggen als deze gebruiker</span>
      </div>
    </div>

    <!-- Modals -->
    <ConfirmModal
      :open="passwordResetModal"
      title="Wachtwoord reset"
      :message="`Wachtwoord reset e-mail versturen naar ${user.email}?`"
      confirm-label="Versturen"
      variant="accent"
      :loading="loading"
      :error="error"
      @confirm="handlePasswordReset"
      @cancel="passwordResetModal = false"
    />

    <ConfirmModal
      :open="toggleActiveModal"
      :title="user.is_active ? 'Account deactiveren' : 'Account activeren'"
      :message="user.is_active
        ? `Weet je zeker dat je '${user.full_name}' wilt deactiveren? Alle sessies worden beëindigd.`
        : `Weet je zeker dat je '${user.full_name}' wilt activeren?`"
      :confirm-label="user.is_active ? 'Deactiveren' : 'Activeren'"
      :variant="user.is_active ? 'danger' : 'accent'"
      require-password
      :loading="loading"
      :error="error"
      @confirm="handleToggleActive"
      @cancel="toggleActiveModal = false"
    />

    <ConfirmModal
      :open="resendVerifyModal"
      title="Verificatie-email versturen"
      :message="`Verificatie-email opnieuw versturen naar ${user.email}?`"
      confirm-label="Versturen"
      variant="accent"
      :loading="loading"
      :error="error"
      @confirm="handleResendVerification"
      @cancel="resendVerifyModal = false"
    />

    <ConfirmModal
      :open="revokeSessionsModal"
      title="Sessies beëindigen"
      :message="`Alle actieve sessies van '${user.full_name}' beëindigen? De gebruiker wordt overal uitgelogd.`"
      confirm-label="Sessies beëindigen"
      variant="danger"
      :loading="loading"
      :error="error"
      @confirm="handleRevokeSessions"
      @cancel="revokeSessionsModal = false"
    />

    <ConfirmModal
      :open="disable2faModal"
      title="2FA uitschakelen"
      :message="`2FA uitschakelen voor '${user.full_name}'? Alle sessies worden beëindigd.`"
      confirm-label="2FA uitschakelen"
      variant="danger"
      require-password
      :loading="loading"
      :error="error"
      @confirm="handleDisable2FA"
      @cancel="disable2faModal = false"
    />

    <ImpersonateModal
      :open="impersonateModal"
      :user-id="user.id"
      :user-name="user.full_name"
      :user-email="user.email"
      @close="impersonateModal = false"
    />
  </div>
</template>
