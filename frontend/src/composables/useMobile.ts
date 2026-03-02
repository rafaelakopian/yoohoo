import { ref, onMounted, onUnmounted } from 'vue'

export function useMobile(breakpoint = 768) {
  const isMobile = ref(false)
  let mq: MediaQueryList

  function update(e: MediaQueryListEvent | MediaQueryList) {
    isMobile.value = !e.matches
  }

  onMounted(() => {
    mq = window.matchMedia(`(min-width: ${breakpoint}px)`)
    isMobile.value = !mq.matches
    mq.addEventListener('change', update)
  })

  onUnmounted(() => {
    mq?.removeEventListener('change', update)
  })

  return { isMobile }
}
