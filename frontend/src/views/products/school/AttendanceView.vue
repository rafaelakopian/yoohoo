<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import {
  ChevronLeft,
  ChevronRight,
  Save,
  Filter,
  CalendarDays,
  ClipboardCheck,
} from 'lucide-vue-next'
import { attendanceApi } from '@/api/products/school/attendance'
import { studentsApi } from '@/api/products/school/students'
import type { Student, AttendanceRecord, AttendanceStatus } from '@/types/models'
import { theme } from '@/theme'
import { usePermissions } from '@/composables/usePermissions'
import PageHeader from '@/components/shared/PageHeader.vue'
import SkeletonLoader from '@/components/shared/SkeletonLoader.vue'

const { hasPermission } = usePermissions()

// State
const students = ref<Student[]>([])
const records = ref<AttendanceRecord[]>([])
const selectedDate = ref(todayString())
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const successMessage = ref<string | null>(null)

// Filter state
const filterStudentId = ref<string>('')
const dateFrom = ref('')
const dateTo = ref('')
const showFilters = ref(false)
const viewMode = ref<'register' | 'history'>('register')

// Bulk registration: map student_id -> status
const bulkStatuses = ref<Record<string, AttendanceStatus>>({})
const bulkNotes = ref<Record<string, string>>({})

// Existing records for selected date (to detect updates vs creates)
const existingRecordsByStudent = computed(() => {
  const map: Record<string, AttendanceRecord> = {}
  for (const r of records.value) {
    if (r.lesson_date === selectedDate.value) {
      map[r.student_id] = r
    }
  }
  return map
})

const statusOptions: { value: AttendanceStatus; label: string; color: string }[] = [
  { value: 'present', label: 'Aanwezig', color: 'bg-green-100 text-green-700 ring-1 ring-green-300' },
  { value: 'absent', label: 'Afwezig', color: 'bg-red-100 text-red-700 ring-1 ring-red-300' },
  { value: 'sick', label: 'Ziek', color: 'bg-yellow-100 text-yellow-700 ring-1 ring-yellow-300' },
  { value: 'excused', label: 'Verontschuldigd', color: 'bg-gray-100 text-gray-700 ring-1 ring-gray-300' },
]

function todayString(): string {
  return new Date().toISOString().split('T')[0]
}

function changeDate(days: number) {
  const d = new Date(selectedDate.value)
  d.setDate(d.getDate() + days)
  selectedDate.value = d.toISOString().split('T')[0]
  loadForDate()
}

