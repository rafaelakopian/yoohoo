<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authApi } from '@/api/platform/auth'
import { useBrandingStore } from '@/stores/branding'
import { theme } from '@/theme'

const route = useRoute()
const router = useRouter()
const branding = useBrandingStore()

const loading = ref(true)
const success = ref(false)
const error = ref('')
const message = ref('')

onMounted(async () => {
  const token = route.query.token as string
  if (!token) {
    error.value = 'Geen token opgegeven'
    loading.value = false
    return
  }

  // Strip token from URL to prevent leakage via referrer/history
  router.replace({ path: route.path, query: {} })

  try {
    const result = await authApi.confirmEmailChange(token)
    message.value = result.message
    success.value = true
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Ongeldige of verlopen link'
  } finally {
    loading.value = false
  }
})

function goToLogin() {
  router.push('/auth/login')
}
</script>

<template>
  <div :class="theme.page.bgCenter">
    <div class="w-full max-w-md">
      <div :class="theme.card.padded" class="text-center">
        <h2 :class="theme.text.h2" class="mb-2">{{ branding.platformNameShort }}</h2>
        <h2 :class="theme.text.h3" class="mb-6">E-mailadres wijzigen</h2>

        <div v-if="loading" :class="theme.text.muted" class="py-8">
          Bezig met verifiëren...
        </div>

        <div v-else-if="success" class="space-y-4">
          <div :class="theme.alert.success">
            {{ message }}
          </div>
          <button @click="goToLogin" :class="theme.btn.primary" class="w-full">
            Naar inloggen
          </button>
        </div>

        <div v-else class="space-y-4">
          <div :class="theme.alert.error">{{ error }}</div>
          <button @click="goToLogin" :class="theme.btn.secondary" class="w-full">
            Naar inloggen
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
