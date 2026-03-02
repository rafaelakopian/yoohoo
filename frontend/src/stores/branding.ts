import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { fetchBranding } from '@/api/platform/branding'

export type ThemeId = 'default' | 'yoohoo' | 'pastel' | 'violet'

export interface ThemeConfig {
  id: ThemeId
  label: string
  logo?: string
}

export const AVAILABLE_THEMES: ThemeConfig[] = [
  { id: 'default', label: 'Yoohoo', logo: '/logos/yoohoo.svg' },
  { id: 'yoohoo', label: 'Yoohoo', logo: '/logos/yoohoo.svg' },
  { id: 'pastel', label: 'Pastel', logo: '/logos/yoohoo.svg' },
  { id: 'violet', label: 'Violet Glow', logo: '/logos/yoohoo.svg' },
]

export const useBrandingStore = defineStore('branding', () => {
  const platformName = ref('Yoohoo')
  const platformNameShort = ref('Yoohoo')
  const platformUrl = ref('')
  const loaded = ref(false)

  // Theme switching
  const currentTheme = ref<ThemeId>(
    (localStorage.getItem('app_theme') as ThemeId) || 'default'
  )

  function setTheme(themeId: ThemeId) {
    currentTheme.value = themeId
    localStorage.setItem('app_theme', themeId)
  }

  // Apply data-theme attribute reactively
  watch(currentTheme, (theme) => {
    if (theme === 'default') {
      document.documentElement.removeAttribute('data-theme')
    } else {
      document.documentElement.setAttribute('data-theme', theme)
    }
  }, { immediate: true })

  async function load() {
    if (loaded.value) return
    try {
      const data = await fetchBranding()
      platformName.value = data.platform_name
      platformNameShort.value = data.platform_name_short
      platformUrl.value = data.platform_url
    } catch {
      // Fallback values if endpoint unreachable
      platformName.value = 'Yoohoo'
      platformNameShort.value = 'Yoohoo'
    }
    loaded.value = true
  }

  const currentLogo = computed(() => {
    const theme = AVAILABLE_THEMES.find(t => t.id === currentTheme.value)
    return theme?.logo ?? null
  })

  return { platformName, platformNameShort, platformUrl, loaded, load, currentTheme, currentLogo, setTheme }
})