function formatDateNl(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('nl-NL', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

onMounted(async () => {
  loading.value = true
  try {
    const result = await studentsApi.list({ active: true, per_page: 100 })
    students.value = result.items
  } catch {
    error.value = 'Kon leerlingen niet laden'
  } finally {
    loading.value = false
  }
  await loadForDate()
})

async function loadForDate() {
  error.value = null
  try {
    const result = await attendanceApi.list({
      date_from: selectedDate.value,
      date_to: selectedDate.value,
      per_page: 100,
    })
    records.value = result.items

    // Pre-fill bulk statuses from existing records
    bulkStatuses.value = {}
    bulkNotes.value = {}
    for (const r of result.items) {
      bulkStatuses.value[r.student_id] = r.status
      if (r.notes) bulkNotes.value[r.student_id] = r.notes
    }
  } catch {
    // silently fail — no records for this date yet
    records.value = []
    bulkStatuses.value = {}
    bulkNotes.value = {}
  }
}

function setStatus(studentId: string, status: AttendanceStatus) {
  if (bulkStatuses.value[studentId] === status) {
    // Toggle off
    delete bulkStatuses.value[studentId]
  } else {
    bulkStatuses.value[studentId] = status
  }
}

function getStatusClass(status: AttendanceStatus): string {
  return statusOptions.find((s) => s.value === status)?.color ?? ''
}

function getStatusLabel(status: AttendanceStatus): string {
  return statusOptions.find((s) => s.value === status)?.label ?? status
}

async function saveBulk() {
  const entries = Object.entries(bulkStatuses.value)
  if (entries.length === 0) {
    error.value = 'Selecteer minimaal één leerling'
    return
  }

  saving.value = true
  error.value = null
  successMessage.value = null

  try {
    const result = await attendanceApi.bulkCreate({
      lesson_date: selectedDate.value,
      records: entries.map(([student_id, status]) => ({
        student_id,
        status,
        notes: bulkNotes.value[student_id] || undefined,
      })),
    })
    successMessage.value = `${result.created} aangemaakt, ${result.updated} bijgewerkt`
    if (result.errors.length > 0) {
      error.value = result.errors.join(', ')
    }
    await loadForDate()
    setTimeout(() => { successMessage.value = null }, 3000)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Opslaan mislukt'
  } finally {
    saving.value = false
  }
}

// History view
const historyRecords = ref<AttendanceRecord[]>([])
const historyLoading = ref(false)
const historyTotal = ref(0)
const historyPage = ref(1)

async function loadHistory() {
  historyLoading.value = true
  try {
    const result = await attendanceApi.list({
      student_id: filterStudentId.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      page: historyPage.value,
      per_page: 25,
    })
    historyRecords.value = result.items
    historyTotal.value = result.total
  } catch {
    error.value = 'Kon historie niet laden'
  } finally {
    historyLoading.value = false
  }
}

function switchToHistory() {
  viewMode.value = 'history'
  loadHistory()
}

function switchToRegister() {
  viewMode.value = 'register'
  loadForDate()
}

function getStudentName(studentId: string): string {
  const s = students.value.find((st) => st.id === studentId)
  if (s) return `${s.first_name} ${s.last_name ?? ''}`.trim()
  return studentId.slice(0, 8)
}

const selectedCount = computed(() => Object.keys(bulkStatuses.value).length)
</script>

<template>
  <div>
    <!-- Header -->
    <PageHeader :icon="ClipboardCheck" title="Aanwezigheid" description="Registratie en historie">
      <template #actions>
        <button
          @click="switchToRegister"
          :class="[
            'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            viewMode === 'register'
              ? 'bg-accent-700 text-white'
              : 'bg-navy-50 text-navy-700 hover:bg-navy-100'
          ]"
        >
          Registreren
        </button>
        <button
          @click="switchToHistory"
          :class="[
            'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            viewMode === 'history'
              ? 'bg-accent-700 text-white'
              : 'bg-navy-50 text-navy-700 hover:bg-navy-100'
          ]"
        >
          Historie
        </button>
      </template>
    </PageHeader>

    <!-- REGISTER MODE -->
    <template v-if="viewMode === 'register'">
      <!-- Date picker -->
      <div :class="[theme.card.padded, 'mb-6']">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <button
              @click="changeDate(-1)"
              class="p-2 rounded-lg hover:bg-surface transition-colors"
            >
              <ChevronLeft :size="18" />
            </button>
            <div class="flex items-center gap-2">
              <CalendarDays :size="18" class="text-accent-600" />
              <input
                v-model="selectedDate"
                type="date"
                @change="loadForDate"
                :class="[theme.form.input, 'w-auto']"
              />
            </div>
            <button
              @click="changeDate(1)"
              class="p-2 rounded-lg hover:bg-surface transition-colors"
            >
              <ChevronRight :size="18" />
            </button>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-sm text-muted hidden md:inline">{{ selectedCount }} leerling(en) geselecteerd</span>
            <button
              v-if="hasPermission('attendance.create')"
              @click="saveBulk"
              :disabled="saving || selectedCount === 0"
              :class="[theme.btn.primarySm, 'flex items-center gap-1.5 disabled:opacity-50']"
            >
              <Save :size="16" />
              {{ saving ? 'Opslaan...' : 'Opslaan' }}
            </button>
          </div>
        </div>
        <p class="text-sm text-navy-700 mt-2 capitalize">{{ formatDateNl(selectedDate) }}</p>
      </div>

      <!-- Messages -->
      <div v-if="error" :class="[theme.alert.error, 'mb-4']">{{ error }}</div>
      <div v-if="successMessage" :class="theme.alert.success">
        {{ successMessage }}
      </div>

      <!-- Loading -->
      <SkeletonLoader v-if="loading" variant="table" :rows="6" />

      <!-- Student list with status selection -->
      <div v-else :class="[theme.card.base, 'fade-in-up']">
        <div v-if="students.length === 0" :class="theme.list.empty">
          <p class="text-navy-900 font-medium">Geen actieve leerlingen</p>
          <p :class="[theme.text.muted, 'mt-1']">Voeg eerst leerlingen toe.</p>
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-navy-100 text-left">
                <th class="px-6 py-3 font-medium text-navy-700">Leerling</th>
                <th class="px-6 py-3 font-medium text-navy-700">Status</th>
                <th class="px-6 py-3 font-medium text-navy-700">Opmerking</th>
              </tr>
            </thead>
            <tbody :class="theme.list.divider">
              <tr
                v-for="student in students"
                :key="student.id"
                class="hover:bg-surface transition-colors"
                :class="{ 'bg-green-50/30': bulkStatuses[student.id] === 'present' }"
              >
                <td class="px-6 py-3">
                  <p :class="theme.text.h4">{{ student.first_name }} {{ student.last_name ?? '' }}</p>
                  <p v-if="student.lesson_time" class="text-xs text-muted">
                    {{ student.lesson_day }} {{ student.lesson_time }}
                  </p>
                </td>
                <td class="px-6 py-3">
                  <div class="flex gap-1.5 flex-wrap">
                    <button
                      v-for="opt in statusOptions"
                      :key="opt.value"
                      @click="setStatus(student.id, opt.value)"
                      :class="[
                        'px-3 py-1 rounded-full text-xs font-medium transition-all',
                        bulkStatuses[student.id] === opt.value
                          ? opt.color
                          : 'bg-navy-50 text-navy-400 hover:bg-navy-100'
                      ]"
                    >
                      {{ opt.label }}
                    </button>
                  </div>
                </td>
                <td class="px-6 py-3">
                  <input
                    v-model="bulkNotes[student.id]"
                    type="text"
                    placeholder="Optioneel..."
                    :class="theme.form.input"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- HISTORY MODE -->
    <template v-if="viewMode === 'history'">
      <!-- Filters -->
      <div :class="[theme.card.padded, 'mb-6']">
        <div class="flex flex-col md:flex-row gap-4 md:items-end flex-wrap">
          <div>
            <label :class="theme.form.label">Leerling</label>
            <select v-model="filterStudentId" :class="[theme.form.input, 'w-48']" @change="loadHistory">
              <option value="">Alle leerlingen</option>
              <option v-for="s in students" :key="s.id" :value="s.id">
                {{ s.first_name }} {{ s.last_name ?? '' }}
              </option>
            </select>
          </div>
          <div>
            <label :class="theme.form.label">Van</label>
            <input v-model="dateFrom" type="date" :class="theme.form.input" @change="loadHistory" />
          </div>
          <div>
            <label :class="theme.form.label">Tot</label>
            <input v-model="dateTo" type="date" :class="theme.form.input" @change="loadHistory" />
          </div>
        </div>
      </div>

      <!-- Error -->
      <div v-if="error" :class="[theme.alert.error, 'mb-4']">{{ error }}</div>

      <!-- History table -->
      <SkeletonLoader v-if="historyLoading" variant="table" :rows="6" />

      <div v-else :class="[theme.card.base, 'fade-in-up']">
        <div v-if="historyRecords.length === 0" :class="theme.list.empty">
          <p class="text-navy-900 font-medium">Geen records gevonden</p>
          <p :class="[theme.text.muted, 'mt-1']">Pas de filters aan of registreer aanwezigheid.</p>
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-navy-100 text-left">
                <th class="px-6 py-3 font-medium text-navy-700">Datum</th>
                <th class="px-6 py-3 font-medium text-navy-700">Leerling</th>
                <th class="px-6 py-3 font-medium text-navy-700">Status</th>
                <th class="px-6 py-3 font-medium text-navy-700">Opmerking</th>
              </tr>
            </thead>
            <tbody :class="theme.list.divider">
              <tr
                v-for="record in historyRecords"
                :key="record.id"
                class="hover:bg-surface transition-colors"
              >
                <td class="px-6 py-3 text-body">
                  {{ new Date(record.lesson_date).toLocaleDateString('nl-NL') }}
                </td>
                <td class="px-6 py-3">
                  <p :class="theme.text.h4">{{ getStudentName(record.student_id) }}</p>
                </td>
                <td class="px-6 py-3">
                  <span :class="['px-3 py-1 rounded-full text-xs font-medium', getStatusClass(record.status)]">
                    {{ getStatusLabel(record.status) }}
                  </span>
                </td>
                <td class="px-6 py-3 text-body">{{ record.notes ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div v-if="historyTotal > 25" class="flex items-center justify-between px-6 py-3 border-t border-navy-100">
          <p class="text-sm text-muted">
            {{ (historyPage - 1) * 25 + 1 }}–{{ Math.min(historyPage * 25, historyTotal) }} van {{ historyTotal }}
          </p>
          <div class="flex items-center gap-2">
            <button
              @click="historyPage--; loadHistory()"
              :disabled="historyPage <= 1"
              class="p-1.5 rounded-lg hover:bg-surface disabled:opacity-30 transition-colors"
            >
              <ChevronLeft :size="16" />
            </button>
            <span class="text-sm text-navy-700">{{ historyPage }}</span>
            <button
              @click="historyPage++; loadHistory()"
              :disabled="historyPage * 25 >= historyTotal"
              class="p-1.5 rounded-lg hover:bg-surface disabled:opacity-30 transition-colors"
            >
              <ChevronRight :size="16" />
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
