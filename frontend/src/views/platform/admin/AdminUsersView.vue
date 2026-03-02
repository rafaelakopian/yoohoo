<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Search,
  Shield,
  ShieldOff,
  Eye,
  ChevronLeft,
  ChevronRight,
} from 'lucide-vue-next'
import { theme } from '@/theme'
import { adminApi, type AdminUserItem } from '@/api/platform/admin'
import { useAuthStore } from '@/stores/auth'
import IconButton from '@/components/ui/IconButton.vue'
import RouteTabs from '@/components/ui/RouteTabs.vue'

const platformTabs = [
  { label: 'Gebruikers', to: '/platform/users' },
  { label: 'Groepen', to: '/platform/groups' },
]

const router = useRouter()
const authStore = useAuthStore()

const users = ref<AdminUserItem[]>([])
const totalUsers = ref(0)
const loading = ref(true)
const searchQuery = ref('')
const searchTimeout = ref<ReturnType<typeof setTimeout> | null>(null)
const currentPage = ref(0)
const pageSize = 25

const totalPages = computed(() => Math.max(1, Math.ceil(totalUsers.value / pageSize)))

onMounted(() => fetchUsers())

async function fetchUsers(search?: string) {
  loading.value = true
  try {
    const result = await adminApi.getUsers({
      search,
      skip: currentPage.value * pageSize,
      limit: pageSize,
    })
    users.value = result.items
    totalUsers.value = result.total
  } catch {
    // Handled silently
  } finally {
    loading.value = false
  }
}

function onSearch() {
  if (searchTimeout.value) clearTimeout(searchTimeout.value)
  searchTimeout.value = setTimeout(() => {
    currentPage.value = 0
    fetchUsers(searchQuery.value || undefined)
  }, 300)
}

function goToPage(page: number) {
  currentPage.value = page
  fetchUsers(searchQuery.value || undefined)
}

async function toggleSuperAdmin(user: AdminUserItem) {
  const newValue = !user.is_superadmin
  try {
    await adminApi.toggleSuperAdmin(user.id, newValue)
    user.is_superadmin = newValue
  } catch {
    // Handled silently
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('nl-NL', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 :class="theme.text.h2">Toegangsbeheer</h2>
    </div>

    <RouteTabs :tabs="platformTabs" />

    <!-- Search -->
    <div :class="[theme.card.base, 'mb-4']">
      <div class="p-4">
        <div class="relative">
          <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-body" />
          <input
            v-model="searchQuery"
            @input="onSearch"
            type="text"
            placeholder="Zoek op naam of e-mail..."
            :class="[theme.form.input, 'pl-10']"
          />
        </div>
      </div>
    </div>

    <!-- Users table -->
    <div :class="theme.card.base">
      <div v-if="loading" :class="theme.list.empty">
        <p :class="theme.text.muted">Laden...</p>
      </div>

      <div v-else-if="users.length === 0" :class="theme.list.empty">
        <p :class="theme.text.muted">Geen gebruikers gevonden</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-navy-100 text-left">
              <th class="px-6 py-3 font-medium text-navy-700">Gebruiker</th>
              <th class="px-6 py-3 font-medium text-navy-700">Status</th>
              <th class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">Rol</th>
              <th class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">Scholen</th>
              <th class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">Aangemaakt</th>
              <th class="px-6 py-3 font-medium text-navy-700 text-right">Acties</th>
            </tr>
          </thead>
          <tbody :class="theme.list.divider">
            <tr
              v-for="user in users"
              :key="user.id"
              class="hover:bg-surface transition-colors cursor-pointer"
              @click="router.push(`/platform/users/${user.id}`)"
            >
              <td class="px-6 py-4">
                <div class="flex items-center gap-2">
                  <div>
                    <p class="font-medium text-navy-900">{{ user.full_name }}</p>
                    <p class="text-xs text-body">{{ user.email }}</p>
                  </div>
                  <span
                    v-if="user.id === authStore.user?.id"
                    :class="[theme.badge.base, theme.badge.info]"
                  >You</span>
                </div>
              </td>
              <td class="px-6 py-4">
                <div class="flex items-center gap-2">
                  <span
                    :class="[theme.badge.base, user.is_active ? theme.badge.success : theme.badge.warning]"
                  >{{ user.is_active ? 'Actief' : 'Inactief' }}</span>
                  <span v-if="!user.email_verified" :class="[theme.badge.base, theme.badge.warning]">
                    Niet geverifieerd
                  </span>
                </div>
              </td>
              <td class="px-6 py-4 hidden md:table-cell">
                <span v-if="user.is_superadmin" :class="[theme.badge.base, theme.badge.info]">Super Admin</span>
                <span v-else class="text-body">Gebruiker</span>
              </td>
              <td class="px-6 py-4 text-body hidden md:table-cell">{{ user.membership_count }}</td>
              <td class="px-6 py-4 text-body hidden md:table-cell">{{ formatDate(user.created_at) }}</td>
              <td class="px-6 py-4">
                <div class="flex items-center justify-end gap-1">
                  <IconButton
                    variant="accent"
                    title="Details bekijken"
                    @click.stop="router.push(`/platform/users/${user.id}`)"
                  >
                    <Eye :size="16" />
                  </IconButton>
                  <IconButton
                    :variant="user.is_superadmin ? 'danger' : 'accent'"
                    :title="user.id === authStore.user?.id && user.is_superadmin
                      ? 'Je kunt je eigen superadmin niet ontnemen'
                      : user.is_superadmin ? 'Admin intrekken' : 'Admin maken'"
                    :disabled="user.id === authStore.user?.id && user.is_superadmin"
                    @click.stop="toggleSuperAdmin(user)"
                  >
                    <ShieldOff v-if="user.is_superadmin" :size="16" />
                    <Shield v-else :size="16" />
                  </IconButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-between px-6 py-3 border-t border-navy-100">
          <p class="text-xs text-body">
            {{ totalUsers }} gebruiker{{ totalUsers === 1 ? '' : 's' }} totaal
          </p>
          <div class="flex items-center gap-1">
            <button
              @click="goToPage(currentPage - 1)"
              :disabled="currentPage === 0"
              class="p-1.5 rounded text-body hover:text-navy-900 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft :size="16" />
            </button>
            <span class="text-xs text-navy-700 px-2">
              {{ currentPage + 1 }} / {{ totalPages }}
            </span>
            <button
              @click="goToPage(currentPage + 1)"
              :disabled="currentPage >= totalPages - 1"
              class="p-1.5 rounded text-body hover:text-navy-900 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight :size="16" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
