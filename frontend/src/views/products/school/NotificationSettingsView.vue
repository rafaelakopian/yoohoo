<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Settings, History, Bell } from 'lucide-vue-next'
import { theme } from '@/theme'
import PageHeader from '@/components/shared/PageHeader.vue'
import SkeletonLoader from '@/components/shared/SkeletonLoader.vue'
import { useNotificationStore } from '@/stores/notification'
import PreferenceToggle from '@/components/products/school/notification/PreferenceToggle.vue'
import NotificationLogTable from '@/components/products/school/notification/NotificationLogTable.vue'

const store = useNotificationStore()
const activeTab = ref<'preferences' | 'history'>('preferences')

async function handleUpdate(type: string, field: string, value: boolean) {
  await store.updatePreference(type, { [field]: value })
}

onMounted(async () => {
  await store.fetchPreferences()
  if (store.preferences.length === 0) {
    await store.initializePreferences()
  }
  await store.fetchLogs()
})
</script>

<template>
  <div>
      <!-- Header -->
      <PageHeader :icon="Bell" title="Notificaties" description="Meldingen en voorkeuren beheren" />

      <!-- Tabs -->
      <div class="flex gap-1 mb-4 bg-white rounded-lg border border-navy-100 p-1 w-fit">
        <button
          @click="activeTab = 'preferences'"
          :class="[
            'flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors',
            activeTab === 'preferences' ? 'bg-accent-700 text-white' : 'text-body hover:text-navy-900',
          ]"
        >
          <Settings :size="14" />
          Voorkeuren
        </button>
        <button
          @click="activeTab = 'history'; store.fetchLogs()"
          :class="[
            'flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors',
            activeTab === 'history' ? 'bg-accent-700 text-white' : 'text-body hover:text-navy-900',
          ]"
        >
          <History :size="14" />
          Verzendhistorie
        </button>
      </div>

      <div v-if="store.error" :class="theme.alert.error">{{ store.error }}</div>

      <!-- Preferences tab -->
      <div v-if="activeTab === 'preferences'" :class="theme.card.padded">
        <SkeletonLoader v-if="store.preferences.length === 0" variant="list" :rows="4" />
        <div v-else class="divide-y divide-navy-100">
          <PreferenceToggle
            v-for="pref in store.preferences"
            :key="pref.id"
            :preference="pref"
            @update="(field, value) => handleUpdate(pref.notification_type, field, value)"
          />
        </div>
      </div>

      <!-- History tab -->
      <div v-if="activeTab === 'history'" :class="theme.card.padded">
        <NotificationLogTable :logs="store.logs" :loading="store.loading" />
      </div>
  </div>
</template>
