<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { AlertTriangle, Info } from 'lucide-vue-next'
import { theme } from '@/theme'

type Variant = 'danger' | 'primary' | 'accent'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmLabel?: string
    cancelLabel?: string
    variant?: Variant
    requireConfirmCheck?: boolean
    requirePassword?: boolean
    error?: string
    loading?: boolean
  }>(),
  {
    confirmLabel: 'Bevestigen',
    cancelLabel: 'Annuleren',
    variant: 'danger',
    requireConfirmCheck: false,
    requirePassword: false,
    error: '',
    loading: false,
  },
)

const emit = defineEmits<{
  confirm: [password: string]
  cancel: []
}>()

const confirmed = ref(false)
const password = ref('')

// Reset state when modal closes
watch(() => props.open, (isOpen) => {
  if (!isOpen) {
    confirmed.value = false
    password.value = ''
  }
})

const canConfirm = computed(() => {
  if (props.loading) return false
  if (props.requireConfirmCheck && !confirmed.value) return false
  if (props.requirePassword && !password.value) return false
  return true
})

function handleConfirm() {
  if (!canConfirm.value) return
  emit('confirm', password.value)
}

const iconClasses: Record<Variant, string> = {
  danger: 'bg-red-50 text-red-500',
  primary: 'bg-primary-50 text-primary-500',
  accent: 'bg-accent-50 text-accent-500',
}

const confirmBtnClasses: Record<Variant, string> = {
  danger: theme.btn.dangerFill,
  primary: theme.btn.primary,
  accent: theme.btn.secondary,
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
        @click.self="emit('cancel')"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-navy-900/40 pointer-events-none" />

        <!-- Modal -->
        <div
          class="relative z-10 bg-white rounded-xl shadow-xl border border-navy-100 w-full max-w-md p-6"
          @click.stop
        >
          <div class="flex gap-4">
            <!-- Icon -->
            <div
              :class="[
                'flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center',
                iconClasses[variant],
              ]"
            >
              <AlertTriangle v-if="variant === 'danger'" :size="20" />
              <Info v-else :size="20" />
            </div>

            <!-- Content -->
            <div class="flex-1 min-w-0">
              <h3 :class="theme.text.h3">{{ title }}</h3>
              <p class="mt-2 text-sm text-body leading-relaxed">{{ message }}</p>
            </div>
          </div>

          <!-- Confirm checkbox -->
          <div v-if="requireConfirmCheck" class="mt-4">
            <label class="flex items-start gap-2 cursor-pointer select-none">
              <input
                v-model="confirmed"
                type="checkbox"
                class="mt-0.5 rounded border-navy-300 text-red-600 focus:ring-red-500"
              />
              <span class="text-sm text-navy-700">
                Ik begrijp dat deze actie onherstelbaar is
              </span>
            </label>
          </div>

          <!-- Password field -->
          <div v-if="requirePassword" class="mt-4">
            <label :class="theme.form.label">
              Bevestig met uw wachtwoord
            </label>
            <input
              v-model="password"
              type="password"
              :disabled="requireConfirmCheck && !confirmed"
              placeholder="Wachtwoord"
              :class="[
                theme.form.input,
                requireConfirmCheck && !confirmed ? 'opacity-50 cursor-not-allowed' : '',
                error ? 'border-red-500 focus:ring-red-500' : '',
              ]"
              @keyup.enter="handleConfirm"
            />
          </div>

          <!-- Error message -->
          <p v-if="error" class="mt-3 text-sm text-red-600 font-medium">
            {{ error }}
          </p>

          <!-- Actions -->
          <div class="flex justify-end gap-3 mt-6">
            <button
              type="button"
              :class="theme.btn.ghost"
              @click="emit('cancel')"
            >
              {{ cancelLabel }}
            </button>
            <button
              type="button"
              :disabled="!canConfirm"
              :class="[
                'px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm',
                canConfirm ? confirmBtnClasses[variant] : 'bg-navy-200 text-navy-400 cursor-not-allowed',
              ]"
              @click="handleConfirm"
            >
              {{ confirmLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
