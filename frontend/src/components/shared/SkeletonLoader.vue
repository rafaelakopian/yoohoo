<script setup lang="ts">
defineProps<{
  /** Number of skeleton rows to render */
  rows?: number
  /** Variant: 'table' shows a fake table, 'cards' shows stat cards, 'list' shows basic lines */
  variant?: 'table' | 'cards' | 'list'
  /** Number of columns for table variant */
  columns?: number
}>()
</script>

<template>
  <!-- Cards variant: stat card skeletons -->
  <div v-if="variant === 'cards'" class="grid grid-cols-2 md:grid-cols-4 gap-4">
    <div
      v-for="i in (rows ?? 4)"
      :key="i"
      class="bg-white p-5 rounded-xl border border-navy-100 skeleton-fade-in"
      :style="{ animationDelay: i * 80 + 'ms' }"
    >
      <div class="h-4 w-20 bg-navy-100 rounded animate-pulse mb-2" />
      <div class="h-7 w-14 bg-navy-100 rounded animate-pulse" />
    </div>
  </div>

  <!-- Table variant: fake table with rows -->
  <div v-else-if="variant === 'table'" class="overflow-hidden rounded-xl border border-navy-100">
    <div class="bg-surface h-[42px]" />
    <div class="bg-white divide-y divide-navy-50">
      <div
        v-for="n in (rows ?? 6)"
        :key="n"
        class="flex items-center gap-4 px-4 py-3.5 skeleton-fade-in"
        :style="{ animationDelay: n * 60 + 'ms' }"
      >
        <div
          v-for="c in (columns ?? 4)"
          :key="c"
          class="h-4 bg-navy-100 rounded animate-pulse"
          :style="{ width: ['40%', '25%', '20%', '15%'][c % 4] }"
        />
      </div>
    </div>
  </div>

  <!-- List variant (default): simple line skeletons -->
  <div v-else class="space-y-3">
    <div
      v-for="n in (rows ?? 5)"
      :key="n"
      class="skeleton-fade-in"
      :style="{ animationDelay: n * 60 + 'ms' }"
    >
      <div class="h-4 bg-navy-100 rounded animate-pulse mb-2" :style="{ width: n % 2 === 0 ? '70%' : '55%' }" />
      <div class="h-3 bg-navy-50 rounded animate-pulse" style="width: 40%" />
    </div>
  </div>
</template>
