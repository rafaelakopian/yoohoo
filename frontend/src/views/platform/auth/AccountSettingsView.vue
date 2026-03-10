<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { User as UserIcon, Lock, Monitor, Shield, X, LogOut, Smartphone, Tablet, Phone, CheckCircle, MessageSquare } from 'lucide-vue-next'
import OtpInput from '@/components/ui/OtpInput.vue'
import { authApi } from '@/api/platform/auth'
import { useAuthStore } from '@/stores/auth'
import { theme } from '@/theme'
import type { SessionInfo } from '@/types/auth'
import IconButton from '@/components/ui/IconButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'

const authStore = useAuthStore()

// Tab state
const activeTab = ref<'profile' | 'password' | 'sessions' | '2fa'>('profile')

// --- Profile tab ---
const profileFullName = ref('')
const profileEmail = ref('')
const profilePhone = ref<string | null>(null)
const profileLoading = ref(false)
const profileError = ref('')
const profileSuccess = ref('')

// Phone verification
const phoneVerifying = ref(false)
const phoneVerificationId = ref<string | null>(null)
const phoneOtpCode = ref('')
const phoneVerifyLoading = ref(false)
const phoneVerifyError = ref('')
const phoneVerifySuccess = ref('')
const phoneVerified = ref(false)
const smsConfigured = ref(false)

// Email change
const showEmailModal = ref(false)
const emailChangeNew = ref('')
const emailChangePassword = ref('')
const emailChangeLoading = ref(false)
const emailChangeError = ref('')
const emailChangeSuccess = ref('')

function loadProfile() {
  // User type doesn't include phone/totp fields — extended at runtime by /me endpoint
  const user = authStore.user as any
  profileFullName.value = user?.full_name ?? ''
  profileEmail.value = user?.email ?? ''
  profilePhone.value = user?.phone_number ?? null
  phoneVerified.value = user?.phone_verified ?? false
  smsConfigured.value = user?.sms_configured ?? false
}

async function handleEmailChange() {
  emailChangeError.value = ''
  emailChangeSuccess.value = ''
  emailChangeLoading.value = true
  try {
    const result = await authApi.requestEmailChange(emailChangeNew.value, emailChangePassword.value)
    emailChangeSuccess.value = result.message
    showEmailModal.value = false
    emailChangeNew.value = ''
    emailChangePassword.value = ''
  } catch (e: any) {
    emailChangeError.value = e.response?.data?.detail || 'Er is een fout opgetreden'
  } finally {
    emailChangeLoading.value = false
  }
}

async function handleUpdateProfile() {
  profileError.value = ''
  profileSuccess.value = ''
  profileLoading.value = true
  try {
    await authApi.updateProfile({ full_name: profileFullName.value, phone_number: profilePhone.value })
    await authStore.fetchUser()
    profileSuccess.value = 'Profiel bijgewerkt'
  } catch (e: any) {
    profileError.value = e.response?.data?.detail || 'Er is een fout opgetreden'
  } finally {
    profileLoading.value = false
  }
}

async function requestPhoneVerify() {
  phoneVerifyError.value = ''
  phoneVerifySuccess.value = ''
  phoneVerifyLoading.value = true
  try {
    const result = await authApi.requestPhoneVerification()
    phoneVerificationId.value = result.verification_id
    phoneVerifying.value = true
    phoneVerifySuccess.value = result.message
  } catch (e: any) {
    phoneVerifyError.value = e.response?.data?.detail || 'Kon geen verificatiecode versturen'
  } finally {
    phoneVerifyLoading.value = false
  }
}

async function confirmPhoneVerify() {
  if (!phoneVerificationId.value) return
  phoneVerifyError.value = ''
  phoneVerifyLoading.value = true
  try {
    await authApi.verifyPhone(phoneVerificationId.value, phoneOtpCode.value)
    phoneVerified.value = true
    phoneVerifying.value = false
    phoneVerifySuccess.value = 'Telefoonnummer succesvol geverifieerd'
    phoneOtpCode.value = ''
    phoneVerificationId.value = null
    await authStore.fetchUser()
  } catch (e: any) {
    phoneVerifyError.value = e.response?.data?.detail || 'Ongeldige code'
  } finally {
    phoneVerifyLoading.value = false
  }
}

function cancelPhoneVerify() {
  phoneVerifying.value = false
  phoneOtpCode.value = ''
  phoneVerificationId.value = null
  phoneVerifyError.value = ''
}

