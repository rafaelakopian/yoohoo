<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Users, KeyRound } from 'lucide-vue-next'
import { theme } from '@/theme'
import { useAuthStore } from '@/stores/auth'
import { adminApi, type PlatformStats } from '@/api/platform/admin'
import { PLATFORM } from '@/router/routes'

const route = useRoute()
const authStore = useAuthStore()
const isSuperAdmin = computed(() => authStore.user?.is_superadmin === true)

const stats = ref<PlatformStats | null>(null)

const isListView = computed(() =>
  route.name === 'platform-access-users' || route.name === 'platform-access-groups'
)

onMounted(async () => {
  try {
    stats.value = await adminApi.getStats()
  } catch {
    // silent
  }
})
</script>

<template>
  <div>
    <!-- Header + tabs: only on list views -->
    <template v-if="isListView">
      <div class="mb-6">
        <h2 :class="theme.text.h2">Toegangsbeheer</h2>
        <p :class="theme.text.muted">
          Beheer platform gebruikers en permissiegroepen
        </p>
      </div>

      <div class="flex gap-1 mb-6 bg-white rounded-lg border border-navy-100 p-1 w-fit">
        <router-link
          :to="`${PLATFORM}/access/users`"
          :class="[
            'flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors no-underline',
            route.name === 'platform-access-users' ? 'bg-accent-700 text-white' : 'text-body hover:text-navy-900',
          ]"
        >
          <Users :size="14" />
          Gebruikers
          <span
            v-if="stats?.platform_user_count != null"
            :class="[
              'ml-1.5 px-2 py-0.5 rounded-full text-xs font-semibold',
              route.name === 'platform-access-users' ? 'bg-accent-900 text-white' : 'bg-navy-100 text-navy-600',
            ]"
          >{{ stats.platform_user_count }}</span>
        </router-link>
        <router-link
          v-if="isSuperAdmin"
          :to="`${PLATFORM}/access/groups`"
          :class="[
            'flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors no-underline',
            route.name === 'platform-access-groups' ? 'bg-accent-700 text-white' : 'text-body hover:text-navy-900',
          ]"
        >
          <KeyRound :size="14" />
          Permissiegroepen
          <span
            v-if="stats?.platform_group_count != null"
            :class="[
              'ml-1.5 px-2 py-0.5 rounded-full text-xs font-semibold',
              route.name === 'platform-access-groups' ? 'bg-accent-900 text-white' : 'bg-navy-100 text-navy-600',
            ]"
          >{{ stats.platform_group_count }}</span>
        </router-link>
      </div>
    </template>

    <router-view />
  </div>
</template>
