<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { Component } from 'vue'
import {
  LayoutDashboard,
  CalendarDays,
  CalendarOff,
  Bell,
  ChevronsLeft,
  ChevronsRight,
  Users,
  ClipboardCheck,
  Building2,
  Shield,
  ArrowLeft,
  ArrowRight,
  FileText,
  Receipt,
  Network,
  Activity,
  ListChecks,
  Search,
} from 'lucide-vue-next'

interface NavItem {
  label: string
  to: string
  icon: Component
  activePaths?: string[]
  exact?: boolean
}
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { useBrandingStore } from '@/stores/branding'
import { usePermissions } from '@/composables/usePermissions'
import { useMobile } from '@/composables/useMobile'
import { orgPath, PLATFORM, WELCOME, OPS } from '@/router/routes'
import { theme } from '@/theme'
import { COLLABORATION_LABEL_SINGULAR } from '@/constants/collaboration'

const route = useRoute()
const authStore = useAuthStore()
const tenantStore = useTenantStore()
const branding = useBrandingStore()
const { hasPermission, hasAnyPermission } = usePermissions()
const { isMobile } = useMobile()
const collapsed = ref(false)
const mobileOpen = ref(false)

function toggleMobile() {
  mobileOpen.value = !mobileOpen.value
}

defineExpose({ toggleMobile })

// Auto-close mobile drawer on navigation
watch(() => route.path, () => {
  if (isMobile.value) mobileOpen.value = false
})

const navItems = computed(() => {
  // Mode 1: Platform Admin (superadmin or platform permissions, no tenant selected)
  if (authStore.hasPlatformAccess && !tenantStore.hasTenant) {
    const items: NavItem[] = []
    if (hasPermission('platform.view_stats'))
      items.push({ label: 'Platform', to: PLATFORM, icon: LayoutDashboard, exact: true })
    if (hasPermission('platform.view_orgs'))
      items.push({ label: 'Organisaties', to: `${PLATFORM}/orgs`, icon: Building2 })
    if (hasAnyPermission('platform.view_users', 'platform.manage_groups'))
      items.push({
        label: 'Toegangsbeheer', to: `${PLATFORM}/users`, icon: Shield,
        activePaths: [`${PLATFORM}/users`, `${PLATFORM}/groups`],
      })
    if (hasPermission('platform.view_audit_logs'))
      items.push({ label: 'Audit logs', to: `${PLATFORM}/audit-logs`, icon: FileText })
    items.push({ label: 'Topology', to: `${PLATFORM}/topology`, icon: Network })

    // Operations
    if (hasPermission('operations.view_dashboard'))
      items.push({ label: 'Klantoverzicht', to: OPS, icon: Activity, exact: true })
    if (hasPermission('operations.view_onboarding'))
      items.push({ label: 'Onboarding', to: `${OPS}/onboarding`, icon: ListChecks })
    if (hasPermission('operations.view_users'))
      items.push({ label: 'User Lookup', to: `${OPS}/users`, icon: Search })

    return items
  }

  // Mode 2: Org Portal (tenant selected)
  if (tenantStore.hasTenant) {
    const items: NavItem[] = [
      { label: 'Dashboard', to: orgPath('dashboard'), icon: LayoutDashboard },
    ]

    if (hasAnyPermission('students.view', 'students.view_assigned', 'students.view_own')) {
      items.push({ label: 'Leerlingen', to: orgPath('students'), icon: Users })
    }
    if (hasAnyPermission('attendance.view', 'attendance.view_assigned', 'attendance.view_own')) {
      items.push({ label: 'Aanwezigheid', to: orgPath('attendance'), icon: ClipboardCheck })
    }
    if (hasAnyPermission('schedule.view', 'schedule.view_assigned')) {
      items.push({ label: 'Rooster', to: orgPath('schedule'), icon: CalendarDays })
      items.push({ label: 'Vakanties', to: orgPath('holidays'), icon: CalendarOff })
    }
    if (hasPermission('notifications.view')) {
      items.push({ label: 'Notificaties', to: orgPath('notifications'), icon: Bell })
    }
    if (hasAnyPermission('billing.view', 'billing.view_own')) {
      items.push({
        label: 'Facturatie', to: orgPath('billing'), icon: Receipt,
        activePaths: [orgPath('billing'), orgPath('billing/plans'), orgPath('billing/students'), orgPath('billing/invoices')],
      })
    }
    if (hasAnyPermission('invitations.view', 'invitations.manage', 'org_settings.view', 'collaborations.view', 'collaborations.manage')) {
      items.push({
        label: 'Toegangsbeheer', to: orgPath('users'), icon: Shield,
        activePaths: [orgPath('users'), orgPath('permissions'), orgPath('collaborations')],
      })
    }

    return items
  }

  // Mode 3: No tenant (non-admin user) — no sidebar
  return []
})

const showSidebar = computed(() => navItems.value.length > 0)

