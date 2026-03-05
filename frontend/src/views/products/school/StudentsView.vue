<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import {
  Search,
  Plus,
  Upload,
  X,
  Pencil,
  UserX,
  UserCheck,
  ChevronLeft,
  ChevronRight,
  UserPlus,
  UserMinus,
  Info,
} from 'lucide-vue-next'
import { studentsApi } from '@/api/products/school/students'
import type { Student, StudentCreate, StudentImportResponse, Member, TeacherStudentAssignment } from '@/types/models'
import { theme } from '@/theme'
import IconButton from '@/components/ui/IconButton.vue'
import { usePermissions } from '@/composables/usePermissions'
import { useTenantStore } from '@/stores/tenant'
import { useAuthStore } from '@/stores/auth'

const { hasPermission, hasAnyPermission } = usePermissions()
const tenantStore = useTenantStore()
const authStore = useAuthStore()

// Teacher-scoped: user sees only their own students
const isTeacherScope = computed(() =>
  hasPermission('students.view_assigned') && !hasPermission('students.view')
)

const students = ref<Student[]>([])
const total = ref(0)
const page = ref(1)
const perPage = 25
const search = ref('')
const showActive = ref(true)
const loading = ref(false)
const error = ref<string | null>(null)

// Modal state
const showForm = ref(false)
const editingStudent = ref<Student | null>(null)
const formLoading = ref(false)
const formError = ref<string | null>(null)

// Import state
const showImport = ref(false)
const importFile = ref<File | null>(null)
const importResult = ref<StudentImportResponse | null>(null)
const importLoading = ref(false)
const importError = ref<string | null>(null)

// Form fields
const form = ref<StudentCreate>({
  first_name: '',
  last_name: null,
  email: null,
  phone: null,
  date_of_birth: null,
  lesson_day: null,
  lesson_duration: null,
  lesson_time: null,
  level: null,
  notes: null,
  guardian_name: null,
  guardian_relationship: null,
  guardian_phone: null,
  guardian_phone_work: null,
  guardian_email: null,
})

// Teacher assignment state
const showAssignModal = ref(false)
const assignStudentId = ref<string | null>(null)
const assignTeacherId = ref('')
const assignLoading = ref(false)
const assignError = ref<string | null>(null)
const teacherSearch = ref('')
const teachers = ref<Member[]>([])

// Per-student teacher assignments cache
const studentTeachers = ref<Record<string, TeacherStudentAssignment[]>>({})

const filteredTeachers = computed(() => {
  if (!teacherSearch.value) return teachers.value
  const q = teacherSearch.value.toLowerCase()
  return teachers.value.filter(
    (t) => t.full_name.toLowerCase().includes(q) || (t.email?.toLowerCase().includes(q) ?? false),
  )
})

async function loadTeachers() {
  teachers.value = await tenantStore.getTeachers()
}

function teacherName(userId: string): string {
  const t = teachers.value.find((m) => m.user_id === userId)
  return t?.full_name ?? userId.slice(0, 8) + '...'
}

function getStudentTeacherNames(studentId: string): string {
  const assignments = studentTeachers.value[studentId]
  if (!assignments || assignments.length === 0) return '—'
  const names = assignments.map((a) => teacherName(a.user_id))
  if (names.length <= 2) return names.join(', ')
  return `${names[0]} +${names.length - 1}`
}

function getStudentTeacherTooltip(studentId: string): string {
  const assignments = studentTeachers.value[studentId]
  if (!assignments || assignments.length <= 2) return ''
  return assignments.map((a) => teacherName(a.user_id)).join('\n')
}

async function fetchStudentTeachers() {
  const result: Record<string, TeacherStudentAssignment[]> = {}
  await Promise.all(
    students.value.map(async (s) => {
      try {
        const resp = await studentsApi.listTeachers(s.id)
        result[s.id] = resp.items
      } catch {
        result[s.id] = []
      }
    }),
  )
  studentTeachers.value = result
}

async function openAssignTeacher(studentId: string) {
  assignStudentId.value = studentId
  assignTeacherId.value = ''
  teacherSearch.value = ''
  assignError.value = null
  showAssignModal.value = true
  await loadTeachers()
}

async function confirmAssignTeacher() {
  if (!assignStudentId.value || !assignTeacherId.value) return
  assignLoading.value = true
  assignError.value = null
  try {
    await studentsApi.assignTeacher(assignStudentId.value, {
      user_id: assignTeacherId.value,
    })
    showAssignModal.value = false
    assignStudentId.value = null
    await fetchStudents()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    assignError.value = err.response?.data?.detail ?? 'Toewijzen mislukt'
  } finally {
    assignLoading.value = false
  }
}

