<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

defineProps<{
  tabs: Array<{ label: string; to: string }>
}>()

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}
</script>

<template>
  <div class="flex overflow-x-auto border-b border-navy-100 mb-6">
    <router-link
      v-for="tab in tabs"
      :key="tab.to"
      :to="tab.to"
      class="px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px whitespace-nowrap"
      :class="isActive(tab.to)
        ? 'border-accent-700 text-accent-700'
        : 'border-transparent text-body hover:text-navy-900'"
    >{{ tab.label }}</router-link>
  </div>
</template>
