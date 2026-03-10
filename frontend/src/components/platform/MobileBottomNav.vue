<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { usePermissions } from '@/composables/usePermissions'
import { Home, Building2, Euro, Settings } from 'lucide-vue-next'
import { PLATFORM, FINANCE } from '@/router/routes'
import { theme } from '@/theme'

const { hasPermission } = usePermissions()
const route = useRoute()

const tabs = computed(() => {
  const t = [
    { label: 'Home', to: PLATFORM, icon: Home },
  ]
  if (hasPermission('platform.view_orgs') || hasPermission('operations.view_users'))
    t.push({ label: 'Klanten', to: `${PLATFORM}/orgs`, icon: Building2 })
  if (hasPermission('finance.view_dashboard'))
    t.push({ label: 'Finance', to: `${FINANCE}/revenue`, icon: Euro })
  if (hasPermission('operations.view_jobs') || hasPermission('platform.view_audit_logs'))
    t.push({ label: 'Systeem', to: `${PLATFORM}/topology`, icon: Settings })
  return t
})

function isActive(to: string): boolean {
  return route.path === to || route.path.startsWith(to + '/')
}
</script>

<template>
  <nav :class="theme.bottomNav.bar">
    <RouterLink
      v-for="tab in tabs"
      :key="tab.to"
      :to="tab.to"
      :class="[theme.bottomNav.item, isActive(tab.to) ? theme.bottomNav.itemActive : theme.bottomNav.itemInactive]"
    >
      <component :is="tab.icon" class="w-5 h-5" />
      <span :class="theme.bottomNav.label">{{ tab.label }}</span>
    </RouterLink>
  </nav>
</template>
