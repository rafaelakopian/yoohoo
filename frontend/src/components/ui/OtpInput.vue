<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { theme } from '@/theme'

const props = withDefaults(defineProps<{
  length?: number
  modelValue: string
  autofocus?: boolean
}>(), {
  length: 6,
  autofocus: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  submit: []
}>()

const digits = ref<string[]>(Array(props.length).fill(''))
const inputRefs = ref<(HTMLInputElement | null)[]>([])

// Sync external modelValue → digits
watch(() => props.modelValue, (val) => {
  const chars = val.split('')
  for (let i = 0; i < props.length; i++) {
    digits.value[i] = chars[i] ?? ''
  }
}, { immediate: true })

function emitValue() {
  emit('update:modelValue', digits.value.join(''))
}

function focusIndex(i: number) {
  nextTick(() => {
    inputRefs.value[i]?.focus()
    inputRefs.value[i]?.select()
  })
}

function handleInput(index: number, event: Event) {
  const el = event.target as HTMLInputElement
  const val = el.value.replace(/\D/g, '')

  if (val.length === 0) {
    digits.value[index] = ''
    emitValue()
    return
  }

  // Take only the last typed digit
  digits.value[index] = val.slice(-1)
  emitValue()

  // Auto-advance
  if (index < props.length - 1) {
    focusIndex(index + 1)
  } else {
    // Last digit filled → auto-submit
    nextTick(() => {
      if (digits.value.every(d => d !== '')) {
        emit('submit')
      }
    })
  }
}

function handleKeydown(index: number, event: KeyboardEvent) {
  if (event.key === 'Backspace') {
    if (digits.value[index] === '' && index > 0) {
      // Empty field + backspace → go back
      event.preventDefault()
      digits.value[index - 1] = ''
      emitValue()
      focusIndex(index - 1)
    } else {
      // Clear current
      digits.value[index] = ''
      emitValue()
    }
  } else if (event.key === 'ArrowLeft' && index > 0) {
    event.preventDefault()
    focusIndex(index - 1)
  } else if (event.key === 'ArrowRight' && index < props.length - 1) {
    event.preventDefault()
    focusIndex(index + 1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    if (digits.value.every(d => d !== '')) {
      emit('submit')
    }
  }
}

function handlePaste(event: ClipboardEvent) {
  event.preventDefault()
  const pasted = (event.clipboardData?.getData('text') ?? '').replace(/\D/g, '').slice(0, props.length)
  if (!pasted) return

  for (let i = 0; i < props.length; i++) {
    digits.value[i] = pasted[i] ?? ''
  }
  emitValue()

  // Focus last filled or last field
  const lastIndex = Math.min(pasted.length, props.length) - 1
  focusIndex(lastIndex)

  if (pasted.length >= props.length) {
    nextTick(() => emit('submit'))
  }
}

function setRef(el: unknown, i: number) {
  inputRefs.value[i] = el as HTMLInputElement | null
}
</script>

<template>
  <div class="flex justify-center gap-2" @paste="handlePaste">
    <input
      v-for="(_, i) in length"
      :key="i"
      :ref="(el) => setRef(el, i)"
      type="text"
      inputmode="numeric"
      maxlength="1"
      :value="digits[i]"
      :autofocus="autofocus && i === 0"
      :class="theme.form.input"
      class="w-11 h-13 text-center text-xl font-semibold tracking-normal !px-0"
      autocomplete="one-time-code"
      @input="handleInput(i, $event)"
      @keydown="handleKeydown(i, $event)"
    />
  </div>
</template>
