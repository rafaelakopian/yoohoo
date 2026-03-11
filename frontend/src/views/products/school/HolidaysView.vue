<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus, Pencil, Trash2, CalendarOff, X } from 'lucide-vue-next'
import PageHeader from '@/components/shared/PageHeader.vue'
import SkeletonLoader from '@/components/shared/SkeletonLoader.vue'
import EmptyState from '@/components/shared/EmptyState.vue'
import IconButton from '@/components/ui/IconButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import { theme } from '@/theme'
import { holidayApi } from '@/api/products/school/schedule'
import type { Holiday } from '@/types/models'
import { usePermissions } from '@/composables/usePermissions'

const { hasPermission } = usePermissions()

const holidays = ref<Holiday[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

// Form state
const showForm = ref(false)
const editId = ref<string | null>(null)
const form = ref({
  name: '',
  start_date: '',
  end_date: '',
  description: '',
  is_recurring: false,
})
const formLoading = ref(false)
const formError = ref<string | null>(null)

async function loadHolidays() {
  loading.value = true
  try {
    const result = await holidayApi.list({ per_page: 100 })
    holidays.value = result.items
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Kon vakanties niet laden'
  } finally {
    loading.value = false
  }
}

function openNew() {
  editId.value = null
  form.value = { name: '', start_date: '', end_date: '', description: '', is_recurring: false }
  formError.value = null
  showForm.value = true
}

function openEdit(h: Holiday) {
  editId.value = h.id
  form.value = {
    name: h.name,
    start_date: h.start_date,
    end_date: h.end_date,
    description: h.description || '',
    is_recurring: h.is_recurring,
  }
  formError.value = null
  showForm.value = true
}

async function handleSubmit() {
  formLoading.value = true
  formError.value = null

  try {
    const data = {
      ...form.value,
      description: form.value.description || undefined,
    }

    if (editId.value) {
      await holidayApi.update(editId.value, data)
    } else {
      await holidayApi.create(data)
    }
    showForm.value = false
    await loadHolidays()
  } catch (e: any) {
    formError.value = e.response?.data?.detail || 'Opslaan mislukt'
  } finally {
    formLoading.value = false
  }
}

const deleteModal = ref(false)
const deletingId = ref<string | null>(null)
const deleteError = ref('')

function promptDelete(id: string) {
  deletingId.value = id
  deleteError.value = ''
  deleteModal.value = true
}

async function confirmDelete() {
  if (!deletingId.value) return
  try {
    await holidayApi.delete(deletingId.value)
    deleteModal.value = false
    deletingId.value = null
    await loadHolidays()
  } catch (e: any) {
    deleteError.value = e.response?.data?.detail || 'Verwijderen mislukt'
  }
}

function formatDateRange(start: string, end: string): string {
  const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long', year: 'numeric' }
  const s = new Date(start + 'T00:00:00').toLocaleDateString('nl-NL', opts)
  const e = new Date(end + 'T00:00:00').toLocaleDateString('nl-NL', opts)
  return `${s} t/m ${e}`
}

onMounted(loadHolidays)
</script>

<template>
  <div>
      <!-- Header -->
      <PageHeader :icon="CalendarOff" title="Vakanties" description="Beheer vakanties en vrije dagen">
        <template #actions>
          <button v-if="hasPermission('schedule.manage')" @click="openNew" :class="theme.btn.addInline">
            <span :class="theme.btn.addInlineIcon"><Plus :size="14" /></span>
            Nieuwe vakantie
          </button>
        </template>
      </PageHeader>

      <div v-if="error" :class="theme.alert.error">{{ error }}</div>

      <!-- List -->
      <div :class="theme.card.base">
        <SkeletonLoader v-if="loading" variant="list" :rows="4" />

        <EmptyState v-else-if="holidays.length === 0" :icon="CalendarOff" title="Geen vakanties" description="Geen vakanties ingesteld" action-label="Voeg een vakantie toe" @action="openNew" />

        <div v-else :class="theme.list.divider" class="fade-in-up">
          <div v-for="h in holidays" :key="h.id" :class="theme.list.item">
            <div>
              <p class="font-medium text-navy-900">{{ h.name }}</p>
              <p class="text-sm text-body">{{ formatDateRange(h.start_date, h.end_date) }}</p>
              <p v-if="h.description" class="text-xs text-muted mt-1">{{ h.description }}</p>
              <span v-if="h.is_recurring" :class="[theme.badge.base, theme.badge.success, 'mt-1 inline-block']">
                Jaarlijks terugkerend
              </span>
            </div>
            <div v-if="hasPermission('schedule.manage')" class="flex items-center gap-1">
              <IconButton variant="accent" title="Bewerken" @click="openEdit(h)">
                <Pencil :size="14" />
              </IconButton>
              <IconButton variant="danger" title="Verwijderen" @click="promptDelete(h.id)">
                <Trash2 :size="14" />
              </IconButton>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <ConfirmModal
      :open="deleteModal"
      title="Vakantie verwijderen"
      message="Weet je zeker dat je deze vakantie wilt verwijderen? Dit kan niet ongedaan worden gemaakt."
      confirm-label="Verwijderen"
      variant="danger"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="deleteModal = false; deletingId = null"
    />

    <!-- Form modal -->
    <div v-if="showForm" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showForm = false">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div class="flex items-center justify-between p-6 border-b border-navy-100">
          <h3 :class="theme.text.h3">{{ editId ? 'Vakantie bewerken' : 'Nieuwe vakantie' }}</h3>
          <button @click="showForm = false" class="p-1 rounded hover:bg-surface">
            <X :size="18" />
          </button>
        </div>

        <form @submit.prevent="handleSubmit" class="p-6 space-y-4">
          <div v-if="formError" :class="theme.alert.error">{{ formError }}</div>

          <div :class="theme.form.group">
            <label :class="theme.form.label">Naam</label>
            <input v-model="form.name" :class="theme.form.input" required placeholder="Bijv. Kerstvakantie" />
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div :class="theme.form.group">
              <label :class="theme.form.label">Startdatum</label>
              <input v-model="form.start_date" type="date" :class="theme.form.input" required />
            </div>
            <div :class="theme.form.group">
              <label :class="theme.form.label">Einddatum</label>
              <input v-model="form.end_date" type="date" :class="theme.form.input" required />
            </div>
          </div>

          <div :class="theme.form.group">
            <label :class="theme.form.label">Beschrijving (optioneel)</label>
            <input v-model="form.description" :class="theme.form.input" />
          </div>

          <div class="flex items-center gap-2">
            <input v-model="form.is_recurring" type="checkbox" id="recurring" class="rounded" />
            <label for="recurring" class="text-sm text-navy-700">Jaarlijks terugkerend</label>
          </div>

          <div class="flex justify-end gap-3 pt-2">
            <button type="button" @click="showForm = false" class="px-4 py-2 text-sm text-body hover:text-navy-900">
              Annuleren
            </button>
            <button type="submit" :class="theme.btn.primarySm" :disabled="formLoading">
              {{ formLoading ? 'Opslaan...' : 'Opslaan' }}
            </button>
          </div>
        </form>
      </div>
  </div>
</template>
