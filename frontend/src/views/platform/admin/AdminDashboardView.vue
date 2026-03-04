<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Building2,
  Users,
  BarChart3,
  ArrowRight,
  Network,
} from 'lucide-vue-next'
import { theme } from '@/theme'
import { useBrandingStore } from '@/stores/branding'
import { adminApi, type PlatformStats } from '@/api/platform/admin'

const branding = useBrandingStore()

const router = useRouter()
const stats = ref<PlatformStats | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    stats.value = await adminApi.getStats()
  } catch {
    // Handled silently
  } finally {
    loading.value = false
  }
})

const cards = [
  {
    label: 'Organisaties beheren',
    description: 'Bekijk en beheer alle organisaties',
    icon: Building2,
    to: '/platform/orgs',
  },
  {
    label: 'Gebruikers beheren',
    description: 'Bekijk en beheer alle gebruikers',
    icon: Users,
    to: '/platform/users',
  },
  {
    label: 'Service Topology',
    description: 'Architectuur en infrastructuur overzicht',
    icon: Network,
    to: '/platform/topology',
  },
]
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 :class="theme.text.h2">Platform Beheer</h2>
      <p :class="[theme.text.body, 'mt-1']">Overzicht van het {{ branding.platformNameShort }} platform</p>
    </div>

    <!-- Stats -->
    <div v-if="loading" class="text-center py-8">
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <div v-else-if="stats" class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      <div :class="[theme.card.padded, 'flex items-center gap-4']">
        <div class="w-12 h-12 rounded-xl bg-primary-50 flex items-center justify-center">
          <Building2 :size="24" class="text-primary-600" />
        </div>
        <div>
          <p :class="theme.text.muted">Organisaties</p>
          <p :class="theme.text.h2">{{ stats.active_tenants }}</p>
          <p class="text-xs text-body">{{ stats.provisioned_tenants }} ingericht</p>
        </div>
      </div>

      <div :class="[theme.card.padded, 'flex items-center gap-4']">
        <div class="w-12 h-12 rounded-xl bg-accent-50 flex items-center justify-center">
          <Users :size="24" class="text-accent-700" />
        </div>
        <div>
          <p :class="theme.text.muted">Gebruikers</p>
          <p :class="theme.text.h2">{{ stats.total_users }}</p>
          <p class="text-xs text-body">{{ stats.active_users }} actief</p>
        </div>
      </div>

      <div :class="[theme.card.padded, 'flex items-center gap-4']">
        <div class="w-12 h-12 rounded-xl bg-green-50 flex items-center justify-center">
          <BarChart3 :size="24" class="text-green-600" />
        </div>
        <div>
          <p :class="theme.text.muted">Totaal organisaties</p>
          <p :class="theme.text.h2">{{ stats.total_tenants }}</p>
          <p class="text-xs text-body">{{ stats.total_tenants - stats.active_tenants }} inactief</p>
        </div>
      </div>
    </div>

    <!-- Quick links -->
    <h3 :class="[theme.text.h3, 'mb-4']">Snelkoppelingen</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <button
        v-for="card in cards"
        :key="card.to"
        @click="router.push(card.to)"
        :class="[theme.card.padded, 'flex items-center justify-between hover:shadow-md transition-shadow cursor-pointer text-left w-full']"
      >
        <div class="flex items-center gap-4">
          <div class="w-10 h-10 rounded-lg bg-surface flex items-center justify-center">
            <component :is="card.icon" :size="20" class="text-navy-600" />
          </div>
          <div>
            <p :class="theme.text.h4">{{ card.label }}</p>
            <p :class="theme.text.body">{{ card.description }}</p>
          </div>
        </div>
        <ArrowRight :size="18" class="text-body" />
      </button>
    </div>
  </div>
</template>
