<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Info } from 'lucide-vue-next'
import { theme } from '@/theme'
import { impersonateUser } from '@/api/platform/operations'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  open: boolean
  userId: string
  userName: string
  userEmail: string
  memberships?: { tenant_id: string; tenant_name: string }[]
}>()

const emit = defineEmits<{
  close: []
}>()

const authStore = useAuthStore()
const reason = ref('')
const selectedTenantId = ref('')
const loading = ref(false)
const error = ref('')

watch(() => props.open, (val) => {
  if (val) {
    reason.value = ''
    error.value = ''
    selectedTenantId.value = props.memberships?.[0]?.tenant_id ?? ''
  }
})

const canConfirm = computed(() => !loading.value && reason.value.length >= 5)

async function handleConfirm() {
  if (!canConfirm.value) return
  loading.value = true
  error.value = ''
  try {
    const response = await impersonateUser({
      user_id: props.userId,
      reason: reason.value,
      tenant_id: selectedTenantId.value || undefined,
    })
    emit('close')
    await authStore.startImpersonation(response)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Er is een fout opgetreden'
  } finally {
    loading.value = false
  }
}
</script>

<template>
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
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center px-4"
        @click.self="emit('close')"
      >
        <div class="absolute inset-0 bg-navy-900/40 pointer-events-none" />

        <div
          class="relative z-10 bg-white rounded-xl shadow-xl border border-navy-100 w-full max-w-md p-6"
          @click.stop
        >
          <div class="flex gap-4">
            <div class="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center bg-accent-50 text-accent-500">
              <Info :size="20" />
            </div>
            <div class="flex-1 min-w-0">
              <h3 :class="theme.text.h3">Inloggen als gebruiker</h3>
              <p class="mt-2 text-sm text-body leading-relaxed">
                Je gaat inloggen als <strong>{{ userName }}</strong>
                ({{ userEmail }}). Alle acties worden gelogd.
              </p>
            </div>
          </div>

          <div class="mt-4 space-y-3">
            <div>
              <label :class="theme.form.label">Reden *</label>
              <textarea
                v-model="reason"
                :class="theme.form.input"
                rows="2"
                placeholder="Waarom log je in als deze gebruiker? (min. 5 tekens)"
              />
            </div>

            <div v-if="memberships && memberships.length > 1">
              <label :class="theme.form.label">Organisatie</label>
              <select v-model="selectedTenantId" :class="theme.form.input">
                <option v-for="m in memberships" :key="m.tenant_id" :value="m.tenant_id">
                  {{ m.tenant_name }}
                </option>
              </select>
            </div>
          </div>

          <p v-if="error" class="mt-3 text-sm text-red-600 font-medium">{{ error }}</p>

          <div class="flex justify-end gap-3 mt-6">
            <button type="button" :class="theme.btn.ghost" @click="emit('close')">
              Annuleren
            </button>
            <button
              type="button"
              :disabled="!canConfirm"
              :class="[
                'px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm',
                canConfirm ? theme.btn.secondary : 'bg-navy-200 text-navy-400 cursor-not-allowed',
              ]"
              @click="handleConfirm"
            >
              Inloggen als {{ userName }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
