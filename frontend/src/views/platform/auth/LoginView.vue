<script setup lang="ts">
import { ref, computed } from 'vue'
import { Mail, Lock, Shield } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useBrandingStore } from '@/stores/branding'
import { authApi } from '@/api/platform/auth'
import { theme } from '@/theme'
import OtpInput from '@/components/ui/OtpInput.vue'

const authStore = useAuthStore()
const branding = useBrandingStore()

const email = ref('')
const password = ref('')
const rememberMe = ref(false)
const twoFactorCode = ref('')

// Email 2FA state
const twoFAMethod = ref<'totp' | 'email'>('totp')
const emailVerificationId = ref<string | null>(null)
const emailCodeSent = ref(false)
const sendingEmailCode = ref(false)
const emailCooldown = ref(0)
let cooldownTimer: ReturnType<typeof setInterval> | null = null

const hasEmailMethod = computed(() => authStore.available2FAMethods.includes('email'))

async function handleLogin() {
  try {
    await authStore.login(email.value, password.value, rememberMe.value)
  } catch {
    // Error is already handled in store
  }
}

function resetEmailVerification() {
  authStore.requiresEmailVerification = false
  authStore.error = null
}

async function handle2FA() {
  try {
    await authStore.verify2FA(
      twoFactorCode.value,
      twoFAMethod.value,
      twoFAMethod.value === 'email' ? emailVerificationId.value ?? undefined : undefined,
    )
  } catch {
    // Error is already handled in store
  }
}

async function sendEmailCode(purpose: string = '2fa_login') {
  if (!authStore.twoFactorToken || sendingEmailCode.value) return
  sendingEmailCode.value = true
  authStore.error = null

  try {
    const result = await authApi.send2FAEmailCode(authStore.twoFactorToken, purpose)
    emailVerificationId.value = result.verification_id
    emailCodeSent.value = true
    twoFAMethod.value = 'email'
    startCooldown()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    authStore.error = err.response?.data?.detail ?? 'Kon geen code versturen'
  } finally {
    sendingEmailCode.value = false
  }
}

