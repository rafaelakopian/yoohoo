<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ChevronLeft, ChevronRight, CalendarDays, Plus, Zap, X, CheckCircle, Pencil, Trash2, RefreshCw } from 'lucide-vue-next'
import IconButton from '@/components/ui/IconButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import { theme } from '@/theme'
import PageHeader from '@/components/shared/PageHeader.vue'
import SkeletonLoader from '@/components/shared/SkeletonLoader.vue'
import { calendarApi, lessonApi, slotApi } from '@/api/products/school/schedule'
import type { CalendarDayEntry, CalendarWeekResponse, LessonSlot, GenerateLessonsResponse, Member } from '@/types/models'
import WeekCalendar from '@/components/products/school/schedule/WeekCalendar.vue'
import LessonSlotForm from '@/components/products/school/schedule/LessonSlotForm.vue'
import GenerateLessonsModal from '@/components/products/school/schedule/GenerateLessonsModal.vue'
import RescheduleModal from '@/components/products/school/schedule/RescheduleModal.vue'
import { usePermissions } from '@/composables/usePermissions'
import { useTenantStore } from '@/stores/tenant'

const { hasPermission, hasAnyPermission } = usePermissions()
const tenantStore = useTenantStore()

const loading = ref(false)
const error = ref<string | null>(null)

// Current week
const currentMonday = ref(getMonday(new Date()))
const calendar = ref<CalendarWeekResponse | null>(null)

// Modals
const showSlotForm = ref(false)
const editSlotId = ref<string | undefined>()
const showGenerateModal = ref(false)
const showRescheduleModal = ref(false)
const selectedLesson = ref<CalendarDayEntry | null>(null)
const generateResult = ref<GenerateLessonsResponse | null>(null)
const showCancelModal = ref(false)
const cancelReason = ref('')
const lessonActionError = ref('')

// Slots
const slots = ref<LessonSlot[]>([])
const showSlotList = ref(false)

function getMonday(d: Date): string {
  const date = new Date(d)
  const day = date.getDay()
  const diff = date.getDate() - day + (day === 0 ? -6 : 1)
  date.setDate(diff)
  return date.toISOString().split('T')[0]
}

function formatWeekLabel(start: string): string {
  const d = new Date(start + 'T00:00:00')
  const endD = new Date(d)
  endD.setDate(d.getDate() + 6)
  const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' }
  return `${d.toLocaleDateString('nl-NL', opts)} — ${endD.toLocaleDateString('nl-NL', opts)} ${endD.getFullYear()}`
}

async function loadWeek() {
  loading.value = true
  error.value = null
  try {
    calendar.value = await calendarApi.getWeek(currentMonday.value)
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Kon rooster niet laden'
  } finally {
    loading.value = false
  }
}

async function loadSlots() {
  try {
    const result = await slotApi.list({ per_page: 100 })
    slots.value = result.items
  } catch {
    // ignore
  }
}

function prevWeek() {
  const d = new Date(currentMonday.value + 'T00:00:00')
  d.setDate(d.getDate() - 7)
  currentMonday.value = d.toISOString().split('T')[0]
  loadWeek()
}

function nextWeek() {
  const d = new Date(currentMonday.value + 'T00:00:00')
  d.setDate(d.getDate() + 7)
  currentMonday.value = d.toISOString().split('T')[0]
  loadWeek()
}

function goToday() {
  currentMonday.value = getMonday(new Date())
  loadWeek()
}

function handleLessonClick(lesson: CalendarDayEntry) {
  selectedLesson.value = lesson
}

function handleCancelLesson() {
  cancelReason.value = ''
  lessonActionError.value = ''
  showCancelModal.value = true
}

async function confirmCancelLesson() {
  if (!selectedLesson.value) return
  try {
    await lessonApi.cancel(selectedLesson.value.id, cancelReason.value || undefined)
    showCancelModal.value = false
    selectedLesson.value = null
    await loadWeek()
  } catch (e: any) {
    lessonActionError.value = e.response?.data?.detail || 'Annuleren mislukt'
  }
}

