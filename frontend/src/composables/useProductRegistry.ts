import { ref, onMounted } from 'vue'
import { getProductRegistry, type NavigationItemResponse } from '@/api/platform/products'

const navigation = ref<NavigationItemResponse[]>([])
const loaded = ref(false)
let _loadPromise: Promise<void> | null = null

export function useProductRegistry() {
  async function load() {
    if (loaded.value) return
    if (_loadPromise) return _loadPromise

    _loadPromise = (async () => {
      try {
        const data = await getProductRegistry()
        navigation.value = data.navigation
        loaded.value = true
      } catch {
        // Fallback: empty navigation — sidebar stays functional
      } finally {
        _loadPromise = null
      }
    })()

    return _loadPromise
  }

  onMounted(load)

  return { navigation, loaded, load }
}
