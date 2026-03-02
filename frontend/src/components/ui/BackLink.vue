<script setup lang="ts">
import { ArrowLeft } from 'lucide-vue-next'

defineProps<{
  to: string
}>()
</script>

<template>
  <router-link
    :to="to"
    class="w-8 h-8 rounded-full border border-navy-100 bg-white flex items-center justify-center text-navy-400 hover:text-navy-700 hover:border-navy-200 transition-colors shrink-0"
  >
    <ArrowLeft :size="16" />
  </router-link>
</template>