function isActive(item: NavItem): boolean {
  const paths = item.activePaths || [item.to]
  if (item.exact) return paths.some(p => route.path === p)
  return paths.some(p => route.path === p || route.path.startsWith(p + '/'))
}
</script>

<template>
  <!-- Mobile backdrop overlay -->
  <Transition
    enter-active-class="transition-opacity duration-300"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-200"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="isMobile && mobileOpen && showSidebar"
      class="fixed inset-0 bg-black/40 z-[55] md:hidden"
      @click="mobileOpen = false"
    />
  </Transition>

  <aside
    v-if="showSidebar"
    :class="[
      'bg-white border-r border-navy-100 flex flex-col transition-all duration-200 overflow-visible',
      isMobile
        ? 'fixed inset-y-0 left-0 w-64 z-[60] transition-transform duration-300 ' + (mobileOpen ? 'translate-x-0' : '-translate-x-full')
        : 'relative min-h-screen z-[60]'
    ]"
    :style="!isMobile ? { width: collapsed ? '128px' : '256px', minWidth: collapsed ? '128px' : '256px', flexShrink: 0 } : undefined"
  >
    <!-- Collapse knop — alleen desktop -->
    <button
      v-if="!isMobile"
      @click="collapsed = !collapsed"
      :class="[
        'absolute top-2 z-[1000] p-1 rounded-full border border-navy-100 bg-white/80 text-navy-200 hover:text-navy-400 hover:border-navy-200 transition-all cursor-pointer',
        collapsed ? 'left-1/2 -translate-x-1/2' : 'right-2'
      ]"
      :title="collapsed ? 'Uitklappen' : 'Inklappen'"
    >
      <ChevronsLeft v-if="!collapsed" :size="14" />
      <ChevronsRight v-else :size="14" />
    </button>

    <!-- Brand Logo Medallion -->
    <div
      v-if="branding.currentLogo"
      class="flex justify-center pt-12 pb-4 relative z-[999]"
    >
      <img
        :src="branding.currentLogo"
        alt="Logo"
        :class="[
          'rounded-full object-contain shadow-lg ring-4 ring-white bg-white transition-all duration-200',
          !isMobile && collapsed ? 'w-20 h-20' : 'w-24 h-24'
        ]"
      />
    </div>

    <!-- Collaboration badge -->
    <div
      v-if="tenantStore.isCurrentCollaboration"
      class="flex justify-center pb-1"
    >
      <span :class="[theme.badge.base, theme.badge.info]">
        {{ COLLABORATION_LABEL_SINGULAR }}
      </span>
    </div>

    <!-- Navigatie -->
    <nav class="px-3 mt-8">
      <ul class="space-y-1">
        <li v-for="item in navItems" :key="item.to">
          <router-link
            :to="item.to"
            :class="[
              theme.sidebar.navItem,
              isActive(item) ? theme.sidebar.navActive : theme.sidebar.navInactive,
              !isMobile && collapsed ? 'justify-center px-0' : ''
            ]"
            :title="!isMobile && collapsed ? item.label : undefined"
          >
            <component :is="item.icon" :size="18" />
            <span v-if="isMobile || !collapsed">{{ item.label }}</span>
          </router-link>
        </li>
      </ul>
    </nav>

    <!-- Bottom links -->
    <div class="mt-auto px-3 pb-4">
      <!-- Platform user + tenant selected: "Terug naar platform" -->
      <router-link
        v-if="authStore.hasPlatformAccess && tenantStore.hasTenant"
        :to="PLATFORM"
        :class="[
          theme.sidebar.navItem,
          theme.sidebar.navInactive,
          !isMobile && collapsed ? 'justify-center px-0' : '',
          'border-t border-navy-100 pt-3 mt-3'
        ]"
        :title="!isMobile && collapsed ? 'Terug naar platform' : undefined"
        @click="tenantStore.clearTenant()"
      >
        <ArrowLeft :size="18" />
        <span v-if="isMobile || !collapsed">Terug naar platform</span>
      </router-link>

      <!-- Non-admin + tenant selected: "Mijn werkruimten" or "Andere organisatie" -->
      <router-link
        v-else-if="tenantStore.hasTenant"
        :to="WELCOME"
        :class="[
          theme.sidebar.navItem,
          theme.sidebar.navInactive,
          !isMobile && collapsed ? 'justify-center px-0' : '',
          'border-t border-navy-100 pt-3 mt-3'
        ]"
        :title="!isMobile && collapsed ? (tenantStore.isCurrentCollaboration ? 'Mijn werkruimten' : 'Andere organisatie') : undefined"
      >
        <Building2 :size="18" />
        <span v-if="isMobile || !collapsed">{{ tenantStore.isCurrentCollaboration ? 'Mijn werkruimten' : 'Andere organisatie' }}</span>
      </router-link>
    </div>
  </aside>
</template>
