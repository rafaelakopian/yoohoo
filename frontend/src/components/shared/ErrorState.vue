<script setup lang="ts">
import { AlertCircle } from 'lucide-vue-next'
import { theme } from '@/theme'

defineProps<{
  message: string
  retryLabel?: string
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <div :class="theme.emptyState.wrapper">
    <div class="w-14 h-14 rounded-2xl bg-red-50 flex items-center justify-center mb-4">
      <AlertCircle :size="24" class="text-red-400" />
    </div>
    <p :class="theme.emptyState.title">Er ging iets mis</p>
    <p :class="theme.emptyState.description">{{ message }}</p>
    <button v-if="retryLabel" :class="[theme.btn.secondary, 'mt-4']" @click="$emit('retry')">
      {{ retryLabel }}
    </button>
  </div>
</template>
