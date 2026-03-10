<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { useBrandingStore } from '@/stores/branding'
import { useMobile } from '@/composables/useMobile'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import ImpersonationBanner from '@/components/ui/ImpersonationBanner.vue'
import MobileBottomNav from '@/components/platform/MobileBottomNav.vue'
import { theme } from '@/theme'

const authStore = useAuthStore()
const tenantStore = useTenantStore()
const brandingStore = useBrandingStore()
const { isMobile } = useMobile()
const sidebarRef = ref<InstanceType<typeof AppSidebar> | null>(null)

// Bottom nav: only on mobile, platform mode, no tenant selected
const showBottomNav = computed(() =>
  isMobile.value && authStore.hasPlatformAccess && !tenantStore.hasTenant && authStore.isAuthenticated
)

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
      <div class="flex min-h-screen" :class="[authStore.isImpersonating ? 'pt-12' : '', showBottomNav ? 'pb-16' : '']">
        <AppSidebar ref="sidebarRef" />
        <main class="flex-1 p-3 md:p-6 lg:p-8 relative max-w-[1800px]">
          <AppHeader @toggle-sidebar="sidebarRef?.toggleMobile()" />
          <div :class="theme.page.content">
            <router-view />
          </div>
        </main>
      </div>
      <MobileBottomNav v-if="showBottomNav" />
    </template>
    <template v-else>
      <router-view />
    </template>
  </div>
</template>
