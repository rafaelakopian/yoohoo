<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Mail, Lock, User } from 'lucide-vue-next'
import { authApi } from '@/api/platform/auth'
import { useBrandingStore } from '@/stores/branding'
import { theme } from '@/theme'

const branding = useBrandingStore()
import type { InviteInfo } from '@/types/auth'
import { useAuthStore } from '@/stores/auth'
import { extractError } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const isLoggedIn = computed(() => !!authStore.user)

const token = ref('')
const info = ref<InviteInfo | null>(null)
const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const success = ref(false)

// New user fields
const fullName = ref('')
const password = ref('')
const confirmPassword = ref('')

const needsLogin = computed(() =>
  info.value?.is_existing_user &&
  info.value?.invitation_type === 'platform' &&
  !isLoggedIn.value
)

function getRoleLabel(info: InviteInfo): string {
  if (info.group_name) return info.group_name
  return 'Lid'
}

onMounted(async () => {
  // Try URL token first, fallback to sessionStorage (for returning from login)
  token.value = (route.query.token as string) || sessionStorage.getItem('pending_invite_token') || ''
  if (!token.value) {
    error.value = 'Geen geldige uitnodigingslink gevonden'
    loading.value = false
    return
  }

  // Persist token for post-login return, then strip from URL
  sessionStorage.setItem('pending_invite_token', token.value)
  if (route.query.token) {
    router.replace({ path: route.path, query: {} })
  }

  try {
    info.value = await authApi.getInviteInfo(token.value)
  } catch (e: unknown) {
    error.value = extractError(e, 'accept')
    // Token is invalid/expired — clean up so future logins aren't redirected here
    sessionStorage.removeItem('pending_invite_token')
  } finally {
    loading.value = false
  }
})

async function handleAccept() {
  error.value = ''

  if (!info.value?.is_existing_user) {
    if (password.value !== confirmPassword.value) {
      error.value = 'Wachtwoorden komen niet overeen'
      return
    }
  }

  submitting.value = true
  try {
    const payload: any = { token: token.value }
    if (!info.value?.is_existing_user) {
      payload.password = password.value
      payload.full_name = fullName.value
    }
    await authApi.acceptInvite(payload)
    sessionStorage.removeItem('pending_invite_token')
    success.value = true
  } catch (e: unknown) {
    error.value = extractError(e, 'accept')
  } finally {
    submitting.value = false
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

      <!-- Loading -->
      <div v-if="loading" :class="theme.card.form" class="text-center">
        <h2 :class="theme.text.h2" class="mb-4">Uitnodiging</h2>
        <p :class="theme.text.muted">Uitnodiging laden...</p>
      </div>

      <!-- Error (no info) -->
      <div v-else-if="error && !info" :class="theme.card.form">
        <div :class="theme.alert.error">{{ error }}</div>
        <router-link to="/auth/login" :class="theme.link.primary">Naar inloggen</router-link>
      </div>

      <!-- Success -->
      <div v-else-if="success" :class="theme.card.form" class="text-center">
        <div class="mb-4 text-green-600 text-4xl">&#10003;</div>
        <p :class="theme.text.body" class="mb-4">
          <template v-if="info?.invitation_type === 'platform'">
            Uitnodiging geaccepteerd! Je bent nu medewerker van het platform.
          </template>
          <template v-else-if="info?.invitation_type === 'collaboration'">
            Uitnodiging geaccepteerd! Je bent nu medewerker bij {{ info?.org_name }}.
          </template>
          <template v-else>
            Uitnodiging geaccepteerd! Je bent nu lid van {{ info?.org_name }}.
          </template>
        </p>
        <router-link to="/auth/login" :class="theme.link.primary">
          Naar inloggen
        </router-link>
      </div>

      <!-- Accept form -->
      <div v-else-if="info" :class="theme.card.form">
        <h2 :class="theme.text.h2" class="text-center mb-4">Uitnodiging</h2>
        <div class="mb-6 text-center">
          <p :class="theme.text.body">
            <template v-if="info.invitation_type === 'platform'">
              <strong>{{ info.inviter_name }}</strong> heeft je uitgenodigd als
              <strong>medewerker</strong> van het platform
            </template>
            <template v-else-if="info.invitation_type === 'collaboration'">
              <strong>{{ info.inviter_name }}</strong> heeft je uitgenodigd als
              <strong>externe medewerker</strong> bij
            </template>
            <template v-else>
              <strong>{{ info.inviter_name }}</strong> heeft je uitgenodigd als
              <strong>{{ getRoleLabel(info) }}</strong> bij
            </template>
          </p>
          <p v-if="info.org_name" :class="theme.text.h3" class="mt-1">{{ info.org_name }}</p>
        </div>

        <div v-if="error" :class="theme.alert.error">{{ error }}</div>

        <!-- Existing user: needs login first (platform invites) -->
        <div v-if="needsLogin">
          <p :class="theme.text.body" class="mb-4">
            Je hebt al een account met <strong>{{ info.email }}</strong>.
            Log eerst in om de uitnodiging te accepteren.
          </p>
          <router-link to="/auth/login" :class="['w-full block text-center', theme.btn.primary]">
            Inloggen
          </router-link>
        </div>

        <!-- Existing user: logged in, just accept -->
        <div v-else-if="info.is_existing_user">
          <p :class="theme.text.body" class="mb-4">
            Je hebt al een account met <strong>{{ info.email }}</strong>.
            Klik hieronder om de uitnodiging te accepteren.
          </p>
          <button @click="handleAccept" :disabled="submitting" :class="['w-full', theme.btn.primary]">
            {{ submitting ? 'Accepteren...' : 'Uitnodiging accepteren' }}
          </button>
        </div>

        <!-- New user: registration form -->
        <form v-else @submit.prevent="handleAccept" class="space-y-4">
          <p :class="theme.text.body" class="mb-2">
            Maak een account aan voor <strong>{{ info.email }}</strong>:
          </p>

          <div>
            <label :class="theme.form.label">Volledige naam</label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
                <User :size="18" />
              </div>
              <input v-model="fullName" v-mask-name type="text" required autocomplete="name" :class="theme.form.input" class="pl-10" placeholder="Je naam" />
            </div>
          </div>

          <div>
            <label :class="theme.form.label">Wachtwoord</label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
                <Lock :size="18" />
              </div>
              <input v-model="password" type="password" required minlength="8" autocomplete="new-password" :class="theme.form.input" class="pl-10" placeholder="Minimaal 8 tekens" />
            </div>
          </div>

          <div>
            <label :class="theme.form.label">Bevestig wachtwoord</label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
                <Lock :size="18" />
              </div>
              <input v-model="confirmPassword" type="password" required minlength="8" autocomplete="new-password" :class="theme.form.input" class="pl-10" />
            </div>
          </div>

          <button type="submit" :disabled="submitting" :class="['w-full', theme.btn.primary]">
            {{ submitting ? 'Account aanmaken...' : 'Account aanmaken & accepteren' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>
