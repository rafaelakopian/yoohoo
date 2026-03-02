<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import { theme } from '@/theme'

export interface GroupFormData {
  name: string
  slug: string
  description: string
  permissions: string[]
}

export interface ModulePermissionItem {
  codename: string
  label: string
  description?: string
}

export interface ModulePermissionsGroup {
  module_name: string
  label: string
  permissions: ModulePermissionItem[]
}

export interface EditingGroup {
  id: string
  name: string
  slug: string
  description?: string | null
  permissions: string[]
}

const props = defineProps<{
  open: boolean
  editingGroup: EditingGroup | null
  registry: ModulePermissionsGroup[]
}>()

const emit = defineEmits<{
  save: [data: GroupFormData]
  close: []
}>()

const form = ref<GroupFormData>({ name: '', slug: '', description: '', permissions: [] })
const expandedModules = ref<Set<string>>(new Set())
const validationError = ref('')

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      if (props.editingGroup) {
        form.value = {
          name: props.editingGroup.name,
          slug: props.editingGroup.slug,
          description: props.editingGroup.description ?? '',
          permissions: [...props.editingGroup.permissions],
        }
      } else {
        form.value = { name: '', slug: '', description: '', permissions: [] }
      }
      expandedModules.value = new Set()
      validationError.value = ''
    }
  },
)

function autoSlug() {
  if (!props.editingGroup) {
    form.value.slug = form.value.name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '')
  }
}

function toggleModule(moduleName: string) {
  if (expandedModules.value.has(moduleName)) {
    expandedModules.value.delete(moduleName)
  } else {
    expandedModules.value.add(moduleName)
  }
}

function togglePermission(codename: string) {
  const idx = form.value.permissions.indexOf(codename)
  if (idx === -1) {
    form.value.permissions.push(codename)
  } else {
    form.value.permissions.splice(idx, 1)
  }
}

const allCodenames = computed(() => {
  const all = new Set<string>()
  for (const m of props.registry) {
    for (const p of m.permissions) {
      all.add(p.codename)
    }
  }
  return all
})

function selectAll() {
  form.value.permissions = [...allCodenames.value]
}

function deselectAll() {
  form.value.permissions = []
}

function handleSubmit() {
  const name = form.value.name.trim()
  const slug = form.value.slug.trim()
  if (!name) {
    validationError.value = 'Naam is verplicht.'
    return
  }
  if (!slug) {
    validationError.value = 'Slug is verplicht.'
    return
  }
  validationError.value = ''
  emit('save', { ...form.value })
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    @click.self="emit('close')"
  >
    <div class="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
      <h2 :class="[theme.text.h3, 'mb-4']">
        {{ editingGroup ? 'Groep bewerken' : 'Nieuwe groep' }}
      </h2>

      <div class="space-y-4">
        <div>
          <label :class="theme.form.label">Naam</label>
          <input
            v-model="form.name"
            @input="autoSlug"
            type="text"
            :class="theme.form.input"
            placeholder="Bijv. Support"
          />
        </div>

        <div v-if="!editingGroup">
          <label :class="theme.form.label">Slug</label>
          <input
            v-model="form.slug"
            type="text"
            :class="theme.form.input"
            placeholder="support"
          />
        </div>

        <div>
          <label :class="theme.form.label">Beschrijving</label>
          <textarea
            v-model="form.description"
            :class="theme.form.input"
            rows="2"
            placeholder="Optionele beschrijving..."
          />
        </div>

        <!-- Permission matrix -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <label :class="[theme.form.label, '!mb-0']">Rechten</label>
            <div class="flex gap-3">
              <button @click="selectAll" :class="theme.btn.link">Alles selecteren</button>
              <button @click="deselectAll" :class="theme.btn.link">Alles deselecteren</button>
            </div>
          </div>

          <div :class="[theme.card.base, theme.list.divider]">
            <div v-for="mod in registry" :key="mod.module_name">
              <button
                @click="toggleModule(mod.module_name)"
                class="w-full flex items-center justify-between p-3 hover:bg-surface text-left"
              >
                <span :class="theme.text.h4">{{ mod.label }}</span>
                <ChevronUp v-if="expandedModules.has(mod.module_name)" :size="16" class="text-body" />
                <ChevronDown v-else :size="16" class="text-body" />
              </button>
              <div v-if="expandedModules.has(mod.module_name)" class="px-3 pb-3 space-y-1.5">
                <label
                  v-for="perm in mod.permissions"
                  :key="perm.codename"
                  class="flex items-center gap-2 text-sm cursor-pointer hover:bg-surface p-1 rounded"
                >
                  <input
                    type="checkbox"
                    :checked="form.permissions.includes(perm.codename)"
                    @change="togglePermission(perm.codename)"
                    class="rounded border-navy-300"
                  />
                  <span class="text-navy-800">{{ perm.label }}</span>
                  <span v-if="perm.description" class="text-xs text-body ml-auto">
                    {{ perm.description }}
                  </span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      <p v-if="validationError" :class="theme.alert.errorInline" class="mt-4">
        {{ validationError }}
      </p>

      <div class="flex justify-end gap-3 mt-6">
        <button @click="emit('close')" :class="theme.btn.secondary">Annuleren</button>
        <button @click="handleSubmit" :class="theme.btn.primary">
          {{ editingGroup ? 'Opslaan' : 'Aanmaken' }}
        </button>
      </div>
    </div>
  </div>
</template>