// --- Password tab ---
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const passwordLoading = ref(false)
const passwordError = ref('')
const passwordSuccess = ref('')

async function handleChangePassword() {
  passwordError.value = ''
  passwordSuccess.value = ''

  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = 'Wachtwoorden komen niet overeen'
    return
  }

  passwordLoading.value = true
  try {
    const result = await authApi.changePassword(currentPassword.value, newPassword.value)
    // Update tokens in localStorage
    localStorage.setItem('access_token', result.access_token)
    localStorage.setItem('refresh_token', result.refresh_token)
    authStore.accessToken = result.access_token
    authStore.refreshToken = result.refresh_token
    passwordSuccess.value = result.message
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (e: any) {
    passwordError.value = e.response?.data?.detail || 'Er is een fout opgetreden'
  } finally {
    passwordLoading.value = false
  }
}

// --- Sessions tab ---
const sessions = ref<SessionInfo[]>([])
const sessionsLoading = ref(false)
const sessionsError = ref('')

async function loadSessions() {
  sessionsLoading.value = true
  sessionsError.value = ''
  try {
    sessions.value = await authApi.listSessions()
  } catch (e: any) {
    sessionsError.value = e.response?.data?.detail || 'Kon sessies niet laden'
  } finally {
    sessionsLoading.value = false
  }
}

const revokeSessionModal = ref(false)
const revokingSessionId = ref<string | null>(null)
const logoutAllModal = ref(false)

function promptRevokeSession(sessionId: string) {
  revokingSessionId.value = sessionId
  revokeSessionModal.value = true
}

async function confirmRevokeSession() {
  if (!revokingSessionId.value) return
  try {
    await authApi.revokeSession(revokingSessionId.value)
    sessions.value = sessions.value.filter(s => s.id !== revokingSessionId.value)
  } catch {
    // silently handle
  } finally {
    revokeSessionModal.value = false
    revokingSessionId.value = null
  }
}

async function confirmLogoutAll() {
  try {
    await authApi.logoutAll()
    await authStore.logout()
  } catch {
    // silently handle
  } finally {
    logoutAllModal.value = false
  }
}

// --- 2FA tab ---
const totpEnabled = ref(false)
const setupSecret = ref('')
const setupQrUri = ref('')
const setupCode = ref('')
const disablePassword = ref('')
const twoFaLoading = ref(false)
const twoFaError = ref('')
const twoFaSuccess = ref('')
const showSetup = ref(false)

async function startSetup2FA() {
  twoFaError.value = ''
  twoFaLoading.value = true
  try {
    const result = await authApi.setup2FA()
    setupSecret.value = result.secret
    setupQrUri.value = result.qr_code_uri
    showSetup.value = true
  } catch (e: any) {
    twoFaError.value = e.response?.data?.detail || 'Fout bij opzetten 2FA'
  } finally {
    twoFaLoading.value = false
  }
}

async function confirmSetup2FA() {
  twoFaError.value = ''
  twoFaLoading.value = true
  try {
    const result = await authApi.verifySetup2FA(setupCode.value)
    showSetup.value = false
    totpEnabled.value = true
    twoFaSuccess.value = result.message
    // Clear sensitive setup data from memory
    setupSecret.value = ''
    setupQrUri.value = ''
    setupCode.value = ''
  } catch (e: any) {
    twoFaError.value = e.response?.data?.detail || 'Ongeldige code'
  } finally {
    twoFaLoading.value = false
  }
}

async function disable2FA() {
  twoFaError.value = ''
  twoFaLoading.value = true
  try {
    await authApi.disable2FA(disablePassword.value)
    totpEnabled.value = false
    disablePassword.value = ''
    twoFaSuccess.value = '2FA is uitgeschakeld'
  } catch (e: any) {
    twoFaError.value = e.response?.data?.detail || 'Fout bij uitschakelen 2FA'
  } finally {
    twoFaLoading.value = false
  }
}

// --- Delete Account ---
const showDeleteModal = ref(false)
const deletePassword = ref('')
const deleteLoading = ref(false)
const deleteError = ref('')

async function handleDeleteAccount() {
  deleteError.value = ''
  deleteLoading.value = true
  try {
    await authApi.deleteAccount(deletePassword.value)
    await authStore.logout()
  } catch (e: any) {
    deleteError.value = e.response?.data?.detail || 'Er is een fout opgetreden'
  } finally {
    deleteLoading.value = false
  }
}

function formatDate(d: string) {
  return new Date(d).toLocaleString('nl-NL')
}

