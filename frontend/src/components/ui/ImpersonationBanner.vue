<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { AlertTriangle } from 'lucide-vue-next'
import { theme } from '@/theme'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const remainingSeconds = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

function updateCountdown() {
  if (!authStore.impersonationExpiresAt) return
  const diff = new Date(authStore.impersonationExpiresAt).getTime() - Date.now()
  remainingSeconds.value = Math.max(0, Math.floor(diff / 1000))
  if (remainingSeconds.value <= 0) {
    authStore.stopImpersonation()
  }
}

const formattedTime = computed(() => {
  const mins = Math.floor(remainingSeconds.value / 60)
  const secs = remainingSeconds.value % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
})

onMounted(() => {
  updateCountdown()
  timer = setInterval(updateCountdown, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div :class="theme.banner.warning" class="fixed top-0 left-0 right-0 z-[100]">
    <div class="max-w-7xl mx-auto flex items-center justify-between gap-4">
      <div class="flex items-center gap-2 min-w-0">
        <AlertTriangle :size="16" class="shrink-0" />
        <span class="truncate">
          <span class="hidden md:inline">
            Je bent ingelogd als "{{ authStore.impersonationTargetName }}"
            ({{ authStore.impersonationTargetEmail }})
          </span>
          <span class="md:hidden">
            Ingelogd als {{ authStore.impersonationTargetName }}
          </span>
        </span>
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <span class="tabular-nums font-mono text-sm">{{ formattedTime }}</span>
        <button
          class="bg-white/20 hover:bg-white/30 px-3 py-1 rounded text-sm font-medium transition-colors"
          @click="authStore.stopImpersonation()"
        >
          Terug naar admin
        </button>
      </div>
    </div>
  </div>
</template>
