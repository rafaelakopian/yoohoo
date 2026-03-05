<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search, ChevronDown } from 'lucide-vue-next'
import { theme } from '@/theme'
import { lookupUser, type UserLookupResult } from '@/api/platform/operations'
import QuickActions from '@/components/operations/QuickActions.vue'

const router = useRouter()
const query = ref('')
const results = ref<UserLookupResult[]>([])
const loading = ref(false)
const searched = ref(false)
const expandedUserId = ref<string | null>(null)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(query, (val) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (val.length < 3) {
    results.value = []
    searched.value = false
    expandedUserId.value = null
    return
  }
  debounceTimer = setTimeout(async () => {
    loading.value = true
    searched.value = true
    expandedUserId.value = null
    try {
      results.value = await lookupUser(val)
    } catch {
      results.value = []
    } finally {
      loading.value = false
    }
  }, 300)
})

function toggleExpand(u: UserLookupResult) {
  expandedUserId.value = expandedUserId.value === u.id ? null : u.id
}

function goToUser(u: UserLookupResult) {
  router.push({ name: 'platform-user-detail', params: { userId: u.id } })
}

async function reloadResults() {
  if (query.value.length >= 3) {
    results.value = await lookupUser(query.value)
  }
}
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 :class="theme.text.h2">User Lookup</h2>
      <p :class="[theme.text.muted, 'mt-1']">Zoek gebruikers op e-mail of naam</p>
    </div>

    <!-- Search -->
    <div class="relative mb-6 max-w-md">
      <Search :size="18" class="absolute left-3 top-1/2 -translate-y-1/2 text-body" />
      <input
        v-model="query"
        type="text"
        placeholder="Zoek op e-mail of naam (min. 3 tekens)..."
        :class="[theme.form.input, 'pl-10']"
      />
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-8">
      <p :class="theme.text.muted">Zoeken...</p>
    </div>

    <!-- Results -->
    <div v-else-if="results.length > 0" :class="theme.card.base" class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr :class="theme.list.sectionHeader">
            <th class="text-left p-3">Gebruiker</th>
            <th class="text-left p-3 hidden md:table-cell">Status</th>
            <th class="text-left p-3 hidden md:table-cell">Organisaties</th>
            <th class="text-right p-3 hidden lg:table-cell">Sessies</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="u in results" :key="u.id">
            <tr
              :class="theme.list.item"
              class="cursor-pointer hover:bg-surface/50"
              @click="toggleExpand(u)"
            >
              <td class="p-3">
                <p :class="theme.text.body" class="font-medium">{{ u.full_name }}</p>
                <p :class="theme.text.muted" class="text-xs">{{ u.email }}</p>
              </td>
              <td class="p-3 hidden md:table-cell">
                <div class="flex gap-1 flex-wrap">
                  <span :class="[theme.badge.base, u.is_active ? theme.badge.success : theme.badge.error]">
                    {{ u.is_active ? 'Actief' : 'Inactief' }}
                  </span>
                  <span v-if="u.is_superadmin" :class="[theme.badge.base, theme.badge.info]">
                    Superadmin
                  </span>
                  <span v-if="u.totp_enabled" :class="[theme.badge.base, theme.badge.default]">
                    2FA
                  </span>
                </div>
              </td>
              <td class="p-3 hidden md:table-cell">
                <div class="flex gap-1 flex-wrap">
                  <span
                    v-for="m in u.memberships"
                    :key="m.tenant_id"
                    :class="[theme.badge.base, theme.badge.default]"
                  >{{ m.tenant_name }}</span>
                  <span v-if="u.memberships.length === 0" :class="theme.text.muted">Geen orgs</span>
                </div>
              </td>
              <td class="p-3 text-right hidden lg:table-cell">
                <div class="flex items-center justify-end gap-2">
                  {{ u.active_sessions }}
                  <ChevronDown
                    :size="14"
                    class="transition-transform"
                    :class="expandedUserId === u.id ? 'rotate-180' : ''"
                  />
                </div>
              </td>
            </tr>
            <!-- Expandable detail row -->
            <tr v-if="expandedUserId === u.id && !u.is_superadmin">
              <td colspan="4" class="p-0">
                <div class="bg-surface p-4">
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <QuickActions :user="u" @reload="reloadResults" />
                    <div class="flex flex-col gap-2">
                      <button :class="theme.btn.ghost" @click="goToUser(u)">
                        Bekijk volledig profiel
                      </button>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- No results -->
    <div v-else-if="searched && !loading" :class="[theme.card.padded, 'text-center']">
      <p :class="theme.text.muted">Geen gebruikers gevonden voor "{{ query }}"</p>
    </div>
  </div>
</template>
