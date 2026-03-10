<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { LogOut, UserRound, ChevronDown, Settings, Palette, Menu, Building2, ListChecks } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { useBrandingStore, AVAILABLE_THEMES } from '@/stores/branding'
import { usePermissions } from '@/composables/usePermissions'
import { theme } from '@/theme'
import { PLATFORM } from '@/router/routes'
import NotificationBell from '@/components/products/school/notification/NotificationBell.vue'
import PlatformNotificationBell from '@/components/layout/PlatformNotificationBell.vue'
import TenantSwitcher from '@/components/ui/TenantSwitcher.vue'

const emit = defineEmits<{ 'toggle-sidebar': [] }>()

const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()
const branding = useBrandingStore()

const route = useRoute()
const { hasPermission } = usePermissions()

const isPlatformMode = computed(() => authStore.hasPlatformAccess && !tenantStore.hasTenant)

const klantenNav = computed(() => {
  if (!isPlatformMode.value) return []
  const items: { label: string; to: string; icon: object; activePaths: string[]; excludePaths?: string[] }[] = []
  if (hasPermission('platform.view_orgs'))
    items.push({ label: 'Organisaties', to: `${PLATFORM}/orgs`, icon: Building2, activePaths: [`${PLATFORM}/orgs`], excludePaths: [`${PLATFORM}/orgs/onboarding`] })
  if (hasPermission('operations.view_onboarding'))
    items.push({ label: 'Onboarding', to: `${PLATFORM}/orgs/onboarding`, icon: ListChecks, activePaths: [`${PLATFORM}/orgs/onboarding`] })
  return items
})

function isNavActive(item: { activePaths: string[]; excludePaths?: string[] }): boolean {
  const matched = item.activePaths.some(p => route.path === p || route.path.startsWith(p + '/'))
  if (!matched || !item.excludePaths) return matched
  return !item.excludePaths.some(p => route.path === p || route.path.startsWith(p + '/'))
}

const menuOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)
const scrolled = ref(false)

function onScroll() {
  scrolled.value = window.scrollY > 8
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
})

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function closeMenu() {
  menuOpen.value = false
}

function onDocumentClick(e: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) {
    closeMenu()
  }
}

watch(menuOpen, (open) => {
  if (open) {
    document.addEventListener('click', onDocumentClick, true)
  } else {
    document.removeEventListener('click', onDocumentClick, true)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick, true)
  window.removeEventListener('scroll', onScroll)
})

function handleLogout() {
  closeMenu()
  authStore.logout()
}
</script>

<template>
  <div
    class="flex items-center justify-between gap-2 mb-4 md:mb-0 md:fixed md:top-0 md:right-0 md:left-64 z-50 md:px-6 md:py-3 bg-surface transition-shadow duration-300"
    :class="scrolled ? 'md:shadow-sm' : ''"
  >
    <!-- Left: hamburger (mobile) + Klanten nav (desktop platform mode) -->
    <div class="flex items-center gap-1">
      <button
        @click="emit('toggle-sidebar')"
        class="p-2 rounded-none hover:bg-surface transition-colors md:hidden"
      >
        <Menu :size="20" class="text-navy-700" />
      </button>

      <template v-if="klantenNav.length">
        <router-link
          v-for="item in klantenNav"
          :key="item.to"
          :to="item.to"
          :class="[
            'hidden md:flex items-center gap-1.5 px-3 py-1.5 text-sm transition-colors',
            isNavActive(item)
              ? 'text-accent-700 font-medium'
              : 'text-body hover:text-navy-900',
          ]"
        >
          <component :is="item.icon" :size="15" />
          <span>{{ item.label }}</span>
        </router-link>
      </template>
    </div>

    <!-- Right: switcher + notifications + user menu -->
    <div class="flex items-center gap-2">
      <TenantSwitcher />
      <PlatformNotificationBell />
      <NotificationBell />

      <!-- Gebruikersmenu -->
      <div ref="menuRef" class="relative">
        <button
          @click="toggleMenu"
          class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white shadow-sm border border-navy-100 hover:bg-surface transition-colors"
        >
          <div class="w-7 h-7 rounded-full bg-navy-100 flex items-center justify-center">
            <UserRound :size="14" class="text-navy-600" />
          </div>
          <span class="text-sm font-medium text-navy-700 hidden sm:inline">
            {{ authStore.user?.full_name }}
          </span>
          <ChevronDown :size="14" class="text-navy-400" :class="{ 'rotate-180': menuOpen }" />
        </button>

        <Transition
          enter-active-class="transition duration-150 ease-out"
          enter-from-class="opacity-0 scale-95 -translate-y-1"
          enter-to-class="opacity-100 scale-100 translate-y-0"
          leave-active-class="transition duration-100 ease-in"
          leave-from-class="opacity-100 scale-100 translate-y-0"
          leave-to-class="opacity-0 scale-95 -translate-y-1"
        >
          <div
            v-if="menuOpen"
            class="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-navy-100 py-1 z-50"
          >
            <div class="px-4 py-2 border-b border-navy-100">
              <p class="text-sm font-medium text-navy-900">{{ authStore.user?.full_name }}</p>
              <p class="text-xs text-muted truncate">{{ authStore.user?.email }}</p>
            </div>
            <button
              @click="closeMenu(); router.push('/auth/account')"
              class="w-full flex items-center gap-2 px-4 py-2 text-sm text-navy-700 hover:bg-surface transition-colors"
            >
              <Settings :size="14" />
              Account
            </button>
            <!-- Theme switcher -->
            <div class="border-t border-navy-100">
              <div class="flex items-center gap-2 text-xs text-muted px-4 pt-2 pb-1">
                <Palette :size="12" />
                <span>Thema</span>
              </div>
              <button
                v-for="t in AVAILABLE_THEMES"
                :key="t.id"
                @click="branding.setTheme(t.id)"
                :class="[
                  'w-full text-left px-4 py-1.5 text-sm transition-colors',
                  branding.currentTheme === t.id
                    ? 'text-accent-700 font-medium bg-accent-50'
                    : 'text-navy-700 hover:bg-surface'
                ]"
              >
                {{ t.label }}
              </button>
            </div>
            <button
              @click="handleLogout"
              class="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors border-t border-navy-100"
            >
              <LogOut :size="14" />
              Uitloggen
            </button>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>
