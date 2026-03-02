<script setup lang="ts">
import { computed } from 'vue'

type Variant = 'neutral' | 'danger' | 'primary' | 'accent' | 'success' | 'warning'

const props = withDefaults(
  defineProps<{
    variant?: Variant
    title?: string
    disabled?: boolean
  }>(),
  {
    variant: 'neutral',
    disabled: false,
  },
)

const variantClasses: Record<Variant, string> = {
  neutral: 'bg-navy-50 text-navy-400 hover:bg-navy-100 hover:text-navy-700',
  danger: 'bg-red-50 text-red-400 hover:bg-red-100 hover:text-red-600',
  primary: 'bg-primary-50 text-primary-400 hover:bg-primary-100 hover:text-primary-600',
  accent: 'bg-accent-50 text-accent-400 hover:bg-accent-100 hover:text-accent-600',
  success: 'bg-green-50 text-green-400 hover:bg-green-100 hover:text-green-600',
  warning: 'bg-yellow-50 text-yellow-500 hover:bg-yellow-100 hover:text-yellow-700',
}

const classes = computed(() => [
  'inline-flex items-center justify-center p-1.5 rounded-lg transition-colors',
  variantClasses[props.variant],
  props.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
])
</script>

<template>
  <button :class="classes" :title="title" :disabled="disabled">
    <slot />
  </button>
</template>
