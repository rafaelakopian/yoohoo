<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Building2, Users, CheckCircle, Activity } from 'lucide-vue-next'
import { theme } from '@/theme'
import {
  getOperationsDashboard,
  type TenantHealthDashboard,
  type TenantHealthItem,
} from '@/api/platform/operations'

const router = useRouter()
const dashboard = ref<TenantHealthDashboard | null>(null)
const loading = ref(true)
const error = ref('')
const search = ref('')
const statusFilter = ref<'all' | 'active' | 'inactive' | 'unprovisioned'>('all')

onMounted(async () => {
  try {
    dashboard.value = await getOperationsDashboard()
  } catch {
    error.value = 'Kon dashboard niet laden'
  } finally {
    loading.value = false
  }
})

const filteredTenants = computed(() => {
  if (!dashboard.value) return []
  let items = dashboard.value.tenants

  if (search.value) {
    const q = search.value.toLowerCase()
    items = items.filter(
      (t) => t.name.toLowerCase().includes(q) || t.slug.toLowerCase().includes(q),
    )
  }

  if (statusFilter.value === 'active') items = items.filter((t) => t.is_active)
  if (statusFilter.value === 'inactive') items = items.filter((t) => !t.is_active)
  if (statusFilter.value === 'unprovisioned') items = items.filter((t) => !t.is_provisioned)

  return items
})

function goToTenant(t: TenantHealthItem) {
  router.push({ name: 'ops-tenant-360', params: { tenantId: t.id } })
}

function formatDate(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 :class="theme.text.h2">Klantoverzicht</h2>
      <p :class="[theme.text.muted, 'mt-1']">Platform monitoring &amp; tenant health</p>
    </div>

    <div v-if="loading" class="text-center py-8">
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <div v-else-if="error" :class="theme.alert.error">{{ error }}</div>

    <template v-else-if="dashboard">
      <!-- Stats cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div :class="[theme.card.padded, 'flex items-center gap-3']">
          <Building2 :size="20" class="text-primary-600" />
          <div>
            <p :class="theme.text.muted">Organisaties</p>
            <p :class="theme.text.h3">{{ dashboard.total_tenants }}</p>
          </div>
        </div>
        <div :class="[theme.card.padded, 'flex items-center gap-3']">
          <CheckCircle :size="20" class="text-green-600" />
          <div>
            <p :class="theme.text.muted">Actief</p>
            <p :class="theme.text.h3">{{ dashboard.active_tenants }}</p>
          </div>
        </div>
        <div :class="[theme.card.padded, 'flex items-center gap-3']">
          <Activity :size="20" class="text-accent-600" />
          <div>
            <p :class="theme.text.muted">Ingericht</p>
            <p :class="theme.text.h3">{{ dashboard.provisioned_tenants }}</p>
          </div>
        </div>
        <div :class="[theme.card.padded, 'flex items-center gap-3']">
          <Users :size="20" class="text-navy-600" />
          <div>
            <p :class="theme.text.muted">Gebruikers</p>
            <p :class="theme.text.h3">{{ dashboard.active_users }}</p>
          </div>
        </div>
      </div>

      <!-- Filters -->
      <div class="flex flex-col md:flex-row gap-3 mb-4">
        <input
          v-model="search"
          type="text"
          placeholder="Zoek op naam of slug..."
          :class="[theme.form.input, 'md:w-64']"
        />
        <select v-model="statusFilter" :class="[theme.form.input, 'md:w-48']">
          <option value="all">Alle</option>
          <option value="active">Actief</option>
          <option value="inactive">Inactief</option>
          <option value="unprovisioned">Niet ingericht</option>
        </select>
      </div>

      <!-- Tenant table -->
      <div :class="theme.card.base" class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr :class="theme.list.sectionHeader">
              <th class="text-left p-3">Organisatie</th>
              <th class="text-left p-3 hidden md:table-cell">Status</th>
              <th class="text-right p-3 hidden md:table-cell">Leden</th>
              <th class="text-right p-3 hidden md:table-cell">Leerlingen</th>
              <th class="text-right p-3 hidden md:table-cell">Docenten</th>
              <th class="text-right p-3 hidden lg:table-cell">Facturen</th>
              <th class="text-left p-3 hidden lg:table-cell">Laatst actief</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="t in filteredTenants"
              :key="t.id"
              :class="theme.list.item"
              class="cursor-pointer hover:bg-surface/50"
              @click="goToTenant(t)"
            >
              <td class="p-3">
                <p :class="theme.text.body" class="font-medium">{{ t.name }}</p>
                <p :class="theme.text.muted" class="text-xs">{{ t.slug }}</p>
              </td>
              <td class="p-3 hidden md:table-cell">
                <span
                  :class="[
                    theme.badge.base,
                    t.is_active && t.is_provisioned ? theme.badge.success :
                    t.is_active ? theme.badge.warning : theme.badge.error,
                  ]"
                >
                  {{ t.is_active && t.is_provisioned ? 'Actief' : t.is_active ? 'Niet ingericht' : 'Inactief' }}
                </span>
              </td>
              <td class="p-3 text-right hidden md:table-cell">{{ t.member_count }}</td>
              <td class="p-3 text-right hidden md:table-cell">
                {{ t.metrics_available ? t.student_count : '—' }}
              </td>
              <td class="p-3 text-right hidden md:table-cell">
                {{ t.metrics_available ? t.teacher_count : '—' }}
              </td>
              <td class="p-3 text-right hidden lg:table-cell">
                {{ t.metrics_available ? t.active_invoice_count : '—' }}
              </td>
              <td class="p-3 hidden lg:table-cell" :class="theme.text.muted">
                {{ formatDate(t.last_activity_at) }}
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="filteredTenants.length === 0" :class="[theme.list.empty, 'p-8']">
          Geen organisaties gevonden
        </div>
      </div>

      <p v-if="dashboard.cached_at" :class="[theme.text.muted, 'text-xs mt-2']">
        Laatst bijgewerkt: {{ new Date(dashboard.cached_at).toLocaleTimeString('nl-NL') }}
      </p>
    </template>
  </div>
</template>
