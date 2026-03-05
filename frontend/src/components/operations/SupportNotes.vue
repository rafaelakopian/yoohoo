<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { Pin, Plus, Pencil, Trash2 } from 'lucide-vue-next'
import { theme } from '@/theme'
import { useAuthStore } from '@/stores/auth'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import {
  getTenantNotes,
  createTenantNote,
  getUserNotes,
  createUserNote,
  updateNote,
  deleteNote,
  togglePinNote,
  type SupportNote,
} from '@/api/platform/operations'

const props = defineProps<{
  targetType: 'tenant' | 'user'
  targetId: string
}>()

const authStore = useAuthStore()
const notes = ref<SupportNote[]>([])
const loading = ref(true)
const error = ref('')
const success = ref('')

// New note form
const showNewForm = ref(false)
const newContent = ref('')
const newPinned = ref(false)
const saving = ref(false)

// Edit state
const editingId = ref<string | null>(null)
const editContent = ref('')

// Delete confirmation
const deleteTarget = ref<SupportNote | null>(null)
const deleting = ref(false)

const currentUserId = computed(() => authStore.user?.id)

async function loadNotes() {
  try {
    notes.value = props.targetType === 'tenant'
      ? await getTenantNotes(props.targetId)
      : await getUserNotes(props.targetId)
  } catch {
    error.value = 'Kon notities niet laden'
  } finally {
    loading.value = false
  }
}

onMounted(loadNotes)

async function handleCreate() {
  if (!newContent.value.trim()) return
  saving.value = true
  try {
    const body = { content: newContent.value, is_pinned: newPinned.value }
    const note = props.targetType === 'tenant'
      ? await createTenantNote(props.targetId, body)
      : await createUserNote(props.targetId, body)
    notes.value.unshift(note)
    sortNotes()
    newContent.value = ''
    newPinned.value = false
    showNewForm.value = false
    flashSuccess('Notitie aangemaakt')
  } catch {
    error.value = 'Kon notitie niet aanmaken'
  } finally {
    saving.value = false
  }
}

function startEdit(note: SupportNote) {
  editingId.value = note.id
  editContent.value = note.content
}

function cancelEdit() {
  editingId.value = null
  editContent.value = ''
}

async function handleUpdate(noteId: string) {
  if (!editContent.value.trim()) return
  saving.value = true
  try {
    const updated = await updateNote(noteId, { content: editContent.value })
    const idx = notes.value.findIndex(n => n.id === noteId)
    if (idx >= 0) notes.value[idx] = updated
    editingId.value = null
    flashSuccess('Notitie bijgewerkt')
  } catch {
    error.value = 'Kon notitie niet bijwerken'
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteNote(deleteTarget.value.id)
    notes.value = notes.value.filter(n => n.id !== deleteTarget.value!.id)
    deleteTarget.value = null
    flashSuccess('Notitie verwijderd')
  } catch {
    error.value = 'Kon notitie niet verwijderen'
  } finally {
    deleting.value = false
  }
}

async function handleTogglePin(note: SupportNote) {
  try {
    const updated = await togglePinNote(note.id)
    const idx = notes.value.findIndex(n => n.id === note.id)
    if (idx >= 0) notes.value[idx] = updated
    sortNotes()
  } catch {
    error.value = 'Kon pin status niet wijzigen'
  }
}

