import { ref } from 'vue'
import { permissionsApi } from '@/api/products/school/permissions'
import type { ModulePermissions } from '@/types/auth'

const registry = ref<ModulePermissions[]>([])
const loaded = ref(false)
let _loadPromise: Promise<void> | null = null

export function usePermissionRegistry() {
  async function load() {
    if (loaded.value) return
    if (_loadPromise) return _loadPromise

    _loadPromise = (async () => {
      try {
        const data = await permissionsApi.getRegistry()
        registry.value = data.modules
        loaded.value = true
      } catch {
        // non-critical — views remain functional without registry
      } finally {
        _loadPromise = null
      }
    })()

    return _loadPromise
  }

  return { registry, loaded, load }
}
