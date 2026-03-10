<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Plus, Send, Trash2, Megaphone, AlertTriangle, Info,
  AlertCircle, Eye, Clock, Users, X, ChevronDown,
} from 'lucide-vue-next'
import { theme } from '@/theme'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import IconButton from '@/components/ui/IconButton.vue'
import {
  platformNotifAdminApi,
  type PlatformNotificationItem,
  type NotificationTypeInfo,
  type CreateNotificationData,
} from '@/api/platform/notifications'

const notifications = ref<PlatformNotificationItem[]>([])
const types = ref<NotificationTypeInfo[]>([])
const loading = ref(true)
const total = ref(0)
const error = ref('')
const success = ref('')

// Create form
const showCreate = ref(false)
const creating = ref(false)
const form = ref<CreateNotificationData>({
  notification_type: '',
  title: '',
  message: '',
  severity: 'info',
  target_scope: 'all',
})

// Confirm modals
const publishTarget = ref<PlatformNotificationItem | null>(null)
const deleteTarget = ref<PlatformNotificationItem | null>(null)

// Expanded detail
const expandedId = ref<string | null>(null)

// Summary stats
const draftCount = computed(() => notifications.value.filter(n => !n.is_published).length)
const publishedCount = computed(() => notifications.value.filter(n => n.is_published).length)
const totalRecipients = computed(() => notifications.value.reduce((s, n) => s + n.recipient_count, 0))

onMounted(async () => {
  await Promise.all([loadNotifications(), loadTypes()])
})

async function loadNotifications() {
  loading.value = true
  try {
    const result = await platformNotifAdminApi.list()
    notifications.value = result.items
    total.value = result.total
  } catch {
    error.value = 'Kon meldingen niet laden'
  } finally {
    loading.value = false
  }
}

async function loadTypes() {
  try {
    types.value = await platformNotifAdminApi.listTypes()
    if (types.value.length > 0 && !form.value.notification_type) {
      form.value.notification_type = types.value[0].code
    }
  } catch { /* silent */ }
}

async function handleCreate() {
  creating.value = true
  error.value = ''
  try {
    await platformNotifAdminApi.create(form.value)
    showCreate.value = false
    form.value = { notification_type: types.value[0]?.code || '', title: '', message: '', severity: 'info', target_scope: 'all' }
    flashSuccess('Melding aangemaakt als concept')
    await loadNotifications()
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Kon melding niet aanmaken'
  } finally {
    creating.value = false
  }
}

