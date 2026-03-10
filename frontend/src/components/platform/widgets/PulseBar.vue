<script setup lang="ts">
import type { PulseItem } from './index'
import { theme } from '@/theme'

defineProps<{ items: PulseItem[] }>()
</script>

<template>
  <div v-if="items.length" :class="theme.pulse.bar">
    <component
      v-for="(item, i) in items"
      :key="i"
      :is="item.to ? 'RouterLink' : 'div'"
      :to="item.to"
      :class="[theme.pulse.item, theme.pulse.severity[item.severity]]"
    >
      <span :class="[theme.pulse.dot, theme.pulse.dotColor[item.severity]]" />
      {{ item.message }}
    </component>
  </div>
</template>
