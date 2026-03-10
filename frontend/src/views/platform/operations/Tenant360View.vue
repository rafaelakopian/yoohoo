<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, Copy, Check, ChevronDown, Building2,
  GraduationCap, Users, CalendarDays, ClipboardCheck,
  Receipt, Send, AlertTriangle, CheckCircle2, Circle,
  UserRound, Shield, Clock, BadgeCheck, Badge,
} from 'lucide-vue-next'
import { theme } from '@/theme'
import {
  getTenant360,
  type Tenant360Detail,
} from '@/api/platform/operations'
import SupportNotes from '@/components/operations/SupportNotes.vue'
import QuickActions from '@/components/operations/QuickActions.vue'
import CustomerTimeline from '@/components/operations/CustomerTimeline.vue'

const route = useRoute()
const router = useRouter()
const tenant = ref<Tenant360Detail | null>(null)
const loading = ref(true)
const error = ref('')
const copiedField = ref('')
const expandedMemberId = ref<string | null>(null)

const tenantId = route.params.tenantId as string

onMounted(async () => {
  try {
    tenant.value = await getTenant360(tenantId)
  } catch (e: any) {
    error.value = e?.response?.status === 404 ? 'Organisatie niet gevonden' : 'Kon gegevens niet laden'
  } finally {
    loading.value = false
  }
})

const attendanceRate = computed(() => {
  if (!tenant.value || !tenant.value.metrics_available) return null
  const { attendance_total_count, attendance_present_count } = tenant.value
  if (attendance_total_count === 0) return null
  return Math.round((attendance_present_count / attendance_total_count) * 100)
})

