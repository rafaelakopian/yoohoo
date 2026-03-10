<script setup lang="ts">
import type { Component } from 'vue'
import { theme } from '@/theme'

defineProps<{
  label: string
  value: string | number
  sub?: string
  icon: Component
  variant?: 'primary' | 'accent' | 'green' | 'red' | 'default'
  to?: string
  loading?: boolean
}>()
</script>

<template>
  <component
    :is="to ? 'RouterLink' : 'div'"
    :to="to"
    :class="[theme.stat.card, to && theme.stat.cardClickable]"
  >
    <div :class="[theme.stat.iconWrap, theme.stat.iconVariant[variant ?? 'default']]">
      <component :is="icon" class="w-5 h-5" />
    </div>
    <div class="min-w-0">
      <div v-if="loading" :class="theme.stat.skeleton" />
      <div v-else :class="theme.stat.value">{{ value }}</div>
      <div :class="theme.stat.label">{{ label }}</div>
      <div v-if="sub" :class="theme.stat.sub">{{ sub }}</div>
    </div>
  </component>
</template>
