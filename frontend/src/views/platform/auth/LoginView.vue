<script setup lang="ts">
import { ref } from 'vue'
import { Mail, Lock, Shield } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useBrandingStore } from '@/stores/branding'
import { theme } from '@/theme'

const authStore = useAuthStore()
const branding = useBrandingStore()

const email = ref('')
const password = ref('')
const twoFactorCode = ref('')

async function handleLogin() {
  try {
    await authStore.login(email.value, password.value)
  } catch {
    // Error is already handled in store
  }
}

async function handle2FA() {
  try {
    await authStore.verify2FA(twoFactorCode.value)
  } catch {
    // Error is already handled in store
  }
}

function cancel2FA() {
  authStore.twoFactorToken = null
  authStore.twoFactorEmail = null
  authStore.error = null
  twoFactorCode.value = ''
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
          {{ authStore.requires2FA ? 'Voer je verificatiecode in' : 'Log in om verder te gaan' }}
        </p>
      </div>

      <!-- 2FA Form -->
      <form v-if="authStore.requires2FA" @submit.prevent="handle2FA" :class="theme.card.form">
        <div
          v-if="authStore.error"
          :class="theme.alert.error"
        >
          {{ authStore.error }}
        </div>

        <div class="text-center mb-4">
          <Shield :size="32" class="text-accent-700 mx-auto mb-2" />
          <p :class="theme.text.body">
            Voer de 6-cijferige code in vanuit je authenticator-app
          </p>
        </div>

        <div :class="theme.form.groupLast">
          <label for="twoFactorCode" :class="theme.form.label">
            Verificatiecode
          </label>
          <input
            id="twoFactorCode"
            v-model="twoFactorCode"
            type="text"
            inputmode="numeric"
            maxlength="8"
            required
            autocomplete="one-time-code"
            :class="theme.form.input"
            class="text-center text-lg tracking-widest"
            placeholder="000000"
            autofocus
          />
          <p class="text-xs text-muted mt-1">Of gebruik een back-upcode</p>
        </div>

        <button
          type="submit"
          :disabled="authStore.loading"
          :class="['w-full', theme.btn.primary]"
        >
          {{ authStore.loading ? 'Verifiëren...' : 'Verifiëren' }}
        </button>

        <p class="text-center mt-4">
          <button type="button" @click="cancel2FA" :class="theme.link.primary" class="text-sm">
            Annuleren
          </button>
        </p>
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
