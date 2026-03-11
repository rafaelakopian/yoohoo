<script setup lang="ts">
import type { Component } from 'vue'
import { theme } from '@/theme'

defineProps<{
  title: string
  description?: string
  icon?: Component
}>()
</script>

<template>
  <div :class="theme.pageHeader.rowResponsive">
    <div class="flex items-center gap-3">
      <div v-if="icon" :class="theme.stat.iconWrap" class="bg-navy-50">
        <component :is="icon" :size="22" class="text-navy-700" />
      </div>
      <div>
        <h2 :class="theme.text.h2">{{ title }}</h2>
        <p v-if="description" :class="theme.text.muted" class="text-sm mt-0.5">{{ description }}</p>
      </div>
    </div>
    <div v-if="$slots.actions" class="flex items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>
