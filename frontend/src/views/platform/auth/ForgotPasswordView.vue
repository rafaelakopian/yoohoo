<script setup lang="ts">
import { ref } from 'vue'
import { Mail } from 'lucide-vue-next'
import { authApi } from '@/api/platform/auth'
import { theme } from '@/theme'

const email = ref('')
const loading = ref(false)
const sent = ref(false)
const error = ref('')

async function handleSubmit() {
  error.value = ''
  loading.value = true
  try {
    await authApi.forgotPassword(email.value)
    sent.value = true
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Er is een fout opgetreden'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div :class="theme.page.bgCenter">
    <div class="max-w-md w-full">
      <div class="text-center mb-8">
        <h1 :class="theme.text.h1">Wachtwoord vergeten</h1>
        <p :class="theme.text.subtitle">Vul je e-mailadres in om een resetlink te ontvangen</p>
      </div>

      <div v-if="sent" :class="theme.card.form">
        <div class="text-center">
          <div class="mb-4 text-green-600 text-4xl">&#10003;</div>
          <p :class="theme.text.body" class="mb-4">
            Als dit e-mailadres bij ons bekend is, ontvang je een e-mail met een resetlink.
          </p>
          <router-link to="/auth/login" :class="theme.link.primary">
            Terug naar inloggen
          </router-link>
        </div>
      </div>

      <form v-else @submit.prevent="handleSubmit" :class="theme.card.form">
        <div v-if="error" :class="theme.alert.error">{{ error }}</div>

        <div :class="theme.form.groupLast">
          <label for="email" :class="theme.form.label">E-mailadres</label>
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

        <button type="submit" :disabled="loading" :class="['w-full', theme.btn.primary]">
          {{ loading ? 'Verzenden...' : 'Resetlink versturen' }}
        </button>

        <p class="text-center mt-4" :class="theme.text.body">
          <router-link to="/auth/login" :class="theme.link.primary">Terug naar inloggen</router-link>
        </p>
      </form>
    </div>
  </div>
</template>
