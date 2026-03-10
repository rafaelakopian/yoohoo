<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi, type AuditLogItem } from '@/api/platform/admin'
import { ScrollText, User, ExternalLink } from 'lucide-vue-next'
import { theme } from '@/theme'

const props = defineProps<{ maxItems?: number }>()
const entries = ref<AuditLogItem[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const data = await adminApi.getAuditLogs({ limit: props.maxItems ?? 5 })
    entries.value = data.items
  } catch {
    // Silently handle — widget shows empty state
  } finally {
    loading.value = false
  }
})

function formatTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'zojuist'
  if (mins < 60) return `${mins}m geleden`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}u geleden`
  return d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })
}

function actionDotColor(action: string): string {
  if (action.startsWith('auth.')) return 'bg-accent-500'
  if (action.startsWith('security.') || action.startsWith('session.')) return 'bg-red-500'
  if (action.startsWith('tenant.') || action.startsWith('org.')) return 'bg-green-500'
  if (action.startsWith('billing.') || action.startsWith('invoice.')) return 'bg-purple-500'
  return 'bg-navy-400'
}
</script>

<template>
  <div :class="theme.card.base" class="overflow-hidden flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between px-5 pt-5 pb-3">
      <div class="flex items-center gap-2">
        <ScrollText :size="18" class="text-navy-400" />
        <h3 :class="theme.text.h3">Recente activiteit</h3>
      </div>
      <RouterLink to="/platform/audit-logs" class="flex items-center gap-1 text-xs font-medium text-accent-700 hover:text-accent-800 transition-colors">
        Alles bekijken <ExternalLink :size="12" />
      </RouterLink>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="px-5 pb-5 space-y-3">
      <div v-for="n in 4" :key="n" class="flex items-center gap-3 animate-pulse">
        <div class="w-7 h-7 bg-navy-100 rounded-full shrink-0" />
        <div class="flex-1 space-y-1">
          <div class="h-3.5 w-3/4 bg-navy-100 rounded" />
          <div class="h-3 w-1/3 bg-navy-50 rounded" />
        </div>
        <div class="h-3 w-12 bg-navy-50 rounded shrink-0" />
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="!entries.length" class="px-5 pb-5 py-8 text-center">
      <p :class="theme.text.muted" class="text-sm">Geen recente activiteit</p>
    </div>

    <!-- Feed -->
    <div v-else class="flex-1 divide-y divide-navy-50">
      <div v-for="entry in entries" :key="entry.id" class="flex items-center gap-3 px-5 py-3 hover:bg-surface transition-colors">
        <!-- Avatar -->
        <div
          class="w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold"
          :class="entry.user_email ? 'bg-accent-50 text-accent-700' : 'bg-navy-50 text-navy-400'"
        >
          <User :size="12" v-if="!entry.user_email" />
          <template v-else>{{ entry.user_email[0].toUpperCase() }}</template>
        </div>

        <!-- Content -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full shrink-0" :class="actionDotColor(entry.action)" />
            <span class="text-sm text-navy-900 font-medium truncate">{{ entry.action }}</span>
          </div>
          <p :class="theme.text.muted" class="text-xs truncate">
            {{ entry.user_email ?? 'Systeem' }}
          </p>
        </div>

        <!-- Time -->
        <span :class="theme.text.muted" class="text-xs shrink-0">{{ formatTime(entry.created_at) }}</span>
      </div>
    </div>
  </div>
</template>