async function confirmPublish() {
  if (!publishTarget.value) return
  error.value = ''
  try {
    const result = await platformNotifAdminApi.publish(publishTarget.value.id)
    flashSuccess(result.message)
    await loadNotifications()
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Kon melding niet publiceren'
  } finally {
    publishTarget.value = null
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  error.value = ''
  try {
    await platformNotifAdminApi.remove(deleteTarget.value.id)
    flashSuccess('Concept verwijderd')
    await loadNotifications()
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Kon melding niet verwijderen'
  } finally {
    deleteTarget.value = null
  }
}

function flashSuccess(msg: string) {
  success.value = msg
  setTimeout(() => { success.value = '' }, 3000)
}

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('nl-NL', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function timeAgo(d: string): string {
  const diff = Date.now() - new Date(d).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'zojuist'
  if (mins < 60) return `${mins} min geleden`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} uur geleden`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'gisteren'
  if (days < 30) return `${days} dagen geleden`
  return formatDate(d)
}

const severityConfig: Record<string, { icon: object; badge: string; dot: string; label: string }> = {
  critical: { icon: AlertCircle, badge: theme.badge.error, dot: 'bg-red-500', label: 'Kritiek' },
  warning: { icon: AlertTriangle, badge: theme.badge.warning, dot: 'bg-yellow-500', label: 'Waarschuwing' },
  info: { icon: Info, badge: theme.badge.default, dot: 'bg-accent-600', label: 'Info' },
}

const defaultSeverityConfig = { icon: Info, badge: theme.badge.default, dot: 'bg-navy-400', label: 'Info' }

function typeLabel(code: string): string {
  return types.value.find(t => t.code === code)?.label || code
}

// Skeleton
const skeletonRows = Array.from({ length: 4 }, (_, i) => i)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Megaphone class="w-6 h-6 text-navy-700" />
        <h2 :class="theme.text.h2">Platformmeldingen</h2>
      </div>
      <button @click="showCreate = true" :class="theme.btn.addInline">
        <span :class="theme.btn.addInlineIcon"><Plus :size="14" /></span>
        Nieuwe melding
      </button>
    </div>

    <!-- Alerts -->
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="success" :class="theme.alert.success">{{ success }}</div>
    </Transition>
    <div v-if="error" :class="theme.alert.error">{{ error }}</div>

    <!-- ──── Loading Skeleton ──── -->
    <template v-if="loading">
      <!-- Summary skeleton -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div v-for="i in 3" :key="i" :class="theme.stat.card" class="skeleton-card" :style="{ animationDelay: i * 80 + 'ms' }">
          <div :class="theme.stat.iconWrap" class="bg-navy-50">
            <div class="w-5 h-5 rounded bg-navy-100 animate-pulse" />
          </div>
          <div class="flex-1 space-y-1.5">
            <div class="h-7 w-10 bg-navy-100 rounded animate-pulse" />
            <div class="h-3.5 w-20 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </div>

      <!-- List skeleton -->
      <div class="overflow-hidden rounded-xl border border-navy-100">
        <div class="bg-white divide-y divide-navy-50">
          <div v-for="n in skeletonRows" :key="n" class="px-4 md:px-6 py-4 skeleton-row-enter" :style="{ animationDelay: (n + 3) * 60 + 'ms' }">
            <div class="flex items-center gap-2 mb-2">
              <div class="h-5 w-14 bg-navy-100 rounded-full animate-pulse" />
              <div class="h-5 w-24 bg-navy-100 rounded-full animate-pulse" />
              <div class="h-5 w-16 bg-navy-100 rounded-full animate-pulse" />
            </div>
            <div class="h-4 w-3/5 bg-navy-100 rounded animate-pulse mb-1" />
            <div class="h-3 w-1/4 bg-navy-100 rounded animate-pulse" />
          </div>
        </div>
      </div>
    </template>

    <!-- ──── Loaded Content ──── -->
    <template v-else>
      <!-- ─── Summary Cards ─── -->
      <div v-if="notifications.length > 0" class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.default]">
            <Megaphone :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ total }}</p>
            <p :class="theme.stat.label">Totaal</p>
          </div>
        </div>
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, theme.stat.iconVariant.green]">
            <Send :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value" class="!text-green-600">{{ publishedCount }}</p>
            <p :class="theme.stat.label">Gepubliceerd</p>
            <p :class="theme.stat.sub">{{ totalRecipients }} ontvangers totaal</p>
          </div>
        </div>
        <div :class="theme.stat.card">
          <div :class="[theme.stat.iconWrap, draftCount > 0 ? theme.stat.iconVariant.accent : theme.stat.iconVariant.default]">
            <Clock :size="20" />
          </div>
          <div>
            <p :class="theme.stat.value">{{ draftCount }}</p>
            <p :class="theme.stat.label">Concepten</p>
          </div>
        </div>
      </div>

      <!-- ─── Notifications List ─── -->
      <div v-if="notifications.length > 0" class="overflow-hidden rounded-xl border border-navy-100">
        <div class="bg-white divide-y divide-navy-50">
          <template v-for="notif in notifications" :key="notif.id">
            <div
              class="px-4 md:px-6 py-4 hover:bg-surface transition-colors cursor-pointer group"
              @click="toggleExpand(notif.id)"
            >
              <div class="flex items-start justify-between gap-4">
                <div class="flex-1 min-w-0">
                  <!-- Badges -->
                  <div class="flex items-center gap-1.5 flex-wrap mb-2">
                    <span :class="[theme.badge.base, (severityConfig[notif.severity] || defaultSeverityConfig).badge]" class="inline-flex items-center gap-1">
                      <span class="w-1.5 h-1.5 rounded-full" :class="(severityConfig[notif.severity] || defaultSeverityConfig).dot" />
                      {{ (severityConfig[notif.severity] || defaultSeverityConfig).label }}
                    </span>
                    <span :class="[theme.badge.base, theme.badge.default]">
                      {{ typeLabel(notif.notification_type) }}
                    </span>
                    <span v-if="notif.is_published" :class="[theme.badge.base, theme.badge.success]" class="inline-flex items-center gap-1">
                      <Send :size="10" />
                      Gepubliceerd
                    </span>
                    <span v-else :class="[theme.badge.base, theme.badge.warning]" class="inline-flex items-center gap-1">
                      <Clock :size="10" />
                      Concept
                    </span>
                  </div>

                  <!-- Title & meta -->
                  <p class="text-sm font-semibold text-navy-900">{{ notif.title }}</p>
                  <div class="flex items-center gap-2 mt-1">
                    <span :class="theme.text.muted" class="text-xs">
                      {{ timeAgo(notif.published_at || notif.created_at) }}
                    </span>
                    <template v-if="notif.is_published">
                      <span :class="theme.text.muted" class="text-xs">&middot;</span>
                      <span class="flex items-center gap-1 text-xs" :class="theme.text.muted">
                        <Users :size="11" />
                        {{ notif.recipient_count }} ontvangers
                      </span>
                    </template>
                  </div>
                </div>

                <!-- Actions -->
                <div class="flex items-center gap-1.5 shrink-0" @click.stop>
                  <template v-if="!notif.is_published">
                    <IconButton
                      variant="accent"
                      title="Publiceren"
                      @click="publishTarget = notif"
                    >
                      <Send :size="14" />
                    </IconButton>
                    <IconButton
                      variant="danger"
                      title="Verwijderen"
                      @click="deleteTarget = notif"
                    >
                      <Trash2 :size="14" />
                    </IconButton>
                  </template>
                  <ChevronDown
                    :size="16"
                    class="text-navy-200 group-hover:text-accent-700 transition-all ml-1"
                    :class="expandedId === notif.id ? 'rotate-180 text-accent-700' : ''"
                  />
                </div>
              </div>
            </div>

            <!-- Expanded detail -->
            <div v-if="expandedId === notif.id" class="bg-surface border-t border-navy-100 px-4 md:px-6 py-4">
              <div class="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-3 text-sm">
                <div>
                  <p :class="theme.text.muted" class="text-xs mb-0.5">Type</p>
                  <p class="font-medium text-navy-900">{{ typeLabel(notif.notification_type) }}</p>
                </div>
                <div>
                  <p :class="theme.text.muted" class="text-xs mb-0.5">Urgentie</p>
                  <p class="font-medium text-navy-900">{{ (severityConfig[notif.severity] || defaultSeverityConfig).label }}</p>
                </div>
                <div>
                  <p :class="theme.text.muted" class="text-xs mb-0.5">Doelgroep</p>
                  <p class="font-medium text-navy-900">{{ notif.target_scope === 'all' ? 'Alle organisaties' : 'Specifieke organisaties' }}</p>
                </div>
                <div>
                  <p :class="theme.text.muted" class="text-xs mb-0.5">Aangemaakt</p>
                  <p class="font-medium text-navy-900">{{ formatDate(notif.created_at) }}</p>
                </div>
                <div v-if="notif.is_published">
                  <p :class="theme.text.muted" class="text-xs mb-0.5">Gepubliceerd</p>
                  <p class="font-medium text-navy-900">{{ formatDate(notif.published_at!) }}</p>
                </div>
                <div v-if="notif.is_published">
                  <p :class="theme.text.muted" class="text-xs mb-0.5">Ontvangers</p>
                  <p class="font-medium text-navy-900">{{ notif.recipient_count }}</p>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- Footer -->
        <div class="py-3 text-center border-t border-navy-100" :class="theme.text.muted">
          {{ notifications.length }} van {{ total }} meldingen
        </div>
      </div>

      <!-- ──── Empty state ──── -->
      <div v-else :class="theme.emptyState.wrapper">
        <div :class="theme.emptyState.iconWrap">
          <Megaphone :size="24" :class="theme.emptyState.icon" />
        </div>
        <p :class="theme.emptyState.title">Nog geen meldingen</p>
        <p :class="theme.emptyState.description">Maak een melding aan om alle organisaties te informeren.</p>
      </div>
    </template>

    <!-- ──── Create Modal ──── -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div v-if="showCreate" class="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 px-4">
          <div :class="theme.card.base" class="w-full max-w-lg overflow-hidden">
            <!-- Modal header -->
            <div class="flex items-center justify-between px-6 py-4 bg-surface border-b border-navy-100">
              <div class="flex items-center gap-2">
                <Megaphone :size="16" class="text-navy-400" />
                <h3 :class="theme.text.h4">Nieuwe platformmelding</h3>
              </div>
              <button class="p-1 rounded hover:bg-navy-100 text-navy-400 hover:text-navy-700 transition-colors" @click="showCreate = false">
                <X :size="16" />
              </button>
            </div>

            <!-- Modal body -->
            <div class="p-6">
              <div class="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label :class="theme.form.label">Type</label>
                  <select v-model="form.notification_type" :class="theme.form.input">
                    <option v-for="t in types" :key="t.code" :value="t.code">
                      {{ t.label }}
                    </option>
                  </select>
                </div>
                <div>
                  <label :class="theme.form.label">Urgentie</label>
                  <select v-model="form.severity" :class="theme.form.input">
                    <option value="info">Informatie</option>
                    <option value="warning">Waarschuwing</option>
                    <option value="critical">Kritiek</option>
                  </select>
                </div>
              </div>

              <div :class="theme.form.group">
                <label :class="theme.form.label">Titel</label>
                <input
                  v-model="form.title"
                  :class="theme.form.input"
                  placeholder="Kort en duidelijk"
                  maxlength="255"
                />
              </div>

              <div>
                <label :class="theme.form.label">Bericht</label>
                <textarea
                  v-model="form.message"
                  :class="[theme.form.input, 'min-h-[120px] resize-y']"
                  placeholder="Het volledige bericht..."
                />
              </div>
            </div>

            <!-- Modal footer -->
            <div class="flex justify-end gap-2 px-6 py-4 border-t border-navy-100 bg-surface">
              <button @click="showCreate = false" :class="theme.btn.ghost">Annuleren</button>
              <button
                @click="handleCreate"
                :class="theme.btn.primary"
                :disabled="creating || !form.title || !form.message"
              >
                {{ creating ? 'Bezig...' : 'Aanmaken als concept' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Publish confirmation -->
    <ConfirmModal
      :open="!!publishTarget"
      title="Melding publiceren"
      :message="`Weet je zeker dat je '${publishTarget?.title ?? ''}' wilt publiceren? Alle organisaties ontvangen deze melding.`"
      confirm-label="Publiceren"
      variant="accent"
      @confirm="confirmPublish"
      @cancel="publishTarget = null"
    />

    <!-- Delete confirmation -->
    <ConfirmModal
      :open="!!deleteTarget"
      title="Concept verwijderen"
      :message="`Weet je zeker dat je '${deleteTarget?.title ?? ''}' wilt verwijderen?`"
      confirm-label="Verwijderen"
      variant="danger"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    />
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
</style>