async function handleCompleteLesson() {
  if (!selectedLesson.value) return
  lessonActionError.value = ''
  try {
    await lessonApi.update(selectedLesson.value.id, { status: 'completed' })
    selectedLesson.value = null
    await loadWeek()
  } catch (e: any) {
    lessonActionError.value = e.response?.data?.detail || 'Voltooien mislukt'
  }
}

function handleRescheduleClick() {
  showRescheduleModal.value = true
}

async function handleSubstituteClick() {
  substituteTeacherId.value = ''
  substituteReason.value = ''
  substituteError.value = ''
  substituteSearch.value = ''
  showSubstituteModal.value = true
  await loadSubstituteTeachers()
}

async function confirmSubstitute() {
  if (!selectedLesson.value || !substituteTeacherId.value) return
  substituteLoading.value = true
  substituteError.value = ''
  try {
    await lessonApi.assignSubstitute(selectedLesson.value.id, {
      substitute_teacher_user_id: substituteTeacherId.value,
      reason: substituteReason.value || undefined,
    })
    showSubstituteModal.value = false
    selectedLesson.value = null
    await loadWeek()
  } catch (e: any) {
    substituteError.value = e.response?.data?.detail || 'Vervanging registreren mislukt'
  } finally {
    substituteLoading.value = false
  }
}

function handleGenerated(result: GenerateLessonsResponse) {
  generateResult.value = result
  showGenerateModal.value = false
  loadWeek()
}

function handleSlotSaved() {
  showSlotForm.value = false
  editSlotId.value = undefined
  loadSlots()
}

function openNewSlot() {
  editSlotId.value = undefined
  showSlotForm.value = true
}

function editSlot(id: string) {
  editSlotId.value = id
  showSlotForm.value = true
}

// Substitution
const showSubstituteModal = ref(false)
const substituteTeacherId = ref('')
const substituteReason = ref('')
const substituteError = ref('')
const substituteLoading = ref(false)
const substituteSearch = ref('')
const substituteTeachers = ref<Member[]>([])

const filteredSubstituteTeachers = computed(() => {
  if (!substituteSearch.value) return substituteTeachers.value
  const q = substituteSearch.value.toLowerCase()
  return substituteTeachers.value.filter(
    (t) => t.full_name.toLowerCase().includes(q) || (t.email?.toLowerCase().includes(q) ?? false),
  )
})

async function loadSubstituteTeachers() {
  substituteTeachers.value = await tenantStore.getTeachers()
}

function substituteTeacherName(userId: string | null): string {
  if (!userId) return ''
  const t = substituteTeachers.value.find((m) => m.user_id === userId)
  return t?.full_name ?? userId.slice(0, 8) + '...'
}

const deleteSlotModal = ref(false)
const deletingSlotId = ref<string | null>(null)
const deleteSlotError = ref('')

function promptDeleteSlot(id: string) {
  deletingSlotId.value = id
  deleteSlotError.value = ''
  deleteSlotModal.value = true
}

async function confirmDeleteSlot() {
  if (!deletingSlotId.value) return
  try {
    await slotApi.delete(deletingSlotId.value)
    deleteSlotModal.value = false
    deletingSlotId.value = null
    await loadSlots()
  } catch (e: any) {
    deleteSlotError.value = e.response?.data?.detail || 'Verwijderen mislukt'
  }
}

const dayNames: Record<number, string> = {
  1: 'Ma', 2: 'Di', 3: 'Wo', 4: 'Do', 5: 'Vr', 6: 'Za', 7: 'Zo',
}

onMounted(() => {
  loadWeek()
  loadSlots()
  loadSubstituteTeachers()
})
</script>

