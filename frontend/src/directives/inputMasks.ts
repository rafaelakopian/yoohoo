/**
 * Vue custom directives for input masking.
 *
 * These directives filter keystrokes in real-time so invalid characters
 * never reach the v-model. They work alongside v-model — no conflicts.
 *
 * Usage:
 *   <input v-model="phone" v-mask-phone />
 *   <input v-model="name"  v-mask-name />
 *   <input v-model="slug"  v-mask-slug />
 *
 * Register globally in main.ts:
 *   import { maskPhone, maskName, maskSlug } from '@/directives/inputMasks'
 *   app.directive('mask-phone', maskPhone)
 *   app.directive('mask-name', maskName)
 *   app.directive('mask-slug', maskSlug)
 */

import type { Directive } from 'vue'
import { sanitizePhone, sanitizeName, sanitizeSlug } from '@/utils/validators'

function createMaskDirective(sanitizer: (value: string) => string): Directive {
  return {
    mounted(el: HTMLElement) {
      const input = el.tagName === 'INPUT' ? el as HTMLInputElement : el.querySelector('input')
      if (!input) return

      const handler = () => {
        const cleaned = sanitizer(input.value)
        if (cleaned !== input.value) {
          const cursorPos = input.selectionStart ?? cleaned.length
          input.value = cleaned
          input.dispatchEvent(new Event('input', { bubbles: true }))
          // Restore cursor position (adjusted for removed chars)
          const diff = input.value.length - cleaned.length
          input.setSelectionRange(cursorPos + diff, cursorPos + diff)
        }
      }

      input.addEventListener('input', handler)
      ;(input as any).__maskCleanup = () => input.removeEventListener('input', handler)
    },
    unmounted(el: HTMLElement) {
      const input = el.tagName === 'INPUT' ? el as HTMLInputElement : el.querySelector('input')
      if (input && (input as any).__maskCleanup) {
        (input as any).__maskCleanup()
      }
    },
  }
}

export const maskPhone = createMaskDirective(sanitizePhone)
export const maskName = createMaskDirective(sanitizeName)
export const maskSlug = createMaskDirective(sanitizeSlug)
