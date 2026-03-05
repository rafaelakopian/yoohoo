<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Copy, Check, ChevronDown } from 'lucide-vue-next'
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
  if (!d) return '—'
  return new Date(d).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

function formatDateTime(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleString('nl-NL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
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
</script>

<template>
  <div>
    <!-- Back button -->
    <button :class="[theme.btn.ghost, 'mb-4']" @click="router.push({ name: 'ops-dashboard' })">
      <ArrowLeft :size="16" class="mr-1" /> Terug naar overzicht
    </button>

    <div v-if="loading" class="text-center py-8">
      <p :class="theme.text.muted">Laden...</p>
    </div>

    <div v-else-if="error" :class="theme.alert.error">{{ error }}</div>

    <template v-else-if="tenant">
      <!-- Tenant header -->
      <div :class="[theme.card.padded, 'mb-6']">
        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h2 :class="theme.text.h2">{{ tenant.name }}</h2>
            <div class="flex items-center gap-3 mt-1">
              <span :class="theme.text.muted">{{ tenant.slug }}</span>
              <button
                class="text-xs text-body hover:text-navy-700"
                title="Kopieer slug"
                @click="copyToClipboard(tenant.slug, 'slug')"
              >
                <component :is="copiedField === 'slug' ? Check : Copy" :size="14" />
              </button>
              <button
                class="text-xs text-body hover:text-navy-700"
                title="Kopieer tenant ID"
                @click="copyToClipboard(tenant.id, 'id')"
              >
                ID <component :is="copiedField === 'id' ? Check : Copy" :size="14" />
              </button>
            </div>
          </div>
          <div class="flex gap-2">
            <span
              :class="[
                theme.badge.base,
                tenant.is_active ? theme.badge.success : theme.badge.error,
              ]"
            >
              {{ tenant.is_active ? 'Actief' : 'Inactief' }}
            </span>
            <span
              :class="[
                theme.badge.base,
                tenant.is_provisioned ? theme.badge.info : theme.badge.warning,
              ]"
            >
              {{ tenant.is_provisioned ? 'Ingericht' : 'Niet ingericht' }}
            </span>
          </div>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 text-sm">
          <div>
            <p :class="theme.text.muted">Eigenaar</p>
            <p :class="theme.text.body">{{ tenant.owner_name ?? '—' }}</p>
          </div>
          <div>
            <p :class="theme.text.muted">Aangemaakt</p>
            <p :class="theme.text.body">{{ formatDate(tenant.created_at) }}</p>
          </div>
          <div v-if="tenant.settings">
            <p :class="theme.text.muted">E-mail</p>
            <p :class="theme.text.body">{{ tenant.settings.org_email ?? '—' }}</p>
          </div>
          <div v-if="tenant.settings">
            <p :class="theme.text.muted">Telefoon</p>
            <p :class="theme.text.body">{{ tenant.settings.org_phone ?? '—' }}</p>
          </div>
        </div>
      </div>

      <!-- Metrics -->
      <div v-if="tenant.metrics_available" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div :class="theme.card.padded">
          <p :class="theme.text.muted">Leerlingen</p>
          <p :class="theme.text.h3">{{ tenant.active_student_count }}</p>
          <p class="text-xs" :class="theme.text.muted">{{ tenant.student_count }} totaal</p>
        </div>
        <div :class="theme.card.padded">
          <p :class="theme.text.muted">Docenten</p>
          <p :class="theme.text.h3">{{ tenant.teacher_count }}</p>
        </div>
        <div :class="theme.card.padded">
          <p :class="theme.text.muted">Lesslots</p>
          <p :class="theme.text.h3">{{ tenant.lesson_slot_count }}</p>
        </div>
        <div :class="theme.card.padded">
          <p :class="theme.text.muted">Aanwezigheid (30d)</p>
          <p :class="theme.text.h3">{{ attendanceRate !== null ? `${attendanceRate}%` : '—' }}</p>
          <p class="text-xs" :class="theme.text.muted">
            {{ tenant.attendance_present_count }}/{{ tenant.attendance_total_count }}
          </p>
        </div>
      </div>

      <!-- Invoice stats -->
      <div v-if="tenant.metrics_available && tenant.invoice_stats" :class="[theme.card.padded, 'mb-6']">
        <h3 :class="[theme.text.h4, 'mb-3']">Facturatie</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p :class="theme.text.muted">Verstuurd</p>
            <p :class="theme.text.body">{{ tenant.invoice_stats.sent_count }}</p>
          </div>
          <div>
            <p :class="theme.text.muted">Betaald</p>
            <p :class="theme.text.body">{{ tenant.invoice_stats.paid_count }}</p>
          </div>
          <div>
            <p :class="theme.text.muted">Achterstallig</p>
            <p :class="theme.text.body">{{ tenant.invoice_stats.overdue_count }}</p>
          </div>
          <div>
            <p :class="theme.text.muted">Openstaand</p>
            <p :class="theme.text.body">{{ formatCents(tenant.invoice_stats.total_outstanding_cents) }}</p>
          </div>
        </div>
      </div>

      <div v-if="!tenant.metrics_available && tenant.is_provisioned" :class="[theme.alert.errorInline, 'mb-6']">
        Productmetrics konden niet worden opgehaald voor deze organisatie.
      </div>

      <!-- Members -->
      <div :class="[theme.card.base, 'mb-6']">
        <h3 :class="[theme.text.h4, 'p-4']">Leden ({{ tenant.members.length }})</h3>
        <table class="w-full text-sm">
          <thead>
            <tr :class="theme.list.sectionHeader">
              <th class="text-left p-3">Naam</th>
              <th class="text-left p-3 hidden md:table-cell">E-mail</th>
              <th class="text-left p-3 hidden md:table-cell">Groepen</th>
              <th class="text-left p-3 hidden lg:table-cell">Laatst ingelogd</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="m in tenant.members" :key="m.user_id">
              <tr
                :class="theme.list.item"
                class="cursor-pointer hover:bg-surface/50"
                @click="toggleMemberExpand(m.user_id)"
              >
                <td class="p-3">
                  <span :class="theme.text.body">{{ m.full_name }}</span>
                  <span v-if="!m.is_active" :class="[theme.badge.base, theme.badge.error, 'ml-2']">Inactief</span>
                </td>
                <td class="p-3 hidden md:table-cell" :class="theme.text.muted">{{ m.email }}</td>
                <td class="p-3 hidden md:table-cell">
                  <span
                    v-for="g in m.groups" :key="g"
                    :class="[theme.badge.base, theme.badge.default, 'mr-1']"
                  >{{ g }}</span>
                  <span v-if="m.groups.length === 0" :class="theme.text.muted">—</span>
                </td>
                <td class="p-3 hidden lg:table-cell">
                  <div class="flex items-center justify-end gap-2" :class="theme.text.muted">
                    {{ formatDateTime(m.last_login_at) }}
                    <ChevronDown
                      :size="14"
                      class="transition-transform"
                      :class="expandedMemberId === m.user_id ? 'rotate-180' : ''"
                    />
                  </div>
                </td>
              </tr>
              <!-- Expandable detail row -->
              <tr v-if="expandedMemberId === m.user_id">
                <td colspan="4" class="p-0">
                  <div class="bg-surface p-4">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                      <div class="flex flex-col gap-2">
                        <button
                          :class="theme.btn.ghost"
                          @click="router.push({ name: 'platform-user-detail', params: { userId: m.user_id } })"
                        >
                          Bekijk volledig profiel
                        </button>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Support Notes -->
      <SupportNotes
        target-type="tenant"
        :target-id="tenantId"
        class="mb-6"
      />

      <!-- Customer Timeline -->
      <CustomerTimeline :tenant-id="tenantId" :members="tenantMembers" />
    </template>
  </div>
</template>