<template>
  <div>
      <!-- Header -->
      <PageHeader :icon="CalendarDays" title="Rooster" description="Lesplanning en weekoverzicht">
        <template #actions>
          <div v-if="hasPermission('schedule.manage')" class="flex items-center gap-2">
            <button @click="showSlotList = !showSlotList" :class="theme.btn.secondarySm">
              <CalendarDays :size="14" class="inline mr-1" />
              Lesslots
            </button>
            <button @click="showGenerateModal = true" :class="theme.btn.primarySm">
              <Zap :size="14" class="inline mr-1" />
              Genereren
            </button>
          </div>
        </template>
      </PageHeader>

      <!-- Generate result -->
      <div v-if="generateResult" :class="theme.alert.success" class="flex items-center justify-between">
        <span>{{ generateResult.generated }} lessen gegenereerd, {{ generateResult.skipped }} overgeslagen.</span>
        <button @click="generateResult = null" class="p-1 hover:bg-green-100 rounded">
          <X :size="14" />
        </button>
      </div>

      <!-- Error -->
      <div v-if="error" :class="theme.alert.error">{{ error }}</div>

      <!-- Week navigation -->
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <button @click="prevWeek" class="p-2 rounded-lg hover:bg-surface text-body">
            <ChevronLeft :size="20" />
          </button>
          <h3 :class="theme.text.h3">{{ formatWeekLabel(currentMonday) }}</h3>
          <button @click="nextWeek" class="p-2 rounded-lg hover:bg-surface text-body">
            <ChevronRight :size="20" />
          </button>
        </div>
        <button @click="goToday" class="text-sm text-accent-700 hover:text-accent-800 font-medium">
          Vandaag
        </button>
      </div>

      <!-- Calendar -->
      <SkeletonLoader v-if="loading" variant="cards" :rows="4" />
      <WeekCalendar
        class="fade-in-up"
        v-else-if="calendar"
        :week-start="calendar.week_start"
        :week-end="calendar.week_end"
        :lessons="calendar.lessons"
        :holidays="calendar.holidays"
        @lesson-click="handleLessonClick"
      />

      <!-- Slot management panel -->
      <div v-if="showSlotList" :class="[theme.card.padded, 'mt-6']">
        <div class="flex items-center justify-between mb-4">
          <h3 :class="theme.text.h3">Wekelijkse lesslots</h3>
          <button @click="openNewSlot" :class="theme.btn.primarySm">
            <Plus :size="14" class="inline mr-1" />
            Nieuw slot
          </button>
        </div>

        <div v-if="slots.length === 0" class="text-center py-8 text-body">
          Geen lesslots ingesteld. Maak een nieuw slot aan.
        </div>

        <div v-else class="divide-y divide-navy-100">
          <div v-for="slot in slots" :key="slot.id" class="py-3 flex items-center justify-between">
            <div>
              <span class="text-sm font-medium text-navy-900">
                {{ dayNames[slot.day_of_week] }}
              </span>
              <span class="text-sm text-body ml-2">
                {{ slot.start_time.substring(0, 5) }} ({{ slot.duration_minutes }} min)
              </span>
              <span v-if="slot.location" class="text-xs text-muted ml-2">{{ slot.location }}</span>
              <span v-if="!slot.is_active" class="text-xs text-red-500 ml-2">inactief</span>
            </div>
            <div v-if="hasPermission('schedule.manage')" class="flex items-center gap-1">
              <IconButton variant="accent" title="Bewerken" @click="editSlot(slot.id)">
                <Pencil :size="14" />
              </IconButton>
              <IconButton variant="danger" title="Verwijderen" @click="promptDeleteSlot(slot.id)">
                <Trash2 :size="14" />
              </IconButton>
            </div>
          </div>
        </div>
      </div>

      <!-- Lesson detail panel -->
      <div v-if="selectedLesson" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="selectedLesson = null">
        <div class="bg-white rounded-xl shadow-xl w-full max-w-sm">
          <div class="flex items-center justify-between p-6 border-b border-navy-100">
            <h3 :class="theme.text.h3">Lesdetails</h3>
            <button @click="selectedLesson = null" class="p-1 rounded hover:bg-surface">
              <X :size="18" />
            </button>
          </div>
          <div class="p-6 space-y-3">
            <p class="text-sm"><strong>Leerling:</strong> {{ selectedLesson.student_name }}</p>
            <p class="text-sm"><strong>Datum:</strong> {{ selectedLesson.lesson_date }}</p>
            <p class="text-sm"><strong>Tijd:</strong> {{ selectedLesson.start_time.substring(0, 5) }}</p>
            <p class="text-sm"><strong>Duur:</strong> {{ selectedLesson.duration_minutes }} min</p>
            <p class="text-sm"><strong>Status:</strong> {{ selectedLesson.status }}</p>
            <p v-if="selectedLesson.substitute_teacher_user_id" class="text-sm flex items-center gap-2">
              <span :class="[theme.badge.base, theme.badge.warning]">
                <RefreshCw :size="12" class="inline mr-1" />Vervanging
              </span>
              <span class="text-navy-900">{{ substituteTeacherName(selectedLesson.substitute_teacher_user_id) }}</span>
            </p>

            <div v-if="lessonActionError" :class="theme.alert.errorInline" class="mt-2">{{ lessonActionError }}</div>

            <div v-if="selectedLesson.status === 'scheduled' && hasPermission('schedule.manage')" class="flex flex-wrap gap-2 pt-2">
              <button @click="handleCompleteLesson" :class="theme.btn.secondarySm" class="flex-1">
                <CheckCircle :size="14" class="inline mr-1" />
                Voltooien
              </button>
              <button @click="handleRescheduleClick" :class="theme.btn.ghost" class="flex-1">
                Verplaatsen
              </button>
              <button @click="handleCancelLesson" :class="theme.btn.dangerOutline" class="flex-1">
                Annuleren
              </button>
            </div>
            <div v-if="selectedLesson.status === 'scheduled' && hasAnyPermission('schedule.substitute', 'schedule.manage')" class="pt-1">
              <button @click="handleSubstituteClick" :class="[theme.btn.secondarySm, 'w-full']">
                Vervanging registreren
              </button>
            </div>
          </div>
        </div>
      </div>

    <!-- Cancel lesson modal -->
    <Teleport to="body">
      <div v-if="showCancelModal" class="fixed inset-0 z-50 flex items-center justify-center px-4" @click.self="showCancelModal = false">
        <div class="absolute inset-0 bg-navy-900/40 pointer-events-none" />
        <div class="relative z-10 bg-white rounded-xl shadow-xl border border-navy-100 w-full max-w-md p-6" @click.stop>
          <h3 :class="theme.text.h3">Les annuleren</h3>
          <p class="mt-2 text-sm text-body">Reden voor annulering (optioneel):</p>
          <textarea
            v-model="cancelReason"
            :class="theme.form.input"
            class="mt-2 w-full"
            rows="3"
            placeholder="Bijv. leerling ziek"
          />
          <div v-if="lessonActionError" :class="theme.alert.errorInline" class="mt-2">{{ lessonActionError }}</div>
          <div class="flex justify-end gap-3 mt-4">
            <button :class="theme.btn.ghost" @click="showCancelModal = false">Terug</button>
            <button :class="theme.btn.dangerFill" @click="confirmCancelLesson">Annuleren</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Delete slot confirmation -->
    <ConfirmModal
      :open="deleteSlotModal"
      title="Lesslot verwijderen"
      message="Weet je zeker dat je dit lesslot wilt verwijderen? Dit kan niet ongedaan worden gemaakt."
      confirm-label="Verwijderen"
      variant="danger"
      :error="deleteSlotError"
      @confirm="confirmDeleteSlot"
      @cancel="deleteSlotModal = false; deletingSlotId = null"
    />

    <!-- Modals -->
    <LessonSlotForm
      v-if="showSlotForm"
      :slot-id="editSlotId"
      @close="showSlotForm = false; editSlotId = undefined"
      @saved="handleSlotSaved"
    />
    <GenerateLessonsModal
      v-if="showGenerateModal"
      @close="showGenerateModal = false"
      @generated="handleGenerated"
    />
    <RescheduleModal
      v-if="showRescheduleModal && selectedLesson"
      :lesson="selectedLesson"
      @close="showRescheduleModal = false"
      @rescheduled="showRescheduleModal = false; selectedLesson = null; loadWeek()"
    />

    <!-- Substitute modal -->
    <Teleport to="body">
      <div v-if="showSubstituteModal && selectedLesson" class="fixed inset-0 z-50 flex items-center justify-center px-4" @click.self="showSubstituteModal = false">
        <div class="absolute inset-0 bg-navy-900/40 pointer-events-none" />
        <div class="relative z-10 bg-white rounded-xl shadow-xl border border-navy-100 w-full max-w-md p-6" @click.stop>
          <h3 :class="theme.text.h3">Vervanging registreren</h3>

          <!-- Context info -->
          <div class="mt-3 rounded-lg bg-surface p-3 text-sm space-y-1">
            <p><strong>Leerling:</strong> {{ selectedLesson.student_name }}</p>
            <p><strong>Datum:</strong> {{ selectedLesson.lesson_date }} &middot; {{ selectedLesson.start_time.substring(0, 5) }}</p>
            <p v-if="selectedLesson.substitute_teacher_user_id">
              <strong>Huidige vervanging:</strong>
              <span :class="[theme.badge.base, theme.badge.warning, 'ml-1']">
                {{ substituteTeacherName(selectedLesson.substitute_teacher_user_id) }}
              </span>
            </p>
          </div>

          <!-- Search + select teacher -->
          <div class="mt-4">
            <label :class="theme.form.label">Vervangende docent *</label>
            <input
              v-model="substituteSearch"
              type="text"
              :class="[theme.form.input, 'mb-2']"
              placeholder="Zoek op naam of e-mail..."
            />
            <div class="max-h-48 overflow-y-auto border border-navy-200 rounded-lg">
              <div v-if="filteredSubstituteTeachers.length === 0" class="px-3 py-2 text-sm text-muted">
                Geen docenten gevonden
              </div>
              <label
                v-for="t in filteredSubstituteTeachers"
                :key="t.user_id"
                class="flex items-center gap-3 px-3 py-2 hover:bg-surface cursor-pointer text-sm border-b border-navy-50 last:border-b-0"
                :class="{ 'bg-accent-50': substituteTeacherId === t.user_id }"
              >
                <input
                  type="radio"
                  :value="t.user_id"
                  v-model="substituteTeacherId"
                  class="text-accent-700 focus:ring-accent-500"
                />
                <div>
                  <p class="font-medium text-navy-900">{{ t.full_name }}</p>
                  <p v-if="t.email" class="text-xs text-muted">{{ t.email }}</p>
                </div>
              </label>
            </div>
          </div>

          <!-- Reason -->
          <div class="mt-3">
            <label :class="theme.form.label">Reden (optioneel)</label>
            <textarea
              v-model="substituteReason"
              :class="theme.form.input"
              rows="2"
              placeholder="Bijv. docent ziek"
            />
          </div>

          <div v-if="substituteError" :class="[theme.alert.errorInline, 'mt-3']">{{ substituteError }}</div>
          <div class="flex justify-end gap-3 mt-4">
            <button :class="theme.btn.ghost" @click="showSubstituteModal = false">Annuleren</button>
            <button
              :class="theme.btn.primarySm"
              :disabled="!substituteTeacherId || substituteLoading"
              @click="confirmSubstitute"
            >
              {{ substituteLoading ? 'Opslaan...' : 'Registreren' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
