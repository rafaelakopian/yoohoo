<script setup lang="ts">
import { ref } from 'vue'
import { User, Mail, Lock, Eye, EyeOff } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useBrandingStore } from '@/stores/branding'
import { theme } from '@/theme'

const authStore = useAuthStore()
const branding = useBrandingStore()

const fullName = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const validationError = ref<string | null>(null)
const showPassword = ref(false)
const showConfirmPassword = ref(false)

async function handleRegister() {
  validationError.value = null

  if (password.value !== confirmPassword.value) {
    validationError.value = 'Wachtwoorden komen niet overeen'
    return
  }

  if (password.value.length < 8) {
    validationError.value = 'Wachtwoord moet minimaal 8 tekens bevatten'
    return
  }

  try {
    await authStore.register(email.value, password.value, fullName.value)
  } catch {
    // Error is handled in store
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
          class="w-36 h-36 mx-auto rounded-full object-contain shadow-lg"
        />
      </div>

      <form @submit.prevent="handleRegister" :class="theme.card.form">
        <h2 :class="theme.text.h2" class="text-center mb-6">Maak een nieuw account aan</h2>
        <div
          v-if="authStore.error || validationError"
          :class="theme.alert.error"
        >
          {{ validationError || authStore.error }}
        </div>

        <div :class="theme.form.group">
          <label for="fullName" :class="theme.form.label">
            Volledige naam
          </label>
          <div class="relative">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
              <User :size="18" />
            </div>
            <input
              id="fullName"
              v-model="fullName"
              v-mask-name
              type="text"
              required
              autocomplete="name"
              :class="theme.form.input"
              class="pl-10"
              placeholder="Uw naam"
            />
          </div>
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

        <div :class="theme.form.group">
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
              :type="showPassword ? 'text' : 'password'"
              required
              minlength="8"
              autocomplete="new-password"
              :class="theme.form.input"
              class="pl-10 pr-10"
              placeholder="Minimaal 8 tekens"
            />
            <button
              type="button"
              @click="showPassword = !showPassword"
              class="absolute inset-y-0 right-0 pr-3 flex items-center text-muted hover:text-navy-500 transition-colors"
            >
              <EyeOff v-if="showPassword" :size="18" />
              <Eye v-else :size="18" />
            </button>
          </div>
        </div>

        <div :class="theme.form.groupLast">
          <label for="confirmPassword" :class="theme.form.label">
            Wachtwoord bevestigen
          </label>
          <div class="relative">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
              <Lock :size="18" />
            </div>
            <input
              id="confirmPassword"
              v-model="confirmPassword"
              :type="showConfirmPassword ? 'text' : 'password'"
              required
              autocomplete="new-password"
              :class="theme.form.input"
              class="pl-10 pr-10"
              placeholder="Herhaal wachtwoord"
            />
            <button
              type="button"
              @click="showConfirmPassword = !showConfirmPassword"
              class="absolute inset-y-0 right-0 pr-3 flex items-center text-muted hover:text-navy-500 transition-colors"
            >
              <EyeOff v-if="showConfirmPassword" :size="18" />
              <Eye v-else :size="18" />
            </button>
          </div>
        </div>

        <button
          type="submit"
          :disabled="authStore.loading"
          :class="['w-full', theme.btn.primary]"
        >
          {{ authStore.loading ? 'Account aanmaken...' : 'Registreren' }}
        </button>

        <p class="text-center mt-4" :class="theme.text.body">
          Al een account?
          <router-link to="/auth/login" :class="theme.link.primary">
            Inloggen
          </router-link>
        </p>
      </form>
    </div>
  </div>
</template>
