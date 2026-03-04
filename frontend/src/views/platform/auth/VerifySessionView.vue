<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { CheckCircle, XCircle, Loader2 } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/platform/auth'
import { useBrandingStore } from '@/stores/branding'
import { theme } from '@/theme'

const route = useRoute()
const authStore = useAuthStore()
const branding = useBrandingStore()

const status = ref<'loading' | 'success' | 'error'>('loading')
const errorMessage = ref('')

onMounted(async () => {
  const token = route.query.token as string
  if (!token) {
    status.value = 'error'
    errorMessage.value = 'Geen token gevonden in de link.'
    return
  }

  try {
    const response = await authApi.verifyLoginSession(token)

    if (response.access_token && response.refresh_token) {
      // Store tokens and complete login
      authStore._handleTokens(response.access_token, response.refresh_token, 'persistent')
      await authStore.fetchUser()
      status.value = 'success'

      // Redirect to dashboard after brief delay
      setTimeout(() => {
        authStore._routeAfterLogin()
      }, 1500)
    } else {
      status.value = 'error'
      errorMessage.value = 'Geen tokens ontvangen.'
    }
  } catch (e: unknown) {
    status.value = 'error'
    const err = e as { response?: { data?: { detail?: string } } }
    errorMessage.value = err.response?.data?.detail ?? 'De link is ongeldig of verlopen.'
  }
})
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
      </div>

      <div :class="theme.card.padded">
        <!-- Loading -->
        <div v-if="status === 'loading'" class="text-center space-y-4">
          <Loader2 :size="48" class="text-accent-700 mx-auto animate-spin" />
          <p :class="theme.text.body">Sessie bevestigen...</p>
        </div>

        <!-- Success -->
        <div v-else-if="status === 'success'" class="text-center space-y-4">
          <CheckCircle :size="48" class="text-green-600 mx-auto" />
          <h2 :class="theme.text.h3">Sessie bevestigd</h2>
          <p :class="theme.text.body">
            Je bent ingelogd. Je wordt doorgestuurd...
          </p>
        </div>

        <!-- Error -->
        <div v-else class="text-center space-y-4">
          <XCircle :size="48" class="text-red-600 mx-auto" />
          <h2 :class="theme.text.h3">Link ongeldig</h2>
          <p :class="theme.text.body">
            {{ errorMessage }}
          </p>
          <div class="pt-2">
            <router-link to="/auth/login" :class="theme.btn.primary" class="inline-block">
              Opnieuw inloggen
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
