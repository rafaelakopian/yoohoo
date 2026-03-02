/**
 * Centralized route prefix constants.
 *
 * Change a prefix here → every URL in the app updates automatically.
 */

import { useTenantStore } from '@/stores/tenant'

// Route prefixes
export const AUTH = '/auth'
export const PLATFORM = '/platform'
export const ORG = '/org'
export const WELCOME = '/welcome'

/**
 * Build an org-scoped path using the currently selected tenant slug.
 *
 * Usage (inside Vue component setup/computed):
 *   orgPath('dashboard')  → '/org/muziekschool/dashboard'
 *   orgPath('students')   → '/org/muziekschool/students'
 */
export function orgPath(subPath: string): string {
  const tenantStore = useTenantStore()
  const slug = tenantStore.currentTenant?.slug ?? ''
  return `${ORG}/${slug}/${subPath}`
}
