<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useBrandingStore } from '@/stores/branding'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import ImpersonationBanner from '@/components/ui/ImpersonationBanner.vue'
import { theme } from '@/theme'

const authStore = useAuthStore()
const brandingStore = useBrandingStore()
const sidebarRef = ref<InstanceType<typeof AppSidebar> | null>(null)

onMounted(() => {
  brandingStore.load()
})

watch(() => brandingStore.platformNameShort, (name) => {
  if (name) document.title = name
})
</script>

<template>
  <div :class="theme.page.bg">
    <ImpersonationBanner v-if="authStore.isImpersonating" />
    <template v-if="authStore.isAuthenticated">
      <div class="flex min-h-screen" :class="authStore.isImpersonating ? 'pt-12' : ''">
        <AppSidebar ref="sidebarRef" />
        <main class="flex-1 p-3 md:p-6 lg:p-8 relative max-w-[1800px]">
          <AppHeader @toggle-sidebar="sidebarRef?.toggleMobile()" />
          <router-view />
        </main>
      </div>
    </template>
    <template v-else>
      <router-view />
    </template>
  </div>
</template>
