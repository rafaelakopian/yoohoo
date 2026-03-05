<script setup lang="ts">
import { computed } from 'vue'
import { theme } from '@/theme'

const props = defineProps<{
  status: string
}>()

const badgeClass = computed(() => {
  const map: Record<string, string> = {
    paid: theme.badge.success,
    active: theme.badge.success,
    sent: theme.badge.info,
    processing: theme.badge.info,
    pending: theme.badge.warning,
    trialing: theme.badge.warning,
    draft: theme.badge.default,
    overdue: theme.badge.error,
    past_due: theme.badge.error,
    failed: theme.badge.error,
    cancelled: theme.badge.default,
    expired: theme.badge.default,
    refunded: theme.badge.warning,
    paused: theme.badge.warning,
  }
  return map[props.status] || theme.badge.default
})

const label = computed(() => {
  const map: Record<string, string> = {
    paid: 'Betaald',
    active: 'Actief',
    sent: 'Verzonden',
    processing: 'Verwerken',
    pending: 'In afwachting',
    trialing: 'Proefperiode',
    draft: 'Concept',
    overdue: 'Achterstallig',
    past_due: 'Achterstallig',
    failed: 'Mislukt',
    cancelled: 'Geannuleerd',
    expired: 'Verlopen',
    refunded: 'Terugbetaald',
    paused: 'Gepauzeerd',
    partially_refunded: 'Deels terugbetaald',
  }
  return map[props.status] || props.status
})
</script>

<template>
  <span :class="[theme.badge.base, badgeClass]">{{ label }}</span>
</template>