function startCooldown() {
  emailCooldown.value = 60
  if (cooldownTimer) clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    emailCooldown.value--
    if (emailCooldown.value <= 0 && cooldownTimer) {
      clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

function switchToTotp() {
  twoFAMethod.value = 'totp'
  twoFactorCode.value = ''
  authStore.error = null
}

function cancel2FA() {
  authStore.twoFactorToken = null
  authStore.twoFactorEmail = null
  authStore.available2FAMethods = []
  authStore.error = null
  twoFactorCode.value = ''
  twoFAMethod.value = 'totp'
  emailVerificationId.value = null
  emailCodeSent.value = false
  if (cooldownTimer) {
    clearInterval(cooldownTimer)
    cooldownTimer = null
  }
}
</script>

<template>
  <div :class="theme.page.bgCenter">
    <div class="max-w-md w-full">
      <div class="text-center mb-8">
        <img
          v-if="branding.currentLogo"
          :src="branding.currentLogo"
          alt="Logo"
          class="w-36 h-36 mx-auto mb-4 rounded-full object-contain shadow-lg"
        />
        <h1 :class="theme.text.h1">{{ branding.platformNameShort }}</h1>
        <p :class="theme.text.subtitle">
          {{ authStore.requiresEmailVerification ? 'Controleer je e-mail' : authStore.requires2FA ? 'Tweestapsverificatie' : 'Log in om verder te gaan' }}
        </p>
      </div>

      <!-- Email verification screen (magic link sent) -->
      <div v-if="authStore.requiresEmailVerification" :class="theme.card.padded">
        <div class="text-center space-y-4">
          <Mail :size="48" class="text-accent-700 mx-auto" />
          <h2 :class="theme.text.h3">Beveiligingslink verstuurd</h2>
          <p :class="theme.text.body">
            We hebben een beveiligingslink naar je e-mailadres gestuurd.
            Klik op de link in de e-mail om in te loggen.
          </p>
          <p :class="theme.text.muted" class="text-sm">
            De link is 10 minuten geldig.
          </p>
          <div class="pt-4">
            <button @click="resetEmailVerification" :class="theme.btn.secondary">
              Opnieuw inloggen
            </button>
          </div>
        </div>
      </div>

      <!-- 2FA Form -->
      <form v-else-if="authStore.requires2FA" @submit.prevent="handle2FA" :class="theme.card.form">
        <div
          v-if="authStore.error"
          :class="theme.alert.error"
        >
          {{ authStore.error }}
        </div>

        <!-- TOTP method -->
        <template v-if="twoFAMethod === 'totp'">
          <div class="text-center mb-4">
            <Shield :size="32" class="text-accent-700 mx-auto mb-2" />
            <p :class="theme.text.body">
              Voer de 6-cijferige code in vanuit je authenticator-app
            </p>
          </div>

          <div :class="theme.form.groupLast">
            <label :class="theme.form.label">
              Verificatiecode
            </label>
            <OtpInput
              v-model="twoFactorCode"
              :length="6"
              autofocus
              @submit="handle2FA"
            />
            <p class="text-xs text-muted mt-1 text-center">Of gebruik een back-upcode</p>
          </div>
        </template>

        <!-- Email method -->
        <template v-else-if="twoFAMethod === 'email'">
          <div class="text-center mb-4">
            <Mail :size="32" class="text-accent-700 mx-auto mb-2" />
            <p :class="theme.text.body">
              Voer de verificatiecode in die naar je e-mail is verstuurd
            </p>
          </div>

          <div :class="theme.form.groupLast">
            <label :class="theme.form.label">
              E-mail verificatiecode
            </label>
            <OtpInput
              v-model="twoFactorCode"
              :length="6"
              autofocus
              @submit="handle2FA"
            />
            <p class="text-xs text-muted mt-1 text-center">
              <button
                v-if="emailCooldown <= 0"
                type="button"
                @click="sendEmailCode()"
                :class="theme.link.primary"
              >
                Code opnieuw versturen
              </button>
              <span v-else>Opnieuw versturen over {{ emailCooldown }}s</span>
            </p>
          </div>
        </template>

        <button
          type="submit"
          :disabled="authStore.loading || (twoFAMethod === 'email' && !emailCodeSent)"
          :class="['w-full', theme.btn.primary]"
        >
          {{ authStore.loading ? 'Verifiëren...' : 'Verifiëren' }}
        </button>

        <div class="text-center mt-4 space-y-2">
          <!-- Switch to email method -->
          <p v-if="twoFAMethod === 'totp' && hasEmailMethod">
            <button
              type="button"
              @click="sendEmailCode('2fa_recovery')"
              :disabled="sendingEmailCode"
              :class="theme.link.primary"
              class="text-sm"
            >
              {{ sendingEmailCode ? 'Code versturen...' : 'Geen toegang tot je app? Gebruik e-mail' }}
            </button>
          </p>
          <!-- Switch back to TOTP -->
          <p v-if="twoFAMethod === 'email'">
            <button type="button" @click="switchToTotp" :class="theme.link.primary" class="text-sm">
              Authenticator-app gebruiken
            </button>
          </p>
          <p>
            <button type="button" @click="cancel2FA" :class="theme.link.primary" class="text-sm">
              Annuleren
            </button>
          </p>
        </div>
      </form>

      <!-- Login Form -->
      <form v-else @submit.prevent="handleLogin" :class="theme.card.form">
        <div
          v-if="authStore.error"
          :class="theme.alert.error"
        >
          {{ authStore.error }}
        </div>

        <div :class="theme.form.group">
          <label for="email" :class="theme.form.label">
            E-mailadres
          </label>
          <div class="relative">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
              <Mail :size="18" />
            </div>
            <input
              id="email"
              v-model="email"
              type="email"
              required
              autocomplete="email"
              :class="theme.form.input"
              class="pl-10"
              placeholder="naam@voorbeeld.nl"
            />
          </div>
        </div>

        <div :class="theme.form.groupLast">
          <label for="password" :class="theme.form.label">
            Wachtwoord
          </label>
          <div class="relative">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
              <Lock :size="18" />
            </div>
            <input
              id="password"
              v-model="password"
              type="password"
              required
              autocomplete="current-password"
              :class="theme.form.input"
              class="pl-10"
              placeholder="Uw wachtwoord"
            />
          </div>
        </div>

        <div class="flex items-center gap-2 mb-4">
          <input
            id="rememberMe"
            v-model="rememberMe"
            type="checkbox"
            class="rounded border-navy-300 text-accent-700 focus:ring-accent-500"
          />
          <label for="rememberMe" class="text-sm text-body select-none cursor-pointer">
            Ingelogd blijven
          </label>
        </div>

        <button
          type="submit"
          :disabled="authStore.loading"
          :class="['w-full', theme.btn.primary]"
        >
          {{ authStore.loading ? 'Inloggen...' : 'Inloggen' }}
        </button>

        <div class="text-center mt-4 space-y-2">
          <p :class="theme.text.body">
            <router-link to="/auth/forgot-password" :class="theme.link.primary">
              Wachtwoord vergeten?
            </router-link>
          </p>
          <p :class="theme.text.body">
            Nog geen account?
            <router-link to="/auth/register" :class="theme.link.primary">
              Registreren
            </router-link>
          </p>
          <p :class="theme.text.body">
            <router-link to="/auth/account-recovery" :class="theme.link.primary" class="text-xs">
              Problemen met inloggen?
            </router-link>
          </p>
        </div>
      </form>
    </div>
  </div>
</template>
