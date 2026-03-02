<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronDown, School, ArrowRight, Handshake } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { COLLABORATION_LABEL } from '@/constants/collaboration'
import type { Tenant } from '@/types/models'

const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()
const open = ref(false)

onMounted(async () => {
  if (tenantStore.tenants.length === 0) {
    await tenantStore.fetchTenants()
  }
})

const currentId = computed(() => tenantStore.currentTenantId)

const otherFullTenants = computed(() => {
  return tenantStore.mySchools.filter((t) => t.id !== currentId.value)
})

const otherCollabTenants = computed(() => {
  return tenantStore.myCollaborations.filter((t) => t.id !== currentId.value)
})

// Fallback for platform admins: show all other tenants not in mySchools/myCollaborations
const otherAdminTenants = computed(() => {
  if (!authStore.hasPlatformAccess) return []
  const knownIds = new Set([
    ...tenantStore.mySchools.map((t) => t.id),
    ...tenantStore.myCollaborations.map((t) => t.id),
  ])
  return tenantStore.tenants.filter(
    (t) => t.id !== currentId.value && t.is_provisioned && !knownIds.has(t.id),
  )
})

const hasOtherTenants = computed(
  () => otherFullTenants.value.length > 0 || otherCollabTenants.value.length > 0 || otherAdminTenants.value.length > 0,
)

function toggle() {
  open.value = !open.value
}

function close() {
  open.value = false
}

async function switchTenant(tenant: Tenant) {
  close()
  await tenantStore.selectTenant(tenant)
  window.location.href = `/org/${tenant.slug}/dashboard`
}

function goToSelect() {
  close()
  tenantStore.clearTenant()
  router.push('/welcome')
}
</script>

<template>
  <div class="relative">
    <button
      v-if="tenantStore.currentTenant"
      @click="toggle"
      class="flex items-center gap-1.5 px-3 py-1 rounded-lg text-sm text-accent-100 bg-navy-800 hover:bg-navy-700 transition-colors"
    >
      <Handshake v-if="tenantStore.isCurrentCollaboration" :size="14" />
      <School v-else :size="14" />
      {{ tenantStore.currentTenant.name }}
      <ChevronDown :size="12" class="text-navy-400" :class="{ 'rotate-180': open }" />
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
        v-if="open"
        class="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-navy-100 py-1 z-50"
      >
        <!-- Mijn scholen -->
        <template v-if="otherFullTenants.length > 0 || otherAdminTenants.length > 0">
          <div class="px-4 py-2 border-b border-navy-100">
            <p class="text-xs font-medium text-muted uppercase tracking-wider">Mijn scholen</p>
          </div>
          <div class="max-h-32 overflow-y-auto">
            <button
              v-for="tenant in [...otherFullTenants, ...otherAdminTenants]"
              :key="tenant.id"
              @click="switchTenant(tenant)"
              class="w-full flex items-center gap-2 px-4 py-2 text-sm text-navy-700 hover:bg-surface transition-colors"
            >
              <School :size="14" class="text-navy-400 flex-shrink-0" />
              <span class="truncate">{{ tenant.name }}</span>
            </button>
          </div>
        </template>

        <!-- Samenwerkingen -->
        <template v-if="otherCollabTenants.length > 0">
          <div class="px-4 py-2 border-b border-navy-100">
            <p class="text-xs font-medium text-muted uppercase tracking-wider">{{ COLLABORATION_LABEL }}</p>
          </div>
          <div class="max-h-32 overflow-y-auto">
            <button
              v-for="tenant in otherCollabTenants"
              :key="tenant.id"
              @click="switchTenant(tenant)"
              class="w-full flex items-center gap-2 px-4 py-2 text-sm text-navy-700 hover:bg-surface transition-colors"
            >
              <Handshake :size="14" class="text-navy-400 flex-shrink-0" />
              <span class="truncate">{{ tenant.name }}</span>
            </button>
          </div>
        </template>

        <div v-if="!hasOtherTenants" class="px-4 py-2 text-sm text-muted">
          Geen andere werkruimten beschikbaar
        </div>

        <div class="border-t border-navy-100 pt-1">
          <button
            @click="goToSelect"
            class="w-full flex items-center gap-2 px-4 py-2 text-sm text-accent-700 hover:bg-accent-50 transition-colors"
          >
            <ArrowRight :size="14" />
            Alle werkruimten bekijken
          </button>
        </div>
      </div>
    </Transition>

    <!-- Backdrop -->
    <div
      v-if="open"
      class="fixed inset-0 z-40"
      @click="close"
    />
  </div>
</template>