function formatDate(d: string | null) {
  if (!d) return '\u2014'
  return new Date(d).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

function formatDateTime(d: string | null) {
  if (!d) return '\u2014'
  return new Date(d).toLocaleString('nl-NL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function timeAgo(d: string | null) {
  if (!d) return ''
  const diff = Date.now() - new Date(d).getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'vandaag'
  if (days === 1) return 'gisteren'
  if (days < 30) return `${days} dagen geleden`
  const months = Math.floor(days / 30)
  return months === 1 ? '1 maand geleden' : `${months} maanden geleden`
}

function formatCents(cents: number) {
  return new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' }).format(cents / 100)
}

async function copyToClipboard(text: string, field: string) {
  await navigator.clipboard.writeText(text)
  copiedField.value = field
  setTimeout(() => { copiedField.value = '' }, 1500)
}

function toggleMemberExpand(userId: string) {
  expandedMemberId.value = expandedMemberId.value === userId ? null : userId
}

async function reloadTenant() {
  try {
    tenant.value = await getTenant360(tenantId)
  } catch { /* ignore */ }
}

const tenantMembers = computed(() => tenant.value?.members ?? [])

function attendanceRingColor(rate: number | null): string {
  if (rate === null) return 'stroke-navy-200'
  if (rate >= 90) return 'stroke-green-500'
  if (rate >= 70) return 'stroke-accent-700'
  if (rate >= 50) return 'stroke-yellow-500'
  return 'stroke-red-400'
}

// Status badge
const expandedStatusBadge = ref(false)
const statusBadgeRef = ref<HTMLElement | null>(null)

function handleClickOutsideBadge(e: MouseEvent) {
  if (expandedStatusBadge.value && statusBadgeRef.value && !statusBadgeRef.value.contains(e.target as Node)) {
    expandedStatusBadge.value = false
  }
}

onMounted(() => { document.addEventListener('click', handleClickOutsideBadge) })
onUnmounted(() => { document.removeEventListener('click', handleClickOutsideBadge) })

const statusBadgeInfo = computed(() => {
  if (!tenant.value) return { icon: Badge, color: 'bg-navy-50 text-navy-600', label: '' }
  const { is_active, is_provisioned } = tenant.value
  if (is_active && is_provisioned) {
    return { icon: BadgeCheck, color: 'bg-green-50 text-green-700', label: 'Actief & ingericht' }
  }
  if (is_active && !is_provisioned) {
    return { icon: BadgeCheck, color: 'bg-yellow-50 text-yellow-700', label: 'Actief · nog niet ingericht' }
  }
  // Inactive
  return { icon: Badge, color: 'bg-navy-50 text-navy-400', label: is_provisioned ? 'Inactief · ingericht' : 'Inactief · niet ingericht' }
})

// Skeleton helpers
const skeletonCards = Array.from({ length: 4 }, (_, i) => i)
const skeletonRows = Array.from({ length: 3 }, (_, i) => i)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-start gap-3">
      <button
        class="w-9 h-9 rounded-lg border border-navy-200 flex items-center justify-center text-navy-500 hover:bg-navy-50 hover:text-navy-700 transition-colors shrink-0 mt-0.5"
        title="Terug naar organisaties"
        @click="router.push({ name: 'platform-orgs' })"
      >
        <ArrowLeft :size="18" />
      </button>
      <template v-if="!loading && tenant">
        <div class="min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <h2 class="text-xl md:text-2xl font-bold text-navy-900 break-words">{{ tenant.name }}</h2>
            <button
              ref="statusBadgeRef"
              @click.stop="expandedStatusBadge = !expandedStatusBadge"
              class="status-badge inline-flex items-center rounded-full cursor-pointer h-6 gap-0 pl-1 pr-1 shrink-0"
              :class="statusBadgeInfo.color"
              :data-expanded="expandedStatusBadge || undefined"
              :title="expandedStatusBadge ? '' : statusBadgeInfo.label"
            >
              <component
                :is="statusBadgeInfo.icon"
                :size="16"
                class="shrink-0 status-badge-icon"
              />
              <span
                class="status-badge-label text-[11px] font-medium whitespace-nowrap"
              >{{ statusBadgeInfo.label }}</span>
            </button>
          </div>
          <div class="flex items-center gap-2 mt-0.5 flex-wrap">
            <span :class="theme.text.muted" class="text-xs md:text-sm font-mono truncate max-w-[160px] md:max-w-none">{{ tenant.slug }}</span>
            <button
              class="p-0.5 rounded hover:bg-navy-100 transition-colors shrink-0"
              :class="copiedField === 'slug' ? 'text-green-500' : 'text-navy-300'"
              title="Kopieer slug"
              @click.stop="copyToClipboard(tenant.slug, 'slug')"
            >
              <component :is="copiedField === 'slug' ? Check : Copy" :size="13" />
            </button>
            <span class="text-navy-200">|</span>
            <button
              class="inline-flex items-center gap-0.5 p-0.5 rounded hover:bg-navy-100 transition-colors text-xs shrink-0"
              :class="copiedField === 'id' ? 'text-green-500' : 'text-navy-300'"
              title="Kopieer tenant ID"
              @click.stop="copyToClipboard(tenant.id, 'id')"
            >
              ID <component :is="copiedField === 'id' ? Check : Copy" :size="13" />
            </button>
          </div>
        </div>
      </template>
    </div>

    <!-- Error -->
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <!-- ──── Loading Skeleton ──── -->
    <template v-if="loading">
      <!-- Info card skeleton -->
      <div :class="theme.card.padded">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div v-for="i in 4" :key="i" class="space-y-1">
            <div class="h-3 w-16 bg-navy-100 rounded animate-pulse" />
            <div class="h-4 w-28 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </div>

      <!-- Stats skeleton -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div v-for="i in skeletonCards" :key="i" :class="theme.stat.card" class="skeleton-card" :style="{ animationDelay: i * 80 + 'ms' }">
          <div :class="theme.stat.iconWrap" class="bg-navy-50">
            <div class="w-5 h-5 rounded bg-navy-100 animate-pulse" />
          </div>
          <div class="flex-1 space-y-1.5">
            <div class="h-7 w-10 bg-navy-100 rounded animate-pulse" />
            <div class="h-3.5 w-20 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </div>

      <!-- Members skeleton -->
      <div class="overflow-hidden rounded-xl border border-navy-100">
        <div class="bg-surface px-4 h-[46px] flex items-center">
          <div class="h-4 w-24 bg-navy-100 rounded animate-pulse" />
        </div>
        <div class="bg-white divide-y divide-navy-50">
          <div v-for="n in skeletonRows" :key="n" class="flex items-center gap-4 px-4 py-4 skeleton-row-enter" :style="{ animationDelay: n * 60 + 'ms' }">
            <div class="w-8 h-8 rounded-full bg-navy-100 animate-pulse shrink-0" />
            <div class="flex-1 space-y-1">
              <div class="h-4 w-32 bg-navy-100 rounded animate-pulse" />
              <div class="h-3 w-44 bg-navy-100 rounded animate-pulse" />
            </div>
            <div class="h-5 w-16 bg-navy-100 rounded-full animate-pulse hidden md:block" />
          </div>
        </div>
      </div>
    </template>

    <!-- ──── Loaded Content ──── -->
    <template v-else-if="tenant">
      <!-- ─── Info Card ─── -->
      <div :class="theme.card.padded">
        <!-- Key info grid -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-x-4 md:gap-x-6 gap-y-3">
          <div class="min-w-0">
            <p :class="theme.text.muted" class="text-xs mb-0.5">Eigenaar</p>
            <p class="text-sm font-medium text-navy-900 truncate">{{ tenant.owner_name ?? '\u2014' }}</p>
          </div>
          <div>
            <p :class="theme.text.muted" class="text-xs mb-0.5">Aangemaakt</p>
            <p class="text-sm font-medium text-navy-900">{{ formatDate(tenant.created_at) }}</p>
            <p :class="theme.text.muted" class="text-xs">{{ timeAgo(tenant.created_at) }}</p>
          </div>
          <div v-if="tenant.settings" class="min-w-0">
            <p :class="theme.text.muted" class="text-xs mb-0.5">E-mail</p>
            <p class="text-sm font-medium text-navy-900 truncate">{{ tenant.settings.org_email ?? '\u2014' }}</p>
          </div>
          <div v-if="tenant.settings">
            <p :class="theme.text.muted" class="text-xs mb-0.5">Telefoon</p>
            <p class="text-sm font-medium text-navy-900">{{ tenant.settings.org_phone ?? '\u2014' }}</p>
          </div>
        </div>
      </div>

      <!-- ─── Metrics Cards ─── -->
      <div v-if="tenant.metrics_available" class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <!-- Students -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.accent]">
            <GraduationCap :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ tenant.active_student_count }}</p>
            <p :class="theme.stat.label">Actieve leerlingen</p>
            <p :class="theme.stat.sub">{{ tenant.student_count }} totaal</p>
          </div>
        </div>

        <!-- Teachers -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.primary]">
            <Users :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ tenant.teacher_count }}</p>
            <p :class="theme.stat.label">Docenten</p>
          </div>
        </div>

        <!-- Lesson slots -->
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.green]">
            <CalendarDays :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ tenant.lesson_slot_count }}</p>
            <p :class="theme.stat.label">Lesslots</p>
          </div>
        </div>

        <!-- Attendance -->
        <div :class="theme.stat.card">
          <div class="relative flex items-center justify-center w-[44px] h-[44px] shrink-0">
            <svg class="w-[44px] h-[44px] -rotate-90" viewBox="0 0 44 44">
              <circle cx="22" cy="22" r="18" fill="none" stroke-width="3.5" class="stroke-navy-100" />
              <circle cx="22" cy="22" r="18" fill="none" stroke-width="3.5" stroke-linecap="round"
                :class="attendanceRingColor(attendanceRate)"
                :stroke-dasharray="attendanceRate !== null ? `${attendanceRate * 1.131} 113.1` : '0 113.1'"
              />
            </svg>
            <span class="absolute text-[11px] font-bold text-navy-900">
              {{ attendanceRate !== null ? `${attendanceRate}%` : '\u2014' }}
            </span>
          </div>
          <div>
            <p :class="theme.stat.label" class="!mt-0">Aanwezigheid (30d)</p>
            <p :class="theme.stat.sub">
              {{ tenant.attendance_present_count }}/{{ tenant.attendance_total_count }} registraties
            </p>
          </div>
        </div>
      </div>

      <!-- Metrics unavailable warning -->
      <div v-if="!tenant.metrics_available && tenant.is_provisioned" class="flex items-center gap-2 px-4 py-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-sm">
        <AlertTriangle :size="16" class="shrink-0" />
        Productmetrics konden niet worden opgehaald voor deze organisatie.
      </div>

      <!-- ─── Invoice Stats ─── -->
      <div v-if="tenant.metrics_available && tenant.invoice_stats" :class="theme.card.base" class="overflow-hidden">
        <div class="flex items-center gap-2 px-4 md:px-6 py-3 border-b border-navy-100 bg-surface">
          <Receipt :size="16" class="text-navy-400" />
          <h3 :class="theme.text.h4">Facturatie</h3>
        </div>
        <div class="grid grid-cols-3 md:grid-cols-5 divide-y md:divide-y-0 md:divide-x divide-navy-100">
          <div class="p-3 md:p-5 text-center">
            <p class="text-lg md:text-2xl font-bold text-navy-900">{{ tenant.invoice_stats.sent_count }}</p>
            <p :class="theme.text.muted" class="text-[10px] md:text-xs mt-0.5">Verstuurd</p>
          </div>
          <div class="p-3 md:p-5 text-center">
            <p class="text-lg md:text-2xl font-bold text-green-600">{{ tenant.invoice_stats.paid_count }}</p>
            <p :class="theme.text.muted" class="text-[10px] md:text-xs mt-0.5">Betaald</p>
          </div>
          <div class="p-3 md:p-5 text-center">
            <p class="text-lg md:text-2xl font-bold" :class="tenant.invoice_stats.overdue_count > 0 ? 'text-red-500' : 'text-navy-900'">
              {{ tenant.invoice_stats.overdue_count }}
            </p>
            <p :class="theme.text.muted" class="text-[10px] md:text-xs mt-0.5">Achterstallig</p>
          </div>
          <div class="p-3 md:p-5 text-center">
            <p class="text-lg md:text-2xl font-bold text-accent-700">{{ formatCents(tenant.invoice_stats.total_outstanding_cents) }}</p>
            <p :class="theme.text.muted" class="text-[10px] md:text-xs mt-0.5">Openstaand</p>
          </div>
          <div class="p-3 md:p-5 text-center">
            <p class="text-lg md:text-2xl font-bold text-green-600">{{ formatCents(tenant.invoice_stats.total_paid_cents) }}</p>
            <p :class="theme.text.muted" class="text-[10px] md:text-xs mt-0.5">Totaal betaald</p>
          </div>
        </div>
      </div>

      <!-- ─── Members ─── -->
      <div class="overflow-x-auto rounded-xl border border-navy-100">
        <div class="flex items-center justify-between px-4 md:px-6 py-3 bg-surface border-b border-navy-100">
          <div class="flex items-center gap-2">
            <Users :size="16" class="text-navy-400" />
            <h3 :class="theme.text.h4">Leden</h3>
          </div>
          <span :class="[theme.badge.base, theme.badge.default]">{{ tenant.members.length }}</span>
        </div>

        <table class="w-full text-sm">
          <thead>
            <tr class="bg-white border-b border-navy-100">
              <th class="text-left px-4 py-2.5 font-semibold text-navy-700">Gebruiker</th>
              <th class="text-left px-4 py-2.5 font-semibold text-navy-700 hidden md:table-cell">Groepen</th>
              <th class="text-right px-4 py-2.5 font-semibold text-navy-700 hidden lg:table-cell">Laatst ingelogd</th>
              <th class="w-10 px-2 py-2.5" />
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-navy-50">
            <template v-for="m in tenant.members" :key="m.user_id">
              <tr
                class="hover:bg-surface transition-colors cursor-pointer group"
                @click="toggleMemberExpand(m.user_id)"
              >
                <!-- User info -->
                <td class="px-4 py-3">
                  <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                      :class="m.is_active ? 'bg-accent-50' : 'bg-navy-100'"
                    >
                      <UserRound :size="14" :class="m.is_active ? 'text-accent-700' : 'text-navy-400'" />
                    </div>
                    <div class="min-w-0">
                      <div class="flex items-center gap-1.5">
                        <p class="font-medium text-navy-900 truncate">{{ m.full_name }}</p>
                        <span v-if="m.is_superadmin" :class="[theme.badge.base, theme.badge.warning]" class="text-[10px] !px-1.5 !py-0">SA</span>
                        <span v-if="!m.is_active" :class="[theme.badge.base, theme.badge.error]" class="text-[10px] !px-1.5 !py-0">Inactief</span>
                      </div>
                      <p :class="theme.text.muted" class="text-xs truncate">{{ m.email }}</p>
                    </div>
                  </div>
                </td>

                <!-- Groups -->
                <td class="px-4 py-3 hidden md:table-cell">
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="g in m.groups" :key="g"
                      :class="[theme.badge.base, theme.badge.default]"
                      class="text-[11px]"
                    >{{ g }}</span>
                    <span v-if="m.groups.length === 0" :class="theme.text.muted" class="text-xs">\u2014</span>
                  </div>
                </td>

                <!-- Last login -->
                <td class="px-4 py-3 text-right hidden lg:table-cell">
                  <div class="flex items-center justify-end gap-1.5">
                    <Clock v-if="m.last_login_at" :size="12" class="text-navy-300" />
                    <span :class="theme.text.muted" class="text-xs">{{ formatDateTime(m.last_login_at) }}</span>
                  </div>
                </td>

                <!-- Expand arrow -->
                <td class="px-2 py-3 text-center">
                  <ChevronDown
                    :size="16"
                    class="text-navy-200 group-hover:text-accent-700 transition-all inline-block"
                    :class="expandedMemberId === m.user_id ? 'rotate-180 text-accent-700' : ''"
                  />
                </td>
              </tr>

              <!-- Expanded detail row -->
              <tr v-if="expandedMemberId === m.user_id">
                <td colspan="4" class="p-0">
                  <div class="bg-surface border-t border-navy-100 p-3 md:p-5">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
                      <QuickActions
                        :user="{
                          id: m.user_id,
                          email: m.email,
                          full_name: m.full_name,
                          is_active: m.is_active,
                          email_verified: true,
                          totp_enabled: false,
                          active_sessions: 0,
                        }"
                        @reload="reloadTenant"
                      />
                      <SupportNotes
                        target-type="user"
                        :target-id="m.user_id"
                      />
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <!-- Empty members -->
        <div v-if="tenant.members.length === 0" class="py-8 text-center bg-white">
          <p :class="theme.text.muted">Geen leden gevonden</p>
        </div>
      </div>

      <!-- ─── Bottom sections: Notes + Timeline ─── -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SupportNotes
          target-type="tenant"
          :target-id="tenantId"
        />
        <CustomerTimeline :tenant-id="tenantId" :members="tenantMembers" />
      </div>
    </template>

    <!-- ──── Empty state (no tenant) ──── -->
    <div v-else-if="!error" :class="theme.emptyState.wrapper">
      <div :class="theme.emptyState.iconWrap">
        <Building2 :class="theme.emptyState.icon" :size="24" />
      </div>
      <p :class="theme.emptyState.title">Organisatie niet gevonden</p>
      <p :class="theme.emptyState.description">De opgegeven organisatie kon niet worden geladen.</p>
    </div>
  </div>
</template>

<style scoped>
@keyframes skeletonFadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.skeleton-card,
.skeleton-row-enter {
  opacity: 0;
  animation: skeletonFadeIn 0.3s ease forwards;
}

.status-badge {
  transition: gap 300ms ease, padding 300ms ease;
}

.status-badge[data-expanded] {
  gap: 0.375rem;
  padding-right: 0.75rem;
}

.status-badge-icon {
  transition: transform 300ms ease;
}

.status-badge[data-expanded] .status-badge-icon {
  transform: translateX(2px);
}

.status-badge-label {
  max-width: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-width 300ms ease, opacity 200ms ease;
}

.status-badge[data-expanded] .status-badge-label {
  max-width: 200px;
  opacity: 1;
}
</style>
