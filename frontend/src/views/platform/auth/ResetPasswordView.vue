<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock } from 'lucide-vue-next'
import { authApi } from '@/api/platform/auth'
import { theme } from '@/theme'

const route = useRoute()
const router = useRouter()
const token = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const success = ref(false)
const error = ref('')

onMounted(() => {
  token.value = (route.query.token as string) || ''
  if (!token.value) {
    error.value = 'Geen geldige resetlink gevonden'
  } else {
    // Strip token from URL to prevent leakage via referrer/history
    router.replace({ path: route.path, query: {} })
  }
})

async function handleSubmit() {
  error.value = ''

  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Wachtwoorden komen niet overeen'
    return
  }

  if (newPassword.value.length < 8) {
    error.value = 'Wachtwoord moet minimaal 8 tekens bevatten'
    return
  }

  loading.value = true
  try {
    await authApi.resetPassword(token.value, newPassword.value)
    success.value = true
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
        <h1 :class="theme.text.h1">Nieuw wachtwoord</h1>
        <p :class="theme.text.subtitle">Stel een nieuw wachtwoord in voor je account</p>
      </div>

      <div v-if="success" :class="theme.card.form">
        <div class="text-center">
          <div class="mb-4 text-green-600 text-4xl">&#10003;</div>
          <p :class="theme.text.body" class="mb-4">
            Je wachtwoord is succesvol gewijzigd. Je kunt nu inloggen.
          </p>
          <router-link to="/auth/login" :class="theme.link.primary">
            Naar inloggen
          </router-link>
        </div>
      </div>

      <form v-else @submit.prevent="handleSubmit" :class="theme.card.form">
        <div v-if="error" :class="theme.alert.error">{{ error }}</div>

        <div :class="theme.form.group">
          <label for="password" :class="theme.form.label">Nieuw wachtwoord</label>
          <div class="relative">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
              <Lock :size="18" />
            </div>
            <input
              id="password"
              v-model="newPassword"
              type="password"
              required
              minlength="8"
              autocomplete="new-password"
              :class="theme.form.input"
              class="pl-10"
              placeholder="Minimaal 8 tekens"
            />
          </div>
        </div>

        <div :class="theme.form.groupLast">
          <label for="confirm" :class="theme.form.label">Bevestig wachtwoord</label>
          <div class="relative">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
              <Lock :size="18" />
            </div>
            <input
              id="confirm"
              v-model="confirmPassword"
              type="password"
              required
              minlength="8"
              autocomplete="new-password"
              :class="theme.form.input"
              class="pl-10"
              placeholder="Herhaal wachtwoord"
            />
          </div>
        </div>

        <button type="submit" :disabled="loading || !token" :class="['w-full', theme.btn.primary]">
          {{ loading ? 'Opslaan...' : 'Wachtwoord opslaan' }}
        </button>
      </form>
    </div>
  </div>
</template>
