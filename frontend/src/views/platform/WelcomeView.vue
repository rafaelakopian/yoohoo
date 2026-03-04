<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Building2, Handshake } from 'lucide-vue-next'
import { theme } from '@/theme'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { useBrandingStore } from '@/stores/branding'
import { COLLABORATION_LABEL } from '@/constants/collaboration'
import type { Tenant } from '@/types/models'

const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()
const branding = useBrandingStore()

onMounted(async () => {
  if (tenantStore.tenants.length === 0) {
    await tenantStore.fetchTenants()
  }

  // Auto-select if only one org and no collaborations
  if (tenantStore.myOrgs.length === 1 && tenantStore.myCollaborations.length === 0) {
    await selectTenant(tenantStore.myOrgs[0])
  }
})

async function selectTenant(tenant: Tenant) {
  await tenantStore.selectTenant(tenant)
  router.push(`/org/${tenant.slug}/dashboard`)
}
</script>

<template>
  <div :class="[theme.page.bgCenter, 'min-h-screen']">
    <div class="w-full max-w-2xl mx-auto px-4 py-12">
      <!-- Logo -->
      <div v-if="branding.currentLogo" class="flex justify-center mb-8">
        <img
          :src="branding.currentLogo"
          alt="Logo"
          class="w-20 h-20 rounded-full object-contain shadow-lg ring-4 ring-white bg-white"
        />
      </div>

      <h1 :class="[theme.text.h1, 'text-center mb-2']">Welkom, {{ authStore.user?.full_name }}</h1>
      <p :class="[theme.text.muted, 'text-center mb-8']">Kies een werkruimte om aan de slag te gaan.</p>

      <!-- Mijn organisaties -->
      <section v-if="tenantStore.myOrgs.length > 0" class="mb-8">
        <h2 :class="[theme.text.h3, 'mb-3']">Mijn organisaties</h2>
        <div class="grid gap-3">
          <button
            v-for="tenant in tenantStore.myOrgs"
            :key="tenant.id"
            @click="selectTenant(tenant)"
            :class="[theme.card.padded, 'flex items-center gap-4 text-left hover:shadow-md transition-shadow cursor-pointer w-full']"
          >
            <div class="flex items-center justify-center w-10 h-10 rounded-full bg-accent-100 flex-shrink-0">
              <Building2 :size="20" class="text-accent-700" />
            </div>
            <div>
              <p :class="theme.text.h4">{{ tenant.name }}</p>
              <p :class="theme.text.muted">{{ tenant.slug }}</p>
            </div>
          </button>
        </div>
      </section>

      <!-- Samenwerkingen -->
      <section v-if="tenantStore.myCollaborations.length > 0">
        <h2 :class="[theme.text.h3, 'mb-3']">{{ COLLABORATION_LABEL }}</h2>
        <div class="grid gap-3">
          <button
            v-for="tenant in tenantStore.myCollaborations"
            :key="tenant.id"
            @click="selectTenant(tenant)"
            :class="[theme.card.padded, 'flex items-center gap-4 text-left hover:shadow-md transition-shadow cursor-pointer w-full']"
          >
            <div class="flex items-center justify-center w-10 h-10 rounded-full bg-amber-100 flex-shrink-0">
              <Handshake :size="20" class="text-amber-700" />
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-2">
                <p :class="theme.text.h4">{{ tenant.name }}</p>
                <span :class="[theme.badge.base, theme.badge.info]" class="text-xs">{{ COLLABORATION_LABEL }}</span>
              </div>
              <p :class="theme.text.muted">{{ tenant.slug }}</p>
            </div>
          </button>
        </div>
      </section>

      <!-- Empty state -->
      <div
        v-if="tenantStore.myOrgs.length === 0 && tenantStore.myCollaborations.length === 0"
        :class="[theme.card.padded, 'text-center']"
      >
        <p :class="theme.text.muted">Je bent nog niet lid van een organisatie of samenwerking.</p>
      </div>
    </div>
  </div>
</template>