async function handleUnassign(studentId: string, teacherUserId: string) {
  try {
    await studentsApi.unassignTeacher(studentId, teacherUserId)
    await fetchStudents()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Ontkoppelen mislukt'
  }
}

async function handleSelfAssign(studentId: string) {
  try {
    await studentsApi.selfAssign(studentId)
    await fetchStudents()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Zelf toewijzen mislukt'
  }
}

let searchTimeout: ReturnType<typeof setTimeout> | null = null

watch(search, () => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    page.value = 1
    fetchStudents()
  }, 300)
})

watch(showActive, () => {
  page.value = 1
  fetchStudents()
})

onMounted(async () => {
  await fetchStudents()
  loadTeachers()
})

async function fetchStudents() {
  loading.value = true
  error.value = null
  try {
    const result = await studentsApi.list({
      search: search.value || undefined,
      active: showActive.value,
      page: page.value,
      per_page: perPage,
    })
    students.value = result.items
    total.value = result.total
    // Fetch teacher assignments for visible students
    if (students.value.length > 0) {
      fetchStudentTeachers()
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Kon leerlingen niet laden'
  } finally {
    loading.value = false
  }
}

function totalPages(): number {
  return Math.max(1, Math.ceil(total.value / perPage))
}

function prevPage() {
  if (page.value > 1) {
    page.value--
    fetchStudents()
  }
}

function nextPage() {
  if (page.value < totalPages()) {
    page.value++
    fetchStudents()
  }
}

function openCreate() {
  editingStudent.value = null
  resetForm()
  showForm.value = true
}

function openEdit(student: Student) {
  editingStudent.value = student
  form.value = {
    first_name: student.first_name,
    last_name: student.last_name,
    email: student.email,
    phone: student.phone,
    date_of_birth: student.date_of_birth,
    lesson_day: student.lesson_day,
    lesson_duration: student.lesson_duration,
    lesson_time: student.lesson_time,
    level: student.level,
    notes: student.notes,
    guardian_name: student.guardian_name,
    guardian_relationship: student.guardian_relationship,
    guardian_phone: student.guardian_phone,
    guardian_phone_work: student.guardian_phone_work,
    guardian_email: student.guardian_email,
  }
  showForm.value = true
}

function resetForm() {
  form.value = {
    first_name: '',
    last_name: null,
    email: null,
    phone: null,
    date_of_birth: null,
    lesson_day: null,
    lesson_duration: null,
    lesson_time: null,
    level: null,
    notes: null,
    guardian_name: null,
    guardian_relationship: null,
    guardian_phone: null,
    guardian_phone_work: null,
    guardian_email: null,
  }
  formError.value = null
}

function closeForm() {
  showForm.value = false
  editingStudent.value = null
  resetForm()
}

async function submitForm() {
  formLoading.value = true
  formError.value = null
  try {
    if (editingStudent.value) {
      await studentsApi.update(editingStudent.value.id, form.value)
    } else {
      await studentsApi.create(form.value)
    }
    closeForm()
    fetchStudents()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    formError.value = err.response?.data?.detail ?? 'Opslaan mislukt'
  } finally {
    formLoading.value = false
  }
}

async function toggleActive(student: Student) {
  try {
    if (student.is_active) {
      await studentsApi.delete(student.id)
    } else {
      await studentsApi.update(student.id, { is_active: true })
    }
    fetchStudents()
  } catch {
    // silently fail
  }
}

function onFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    importFile.value = target.files[0]
  }
}

