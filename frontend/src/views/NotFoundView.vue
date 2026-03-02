<script setup lang="ts">
import { FileQuestion } from 'lucide-vue-next'
import { theme } from '@/theme'
</script>

<template>
  <div :class="theme.page.bgCenter">
    <div class="text-center">
      <FileQuestion :size="64" class="mx-auto text-navy-200 mb-4" />
      <h1 class="text-6xl font-bold text-navy-200">404</h1>
      <p class="text-lg mt-4" :class="theme.text.subtitle">Pagina niet gevonden</p>
      <router-link
        to="/"
        :class="['inline-block mt-6', theme.btn.primarySm, 'px-6']"
      >
        Terug naar home
      </router-link>
    </div>
  </div>
</template>
