<script setup lang="ts">
import { ref } from 'vue'
import { Mail } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useBrandingStore } from '@/stores/branding'
import { authApi } from '@/api/platform/auth'
import { theme } from '@/theme'

const authStore = useAuthStore()
const branding = useBrandingStore()

const resending = ref(false)
const resendMessage = ref<string | null>(null)
const resendError = ref<string | null>(null)

async function handleResend() {
  if (!authStore.registeredEmail) return
  resending.value = true
  resendMessage.value = null
  resendError.value = null

  try {
    const result = await authApi.resendVerification(authStore.registeredEmail)
    resendMessage.value = result.message
  } catch {
    resendError.value = 'Er is iets misgegaan. Probeer het later opnieuw.'
  } finally {
    resending.value = false
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

      <div :class="theme.card.form" class="text-center">
        <div class="mb-6">
          <div class="mx-auto w-16 h-16 bg-accent-50 rounded-full flex items-center justify-center mb-4">
            <Mail :size="32" class="text-accent-700" />
          </div>
          <h2 :class="theme.text.h2" class="mb-2">Controleer je e-mail</h2>
          <p :class="theme.text.body" class="mb-2">
            We hebben een verificatie-e-mail gestuurd naar:
          </p>
          <p class="font-medium text-navy-900 mb-4">
            {{ authStore.registeredEmail || 'je e-mailadres' }}
          </p>
          <p :class="theme.text.body">
            Klik op de link in de e-mail om je account te activeren.
          </p>
        </div>

        <div v-if="resendMessage" :class="theme.alert.success">
          {{ resendMessage }}
        </div>

        <div v-if="resendError" :class="theme.alert.error">
          {{ resendError }}
        </div>

        <button
          @click="handleResend"
          :disabled="resending || !authStore.registeredEmail"
          :class="['w-full mb-3', theme.btn.secondary]"
        >
          {{ resending ? 'Versturen...' : 'Verificatie-e-mail opnieuw versturen' }}
        </button>

        <p class="text-center mt-4" :class="theme.text.body">
          <router-link to="/auth/login" :class="theme.link.primary">
            Terug naar inloggen
          </router-link>
        </p>
      </div>
    </div>
  </div>
</template>