async function handleImport() {
  if (!importFile.value) return
  importLoading.value = true
  importError.value = null
  importResult.value = null
  try {
    importResult.value = await studentsApi.import(importFile.value)
    importFile.value = null
    fetchStudents()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    importError.value = err.response?.data?.detail ?? 'Import mislukt'
  } finally {
    importLoading.value = false
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('nl-NL')
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-6">
      <h2 :class="theme.text.h2">Leerlingen</h2>
      <div class="flex items-center gap-2">
        <button
          v-if="hasPermission('students.import')"
          @click="showImport = !showImport"
          :class="[theme.btn.secondarySm, 'flex items-center gap-1.5']"
        >
          <Upload :size="16" />
          Excel import
        </button>
        <button
          v-if="hasPermission('students.create')"
          @click="openCreate"
          :class="[theme.btn.primarySm, 'flex items-center gap-1.5']"
        >
          <Plus :size="16" />
          Toevoegen
        </button>
      </div>
    </div>

    <!-- Import section -->
    <div v-if="showImport" :class="[theme.card.padded, 'mb-6']">
      <div class="flex items-center justify-between mb-4">
        <h3 :class="theme.text.h3">Excel importeren</h3>
        <button @click="showImport = false; importResult = null; importError = null" class="text-navy-400 hover:text-navy-600">
          <X :size="18" />
        </button>
      </div>
      <div class="flex flex-col md:flex-row gap-4 md:items-end">
        <div class="flex-1">
          <label :class="theme.form.label">Selecteer Excel bestand</label>
          <input
            type="file"
            accept=".xlsx,.xls"
            @change="onFileSelect"
            :class="theme.form.input"
          />
        </div>
        <button
          @click="handleImport"
          :disabled="!importFile || importLoading"
          :class="[theme.btn.primarySm, 'disabled:opacity-50']"
        >
          {{ importLoading ? 'Importeren...' : 'Importeren' }}
        </button>
      </div>
      <div v-if="importResult" :class="theme.alert.success" class="mt-3">
        {{ importResult.imported }} geïmporteerd, {{ importResult.skipped }} overgeslagen.
        <div v-if="importResult.errors.length > 0" class="mt-1 text-red-600">
          <p v-for="(err, i) in importResult.errors" :key="i">{{ err }}</p>
        </div>
      </div>
      <div v-if="importError" :class="theme.alert.errorInline">{{ importError }}</div>
    </div>

    <!-- Filters -->
    <div :class="[theme.card.padded, 'mb-6']">
      <div class="flex flex-col md:flex-row gap-4 md:items-center">
        <div class="flex-1 relative">
          <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            v-model="search"
            type="text"
            placeholder="Zoek op naam, e-mail..."
            :class="[theme.form.input, 'pl-9']"
          />
        </div>
        <label class="flex items-center gap-2 text-sm text-navy-700 cursor-pointer select-none">
          <input
            v-model="showActive"
            type="checkbox"
            class="rounded border-navy-300 text-accent-700 focus:ring-accent-500"
          />
          Alleen actief
        </label>
      </div>
    </div>

    <!-- Teacher scope banner -->
    <div v-if="isTeacherScope" class="flex items-center gap-2 mb-4 px-4 py-3 rounded-lg bg-blue-50 border border-blue-200 text-sm text-blue-800">
      <Info :size="16" class="shrink-0" />
      Je ziet alleen je eigen leerlingen. Neem contact op met een beheerder om leerlingen toe te wijzen.
    </div>

    <!-- Error -->
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <!-- Loading -->
    <div v-if="loading" :class="[theme.card.padded, 'text-center']">
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <!-- Student table -->
    <div v-else :class="theme.card.base">
      <div v-if="students.length === 0" :class="theme.list.empty">
        <p class="text-navy-900 font-medium">Geen leerlingen gevonden</p>
        <p :class="[theme.text.muted, 'mt-1']">
          {{ search ? 'Probeer een andere zoekterm.' : 'Voeg uw eerste leerling toe.' }}
        </p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-navy-100 text-left">
              <th class="px-6 py-3 font-medium text-navy-700">Naam</th>
              <th class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">E-mail</th>
              <th class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">Telefoon</th>
              <th class="px-6 py-3 font-medium text-navy-700 hidden md:table-cell">Niveau</th>
              <th class="px-6 py-3 font-medium text-navy-700 hidden lg:table-cell">Docent</th>
              <th class="px-6 py-3 font-medium text-navy-700">Les</th>
              <th class="px-6 py-3 font-medium text-navy-700">Status</th>
              <th class="px-6 py-3 font-medium text-navy-700 text-right">Acties</th>
            </tr>
          </thead>
          <tbody :class="theme.list.divider">
            <tr
              v-for="student in students"
              :key="student.id"
              class="hover:bg-surface transition-colors"
            >
              <td class="px-6 py-3">
                <div>
                  <p :class="theme.text.h4">{{ student.first_name }} {{ student.last_name ?? '' }}</p>
                  <p v-if="student.guardian_name" class="text-xs text-muted">
                    Ouder: {{ student.guardian_name }}
                  </p>
                </div>
              </td>
              <td class="px-6 py-3 text-body hidden md:table-cell">{{ student.email ?? '—' }}</td>
              <td class="px-6 py-3 text-body hidden md:table-cell">{{ student.phone ?? '—' }}</td>
              <td class="px-6 py-3 text-body hidden md:table-cell">{{ student.level ?? '—' }}</td>
              <td class="px-6 py-3 text-body hidden lg:table-cell" :title="getStudentTeacherTooltip(student.id)">
                {{ getStudentTeacherNames(student.id) }}
              </td>
              <td class="px-6 py-3 text-body">
                <span v-if="student.lesson_day">
                  {{ student.lesson_day }} {{ student.lesson_time ?? '' }}
                  <span v-if="student.lesson_duration" class="text-muted">({{ student.lesson_duration }}min)</span>
                </span>
                <span v-else>—</span>
              </td>
              <td class="px-6 py-3">
                <span
                  :class="[
                    theme.badge.base,
                    student.is_active ? theme.badge.success : theme.badge.warning
                  ]"
                >
                  {{ student.is_active ? 'Actief' : 'Inactief' }}
                </span>
              </td>
              <td class="px-6 py-3">
                <div class="flex items-center justify-end gap-1">
                  <IconButton v-if="hasPermission('students.assign')" variant="accent" title="Docent toewijzen" @click="openAssignTeacher(student.id)">
                    <UserPlus :size="14" />
                  </IconButton>
                  <IconButton v-if="hasPermission('students.edit')" variant="accent" title="Bewerken" @click="openEdit(student)">
                    <Pencil :size="14" />
                  </IconButton>
                  <IconButton
                    v-if="hasPermission('students.delete')"
                    :variant="student.is_active ? 'warning' : 'success'"
                    :title="student.is_active ? 'Deactiveren' : 'Activeren'"
                    @click="toggleActive(student)"
                  >
                    <UserX v-if="student.is_active" :size="14" />
                    <UserCheck v-else :size="14" />
                  </IconButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="total > perPage" class="flex items-center justify-between px-6 py-3 border-t border-navy-100">
        <p class="text-sm text-muted">
          {{ (page - 1) * perPage + 1 }}–{{ Math.min(page * perPage, total) }} van {{ total }}
        </p>
        <div class="flex items-center gap-2">
          <button
            @click="prevPage"
            :disabled="page <= 1"
            class="p-1.5 rounded-lg hover:bg-surface disabled:opacity-30 transition-colors"
          >
            <ChevronLeft :size="16" />
          </button>
          <span class="text-sm text-navy-700">{{ page }} / {{ totalPages() }}</span>
          <button
            @click="nextPage"
            :disabled="page >= totalPages()"
            class="p-1.5 rounded-lg hover:bg-surface disabled:opacity-30 transition-colors"
          >
            <ChevronRight :size="16" />
          </button>
        </div>
      </div>
    </div>

    <!-- Assign Teacher Modal -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="showAssignModal"
          class="fixed inset-0 z-50 flex items-center justify-center px-4"
          @click.self="showAssignModal = false"
        >
          <div class="absolute inset-0 bg-navy-900/40 pointer-events-none" />
          <div class="relative z-10 bg-white rounded-xl shadow-xl border border-navy-100 w-full max-w-md p-6" @click.stop>
            <h3 :class="theme.text.h3">Docent toewijzen</h3>

            <!-- Current assignments -->
            <div v-if="assignStudentId && (studentTeachers[assignStudentId]?.length ?? 0) > 0" class="mt-3">
              <p class="text-xs text-muted mb-1">Huidige docent(en):</p>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="a in studentTeachers[assignStudentId]"
                  :key="a.id"
                  :class="[theme.badge.base, theme.badge.info, 'flex items-center gap-1']"
                >
                  {{ teacherName(a.user_id) }}
                  <button
                    @click="handleUnassign(assignStudentId!, a.user_id)"
                    class="hover:text-red-600"
                    title="Ontkoppelen"
                  >
                    <X :size="12" />
                  </button>
                </span>
              </div>
            </div>

            <!-- Search + select teacher -->
            <div class="mt-4">
              <label :class="theme.form.label">Docent selecteren *</label>
              <input
                v-model="teacherSearch"
                type="text"
                :class="[theme.form.input, 'mb-2']"
                placeholder="Zoek op naam of e-mail..."
              />
              <div class="max-h-48 overflow-y-auto border border-navy-200 rounded-lg">
                <div v-if="filteredTeachers.length === 0" class="px-3 py-2 text-sm text-muted">
                  Geen docenten gevonden
                </div>
                <label
                  v-for="t in filteredTeachers"
                  :key="t.user_id"
                  class="flex items-center gap-3 px-3 py-2 hover:bg-surface cursor-pointer text-sm border-b border-navy-50 last:border-b-0"
                  :class="{ 'bg-accent-50': assignTeacherId === t.user_id }"
                >
                  <input
                    type="radio"
                    :value="t.user_id"
                    v-model="assignTeacherId"
                    class="text-accent-700 focus:ring-accent-500"
                  />
                  <div>
                    <p class="font-medium text-navy-900">{{ t.full_name }}</p>
                    <p v-if="t.email" class="text-xs text-muted">{{ t.email }}</p>
                  </div>
                </label>
              </div>
            </div>
            <div v-if="assignError" :class="[theme.alert.errorInline, 'mt-3']">{{ assignError }}</div>
            <div class="flex justify-end gap-3 mt-4">
              <button :class="theme.btn.ghost" @click="showAssignModal = false">Annuleren</button>
              <button
                :class="theme.btn.primarySm"
                :disabled="!assignTeacherId || assignLoading"
                @click="confirmAssignTeacher"
              >
                {{ assignLoading ? 'Toewijzen...' : 'Toewijzen' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Create/Edit Modal -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="showForm"
          class="fixed inset-0 z-50 flex items-start justify-center px-4 pt-16 pb-8 overflow-y-auto"
          @click.self="closeForm"
        >
          <div class="absolute inset-0 bg-navy-900/40 pointer-events-none" />

          <div
            class="relative z-10 bg-white rounded-xl shadow-xl border border-navy-100 w-full max-w-2xl p-6"
            @click.stop
          >
            <div class="flex items-center justify-between mb-6">
              <h3 :class="theme.text.h3">
                {{ editingStudent ? 'Leerling bewerken' : 'Nieuwe leerling' }}
              </h3>
              <button @click="closeForm" class="text-navy-400 hover:text-navy-600">
                <X :size="20" />
              </button>
            </div>

            <form @submit.prevent="submitForm">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <!-- Persoonlijk -->
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Voornaam *</label>
                  <input v-model="form.first_name" type="text" required :class="theme.form.input" />
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Achternaam</label>
                  <input v-model="form.last_name" type="text" :class="theme.form.input" />
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">E-mail</label>
                  <input v-model="form.email" type="email" :class="theme.form.input" />
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Telefoon</label>
                  <input v-model="form.phone" type="text" :class="theme.form.input" />
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Geboortedatum</label>
                  <input v-model="form.date_of_birth" type="date" :class="theme.form.input" />
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Niveau</label>
                  <input v-model="form.level" type="text" :class="theme.form.input" placeholder="Beginner, Gevorderd..." />
                </div>

                <!-- Les info -->
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Lesdag</label>
                  <input v-model="form.lesson_day" type="text" :class="theme.form.input" placeholder="Maandag" />
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Lestijd</label>
                  <input v-model="form.lesson_time" type="text" :class="theme.form.input" placeholder="14:00" />
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Lesduur (min)</label>
                  <input v-model.number="form.lesson_duration" type="number" min="15" max="120" :class="theme.form.input" />
                </div>

                <!-- Ouder/voogd -->
                <div class="col-span-1 md:col-span-2 mt-2 mb-2">
                  <p class="text-sm font-medium text-navy-500 uppercase tracking-wider">Ouder/voogd</p>
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Naam ouder</label>
                  <input v-model="form.guardian_name" type="text" :class="theme.form.input" />
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Relatie</label>
                  <input v-model="form.guardian_relationship" type="text" :class="theme.form.input" placeholder="Vader, Moeder..." />
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Telefoon ouder</label>
                  <input v-model="form.guardian_phone" type="text" :class="theme.form.input" />
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">Telefoon werk</label>
                  <input v-model="form.guardian_phone_work" type="text" :class="theme.form.input" />
                </div>
                <div :class="theme.form.group">
                  <label :class="theme.form.label">E-mail ouder</label>
                  <input v-model="form.guardian_email" type="email" :class="theme.form.input" />
                </div>

                <!-- Notes -->
                <div class="col-span-1 md:col-span-2" :class="theme.form.group">
                  <label :class="theme.form.label">Opmerkingen</label>
                  <textarea v-model="form.notes" rows="3" :class="theme.form.input" />
                </div>
              </div>

              <div v-if="formError" :class="[theme.alert.error, 'mt-4']">{{ formError }}</div>

              <div class="flex justify-end gap-3 mt-6">
                <button
                  type="button"
                  @click="closeForm"
                  :class="theme.btn.ghost"
                >
                  Annuleren
                </button>
                <button
                  type="submit"
                  :disabled="formLoading"
                  :class="[theme.btn.primarySm, 'disabled:opacity-50']"
                >
                  {{ formLoading ? 'Opslaan...' : (editingStudent ? 'Bijwerken' : 'Toevoegen') }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
