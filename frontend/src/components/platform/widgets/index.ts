export { default as StatCard } from './StatCard.vue'
export { default as PulseBar } from './PulseBar.vue'
export { default as ActivityFeed } from './ActivityFeed.vue'
export { default as FinanceSnapshot } from './FinanceSnapshot.vue'

export interface PulseItem {
  severity: 'error' | 'warning' | 'ok'
  message: string
  to?: string
}