function sortNotes() {
  notes.value.sort((a, b) => {
    if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
}

function isOwn(note: SupportNote): boolean {
  return note.created_by_id === currentUserId.value
}

function flashSuccess(msg: string) {
  success.value = msg
  setTimeout(() => { success.value = '' }, 3000)
}

function relativeTime(d: string): string {
  const now = Date.now()
  const then = new Date(d).getTime()
  const diff = Math.floor((now - then) / 1000)
  if (diff < 60) return 'Zojuist'
  if (diff < 3600) return `${Math.floor(diff / 60)} min geleden`
  if (diff < 86400) return `${Math.floor(diff / 3600)} uur geleden`
  if (diff < 172800) return 'Gisteren'
  return new Date(d).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div :class="[theme.card.base, 'overflow-hidden']">
    <!-- Header -->
    <div class="flex items-center justify-between p-4">
      <h3 :class="theme.text.h4">
        <span class="hidden md:inline">Interne notities</span>
        <span class="md:hidden">Notities</span>
        <span :class="[theme.text.muted, 'ml-1']">({{ notes.length }})</span>
      </h3>
      <button
        :class="theme.btn.addInline"
        @click="showNewForm = !showNewForm"
      >
        <span :class="theme.btn.addInlineIcon"><Plus :size="14" /></span>
        <span class="hidden md:inline">Notitie</span>
      </button>
    </div>

    <!-- Success alert -->
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="success" :class="[theme.alert.success, 'mx-4']">{{ success }}</div>
    </Transition>

    <!-- Error alert -->
    <div v-if="error" :class="[theme.alert.error, 'mx-4']">{{ error }}</div>

    <!-- New note form -->
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 max-h-0"
      enter-to-class="opacity-100 max-h-60"
      leave-active-class="transition-all duration-200"
      leave-from-class="opacity-100 max-h-60"
      leave-to-class="opacity-0 max-h-0"
    >
      <div v-if="showNewForm" class="px-4 pb-4 overflow-hidden">
        <textarea
          v-model="newContent"
          :class="[theme.form.input, 'min-h-[80px] resize-y']"
          placeholder="Nieuwe notitie..."
          maxlength="5000"
        />
        <div class="flex items-center justify-between mt-2">
          <label class="flex items-center gap-2 text-sm text-body cursor-pointer">
            <input v-model="newPinned" type="checkbox" class="rounded" />
            <Pin :size="14" /> Vastpinnen
          </label>
          <div class="flex gap-2">
            <button :class="theme.btn.ghost" @click="showNewForm = false">Annuleren</button>
            <button
              :class="theme.btn.primarySm"
              :disabled="!newContent.trim() || saving"
              @click="handleCreate"
            >
              {{ saving ? 'Opslaan...' : 'Opslaan' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Loading -->
    <div v-if="loading" class="p-4">
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <!-- Notes list -->
    <div v-else-if="notes.length === 0" :class="[theme.list.empty, 'py-6 text-sm']">
      Geen notities
    </div>

    <div v-else class="divide-y divide-navy-100">
      <div
        v-for="note in notes"
        :key="note.id"
        class="px-4 py-3"
        :class="note.is_pinned ? 'border-l-4 border-amber-400 bg-amber-50/30' : ''"
      >
        <!-- View mode -->
        <template v-if="editingId !== note.id">
          <div class="flex items-start justify-between gap-2">
            <div class="flex-1 min-w-0">
              <p :class="theme.text.body" class="whitespace-pre-wrap break-words">{{ note.content }}</p>
              <p :class="[theme.text.muted, 'text-xs mt-1']">
                {{ note.created_by_name }}
                <span class="mx-1">&middot;</span>
                {{ relativeTime(note.updated_at ?? note.created_at) }}
              </p>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              <button
                class="p-1.5 rounded hover:bg-surface transition-colors"
                :class="note.is_pinned ? 'text-amber-500' : 'text-body/40 hover:text-body'"
                title="Pin toggling"
                @click="handleTogglePin(note)"
              >
                <Pin :size="14" />
              </button>
              <template v-if="isOwn(note)">
                <button
                  class="p-1.5 rounded text-body/40 hover:text-body hover:bg-surface transition-colors"
                  title="Bewerken"
                  @click="startEdit(note)"
                >
                  <Pencil :size="14" />
                </button>
                <button
                  class="p-1.5 rounded text-body/40 hover:text-red-600 hover:bg-red-50 transition-colors"
                  title="Verwijderen"
                  @click="deleteTarget = note"
                >
                  <Trash2 :size="14" />
                </button>
              </template>
            </div>
          </div>
        </template>

        <!-- Edit mode -->
        <template v-else>
          <textarea
            v-model="editContent"
            :class="[theme.form.input, 'min-h-[60px] resize-y']"
            maxlength="5000"
          />
          <div class="flex justify-end gap-2 mt-2">
            <button :class="theme.btn.ghost" @click="cancelEdit">Annuleren</button>
            <button
              :class="theme.btn.primarySm"
              :disabled="!editContent.trim() || saving"
              @click="handleUpdate(note.id)"
            >
              {{ saving ? 'Opslaan...' : 'Opslaan' }}
            </button>
          </div>
        </template>
      </div>
    </div>

    <!-- Delete modal -->
    <ConfirmModal
      :open="!!deleteTarget"
      title="Notitie verwijderen"
      message="Weet je zeker dat je deze notitie wilt verwijderen?"
      confirm-label="Verwijderen"
      variant="danger"
      :loading="deleting"
      @confirm="handleDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>
