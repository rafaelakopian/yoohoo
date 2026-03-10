<script setup lang="ts">
import { ref, computed, watch, markRaw } from 'vue'
import { useRoute } from 'vue-router'
import type { Component } from 'vue'
import {
  LayoutDashboard,
  Users,
  ClipboardCheck,
  CalendarDays,
  CalendarOff,
  Bell,
  Receipt,
  ChevronsLeft,
  ChevronsRight,
  Building2,
  Shield,
  ArrowLeft,
  FileText,
  Network,
  ListChecks,
  Workflow,
  Banknote,
  AlertTriangle,
  FileSpreadsheet,
  Package,
  Sparkles,
  Megaphone,
  CreditCard,
} from 'lucide-vue-next'

const iconMap: Record<string, Component> = {
  LayoutDashboard: markRaw(LayoutDashboard),
  Users: markRaw(Users),
  ClipboardCheck: markRaw(ClipboardCheck),
  CalendarDays: markRaw(CalendarDays),
  CalendarOff: markRaw(CalendarOff),
  Bell: markRaw(Bell),
  Receipt: markRaw(Receipt),
  Shield: markRaw(Shield),
  CreditCard: markRaw(CreditCard),
}

interface NavItem {
  label: string
  to: string
  icon: Component
  activePaths?: string[]
  excludePaths?: string[]
  exact?: boolean
}

interface NavSection {
  title: string
  items: NavItem[]
}
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { useBrandingStore } from '@/stores/branding'
import { usePermissions } from '@/composables/usePermissions'
import { useMobile } from '@/composables/useMobile'
import { useProductRegistry } from '@/composables/useProductRegistry'
import { orgPath, PLATFORM, WELCOME, OPS, FINANCE } from '@/router/routes'
import { theme } from '@/theme'
import { COLLABORATION_LABEL_SINGULAR } from '@/constants/collaboration'

function resolveIcon(name: string): Component {
  return iconMap[name] ?? markRaw(LayoutDashboard)
}

const route = useRoute()
const authStore = useAuthStore()
const tenantStore = useTenantStore()
const branding = useBrandingStore()
const { hasPermission, hasAnyPermission } = usePermissions()
const { isMobile } = useMobile()
const { navigation } = useProductRegistry()
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

const isPlatformMode = computed(() => authStore.hasPlatformAccess && !tenantStore.hasTenant)

// Mode 1: Platform Admin — grouped sections
const platformSections = computed<NavSection[]>(() => {
  if (!isPlatformMode.value) return []
  const sections: NavSection[] = []

  // ── FINANCE ──────────────────────────────────
  const finance: NavItem[] = []
  if (hasPermission('finance.view_dashboard'))
    finance.push({ label: 'Financieel overzicht', to: `${FINANCE}/revenue`, icon: markRaw(Banknote) })
  if (hasPermission('finance.view_dashboard'))
    finance.push({ label: 'Openstaand', to: `${FINANCE}/outstanding`, icon: markRaw(AlertTriangle) })
  if (hasPermission('billing.view'))
    finance.push({ label: 'Facturen', to: `${FINANCE}/invoices`, icon: markRaw(Receipt) })
  if (hasPermission('billing.view'))
    finance.push({ label: 'Abonnementen', to: `${FINANCE}/subscriptions`, icon: markRaw(CreditCard) })
  if (hasPermission('finance.export_reports'))
    finance.push({ label: 'BTW Rapportage', to: `${FINANCE}/tax`, icon: markRaw(FileSpreadsheet) })
  if (finance.length)
    sections.push({ title: 'Finance', items: finance })

  // ── PRODUCTEN & DIENSTEN ───────────────────────
  const producten: NavItem[] = []
  if (hasPermission('platform.manage_orgs'))
    producten.push({ label: 'Pakketbeheer', to: `${FINANCE}/plans`, icon: markRaw(Package) })
  if (producten.length)
    sections.push({ title: 'Producten & Diensten', items: producten })

  // ── SYSTEEM ───────────────────────────────────
  const systeem: NavItem[] = []
  if (hasPermission('platform_notifications.manage'))
    systeem.push({ label: 'Meldingen', to: `${PLATFORM}/notifications`, icon: markRaw(Megaphone) })
  systeem.push({ label: 'Topology', to: `${PLATFORM}/topology`, icon: markRaw(Network) })
  if (hasPermission('operations.view_jobs'))
    systeem.push({ label: 'Achtergrondtaken', to: `${OPS}/jobs`, icon: markRaw(Workflow) })
  if (hasPermission('platform.view_audit_logs'))
    systeem.push({ label: 'Audit logs', to: `${PLATFORM}/audit-logs`, icon: markRaw(FileText) })
  if (hasPermission('platform.view_users'))
    systeem.push({ label: 'Toegangsbeheer', to: `${PLATFORM}/access`, icon: markRaw(Shield), activePaths: [`${PLATFORM}/access`, `${PLATFORM}/groups`] })
  if (systeem.length)
    sections.push({ title: 'Systeem', items: systeem })

  return sections
})

