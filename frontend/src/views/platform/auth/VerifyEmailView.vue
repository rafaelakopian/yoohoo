<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CheckCircle, XCircle } from 'lucide-vue-next'
import { authApi } from '@/api/platform/auth'
import { useBrandingStore } from '@/stores/branding'
import { theme } from '@/theme'

const branding = useBrandingStore()

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const success = ref(false)
const errorMessage = ref<string | null>(null)

onMounted(async () => {
  const token = route.query.token as string | undefined

  if (!token) {
    loading.value = false
    errorMessage.value = 'Geen verificatietoken gevonden.'
    return
  }

  // Strip token from URL to prevent leakage via referrer/history
  router.replace({ path: route.path, query: {} })

  try {
    await authApi.verifyEmail(token)
    success.value = true
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    errorMessage.value = err.response?.data?.detail ?? 'Verificatie mislukt. De link is mogelijk verlopen.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div :class="theme.page.bgCenter">
    <div class="max-w-md w-full">
      <div class="text-center mb-8">
        <h2 :class="theme.text.h2">{{ branding.platformNameShort }}</h2>
      </div>

      <div :class="theme.card.form" class="text-center">
        <!-- Loading -->
        <div v-if="loading" class="py-8">
          <div class="mx-auto w-12 h-12 border-4 border-accent-200 border-t-accent-700 rounded-full animate-spin mb-4"></div>
          <p :class="theme.text.body">E-mailadres verifiëren...</p>
        </div>

        <!-- Success -->
        <div v-else-if="success" class="py-4">
          <div class="mx-auto w-16 h-16 bg-green-50 rounded-full flex items-center justify-center mb-4">
            <CheckCircle :size="32" class="text-green-600" />
          </div>
          <h2 :class="theme.text.h2" class="mb-2">E-mail geverifieerd!</h2>
          <p :class="theme.text.body" class="mb-6">
            Je account is geactiveerd. Je kunt nu inloggen.
          </p>
          <router-link to="/auth/login" :class="['inline-block w-full', theme.btn.primary]">
            Inloggen
          </router-link>
        </div>

        <!-- Error -->
        <div v-else class="py-4">
          <div class="mx-auto w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mb-4">
            <XCircle :size="32" class="text-red-600" />
          </div>
          <h2 :class="theme.text.h2" class="mb-2">Verificatie mislukt</h2>
          <p :class="theme.text.body" class="mb-6">
            {{ errorMessage }}
          </p>
          <router-link to="/auth/register" :class="['inline-block w-full mb-3', theme.btn.primary]">
            Opnieuw registreren
          </router-link>
          <p class="mt-3" :class="theme.text.body">
            <router-link to="/auth/login" :class="theme.link.primary">
              Terug naar inloggen
            </router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
