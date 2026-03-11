<script setup lang="ts">
import type { Component } from 'vue'
import { theme } from '@/theme'

defineProps<{
  icon: Component
  title: string
  description?: string
  actionLabel?: string
}>()

defineEmits<{
  action: []
}>()
</script>

<template>
  <div :class="theme.emptyState.wrapper">
    <div :class="theme.emptyState.iconWrap">
      <component :is="icon" :class="theme.emptyState.icon" :size="24" />
    </div>
    <p :class="theme.emptyState.title">{{ title }}</p>
    <p v-if="description" :class="theme.emptyState.description">{{ description }}</p>
    <button v-if="actionLabel" :class="[theme.btn.primary, 'mt-4']" @click="$emit('action')">
      {{ actionLabel }}
    </button>
  </div>
</template>