const navItems = computed(() => {
  // Mode 1 is now handled by platformSections
  if (isPlatformMode.value) return []

  // Mode 2: Org Portal (tenant selected) — product nav from registry
  if (tenantStore.hasTenant) {
    const items: NavItem[] = []

    // Product navigation (from ProductRegistry)
    for (const nav of navigation.value) {
      // Empty permissions = always visible; otherwise OR logic
      const visible = nav.permissions.length === 0 || hasAnyPermission(...nav.permissions)
      if (visible) {
        items.push({
          label: nav.label,
          to: orgPath(nav.route_suffix),
          icon: resolveIcon(nav.icon),
          activePaths: nav.active_paths?.map(p => orgPath(p)),
        })
      }
    }

    // Framework navigation (always hardcoded — not product-specific)
    if (hasAnyPermission('invitations.view', 'invitations.manage', 'org_settings.view', 'collaborations.view', 'collaborations.manage')) {
      items.push({
        label: 'Toegangsbeheer', to: orgPath('users'), icon: markRaw(Shield),
        activePaths: [orgPath('users'), orgPath('permissions'), orgPath('collaborations')],
      })
    }

    // Upgrade/feature overview (visible to org admins)
    if (hasPermission('org_settings.view')) {
      items.push({
        label: 'Features & Upgrades', to: orgPath('upgrade'), icon: markRaw(Sparkles),
      })
    }

    return items
  }

  // Mode 3: No tenant (non-admin user) — no sidebar
  return []
})

const showSidebar = computed(() => isPlatformMode.value || navItems.value.length > 0)

function isActive(item: NavItem): boolean {
  const paths = item.activePaths || [item.to]
  if (item.exact) return paths.some(p => route.path === p)
  const matched = paths.some(p => route.path === p || route.path.startsWith(p + '/'))
  if (!matched || !item.excludePaths) return matched
  return !item.excludePaths.some(p => route.path === p || route.path.startsWith(p + '/'))
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
        : 'sticky top-0 h-screen overflow-y-auto z-[60]'
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

    <!-- Brand Logo Medallion — sticky on scroll -->
    <div
      v-if="branding.currentLogo"
      class="sticky top-[-30px] flex justify-center pt-[18px] pb-4 z-[999] bg-[inherit]"
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
    <nav class="px-3 mt-8 overflow-y-auto flex-1">
      <!-- Mode 1: Platform Admin — grouped sections -->
      <template v-if="isPlatformMode">
        <!-- Dashboard always on top -->
        <router-link
          :to="PLATFORM"
          :class="[
            theme.sidebar.navItem,
            isActive({ label: 'Dashboard', to: PLATFORM, icon: LayoutDashboard, exact: true }) ? theme.sidebar.navActive : theme.sidebar.navInactive,
            !isMobile && collapsed ? 'justify-center px-0' : ''
          ]"
          :title="!isMobile && collapsed ? 'Dashboard' : undefined"
        >
          <LayoutDashboard :size="18" />
          <span v-if="isMobile || !collapsed">Dashboard</span>
        </router-link>

        <!-- Grouped sections -->
        <template v-for="section in platformSections" :key="section.title">
          <div v-if="isMobile || !collapsed" :class="theme.sidebar.sectionLabel">{{ section.title }}</div>
          <ul class="space-y-0.5">
            <li v-for="item in section.items" :key="item.to">
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
        </template>
      </template>

      <!-- Mode 2: Org Portal — flat list (UNCHANGED) -->
      <ul v-else class="space-y-1">
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
