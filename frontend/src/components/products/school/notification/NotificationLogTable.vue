<script setup lang="ts">
import type { NotificationLog } from '@/types/models'

defineProps<{
  logs: NotificationLog[]
  loading: boolean
}>()

const statusConfig: Record<string, { label: string; class: string }> = {
  pending: { label: 'Wachtend', class: 'bg-yellow-50 text-yellow-700' },
  sent: { label: 'Verzonden', class: 'bg-green-50 text-green-700' },
  failed: { label: 'Mislukt', class: 'bg-red-50 text-red-700' },
  skipped: { label: 'Overgeslagen', class: 'bg-navy-50 text-navy-700' },
}

const typeLabels: Record<string, string> = {
  lesson_reminder: 'Herinnering',
  absence_alert: 'Afwezigheid',
  schedule_change: 'Roosterwijziging',
  attendance_report: 'Overzicht',
}

function formatDate(dt: string): string {
  return new Date(dt).toLocaleString('nl-NL', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="text-left text-xs text-muted border-b border-navy-100">
          <th class="pb-2 font-medium">Datum</th>
          <th class="pb-2 font-medium">Type</th>
          <th class="pb-2 font-medium">Ontvanger</th>
          <th class="pb-2 font-medium">Onderwerp</th>
          <th class="pb-2 font-medium">Status</th>
        </tr>
      </thead>
      <tbody v-if="loading">
        <tr><td colspan="5" class="py-8 text-center text-body">Laden...</td></tr>
      </tbody>
      <tbody v-else-if="logs.length === 0">
        <tr><td colspan="5" class="py-8 text-center text-body">Geen verzendhistorie</td></tr>
      </tbody>
      <tbody v-else class="divide-y divide-navy-50">
        <tr v-for="log in logs" :key="log.id" class="hover:bg-surface/50">
          <td class="py-2.5 text-body">{{ formatDate(log.created_at) }}</td>
          <td class="py-2.5 text-navy-900">{{ typeLabels[log.notification_type] || log.notification_type }}</td>
          <td class="py-2.5">
            <span class="text-navy-900">{{ log.recipient_name || log.recipient_email }}</span>
          </td>
          <td class="py-2.5 text-body max-w-[200px] truncate">{{ log.subject }}</td>
          <td class="py-2.5">
            <span
              :class="['px-2 py-0.5 rounded-full text-xs font-medium', statusConfig[log.status]?.class || '']"
            >
              {{ statusConfig[log.status]?.label || log.status }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