function formatRelativeTime(d: string | null): string {
  if (!d) return 'Nooit'
  const now = Date.now()
  const then = new Date(d).getTime()
  const diffMin = Math.floor((now - then) / 60000)
  if (diffMin < 1) return 'Zojuist'
  if (diffMin < 60) return `${diffMin} min geleden`
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return `${diffHours} uur geleden`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays} dag${diffDays === 1 ? '' : 'en'} geleden`
}

onMounted(() => {
  // User type doesn't include totp_enabled — extended at runtime by /me endpoint
  const user = authStore.user as any
  totpEnabled.value = user?.totp_enabled ?? false
  loadProfile()
})
</script>

<template>
  <div>
    <h2 :class="theme.text.h2" class="mb-6">Account instellingen</h2>

    <!-- Tabs -->
    <div class="flex gap-1 mb-6 border-b border-navy-100 overflow-x-auto">
      <button
        @click="activeTab = 'profile'"
        class="flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="activeTab === 'profile' ? 'border-accent-700 text-accent-700' : 'border-transparent text-body hover:text-navy-900'"
      >
        <UserIcon :size="16" />
        Profiel
      </button>
      <button
        @click="activeTab = 'password'"
        class="flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="activeTab === 'password' ? 'border-accent-700 text-accent-700' : 'border-transparent text-body hover:text-navy-900'"
      >
        <Lock :size="16" />
        Wachtwoord
      </button>
      <button
        @click="activeTab = 'sessions'; loadSessions()"
        class="flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="activeTab === 'sessions' ? 'border-accent-700 text-accent-700' : 'border-transparent text-body hover:text-navy-900'"
      >
        <Monitor :size="16" />
        Sessies
      </button>
      <button
        @click="activeTab = '2fa'"
        class="flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="activeTab === '2fa' ? 'border-accent-700 text-accent-700' : 'border-transparent text-body hover:text-navy-900'"
      >
        <Shield :size="16" />
        2FA
      </button>
    </div>

    <!-- Profile Tab -->
    <div v-if="activeTab === 'profile'" :class="theme.card.padded">
      <h3 :class="theme.text.h3" class="mb-4">Profiel</h3>

      <div v-if="profileError" :class="theme.alert.error">{{ profileError }}</div>
      <div v-if="profileSuccess" :class="theme.alert.success">
        {{ profileSuccess }}
      </div>

      <form @submit.prevent="handleUpdateProfile" class="space-y-4">
        <div>
          <label :class="theme.form.label">Volledige naam</label>
          <input v-model="profileFullName" type="text" required minlength="1" maxlength="255" :class="theme.form.input" />
        </div>
        <div>
          <label :class="theme.form.label">E-mailadres</label>
          <div class="flex gap-2 items-center">
            <input :value="profileEmail" type="email" disabled :class="[theme.form.input, 'bg-surface text-body cursor-not-allowed flex-1']" />
            <button type="button" @click="showEmailModal = true" class="text-sm text-accent-700 hover:text-accent-800 font-medium whitespace-nowrap">
              Wijzigen
            </button>
          </div>
          <div v-if="emailChangeSuccess" :class="theme.alert.success" class="mt-2">
            {{ emailChangeSuccess }}
          </div>
        </div>
        <div>
          <label :class="theme.form.label">Telefoonnummer</label>
          <div class="flex gap-2 items-start">
            <div class="flex-1">
              <div class="relative">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
                  <Phone :size="18" />
                </div>
                <input
                  v-model="profilePhone"
                  v-mask-phone
                  type="tel"
                  :class="theme.form.input"
                  class="pl-10"
                  placeholder="+31612345678"
                />
              </div>
            </div>
            <div v-if="profilePhone && !phoneVerifying" class="pt-1">
              <span v-if="phoneVerified" class="inline-flex items-center gap-1 text-xs font-medium text-green-700">
                <CheckCircle :size="14" /> Geverifieerd
              </span>
              <button
                v-else
                type="button"
                :disabled="!smsConfigured || phoneVerifyLoading"
                :title="!smsConfigured ? 'SMS is momenteel niet beschikbaar' : 'Verifieer je telefoonnummer'"
                @click="requestPhoneVerify"
                class="text-sm font-medium whitespace-nowrap"
                :class="smsConfigured ? 'text-accent-700 hover:text-accent-800' : 'text-muted cursor-not-allowed'"
              >
                {{ phoneVerifyLoading ? 'Verzenden...' : 'Verifiëren' }}
              </button>
            </div>
          </div>

          <!-- Phone OTP verification -->
          <div v-if="phoneVerifying" class="mt-3 p-4 bg-surface rounded-lg border border-navy-100 space-y-3">
            <div class="flex items-center gap-2">
              <MessageSquare :size="16" class="text-accent-700" />
              <p :class="theme.text.body" class="text-sm">
                Voer de 6-cijferige code in die naar je telefoon is verstuurd
              </p>
            </div>
            <div v-if="phoneVerifyError" :class="theme.alert.error" class="text-sm">{{ phoneVerifyError }}</div>
            <OtpInput
              v-model="phoneOtpCode"
              :length="6"
              autofocus
              @submit="confirmPhoneVerify"
            />
            <div class="flex gap-2 justify-end">
              <button type="button" @click="cancelPhoneVerify" :class="theme.btn.secondary" class="text-sm">
                Annuleren
              </button>
              <button
                type="button"
                :disabled="phoneVerifyLoading || phoneOtpCode.length !== 6"
                @click="confirmPhoneVerify"
                :class="theme.btn.primary"
                class="text-sm"
              >
                {{ phoneVerifyLoading ? 'Verifiëren...' : 'Bevestigen' }}
              </button>
            </div>
          </div>

          <div v-if="phoneVerifySuccess && !phoneVerifying" :class="theme.alert.success" class="mt-2 text-sm">
            {{ phoneVerifySuccess }}
          </div>
          <p v-if="!smsConfigured" :class="theme.text.muted" class="text-xs mt-1">
            SMS-verificatie is momenteel niet beschikbaar. Neem contact op met de beheerder.
          </p>
          <p v-else :class="theme.text.muted" class="text-xs mt-1">
            Internationaal formaat (E.164), bijv. +31612345678
          </p>
        </div>
        <button type="submit" :disabled="profileLoading" :class="theme.btn.primary">
          {{ profileLoading ? 'Opslaan...' : 'Profiel opslaan' }}
        </button>
      </form>
    </div>

    <!-- Password Tab -->
    <div v-if="activeTab === 'password'" :class="theme.card.padded">
      <h3 :class="theme.text.h3" class="mb-4">Wachtwoord wijzigen</h3>

      <div v-if="passwordError" :class="theme.alert.error">{{ passwordError }}</div>
      <div v-if="passwordSuccess" :class="theme.alert.success">
        {{ passwordSuccess }}
      </div>

      <form @submit.prevent="handleChangePassword" class="space-y-4">
        <div>
          <label :class="theme.form.label">Huidig wachtwoord</label>
          <input v-model="currentPassword" type="password" required autocomplete="current-password" :class="theme.form.input" />
        </div>
        <div>
          <label :class="theme.form.label">Nieuw wachtwoord</label>
          <input v-model="newPassword" type="password" required minlength="8" autocomplete="new-password" :class="theme.form.input" placeholder="Minimaal 8 tekens" />
        </div>
        <div>
          <label :class="theme.form.label">Bevestig nieuw wachtwoord</label>
          <input v-model="confirmPassword" type="password" required minlength="8" autocomplete="new-password" :class="theme.form.input" />
        </div>
        <button type="submit" :disabled="passwordLoading" :class="theme.btn.primary">
          {{ passwordLoading ? 'Opslaan...' : 'Wachtwoord wijzigen' }}
        </button>
      </form>
    </div>

    <!-- Sessions Tab -->
    <div v-if="activeTab === 'sessions'" :class="theme.card.base">
      <div :class="theme.list.sectionHeader">
        <h3 :class="theme.text.h3">Actieve sessies</h3>
        <IconButton variant="danger" title="Overal uitloggen" @click="logoutAllModal = true">
          <LogOut :size="16" />
        </IconButton>
      </div>

      <div v-if="sessionsError" :class="[theme.alert.error, 'm-4']">{{ sessionsError }}</div>

      <div v-if="sessionsLoading" class="p-6 text-center" :class="theme.text.muted">Laden...</div>

      <div v-else :class="theme.list.divider">
        <div v-for="session in sessions" :key="session.id" :class="theme.list.item">
          <div class="flex items-start gap-3">
            <div class="mt-0.5 text-muted">
              <Smartphone v-if="session.device_info?.device_type === 'mobile'" :size="20" />
              <Tablet v-else-if="session.device_info?.device_type === 'tablet'" :size="20" />
              <Monitor v-else :size="20" />
            </div>
            <div>
              <p :class="theme.text.h4">
                {{ session.device_info?.browser || 'Onbekend' }}
                <span class="font-normal text-muted"> op {{ session.device_info?.os || 'Onbekend' }}</span>
              </p>
              <p :class="theme.text.body" class="text-xs">
                IP: {{ session.ip_address || 'Onbekend' }} &middot;
                Ingelogd: {{ formatDate(session.created_at) }}
              </p>
              <p :class="theme.text.muted" class="text-xs">
                Laatst actief: {{ formatRelativeTime(session.last_used_at) }}
              </p>
              <div class="flex gap-1.5 mt-1">
                <span v-if="session.is_current" :class="[theme.badge.base, theme.badge.success]">Huidige sessie</span>
                <span
                  :class="[theme.badge.base, session.session_type === 'persistent' ? theme.badge.info : theme.badge.default]"
                >
                  {{ session.session_type === 'persistent' ? 'Persistent' : 'Browsersessie' }}
                </span>
              </div>
            </div>
          </div>
          <IconButton
            v-if="!session.is_current"
            variant="danger"
            title="Sessie beëindigen"
            @click="promptRevokeSession(session.id)"
          >
            <X :size="14" />
          </IconButton>
        </div>

        <div v-if="sessions.length === 0" :class="theme.list.empty">
          <p :class="theme.text.muted">Geen actieve sessies gevonden</p>
        </div>
      </div>
    </div>

    <!-- 2FA Tab -->
    <div v-if="activeTab === '2fa'" :class="theme.card.padded">
      <h3 :class="theme.text.h3" class="mb-4">Tweefactorauthenticatie (2FA)</h3>

      <div v-if="twoFaError" :class="theme.alert.error">{{ twoFaError }}</div>
      <div v-if="twoFaSuccess" :class="theme.alert.success">
        {{ twoFaSuccess }}
      </div>

      <!-- 2FA not enabled -->
      <div v-if="!totpEnabled && !showSetup">
        <p :class="theme.text.body" class="mb-4">
          Voeg een extra beveiligingslaag toe aan je account door tweefactorauthenticatie in te schakelen.
        </p>
        <button @click="startSetup2FA" :disabled="twoFaLoading" :class="theme.btn.primary">
          {{ twoFaLoading ? 'Laden...' : '2FA inschakelen' }}
        </button>
      </div>

      <!-- Setup flow -->
      <div v-if="showSetup" class="space-y-4">
        <p :class="theme.text.body">
          Scan de QR-code met je authenticator-app (bijv. Google Authenticator, Authy):
        </p>
        <div class="bg-white p-4 rounded-lg border border-navy-100 text-center">
          <img v-if="setupQrUri" :src="setupQrUri" alt="QR Code" class="mx-auto" />
          <p :class="theme.text.muted" class="mt-2 text-xs break-all">
            Handmatig: {{ setupSecret }}
          </p>
        </div>
        <div>
          <label :class="theme.form.label">Verificatiecode</label>
          <input v-model="setupCode" type="text" inputmode="numeric" maxlength="6" :class="theme.form.input" placeholder="6-cijferige code" />
        </div>
        <button @click="confirmSetup2FA" :disabled="twoFaLoading || setupCode.length !== 6" :class="theme.btn.primary">
          {{ twoFaLoading ? 'Verifiëren...' : 'Verificatie bevestigen' }}
        </button>
      </div>

      <!-- 2FA enabled: status, disable -->
      <div v-if="totpEnabled && !showSetup" class="space-y-4">
        <div class="flex items-center gap-2 mb-2">
          <span :class="[theme.badge.base, theme.badge.success]">Ingeschakeld</span>
          <p :class="theme.text.body">2FA is actief op je account</p>
        </div>

        <div class="p-3 bg-surface rounded-lg border border-navy-100 text-sm text-navy-700 space-y-2">
          <p>
            <strong>Primaire methode:</strong> Authenticator-app (TOTP)
          </p>
          <p>
            <strong>Herstelmethode:</strong> E-mailcode — beschikbaar als je geen toegang hebt tot je app
          </p>
          <p v-if="smsConfigured && phoneVerified">
            <strong>SMS-methode:</strong> SMS-code naar je geverifieerde telefoonnummer
          </p>
          <p v-else-if="smsConfigured && !phoneVerified" :class="theme.text.muted">
            <strong>SMS-methode:</strong> Verifieer je telefoonnummer bij Profiel om SMS als 2FA-methode te gebruiken
          </p>
        </div>

        <div class="border-t border-navy-100 pt-4 mt-4">
          <div>
            <label :class="theme.form.label">Wachtwoord om 2FA uit te schakelen</label>
            <input v-model="disablePassword" type="password" autocomplete="current-password" :class="theme.form.input" />
          </div>
          <button @click="disable2FA" :disabled="twoFaLoading || !disablePassword" class="mt-2 text-sm text-red-600 hover:text-red-800 font-medium">
            {{ twoFaLoading ? 'Uitschakelen...' : '2FA uitschakelen' }}
          </button>
        </div>
      </div>


    </div>

    <!-- Session revoke confirmation -->
    <ConfirmModal
      :open="revokeSessionModal"
      title="Sessie beëindigen"
      message="Weet je zeker dat je deze sessie wilt beëindigen? Het apparaat wordt automatisch uitgelogd."
      confirm-label="Beëindigen"
      variant="danger"
      @confirm="confirmRevokeSession"
      @cancel="revokeSessionModal = false; revokingSessionId = null"
    />

    <!-- Logout all confirmation -->
    <ConfirmModal
      :open="logoutAllModal"
      title="Overal uitloggen"
      message="Weet je zeker dat je op alle apparaten wilt uitloggen? Je wordt ook op dit apparaat uitgelogd."
      confirm-label="Overal uitloggen"
      variant="danger"
      @confirm="confirmLogoutAll"
      @cancel="logoutAllModal = false"
    />

    <!-- Delete Account -->
    <div class="mt-8 border-t border-red-200 pt-6">
      <h3 class="text-lg font-semibold text-red-700 mb-2">Gevarenzone</h3>
      <p :class="theme.text.body" class="mb-4">
        Het verwijderen van je account is permanent. Al je gegevens, sessies en koppelingen worden verwijderd.
      </p>
      <button @click="showDeleteModal = true" :class="theme.btn.dangerFill">
        Account verwijderen
      </button>
    </div>

    <!-- Delete Account Modal -->
    <Teleport to="body">
      <div v-if="showDeleteModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6 mx-4">
          <h3 class="text-lg font-semibold text-red-700 mb-2">Account verwijderen</h3>
          <p :class="theme.text.body" class="mb-4">
            Weet je zeker dat je je account wilt verwijderen? Dit kan niet ongedaan worden gemaakt.
          </p>

          <div v-if="deleteError" :class="[theme.alert.error, 'mb-4']">{{ deleteError }}</div>

          <form @submit.prevent="handleDeleteAccount" class="space-y-4">
            <div>
              <label :class="theme.form.label">Wachtwoord ter bevestiging</label>
              <input v-model="deletePassword" type="password" required autocomplete="current-password" :class="theme.form.input" />
            </div>
            <div class="flex gap-3 justify-end">
              <button type="button" @click="showDeleteModal = false; deleteError = ''; deletePassword = ''" :class="theme.btn.secondary">
                Annuleren
              </button>
              <button type="submit" :disabled="deleteLoading || !deletePassword" :class="theme.btn.dangerFill">
                {{ deleteLoading ? 'Verwijderen...' : 'Definitief verwijderen' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <!-- Email Change Modal -->
    <Teleport to="body">
      <div v-if="showEmailModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6 mx-4">
          <h3 :class="theme.text.h3" class="mb-4">E-mailadres wijzigen</h3>

          <div v-if="emailChangeError" :class="[theme.alert.error, 'mb-4']">{{ emailChangeError }}</div>

          <form @submit.prevent="handleEmailChange" class="space-y-4">
            <div>
              <label :class="theme.form.label">Nieuw e-mailadres</label>
              <input v-model="emailChangeNew" type="email" required :class="theme.form.input" placeholder="nieuw@voorbeeld.nl" />
            </div>
            <div>
              <label :class="theme.form.label">Huidig wachtwoord (ter bevestiging)</label>
              <input v-model="emailChangePassword" type="password" required autocomplete="current-password" :class="theme.form.input" />
            </div>
            <div class="flex gap-3 justify-end">
              <button type="button" @click="showEmailModal = false; emailChangeError = ''" :class="theme.btn.secondary">
                Annuleren
              </button>
              <button type="submit" :disabled="emailChangeLoading" :class="theme.btn.primary">
                {{ emailChangeLoading ? 'Verzenden...' : 'Verificatie versturen' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>
