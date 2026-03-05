<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { CheckCircle2, Circle } from 'lucide-vue-next'
import { theme } from '@/theme'
import { getOnboardingOverview, type OnboardingItem } from '@/api/platform/operations'

const router = useRouter()
const items = ref<OnboardingItem[]>([])
const loading = ref(true)
const error = ref('')
const sortBy = ref<'completion' | 'name' | 'date'>('completion')

onMounted(async () => {
  try {
    items.value = await getOnboardingOverview()
  } catch {
    error.value = 'Kon onboarding gegevens niet laden'
  } finally {
    loading.value = false
  }
})

const sortedItems = computed(() => {
  const copy = [...items.value]
  if (sortBy.value === 'completion') copy.sort((a, b) => a.completion_pct - b.completion_pct)
  if (sortBy.value === 'name') copy.sort((a, b) => a.tenant_name.localeCompare(b.tenant_name))
  if (sortBy.value === 'date') copy.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return copy
})

const stepLabels: Record<string, string> = {
  is_provisioned: 'Ingericht',
  has_settings: 'Instellingen',
  has_members: 'Leden',
  has_students: 'Leerlingen',
  has_schedule: 'Rooster',
  has_attendance: 'Aanwezigheid',
  has_billing_plan: 'Facturatie',
}

const steps = Object.keys(stepLabels)

function goToTenant(item: OnboardingItem) {
  router.push({ name: 'ops-tenant-360', params: { tenantId: item.tenant_id } })
}

function formatDate(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })
}
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 :class="theme.text.h2">Onboarding</h2>
      <p :class="[theme.text.muted, 'mt-1']">Voortgang per organisatie</p>
    </div>

    <div v-if="loading" class="text-center py-8">
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <div v-else-if="error" :class="theme.alert.error">{{ error }}</div>

    <template v-else>
      <!-- Sort control -->
      <div class="flex gap-3 mb-4">
        <select v-model="sortBy" :class="[theme.form.input, 'w-48']">
          <option value="completion">Minst compleet eerst</option>
          <option value="name">Naam A-Z</option>
          <option value="date">Nieuwste eerst</option>
        </select>
      </div>

      <!-- Onboarding table -->
      <div :class="theme.card.base" class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr :class="theme.list.sectionHeader">
              <th class="text-left p-3">Organisatie</th>
              <th v-for="step in steps" :key="step" class="text-center p-3 hidden md:table-cell">
                <span class="text-xs">{{ stepLabels[step] }}</span>
              </th>
              <th class="text-right p-3">Voortgang</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in sortedItems"
              :key="item.tenant_id"
              :class="theme.list.item"
              class="cursor-pointer hover:bg-surface/50"
              @click="goToTenant(item)"
            >
              <td class="p-3">
                <p :class="theme.text.body" class="font-medium">{{ item.tenant_name }}</p>
                <p :class="theme.text.muted" class="text-xs">{{ formatDate(item.created_at) }}</p>
              </td>
              <td
                v-for="step in steps"
                :key="step"
                class="p-3 text-center hidden md:table-cell"
              >
                <CheckCircle2
                  v-if="(item as any)[step]"
                  :size="18"
                  class="text-green-500 inline"
                />
                <Circle v-else :size="18" class="text-body/30 inline" />
              </td>
              <td class="p-3 text-right">
                <div class="flex items-center gap-2 justify-end">
                  <div class="w-24 h-2 bg-surface rounded-full overflow-hidden">
                    <div
                      class="h-full rounded-full transition-all"
                      :class="item.completion_pct === 100 ? 'bg-green-500' : item.completion_pct >= 50 ? 'bg-yellow-500' : 'bg-red-400'"
                      :style="{ width: `${item.completion_pct}%` }"
                    />
                  </div>
                  <span :class="theme.text.muted" class="text-xs w-8 text-right">{{ item.completion_pct }}%</span>
                </div>
                <div v-if="item.missing_steps.length > 0" class="flex gap-1 flex-wrap justify-end mt-1">
                  <span
                    v-for="ms in item.missing_steps"
                    :key="ms"
                    :class="[theme.badge.base, theme.badge.error]"
                    class="text-[10px]"
                  >{{ stepLabels[ms] ?? ms }}</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="sortedItems.length === 0" :class="[theme.list.empty, 'p-8']">
          Geen organisaties gevonden
        </div>
      </div>
    </template>
  </div>
</template>
