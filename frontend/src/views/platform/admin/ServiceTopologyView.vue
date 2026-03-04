<template>
  <div>
    <!-- Header + Toggle -->
    <div class="mb-6">
      <h2 :class="theme.text.h2">Service Topology</h2>
      <p :class="[theme.text.body, 'mt-1 mb-4']">
        {{ activeView === 'software'
          ? 'Applicatie-architectuur: modules, datastromen, security en multi-tenant patronen.'
          : activeView === 'infra'
            ? 'Infrastructuur: Docker containers, netwerk, resource limits en persistentie.'
            : activeView === 'tooling'
              ? 'Technologie-stack: frameworks, libraries, versies en toolchain per component.'
              : 'Technologie-lagen van client tot infrastructuur, met cross-cutting security en observability.' }}
      </p>
      <div class="inline-flex gap-1 bg-gray-100 rounded-lg p-1">
        <button
          v-for="v in views"
          :key="v.id"
          class="flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 select-none cursor-pointer"
          :class="activeView === v.id
            ? 'bg-white text-gray-900 shadow-sm'
            : 'text-gray-500 hover:text-gray-700'"
          @click="activeView = v.id"
        >
          <component :is="v.icon" class="w-4 h-4" />
          {{ v.label }}
        </button>
      </div>
    </div>

    <!-- Topology: Canvas views -->
    <div v-if="activeView !== 'stack'" ref="containerRef" class="relative w-full">
      <div class="relative bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">

        <!-- Dot grid -->
        <div class="absolute inset-0 opacity-[0.03]" :style="dotGridStyle"></div>

        <!-- SVG: columns + zones + connections -->
        <svg
          class="absolute inset-0 w-full h-full pointer-events-none"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          <defs>
            <marker id="t-arw-green" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <path d="M0,0 L8,3 L0,6" fill="#34d399" />
            </marker>
            <marker id="t-arw-blue" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <path d="M0,0 L8,3 L0,6" fill="#60a5fa" />
            </marker>
            <marker id="t-arw-violet" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <path d="M0,0 L8,3 L0,6" fill="#a78bfa" />
            </marker>
            <marker id="t-arw-gray" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <path d="M0,0 L8,3 L0,6" fill="#9ca3af" />
            </marker>
          </defs>

          <!-- Column backgrounds -->
          <rect
            v-for="(bg, i) in colBgs"
            :key="'bg-' + i"
            :x="bg.x" y="2" :width="bg.w" height="96" rx="1.2"
            :fill="bg.fill" fill-opacity="0.5" :stroke="bg.stroke" stroke-width="0.3"
          />

          <!-- Security zones -->
          <rect
            v-for="z in zoneRects"
            :key="z.id"
            :x="z.x" :y="z.y" :width="z.w" :height="z.h"
            rx="2"
            :fill="z.fill" :fill-opacity="z.fillOpacity"
            :stroke="z.stroke" stroke-width="0.15" stroke-dasharray="1.5 1.5"
          />

          <!-- Connections -->
          <g v-for="conn in connections" :key="conn.id">
            <path
              :d="conn.path" fill="none" stroke="transparent" stroke-width="6"
              class="pointer-events-auto cursor-pointer"
              @mouseenter="onHover('conn', conn.id, $event)"
              @mouseleave="onLeave('conn')"
            />
            <path
              :d="conn.path" fill="none"
              :stroke="conn.color"
              :stroke-width="hoveredConn === conn.id ? 1.2 : 0.7"
              :stroke-dasharray="conn.dash"
              :stroke-opacity="connOpacity(conn)"
              :marker-end="`url(#t-arw-${conn.colorKey})`"
              :class="conn.animate ? 'topology-flow' : ''"
              :style="hoveredConn === conn.id ? { filter: `drop-shadow(0 0 2px ${conn.color})` } : {}"
            />
          </g>
        </svg>

        <!-- HTML overlay -->
        <div class="relative w-full" style="padding-bottom: 92%; min-height: 480px;">

          <!-- Column label chips -->
          <div class="absolute top-2 left-0 right-0 z-20 flex pointer-events-none" style="padding: 0 1%;">
            <span
              v-for="(label, i) in columnLabels"
              :key="i"
              class="layer-chip"
              :class="label.chipClass"
              :style="{ left: label.x + '%', position: 'absolute', transform: 'translateX(-50%)' }"
            >{{ label.text }}</span>
          </div>

          <!-- Security badges -->
          <div
            v-for="badge in securityBadges"
            :key="badge.id"
            class="absolute z-30 transform -translate-x-1/2 -translate-y-1/2 transition-opacity duration-200"
            :style="{ left: badge.x + '%', top: badge.y + '%' }"
            :class="badgeOpacity(badge)"
            @mouseenter="onHover('badge', badge.id, $event)"
            @mouseleave="onLeave('badge')"
          >
            <div class="shield-badge" :class="badge.colorClass">
              <component :is="badge.icon" class="w-2.5 h-2.5" />
              <span>{{ badge.label }}</span>
            </div>
          </div>

          <!-- Security zone labels -->
          <div
            v-for="zone in securityZoneLabels"
            :key="zone.id"
            class="absolute z-20 transform -translate-x-1/2 -translate-y-1/2 transition-opacity duration-200 pointer-events-auto"
            :style="{ left: zone.x + '%', top: zone.y + '%' }"
            :class="zoneOpacity(zone)"
            @mouseenter="onHover('zone', zone.id, $event)"
            @mouseleave="onLeave('zone')"
          >
            <div class="zone-chip" :class="zone.colorClass">
              <component :is="zone.icon" class="w-2.5 h-2.5" />
              <span>{{ zone.label }}</span>
            </div>
          </div>

          <!-- Nodes -->
          <div
            v-for="node in nodes"
            :key="node.id"
            class="absolute transform -translate-x-1/2 -translate-y-1/2 z-10 transition-all duration-300 cursor-pointer"
            :style="{ left: node.x + '%', top: node.y + '%' }"
            :class="nodeOpacity(node)"
            @mouseenter="onHover('node', node.id, $event)"
            @mouseleave="onLeave('node')"
          >
            <div
              class="rounded-lg border bg-white/90 px-2 py-1.5 text-center transition-all duration-200 select-none shadow-sm"
              :class="[node.borderClass, node.isHub ? 'ring-2 ring-emerald-200 ring-offset-1 px-3 py-2' : '']"
              :style="'min-width:' + (node.isHub ? '110px' : '84px') + ';'"
            >
              <div class="flex items-center justify-center mb-0.5">
                <component :is="node.icon" :class="[node.isHub ? 'w-4.5 h-4.5' : 'w-3.5 h-3.5', node.iconColor]" />
              </div>
              <p class="font-semibold text-gray-800 leading-tight" :class="node.isHub ? 'text-[11px]' : 'text-[10px]'">{{ node.name }}</p>
              <p v-if="node.port" class="text-[8px] text-gray-400 font-mono">:{{ node.port }}</p>
              <p v-if="node.subtitle" class="text-[7px] text-gray-400 mt-0.5 leading-tight">{{ node.subtitle }}</p>
              <div v-if="node.tools" class="mt-1 flex flex-wrap gap-0.5 justify-center">
                <span v-for="tool in node.tools" :key="tool" class="text-[7px] bg-gray-50 text-gray-500 px-1 rounded border border-gray-100 leading-tight">{{ tool }}</span>
              </div>
            </div>
          </div>

          <!-- Legend -->
          <div class="absolute bottom-3 right-3 z-20 bg-white/90 backdrop-blur-sm rounded-lg border border-gray-200 px-3 py-2 text-[10px] space-y-1">
            <p class="font-semibold text-gray-500 uppercase tracking-wider text-[9px]">Verbindingen</p>
            <div class="flex items-center gap-2">
              <svg width="28" height="6"><line x1="0" y1="3" x2="28" y2="3" stroke="#34d399" stroke-width="1.5" stroke-dasharray="6 4" class="topology-flow" /></svg>
              <span class="text-gray-600">HTTP / REST</span>
            </div>
            <div class="flex items-center gap-2">
              <svg width="28" height="6"><line x1="0" y1="3" x2="28" y2="3" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="2 3" /></svg>
              <span class="text-gray-600">Queue / Job</span>
            </div>
            <div class="flex items-center gap-2">
              <svg width="28" height="6"><line x1="0" y1="3" x2="28" y2="3" stroke="#a78bfa" stroke-width="1.5" stroke-dasharray="8 3 2 3" class="topology-flow" /></svg>
              <span class="text-gray-600">Webhook</span>
            </div>
            <div class="flex items-center gap-2">
              <svg width="28" height="6"><line x1="0" y1="3" x2="28" y2="3" stroke="#9ca3af" stroke-width="1.5" /></svg>
              <span class="text-gray-600">In-process</span>
            </div>
            <div class="border-t border-gray-200 pt-1 mt-1"></div>
            <p class="font-semibold text-gray-500 uppercase tracking-wider text-[9px]">Security zones</p>
            <div class="flex items-center gap-2">
              <span class="w-4 h-3 rounded-sm border border-red-300 bg-red-100/60" :class="activeView === 'tooling' ? 'border-blue-300 bg-blue-100/60' : ''"></span>
              <span class="text-gray-600">{{ activeView === 'software' ? 'Public edge' : activeView === 'infra' ? 'Public edge' : 'TypeScript' }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="w-4 h-3 rounded-sm border border-blue-300 bg-blue-100/60" :class="activeView === 'tooling' ? 'border-emerald-300 bg-emerald-100/60' : ''"></span>
              <span class="text-gray-600">{{ activeView === 'software' ? 'Trusted network' : activeView === 'infra' ? 'Docker network' : 'Python ecosystem' }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="w-4 h-3 rounded-sm border border-amber-300 bg-amber-100/60" :class="activeView === 'tooling' ? 'border-violet-300 bg-violet-100/60' : ''"></span>
              <span class="text-gray-600">{{ activeView === 'software' ? 'Tenant boundary' : activeView === 'infra' ? 'Data plane' : 'DevOps & Ops' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Tooltip -->
      <Transition name="tooltip">
        <div
          v-if="tooltipContent"
          class="absolute z-50 pointer-events-none"
          :class="{
            '-translate-y-full': tooltipPlacement === 'top',
            '-translate-y-1/2': tooltipPlacement === 'left' || tooltipPlacement === 'right',
          }"
          :style="tooltipStyle"
        >
          <div class="bg-gray-900 text-white rounded-lg shadow-xl px-3.5 py-2.5 max-w-[290px] border border-gray-700">
            <div class="flex items-center gap-2 mb-1">
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="tooltipDotClass"></span>
              <p class="text-[11px] font-semibold leading-tight">{{ tooltipContent.title }}</p>
            </div>
            <p class="text-[10px] text-gray-300 leading-relaxed">{{ tooltipContent.desc }}</p>
            <p v-if="tooltipContent.tech" class="text-[9px] text-gray-500 mt-1.5 font-mono">{{ tooltipContent.tech }}</p>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Stack Overview -->
    <div v-else class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden p-6">
      <div class="flex gap-4">
        <!-- Main stack (left) -->
        <div class="flex-1 min-w-0">
          <template v-for="(layer, i) in stackLayers" :key="layer.id">
            <!-- Layer bar -->
            <div
              class="rounded-lg border px-4 py-3 cursor-pointer transition-all duration-200 hover:shadow-md"
              :class="[layer.borderClass, hoveredStack === layer.id ? 'ring-2 ring-offset-1 ' + layer.ringClass : '']"
              :style="{ background: layer.bg }"
              @mouseenter="hoveredStack = layer.id"
              @mouseleave="hoveredStack = null"
            >
              <div class="flex items-center gap-3">
                <div class="flex items-center justify-center w-8 h-8 rounded-lg bg-white/80 border" :class="layer.borderClass">
                  <component :is="layer.icon" class="w-4 h-4" :class="layer.iconColor" />
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-semibold text-gray-800">{{ layer.label }}</p>
                  <div class="flex flex-wrap gap-1 mt-1">
                    <span
                      v-for="item in layer.items" :key="item"
                      class="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-white/60"
                      :class="layer.pillClass"
                    >{{ item }}</span>
                  </div>
                </div>
              </div>
              <!-- Tooltip on hover -->
              <p v-if="hoveredStack === layer.id" class="text-[11px] text-gray-500 mt-2 leading-relaxed border-t border-gray-100 pt-2">
                {{ layer.desc }}
              </p>
            </div>
            <!-- Arrow between layers -->
            <div v-if="i < stackLayers.length - 1" class="flex justify-center py-1">
              <ChevronDown class="w-4 h-4 text-gray-300" />
            </div>
          </template>
        </div>

        <!-- Cross-cutting sidebar (right) -->
        <div class="w-48 flex flex-col gap-3 flex-shrink-0">
          <div
            v-for="cc in stackCrossCutting" :key="cc.id"
            class="flex-1 rounded-lg border px-3 py-3 cursor-pointer transition-all duration-200 hover:shadow-md"
            :class="[cc.borderClass, hoveredStack === cc.id ? 'ring-2 ring-offset-1 ' + cc.ringClass : '']"
            :style="{ background: cc.bg }"
            @mouseenter="hoveredStack = cc.id"
            @mouseleave="hoveredStack = null"
          >
            <div class="flex items-center gap-2 mb-2">
              <component :is="cc.icon" class="w-4 h-4" :class="cc.iconColor" />
              <p class="text-xs font-semibold text-gray-800">{{ cc.label }}</p>
            </div>
            <div class="flex flex-col gap-1">
              <span
                v-for="item in cc.items" :key="item"
                class="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-white/60"
                :class="cc.pillClass"
              >{{ item }}</span>
            </div>
            <p v-if="hoveredStack === cc.id" class="text-[10px] text-gray-500 mt-2 leading-relaxed border-t border-gray-100 pt-2">
              {{ cc.desc }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, type Component } from 'vue'
import {
  Globe, Shield, ShieldCheck, Monitor, Layers, Server, Key, Radio,
  Cpu, Lock, Settings, Building2, Fingerprint, Database, HardDrive,
  Zap, Cloud, CreditCard, Mail, Activity, GraduationCap, ClipboardCheck,
  Calendar, Bell, Receipt, Container, Network, Volume2, Wrench,
  ChevronDown, Eye, Package,
} from 'lucide-vue-next'
import { theme } from '@/theme'

// ── Toggle ──
type ViewId = 'software' | 'infra' | 'tooling' | 'stack'
const activeView = ref<ViewId>('software')
const views = [
  { id: 'software' as const, label: 'Software Architectuur', icon: Server },
  { id: 'infra' as const, label: 'Infrastructuur', icon: Container },
  { id: 'tooling' as const, label: 'Tooling & Stack', icon: Wrench },
  { id: 'stack' as const, label: 'Stack Overview', icon: Layers },
]

// ── Refs ──
const hoveredConn = ref<string | null>(null)
const hoveredNode = ref<string | null>(null)
const hoveredBadge = ref<string | null>(null)
const hoveredZone = ref<string | null>(null)
const hoveredEl = ref<HTMLElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)
const tooltipPlacement = ref('top')

const dotGridStyle = {
  backgroundImage: 'radial-gradient(circle, #000 1px, transparent 1px)',
  backgroundSize: '20px 20px',
}

function onHover(type: string, id: string, e: MouseEvent) {
  if (type === 'node')  hoveredNode.value = id
  if (type === 'badge') hoveredBadge.value = id
  if (type === 'zone')  hoveredZone.value = id
  if (type === 'conn')  hoveredConn.value = id
  hoveredEl.value = (e?.currentTarget as HTMLElement) || null
}
function onLeave(type: string) {
  if (type === 'node')  hoveredNode.value = null
  if (type === 'badge') hoveredBadge.value = null
  if (type === 'zone')  hoveredZone.value = null
  if (type === 'conn')  hoveredConn.value = null
  hoveredEl.value = null
}

// ════════════════════════════════════════════════════════════════════
// SOFTWARE ARCHITECTURE VIEW — Data
// ════════════════════════════════════════════════════════════════════

interface NodeDef {
  id: string; name: string; x: number; y: number; icon: Component
  iconColor: string; borderClass: string; subtitle?: string; port?: number
  isHub?: boolean; tools?: string[]
}

const softwareNodes: NodeDef[] = [
  // Clients
  { id: 'browser',      name: 'Browser',          x: 7.5,  y: 42, icon: Globe,          iconColor: 'text-violet-500',  borderClass: 'border-violet-200' },
  // Presentatielaag
  { id: 'nginx',        name: 'Nginx',            x: 22.5, y: 16, icon: Shield,         iconColor: 'text-blue-600',    borderClass: 'border-blue-200',    subtitle: 'Reverse Proxy · HTTPS/HSTS' },
  { id: 'vueSpa',       name: 'Vue 3 SPA',        x: 22.5, y: 50, icon: Monitor,        iconColor: 'text-blue-500',    borderClass: 'border-blue-200',    subtitle: 'TypeScript · Vite' },
  { id: 'stores',       name: 'Stores & Router',  x: 22.5, y: 82, icon: Layers,         iconColor: 'text-blue-400',    borderClass: 'border-blue-200 border-dashed', subtitle: 'Pinia · Vue Router' },
  // API & Core (Trusted Network — shifted down)
  { id: 'middleware',    name: 'Middleware',        x: 36,   y: 20, icon: ShieldCheck,    iconColor: 'text-emerald-500', borderClass: 'border-emerald-200 border-dashed', subtitle: 'CORS · Rate · Prometheus' },
  { id: 'authSecurity',  name: 'Auth & Security',  x: 48,   y: 20, icon: Key,            iconColor: 'text-emerald-500', borderClass: 'border-emerald-200 border-dashed', subtitle: 'JWT · HMAC · TOTP' },
  { id: 'fastapi',      name: 'FastAPI',          x: 42,   y: 40, icon: Server,         iconColor: 'text-emerald-600', borderClass: 'border-emerald-300', subtitle: 'Python 3.12', isHub: true },
  { id: 'eventBus',     name: 'Event Bus',        x: 36,   y: 62, icon: Radio,          iconColor: 'text-emerald-500', borderClass: 'border-emerald-200 border-dashed', subtitle: 'Pub/Sub' },
  { id: 'arqWorker',    name: 'arq Worker',       x: 48,   y: 62, icon: Cpu,            iconColor: 'text-emerald-600', borderClass: 'border-emerald-200', subtitle: '5 functies' },
  // Modules
  { id: 'platformMods', name: 'Platform Modules', x: 62,   y: 16, icon: Settings,       iconColor: 'text-amber-600',   borderClass: 'border-amber-200',   subtitle: 'Auth · Admin · Billing' },
  { id: 'tenantMods',   name: 'Tenant Modules',   x: 62,   y: 42, icon: Building2,      iconColor: 'text-amber-600',   borderClass: 'border-amber-200',   subtitle: 'Student · Attend · Sched · Notif' },
  { id: 'permissions',  name: 'Permissions',       x: 68,   y: 72, icon: Fingerprint,    iconColor: 'text-amber-500',   borderClass: 'border-amber-200 border-dashed', subtitle: '25 codenames · 4 groepen' },
  // Data
  { id: 'centralDb',    name: 'Central DB',       x: 88,   y: 14, icon: Database,       iconColor: 'text-pink-600',    borderClass: 'border-pink-200',    subtitle: 'ps_core_db' },
  { id: 'tenantDbs',    name: 'Tenant DBs',       x: 88,   y: 40, icon: HardDrive,      iconColor: 'text-pink-600',    borderClass: 'border-pink-200',    subtitle: 'ps_t_{slug}_db' },
  { id: 'redis',        name: 'Redis',            x: 88,   y: 78, icon: Zap,            iconColor: 'text-pink-500',    borderClass: 'border-pink-200',    subtitle: 'Cache · Queue' },
  { id: 'external',     name: 'Externe APIs',     x: 88,   y: 60, icon: Cloud,          iconColor: 'text-pink-500',    borderClass: 'border-pink-200',    subtitle: 'SMTP · Stripe · Mollie' },
]

interface ConnDef {
  id: string; from: string; to: string; type: 'http' | 'queue' | 'webhook' | 'internal'; oY?: number
}

const softwareConnDefs: ConnDef[] = [
  { id: 'browser→nginx',         from: 'browser',      to: 'nginx',        type: 'http' },
  { id: 'nginx→vueSpa',          from: 'nginx',        to: 'vueSpa',       type: 'http' },
  { id: 'nginx→fastapi',         from: 'nginx',        to: 'fastapi',      type: 'http' },
  { id: 'vueSpa→fastapi',        from: 'vueSpa',       to: 'fastapi',      type: 'http' },
  { id: 'vueSpa→stores',         from: 'vueSpa',       to: 'stores',       type: 'internal' },
  { id: 'fastapi→middleware',     from: 'fastapi',      to: 'middleware',   type: 'internal' },
  { id: 'fastapi→auth',          from: 'fastapi',      to: 'authSecurity', type: 'internal' },
  { id: 'fastapi→eventBus',      from: 'fastapi',      to: 'eventBus',     type: 'internal' },
  { id: 'fastapi→arqWorker',     from: 'fastapi',      to: 'arqWorker',    type: 'internal' },
  { id: 'fastapi→platformMods',  from: 'fastapi',      to: 'platformMods', type: 'http' },
  { id: 'fastapi→tenantMods',    from: 'fastapi',      to: 'tenantMods',   type: 'http' },
  { id: 'platformMods→centralDb', from: 'platformMods', to: 'centralDb',   type: 'internal' },
  { id: 'tenantMods→tenantDbs',  from: 'tenantMods',   to: 'tenantDbs',    type: 'internal' },
  { id: 'fastapi→redis',         from: 'fastapi',      to: 'redis',        type: 'internal' },
  { id: 'arqWorker→redis',       from: 'arqWorker',    to: 'redis',        type: 'queue' },
  { id: 'arqWorker→external',    from: 'arqWorker',    to: 'external',     type: 'http' },
  { id: 'arqWorker→centralDb',   from: 'arqWorker',    to: 'centralDb',    type: 'internal' },
  { id: 'arqWorker→tenantDbs',   from: 'arqWorker',    to: 'tenantDbs',    type: 'internal' },
  { id: 'external→fastapi',      from: 'external',     to: 'fastapi',      type: 'webhook' },
]

const softwareNodeTips: Record<string, { title: string; desc: string; tech?: string }> = {
  browser:      { title: 'Browser (Client)',           desc: 'Gebruikers benaderen het platform via een moderne webbrowser. De Vue SPA draait volledig client-side — een onvertrouwde omgeving.', tech: 'Elke moderne browser · HTTPS only' },
  nginx:        { title: 'Nginx Reverse Proxy',        desc: 'Enige public entrypoint. Termineert TLS (HTTPS :443), zet 10 security headers (HSTS, CSP, COOP, CORP, X-Frame-Options), blokkeert /metrics en /docs (404), routeert naar frontend of API. CSP strict met self-hosted fonts (Inter woff2); font-src \'self\' only.', tech: 'Nginx Alpine · TLS 1.2/1.3 · HSTS · COOP · CORP' },
  vueSpa:       { title: 'Vue 3 Single Page App',      desc: 'Frontend applicatie met component-based UI, reactive state management en client-side routing. Communiceert met de API via Axios REST calls.', tech: 'Vue 3 · TypeScript 5 · Vite 7 · Tailwind 4' },
  stores:       { title: 'Pinia Stores & Vue Router',  desc: 'Centralized state management (auth, tenant, notifications, branding) en client-side routing met permission-based guards.', tech: 'Pinia 3 · Vue Router 5 · Axios' },
  fastapi:      { title: 'FastAPI Application',        desc: 'Centrale API server. Verwerkt alle HTTP requests, past middleware pipeline toe, routeert naar modules, en beheert dependency injection.', tech: 'FastAPI · Python 3.12 · uvicorn · async' },
  middleware:   { title: 'Middleware Stack',            desc: 'Request pipeline: CORS policy (max_age=600), per-tenant rate limiting (60/min), Prometheus metrics (latency histogrammen + error counters), security headers, request-ID tracking, max body size (10MB).', tech: 'CORSMiddleware · PrometheusMiddleware · SecurityHeaders · MaxBodySize · RateLimiter' },
  authSecurity: { title: 'Auth & Security Layer',      desc: 'JWT access tokens + refresh token rotation met HMAC-SHA256 hashing. TOTP 2FA (pyotp + QR). Dynamic permission groups per tenant.', tech: 'PyJWT · HMAC-SHA256 · pyotp · pwdlib (Argon2)' },
  eventBus:     { title: 'Event Bus',                  desc: 'In-memory pub/sub systeem voor loose coupling tussen modules. Events zoals user.registered, attendance.created triggeren side-effects.', tech: 'asyncio · app.core.event_bus' },
  arqWorker:    { title: 'arq Background Worker',      desc: 'Async job queue met exponential backoff retry (10s→270s) en retryable allowlist. Taken: email, notificaties, facturen, factuur-emails, cleanup (03:00 cron). Non-retryable errors gaan naar dead letter met Prometheus metric.', tech: 'arq 0.27 · Redis db=1 · 5 jobs · retry + dead letter' },
  platformMods: { title: 'Platform Modules',           desc: 'SaaS-brede functionaliteit in de central database: authenticatie, admin dashboard, tenant/organisatie beheer, en platform billing (Stripe/Mollie).', tech: 'auth/ · admin/ · tenant_mgmt/ · billing/' },
  tenantMods:   { title: 'Tenant Modules',             desc: 'Organisatie-specifieke functionaliteit per organisatie in eigen tenant database: leerlingbeheer, aanwezigheid, rooster, notificaties, lesgeld. Alle mutaties worden geaudit naar central DB (best-effort).', tech: 'student/ · attendance/ · schedule/ · notification/ · billing/' },
  permissions:  { title: 'Permissiesysteem',           desc: '25 codenames over 8 modules. 4 default groepen per tenant (beheerder, docent, ouder, medewerker). DataScope: all/assigned/own zichtbaarheid.', tech: 'PermissionRegistry · auto-discovery · 3-way DataScope' },
  centralDb:    { title: 'Central Database',           desc: 'Gedeelde database voor platform-brede data: gebruikers, tenants, memberships, permissiegroepen, audit logs (incl. tenant mutaties), billing.', tech: 'PostgreSQL 16 · ps_core_db · Alembic central' },
  tenantDbs:    { title: 'Tenant Databases',           desc: 'Per organisatie een eigen database met leerlingen, aanwezigheid, lesrooster, notificaties en lesgeld. Volledige data-isolatie.', tech: 'PostgreSQL 16 · ps_t_{slug}_db · Alembic tenant' },
  redis:        { title: 'Redis',                      desc: 'Twee functies: db=0 voor applicatie caching (rate limits, tenant lookups), db=1 voor arq job queue (background tasks).', tech: 'Redis 7 · hiredis · db=0 cache · db=1 arq' },
  external:     { title: 'Externe APIs',               desc: 'Uitgaande integraties: multi-provider email (SMTP/Resend/Brevo met auto-fallback), Stripe en Mollie voor betalingen. Elke externe API beschermd door eigen circuit breaker (5 named breakers).', tech: 'Email (SMTP/Resend/Brevo) · Stripe API · Mollie API' },
}

const softwareConnTips: Record<string, { title: string; desc: string }> = {
  'browser→nginx':         { title: 'Browser → Nginx',           desc: 'HTTPS verkeer van browser naar reverse proxy. TLS terminatie op Nginx met HSTS preload.' },
  'nginx→vueSpa':          { title: 'Nginx → Vue SPA',           desc: 'Nginx serveert de static build (HTML/JS/CSS) van de Vue applicatie.' },
  'nginx→fastapi':         { title: 'Nginx → FastAPI',           desc: 'Reverse proxy doorsturing van /api/* requests naar de FastAPI backend op :8000.' },
  'vueSpa→fastapi':        { title: 'Vue SPA → FastAPI',         desc: 'REST API calls via Axios met JWT Bearer token in Authorization header. CORS beveiligd.' },
  'vueSpa→stores':         { title: 'Vue SPA → Stores',          desc: 'In-process binding: componenten lezen/schrijven reactive state via Pinia stores.' },
  'fastapi→middleware':    { title: 'FastAPI → Middleware',       desc: 'Elke request passeert de middleware pipeline: RequestID → CORS → RateLimit → Prometheus → SecurityHeaders → MaxBodySize.' },
  'fastapi→auth':          { title: 'FastAPI → Auth',            desc: 'JWT token validatie, permissie checks (require_permission), en DataScope filtering op elke beveiligde route.' },
  'fastapi→eventBus':      { title: 'FastAPI → Event Bus',       desc: 'Modules publiceren events (user.registered, attendance.created) voor cross-module side-effects.' },
  'fastapi→arqWorker':     { title: 'FastAPI → arq Worker',      desc: 'Langlopende taken worden via Redis geënqueued: email, notificaties, facturatie, cleanup. Elke job heeft max_tries + exponential backoff retry.' },
  'fastapi→platformMods':  { title: 'FastAPI → Platform Modules', desc: 'API routers voor auth, admin, tenant management en billing — platform-breed op central DB.' },
  'fastapi→tenantMods':    { title: 'FastAPI → Tenant Modules',   desc: 'Slug-in-URL routers (/api/v1/orgs/{slug}/...) voor tenant-specifieke modules.' },
  'platformMods→centralDb': { title: 'Platform → Central DB',    desc: 'Platform modules benaderen de central database via PgBouncer connection pool (ps_core_db).' },
  'tenantMods→tenantDbs':  { title: 'Tenant → Tenant DBs',       desc: 'Tenant modules benaderen hun organisatie-specifieke database via PgBouncer (ps_t_{slug}_db).' },
  'fastapi→redis':         { title: 'FastAPI → Redis',            desc: 'Directe Redis connectie voor rate limiting (sliding window counters), tenant slug cache, en session data. Fallback naar in-memory bij Redis uitval.' },
  'arqWorker→redis':       { title: 'arq Worker ↔ Redis',        desc: 'Job queue communicatie: Redis db=1 bevat job definitites, resultaten en cron schedules.' },
  'arqWorker→external':    { title: 'Worker → Externe APIs',     desc: 'Background jobs versturen emails via multi-provider systeem (SMTP/Resend/Brevo met auto-fallback), genereren facturen en communiceren met payment providers. 5 named circuit breakers (email_smtp, email_resend, email_brevo, stripe, mollie). Transiente fouten worden automatisch herhaald.' },
  'arqWorker→centralDb':   { title: 'Worker → Central DB',       desc: 'Background jobs benaderen de central database voor cleanup_unverified_users en globale facturatie-queries.' },
  'arqWorker→tenantDbs':   { title: 'Worker → Tenant DBs',       desc: 'Background jobs benaderen tenant databases voor factuurgeneratie, notificatieverwerking en organisatie-specifieke data.' },
  'external→fastapi':      { title: 'Webhooks → FastAPI',        desc: 'Stripe (HMAC-SHA256 signature verificatie) en Mollie (fetch-back patroon) sturen betaalstatus webhooks naar /api/v1/billing/webhooks/*.' },
}

// ════════════════════════════════════════════════════════════════════
// INFRASTRUCTURE VIEW — Data
// ════════════════════════════════════════════════════════════════════

const infraNodes: NodeDef[] = [
  // Extern
  { id: 'internet',    name: 'Internet',         x: 7.5,  y: 26, icon: Globe,      iconColor: 'text-violet-500',  borderClass: 'border-violet-200',  subtitle: 'Clients · CDN' },
  { id: 'paymentApis', name: 'Payment APIs',     x: 7.5,  y: 52, icon: CreditCard, iconColor: 'text-violet-500',  borderClass: 'border-violet-200',  subtitle: 'Stripe · Mollie' },
  { id: 'smtpExt',    name: 'Email Providers',  x: 7.5,  y: 76, icon: Mail,       iconColor: 'text-violet-500',  borderClass: 'border-violet-200 border-dashed', subtitle: 'SMTP · Resend · Brevo' },
  // Ingress
  { id: 'nginxC',      name: 'Nginx',            x: 22.5, y: 26, icon: Shield,     iconColor: 'text-blue-600',    borderClass: 'border-blue-300',    subtitle: 'Only public entrypoint · :80/:443', isHub: true },
  { id: 'frontendC',   name: 'Frontend',         x: 22.5, y: 58, icon: Monitor,    iconColor: 'text-blue-500',    borderClass: 'border-blue-200',    subtitle: 'Internal · :8080 (Docker)' },
  // Compute
  { id: 'apiC',        name: 'API Container',    x: 42,   y: 26, icon: Server,     iconColor: 'text-emerald-600', borderClass: 'border-emerald-300', subtitle: 'Internal · :8000 · 512MB' },
  { id: 'workerC',     name: 'Worker',           x: 42,   y: 56, icon: Cpu,        iconColor: 'text-emerald-600', borderClass: 'border-emerald-200', subtitle: 'Internal · arq · 256MB' },
  { id: 'mailpitC',    name: 'Mailpit',          x: 42,   y: 82, icon: Mail,       iconColor: 'text-emerald-400', borderClass: 'border-emerald-200 border-dashed', subtitle: 'Dev only · :1025/:8025' },
  // Services
  { id: 'pgbouncerC',  name: 'PgBouncer',        x: 65,   y: 26, icon: Layers,     iconColor: 'text-amber-600',   borderClass: 'border-amber-200',   subtitle: 'Internal · :6432 · 128MB' },
  { id: 'redisC',      name: 'Redis',            x: 65,   y: 56, icon: Zap,        iconColor: 'text-amber-600',   borderClass: 'border-amber-200',   subtitle: 'Internal · :6379 · 256MB' },
  { id: 'healthC',     name: 'Health Checks',    x: 65,   y: 82, icon: Activity,   iconColor: 'text-amber-500',   borderClass: 'border-amber-200 border-dashed', subtitle: '/health/live · /ready' },
  // Opslag
  { id: 'postgresC',   name: 'PostgreSQL 16',    x: 88,   y: 20, icon: Database,   iconColor: 'text-pink-600',    borderClass: 'border-pink-200',    subtitle: 'Internal · :5432 · 1GB' },
  { id: 'pgVolume',    name: 'postgres_data',    x: 88,   y: 42, icon: HardDrive,  iconColor: 'text-pink-500',    borderClass: 'border-pink-200 border-dashed', subtitle: 'Docker Volume' },
  { id: 'redisVolume', name: 'redis_data',       x: 88,   y: 62, icon: HardDrive,  iconColor: 'text-pink-500',    borderClass: 'border-pink-200 border-dashed', subtitle: 'Docker Volume' },
  { id: 'sslCerts',    name: 'SSL Certs',        x: 88,   y: 82, icon: Lock,       iconColor: 'text-pink-500',    borderClass: 'border-pink-200 border-dashed', subtitle: './ssl/ mount' },
]

const infraConnDefs: ConnDef[] = [
  { id: 'internet→nginxC',      from: 'internet',    to: 'nginxC',      type: 'http' },
  { id: 'nginxC→apiC',          from: 'nginxC',      to: 'apiC',        type: 'http' },
  { id: 'nginxC→frontendC',     from: 'nginxC',      to: 'frontendC',   type: 'http' },
  { id: 'apiC→pgbouncerC',     from: 'apiC',        to: 'pgbouncerC',  type: 'internal' },
  { id: 'apiC→redisC',         from: 'apiC',        to: 'redisC',      type: 'internal' },
  { id: 'workerC→pgbouncerC',  from: 'workerC',     to: 'pgbouncerC',  type: 'internal' },
  { id: 'workerC→redisC',      from: 'workerC',     to: 'redisC',      type: 'queue' },
  { id: 'workerC→mailpitC',    from: 'workerC',     to: 'mailpitC',    type: 'internal' },
  { id: 'workerC→smtpExt',    from: 'workerC',     to: 'smtpExt',     type: 'http' },
  { id: 'pgbouncerC→postgresC', from: 'pgbouncerC', to: 'postgresC',   type: 'internal' },
  { id: 'postgresC→pgVolume',  from: 'postgresC',   to: 'pgVolume',    type: 'internal' },
  { id: 'redisC→redisVolume',  from: 'redisC',      to: 'redisVolume', type: 'internal' },
  { id: 'paymentApis→apiC',    from: 'paymentApis',  to: 'apiC',       type: 'webhook' },
  { id: 'apiC→healthC',        from: 'apiC',         to: 'healthC',    type: 'internal' },
]

const infraNodeTips: Record<string, { title: string; desc: string; tech?: string }> = {
  internet:    { title: 'Internet / Clients',       desc: 'Inkomend HTTPS verkeer van browsers en API consumers. Alle verkeer passeert via Nginx reverse proxy.', tech: 'HTTPS · TLS 1.2/1.3' },
  paymentApis: { title: 'Payment Provider APIs',    desc: 'Bidirectioneel: Stripe/Mollie sturen webhook callbacks (inbound) en de API maakt payment requests (outbound). HMAC verificatie op inbound webhooks.', tech: 'Stripe Webhooks · Mollie Webhooks · REST API' },
  smtpExt:     { title: 'Email Providers',           desc: 'Multi-provider email systeem met auto-fallback. Drie providers: SMTP (aiosmtplib), Resend (REST API) en Brevo (REST API). Circuit breaker per provider (3 failures → 60s open). Primaire provider configurable via EMAIL_PROVIDER, fallback via EMAIL_FALLBACK_PROVIDER.', tech: 'SMTP · Resend · Brevo · Circuit Breaker · Auto-fallback' },
  nginxC:      { title: 'Nginx Container',           desc: 'Enige publiek bereikbare service. External: :80 (→301 HTTPS) en :443 (TLS termination). Reverse proxy routeert /api/* → api:8000 en / → frontend:8080 (intern Docker netwerk). Security headers (HSTS, CSP, COOP, CORP), OCSP stapling. Self-hosted fonts (Inter woff2). Blokkeert /metrics en /docs (404).', tech: 'nginx:alpine · External :80/:443 · 128MB · 0.25 CPU' },
  frontendC:   { title: 'Frontend Container',        desc: 'Statisch gebouwde Vue 3 SPA geserveerd via interne nginx. Alleen bereikbaar via Nginx reverse proxy (geen host port). In development: Vite dev server met HMR.', tech: 'nginx:alpine · Internal :8080 · 128MB · 0.25 CPU' },
  apiC:        { title: 'API Container',             desc: 'FastAPI applicatie draaiend op uvicorn. Alleen bereikbaar via Nginx reverse proxy (geen host port). Prometheus /metrics endpoint (IP-restricted, intern only).', tech: 'Python 3.12 · uvicorn · Internal :8000 · 512MB · 1 CPU' },
  workerC:     { title: 'Worker Container',          desc: 'arq background worker met exponential backoff retry (10s→270s). Jobs: emails, notificaties, facturen, cleanup (03:00 cron). Dead letter logging bij exhausted retries.', tech: 'arq · 5 functions · max_tries per job · 256MB · 0.5 CPU' },
  mailpitC:    { title: 'Mailpit (Development)',     desc: 'Development email catcher. Vangt alle uitgaande SMTP emails op en toont ze in een web interface. Alleen actief in docker-compose.dev.yml.', tech: 'Mailpit · SMTP :1025 · Web UI :8025' },
  pgbouncerC:  { title: 'PgBouncer Container',       desc: 'Connection pooler in transaction mode. Voorkomt connectie-explosie bij multi-tenant scenario\'s. Asyncpg prepared statement cache uitgeschakeld.', tech: 'edoburu/pgbouncer · :6432 · 128MB · 0.25 CPU' },
  redisC:      { title: 'Redis Container',           desc: 'In-memory data store. db=0: applicatie caching (rate limits, tenant lookups). db=1: arq job queue (achtergrondtaken).', tech: 'redis:7-alpine · :6379 · 256MB · 0.5 CPU' },
  healthC:     { title: 'Health Check Endpoints',    desc: 'Twee endpoints: /health/live (applicatie draait) en /health/ready (alle dependencies bereikbaar: PostgreSQL, Redis, PgBouncer, arq worker).', tech: '/health/live · /health/ready · Docker healthcheck' },
  postgresC:   { title: 'PostgreSQL Container',      desc: 'Primaire database server. Beheert de central database (ps_core_db) en alle tenant databases (ps_t_{slug}_db). WAL mode, Alpine image.', tech: 'postgres:16-alpine · :5432 · 1GB · 1 CPU' },
  pgVolume:    { title: 'postgres_data Volume',      desc: 'Docker named volume voor PostgreSQL data directory. Persistent over container restarts. Bevat alle databases en WAL logs.', tech: 'Docker Volume · /var/lib/postgresql/data' },
  redisVolume: { title: 'redis_data Volume',         desc: 'Docker named volume voor Redis persistence (AOF/RDB). Persistent over container restarts.', tech: 'Docker Volume · /data' },
  sslCerts:    { title: 'SSL Certificaten',          desc: 'Bind mount voor TLS certificaten. In productie: ./ssl/ directory met cert + key. In development: HTTP only (geen SSL).', tech: './ssl:/etc/nginx/ssl:ro · TLS 1.2/1.3' },
}

const infraConnTips: Record<string, { title: string; desc: string }> = {
  'internet→nginxC':      { title: 'Internet → Nginx',          desc: 'Inkomend HTTPS verkeer op poort 80/443. TLS terminatie op Nginx container. /metrics en /docs worden geblokkeerd (404).' },
  'nginxC→apiC':          { title: 'Nginx → API',               desc: 'Reverse proxy: /api/* requests doorgestuurd naar uvicorn op :8000 (intern Docker netwerk).' },
  'nginxC→frontendC':     { title: 'Nginx → Frontend',          desc: 'Alle niet-/api/ requests doorgestuurd naar frontend container (static files of Vite dev server).' },
  'apiC→pgbouncerC':     { title: 'API → PgBouncer',           desc: 'Database connecties via PgBouncer op :6432. Transaction pooling mode, prepared statements uitgeschakeld.' },
  'apiC→redisC':         { title: 'API → Redis',               desc: 'Cache en rate limiting via Redis db=0. Directe asyncio connectie via hiredis.' },
  'workerC→pgbouncerC':  { title: 'Worker → PgBouncer',        desc: 'Background jobs benaderen databases via dezelfde PgBouncer pool als de API.' },
  'workerC→redisC':      { title: 'Worker ↔ Redis',            desc: 'arq job queue via Redis db=1. Worker pollt voor nieuwe jobs, schrijft resultaten terug, en herplant gefaalde jobs met exponential backoff defer.' },
  'workerC→mailpitC':    { title: 'Worker → Mailpit',          desc: 'SMTP email delivery naar Mailpit op :1025. Alleen actief in development (docker-compose.dev.yml).' },
  'workerC→smtpExt':    { title: 'Worker → Email Providers',   desc: 'Uitgaande email delivery via multi-provider systeem. Primaire provider faalt → auto-fallback naar secundaire. SMTP (aiosmtplib, TLS auto-detect), Resend (httpx REST) of Brevo (httpx REST). Circuit breaker per provider.' },
  'pgbouncerC→postgresC': { title: 'PgBouncer → PostgreSQL',   desc: 'Gepoolde connecties naar PostgreSQL op :5432. PgBouncer beheert een pool per database.' },
  'postgresC→pgVolume':  { title: 'PostgreSQL → Volume',       desc: 'Data directory gemount op Docker named volume voor persistentie.' },
  'redisC→redisVolume':  { title: 'Redis → Volume',            desc: 'Redis data (AOF/RDB snapshots) gemount op Docker named volume.' },
  'paymentApis→apiC':    { title: 'Payment Webhooks → API',    desc: 'Stripe/Mollie sturen HTTP POST webhooks naar /api/v1/billing/webhooks/*.' },
  'apiC→healthC':        { title: 'API → Health Checks',       desc: 'Health endpoints worden door Docker healthcheck gepolld elke 5 seconden.' },
}

// ════════════════════════════════════════════════════════════════════
// SECURITY ZONES & BADGES — Per view
// ════════════════════════════════════════════════════════════════════

interface ZoneRect { id: string; x: number; y: number; w: number; h: number; fill: string; fillOpacity: string; stroke: string }
interface BadgeDef { id: string; label: string; x: number; y: number; icon: Component; colorClass: string; connIds: string[]; primary?: boolean }
interface ZoneLabelDef { id: string; label: string; x: number; y: number; colorClass: string; icon: Component }

const softwareZoneRects: ZoneRect[] = [
  { id: 'public',  x: 2,  y: 6,  w: 11, h: 82, fill: '#ef4444', fillOpacity: '0.025', stroke: '#fca5a5' },
  { id: 'trust',   x: 32, y: 12, w: 20, h: 60, fill: '#3b82f6', fillOpacity: '0.02',  stroke: '#93c5fd' },
  { id: 'tenant',  x: 56, y: 32, w: 43, h: 54, fill: '#f59e0b', fillOpacity: '0.03',  stroke: '#fcd34d' },
]
const infraZoneRects: ZoneRect[] = [
  { id: 'dmz',     x: 17, y: 8,  w: 11, h: 62, fill: '#ef4444', fillOpacity: '0.025', stroke: '#fca5a5' },
  { id: 'docker',  x: 32, y: 6,  w: 42, h: 82, fill: '#3b82f6', fillOpacity: '0.02',  stroke: '#93c5fd' },
  { id: 'storage', x: 78, y: 8,  w: 20, h: 82, fill: '#f59e0b', fillOpacity: '0.03',  stroke: '#fcd34d' },
]

const softwareBadges: BadgeDef[] = [
  { id: 'https',       label: 'HTTPS/TLS',       x: 15,   y: 28, icon: Lock,        colorClass: 'badge-blue',   connIds: ['browser→nginx'],          primary: true },
  { id: 'cors',        label: 'CORS',             x: 32,   y: 46, icon: Shield,      colorClass: 'badge-red',    connIds: ['vueSpa→fastapi'] },
  { id: 'rateLimit',   label: 'Rate Limit',       x: 38,   y: 28, icon: ShieldCheck, colorClass: 'badge-red',    connIds: ['fastapi→middleware'] },
  { id: 'jwt',         label: 'JWT + HMAC',       x: 46,   y: 28, icon: Fingerprint, colorClass: 'badge-violet', connIds: ['fastapi→auth'],           primary: true },
  { id: 'encryption',  label: 'Fernet Enc',       x: 46,   y: 24, icon: Lock,        colorClass: 'badge-violet', connIds: ['fastapi→auth'] },
  { id: 'pgPool',      label: 'Conn Pool',        x: 75,   y: 15, icon: Layers,      colorClass: 'badge-violet', connIds: ['platformMods→centralDb'] },
  { id: 'tenantIso',   label: 'Tenant Isolatie',  x: 75,   y: 40.7, icon: Lock,        colorClass: 'badge-amber',  connIds: ['tenantMods→tenantDbs'],   primary: true },
  { id: 'circuitBrk',  label: 'Circuit Breaker',  x: 71,   y: 61, icon: Activity,    colorClass: 'badge-violet', connIds: ['arqWorker→external'],     primary: true },
  { id: 'webhookHmac', label: 'Webhook HMAC',     x: 61,   y: 47, icon: ShieldCheck, colorClass: 'badge-red',    connIds: ['external→fastapi'] },
]
const infraBadges: BadgeDef[] = [
  { id: 'tls',         label: 'TLS Termination',  x: 15,   y: 26, icon: Lock,        colorClass: 'badge-blue',   connIds: ['internet→nginxC'],                         primary: true },
  { id: 'headers',     label: 'Security Headers', x: 28,   y: 34, icon: ShieldCheck, colorClass: 'badge-red',    connIds: ['nginxC→apiC', 'nginxC→frontendC'],          primary: true },
  { id: 'limits',      label: 'Resource Limits',  x: 50,   y: 36, icon: Shield,      colorClass: 'badge-violet', connIds: ['apiC→pgbouncerC', 'apiC→redisC'] },
  { id: 'pool',        label: 'Connection Pool',  x: 77,   y: 23, icon: Layers,      colorClass: 'badge-amber',  connIds: ['pgbouncerC→postgresC'] },
  { id: 'health',      label: 'Health Checks',    x: 54,   y: 54, icon: Activity,    colorClass: 'badge-blue',   connIds: ['apiC→healthC'] },
  { id: 'noHostPort', label: 'No Host Ports',    x: 78,   y: 59, icon: Lock,        colorClass: 'badge-red',    connIds: ['pgbouncerC→postgresC', 'redisC→redisVolume'], primary: true },
]

const softwareZoneLabels: ZoneLabelDef[] = [
  { id: 'public', label: 'Public Edge',        x: 7.5,  y: 12, colorClass: 'zone-red',   icon: Globe },
  { id: 'trust',  label: 'Trusted Network',    x: 42,   y: 14, colorClass: 'zone-blue',  icon: Lock },
  { id: 'tenant', label: 'Tenant Boundary',    x: 77,   y: 36, colorClass: 'zone-amber', icon: ShieldCheck },
]
const infraZoneLabels: ZoneLabelDef[] = [
  { id: 'dmz',     label: 'Public Edge',       x: 22.5, y: 14, colorClass: 'zone-red',   icon: Globe },
  { id: 'docker',  label: 'Docker Network',    x: 53,   y: 10, colorClass: 'zone-blue',  icon: Network },
  { id: 'storage', label: 'Data Plane',        x: 88,   y: 14, colorClass: 'zone-amber', icon: HardDrive },
]

const softwareZoneTips: Record<string, { title: string; desc: string }> = {
  public: { title: 'Public Edge',               desc: 'Browser en frontend draaien in een onvertrouwde omgeving. Alle communicatie naar de API is beveiligd met HTTPS, CORS en JWT authenticatie.' },
  trust:  { title: 'Trusted Network',           desc: 'De FastAPI application server met volledige middleware stack: CORS, rate limiting, Prometheus, security headers, body size limits, JWT validatie en permissie checks.' },
  tenant: { title: 'Tenant Boundary',           desc: 'Database-per-tenant architectuur. Elke organisatie heeft een eigen PostgreSQL database. DataScope mechanisme beperkt data-toegang tot all/assigned/own per gebruikersrol.' },
}
const infraZoneTips: Record<string, { title: string; desc: string }> = {
  dmz:     { title: 'Public Edge',              desc: 'Nginx is het enige component dat direct bereikbaar is van buitenaf (extern :80/:443). TLS terminatie, 10 security headers en reverse proxy logica. Alle interne services zijn afgeschermd.' },
  docker:  { title: 'Docker Network',           desc: 'Intern Docker netwerk waar API, Worker, PgBouncer en Redis communiceren. Niet direct bereikbaar van buitenaf. Services gebruiken interne DNS-namen.' },
  storage: { title: 'Data Plane',               desc: 'Docker named volumes en bind mounts voor data persistentie. PostgreSQL en Redis data overleven container restarts. SSL certificaten als read-only mount.' },
}

const softwareBadgeTips: Record<string, { title: string; desc: string }> = {
  https:     { title: 'HTTPS / TLS',            desc: 'TLS 1.2/1.3 terminatie op Nginx. HSTS preload, COOP/CORP headers, modern cipher suite, OCSP stapling, SSL session caching.' },
  cors:      { title: 'CORS Policy',            desc: 'Strikte CORS configuratie: alleen toegestane origins, credentials allowed, preflight cache 10 minuten (max_age=600). HTTP origins geven startup-waarschuwing.' },
  jwt:       { title: 'JWT + HMAC-SHA256',      desc: 'Access tokens (30 min) + refresh token rotation. Tokens gehashed met HMAC-SHA256 (niet plain SHA256). Automatische migratie van legacy hashes.' },
  rateLimit:   { title: 'Rate Limiting',           desc: 'Dual-layer: per-IP (60/min) + per-tenant (300/min). Login lockout na 5 mislukte pogingen voor 15 min. Forgot-password: 3/uur. Respecteert X-Forwarded-For. Redis sliding window met in-memory fallback. Prometheus metrics tracken alle requests en errors.' },
  encryption:  { title: 'Fernet Encryption',       desc: 'Veld-niveau encryptie voor gevoelige data at rest: TOTP secrets, billing API keys. PBKDF2 key derivation (100K iteraties) met backwards-compatible SHA256 fallback.' },
  pgPool:      { title: 'PgBouncer Connection Pool', desc: 'PgBouncer in transaction mode voorkomt connectie-explosie. Asyncpg prepared statements uitgeschakeld. Elke tenant database heeft een eigen pool.' },
  tenantIso:   { title: 'Tenant Data Isolatie',    desc: 'Elke tenant heeft een eigen PostgreSQL database. TenantDatabaseManager met lazy engine caching. Slug-in-URL routing voorkomt cross-tenant data lekkage.' },
  circuitBrk:  { title: 'Circuit Breaker',          desc: '5 named breakers: email_smtp, email_resend, email_brevo, stripe, mollie. Per breaker: 3 failures → circuit open 60s, half-open recovery met 1 success threshold. Named registry in core/circuit_breaker.py. Voorkomt cascade failures bij externe API uitval.' },
  webhookHmac: { title: 'Webhook Verificatie',      desc: 'Stripe: HMAC-SHA256 signature met timestamp tolerance (5 min). Mollie: fetch-back patroon (payment ID ophalen via API key). Voorkomt webhook spoofing.' },
}
const infraBadgeTips: Record<string, { title: string; desc: string }> = {
  tls:     { title: 'TLS Termination',         desc: 'Nginx handelt alle TLS af met TLSv1.2/1.3, OCSP stapling, session caching, COOP/CORP headers. Backend services communiceren intern via HTTP (trusted netwerk).' },
  headers: { title: 'Security Headers',         desc: 'Dubbele laag: Nginx zet 10 headers (HSTS, CSP, COOP, CORP, X-Frame-Options, Permissions-Policy) EN FastAPI SecurityHeadersMiddleware voegt toe voor directe API calls. CSP strict met self-hosted fonts; font-src \'self\' only, geen externe domeinen.' },
  limits:  { title: 'Docker Resource Limits',   desc: 'Alle containers hebben memory + CPU limits: API 512MB/1CPU, Worker 256MB/0.5CPU, PostgreSQL 1GB/1CPU, Redis 256MB/0.5CPU.' },
  pool:    { title: 'Connection Pooling',       desc: 'PgBouncer in transaction mode voorkomt connectie-explosie. Elke tenant database heeft een eigen pool. Asyncpg prepared statements uitgeschakeld.' },
  health:     { title: 'Health Check Systeem',     desc: '/health/live: applicatie draait. /health/ready: PostgreSQL, Redis, PgBouncer en arq worker allemaal bereikbaar. Docker pollt elke 5s.' },
  noHostPort: { title: 'No Host Port Exposure',   desc: 'PostgreSQL en Redis hebben geen host port mappings in productie. Alleen bereikbaar via intern Docker netwerk. Significante security hardening maatregel.' },
}

// ════════════════════════════════════════════════════════════════════
// TOOLING VIEW — Data
// ════════════════════════════════════════════════════════════════════

const toolingNodes: NodeDef[] = [
  // Frontend
  { id: 'feFramework', name: 'Frontend Framework', x: 10, y: 18, icon: Monitor,        iconColor: 'text-blue-600',    borderClass: 'border-blue-300',    isHub: true, tools: ['Vue 3', 'TypeScript 5', 'Vite 7'] },
  { id: 'feState',     name: 'State & Routing',    x: 10, y: 48, icon: Layers,         iconColor: 'text-blue-500',    borderClass: 'border-blue-200',    tools: ['Pinia 3', 'Vue Router 5', 'Axios'] },
  { id: 'feUI',        name: 'UI & Styling',       x: 10, y: 76, icon: Settings,       iconColor: 'text-blue-400',    borderClass: 'border-blue-200 border-dashed', tools: ['Tailwind 4', 'Lucide Icons'] },
  // API
  { id: 'apiRuntime',  name: 'API Runtime',        x: 30, y: 18, icon: Server,         iconColor: 'text-emerald-600', borderClass: 'border-emerald-300', isHub: true, tools: ['Python 3.12', 'FastAPI', 'uvicorn'] },
  { id: 'authTools',   name: 'Auth & Crypto',      x: 30, y: 48, icon: Key,            iconColor: 'text-emerald-500', borderClass: 'border-emerald-200', tools: ['PyJWT', 'Argon2', 'pyotp', 'Fernet'] },
  // Core Services
  { id: 'observability', name: 'Observability',    x: 50, y: 18, icon: Activity,       iconColor: 'text-amber-600',   borderClass: 'border-amber-200',   tools: ['Prometheus', 'Grafana', 'Loki', 'structlog'] },
  { id: 'jobQueue',    name: 'Job Queue',          x: 50, y: 48, icon: Cpu,            iconColor: 'text-amber-500',   borderClass: 'border-amber-200',   tools: ['arq 0.27', 'retry/backoff', 'dead letter'] },
  // Data
  { id: 'dbOrm',       name: 'Database ORM',       x: 70, y: 18, icon: Database,       iconColor: 'text-pink-600',    borderClass: 'border-pink-200',    tools: ['SQLAlchemy 2', 'Alembic', 'asyncpg'] },
  { id: 'caching',     name: 'Cache & Queue',      x: 70, y: 48, icon: Zap,            iconColor: 'text-pink-500',    borderClass: 'border-pink-200',    tools: ['Redis 7', 'hiredis'] },
  // DevOps
  { id: 'containers',  name: 'Containers & CI/CD',  x: 90, y: 18, icon: Container,      iconColor: 'text-violet-600',  borderClass: 'border-violet-200',  tools: ['Docker', 'GitHub Actions', 'Terraform'] },
  { id: 'testing',     name: 'Testing & QA',       x: 90, y: 48, icon: ClipboardCheck, iconColor: 'text-violet-500',  borderClass: 'border-violet-200',  tools: ['pytest 9', 'ruff', 'factory-boy'] },
  { id: 'integrations', name: 'Integraties',       x: 90, y: 76, icon: CreditCard,     iconColor: 'text-violet-400',  borderClass: 'border-violet-200 border-dashed', tools: ['Stripe', 'Mollie', 'Email (3 providers)'] },
]

const toolingConnDefs: ConnDef[] = [
  { id: 'fe→api',           from: 'feFramework', to: 'apiRuntime',    type: 'http' },
  { id: 'feState→fe',       from: 'feState',     to: 'feFramework',   type: 'internal' },
  { id: 'feUI→fe',          from: 'feUI',        to: 'feFramework',   type: 'internal' },
  { id: 'api→auth',         from: 'apiRuntime',  to: 'authTools',     type: 'internal' },
  { id: 'api→obs',          from: 'apiRuntime',  to: 'observability', type: 'internal' },
  { id: 'api→jobs',         from: 'apiRuntime',  to: 'jobQueue',      type: 'internal' },
  { id: 'api→db',           from: 'apiRuntime',  to: 'dbOrm',         type: 'http' },
  { id: 'jobs→cache',       from: 'jobQueue',    to: 'caching',       type: 'queue' },
  { id: 'db→containers',    from: 'dbOrm',       to: 'containers',    type: 'internal' },
  { id: 'cache→containers', from: 'caching',     to: 'containers',    type: 'internal' },
  { id: 'jobs→integrations', from: 'jobQueue',   to: 'integrations',  type: 'http' },
  { id: 'testing→api',      from: 'testing',     to: 'apiRuntime',    type: 'internal' },
]

const toolingNodeTips: Record<string, { title: string; desc: string; tech?: string }> = {
  feFramework:  { title: 'Frontend Framework',      desc: 'Vue 3 met Composition API (setup script), TypeScript 5 voor type safety, en Vite 7 als build tool met HMR.', tech: 'Vue 3.5 · TypeScript 5.9 · Vite 7' },
  feState:      { title: 'State & Routing',          desc: 'Pinia 3 voor reactive state management (auth, tenant, notifications, branding stores). Vue Router 5 met permission-based guards. Axios met JWT interceptor.', tech: 'Pinia 3 · Vue Router 5 · Axios 1.13' },
  feUI:         { title: 'UI & Styling',             desc: 'Tailwind CSS 4 via centraal theme systeem (theme.ts). 5 thema\'s actief. Self-hosted Inter font (woff2 variable). Lucide Icons voor consistente iconografie.', tech: 'Tailwind CSS 4 · Inter (self-hosted) · Lucide' },
  apiRuntime:   { title: 'API Runtime',              desc: 'Python 3.12 met FastAPI voor async REST API. uvicorn als ASGI server. Volledig async: alle handlers, database queries en HTTP calls.', tech: 'Python 3.12 · FastAPI 0.135 · uvicorn' },
  authTools:    { title: 'Auth & Crypto Tooling',    desc: 'PyJWT voor JWT access/refresh tokens. pwdlib met Argon2id voor wachtwoord hashing. pyotp + segno voor TOTP 2FA met QR codes. Fernet (cryptography) voor at-rest encryptie.', tech: 'PyJWT · pwdlib/Argon2 · pyotp · Fernet' },
  observability: { title: 'Observability Stack',     desc: 'Prometheus v3 + Grafana voor metrics dashboards. Loki + Promtail voor log aggregatie. Alertmanager voor alerting. structlog voor structured JSON logging met request-ID correlatie. Uptime Kuma voor uptime monitoring.', tech: 'Prometheus · Grafana · Loki · Alertmanager · structlog · Uptime Kuma' },
  jobQueue:     { title: 'Background Job Queue',     desc: 'arq 0.27 async job queue op Redis db=1. Exponential backoff retry (10s→270s) met retryable allowlist. Dead letter logging met Prometheus counter. 5 job functies.', tech: 'arq 0.27 · retry.py · Redis db=1' },
  dbOrm:        { title: 'Database ORM & Migrations', desc: 'SQLAlchemy 2 met async sessions (asyncpg driver). Dual-mode Alembic migraties: central/ en tenant/ schema\'s. Multi-tenant: database-per-tenant met lazy engine caching.', tech: 'SQLAlchemy 2 · Alembic · asyncpg' },
  caching:      { title: 'Cache & Queue Backend',    desc: 'Redis 7 met hiredis C-parser voor performance. db=0: rate limiting sliding window, tenant slug cache. db=1: arq job queue. Circuit breaker fallback naar in-memory.', tech: 'Redis 7 · hiredis · 2 databases' },
  containers:   { title: 'CI/CD & Containers',        desc: 'GitHub Actions CI: lint, tests (~297), frontend build, Docker build+scan+push (GHCR). Auto-deploy via SSH. Docker Compose met 8 services. Trivy container scanning. Terraform (Hetzner VPS).', tech: 'GitHub Actions · Docker · GHCR · Terraform · Trivy' },
  testing:      { title: 'Testing & Quality',         desc: 'pytest 9 met pytest-asyncio voor async tests. ~297 tests. factory-boy voor test data factories. ruff voor linting en formatting. pytest-cov voor coverage.', tech: 'pytest 9 · ruff · factory-boy · pytest-cov' },
  integrations: { title: 'Externe Integraties',       desc: 'Stripe en Mollie voor betalingen (HMAC webhook verificatie). Multi-provider email: SMTP (aiosmtplib), Resend (httpx REST), Brevo (httpx REST) met auto-fallback. Circuit breakers beschermen alle externe calls (5 named breakers).', tech: 'Stripe · Mollie · SMTP/Resend/Brevo' },
}

const toolingConnTips: Record<string, { title: string; desc: string }> = {
  'fe→api':           { title: 'Frontend → API',           desc: 'REST API calls via Axios met JWT Bearer token. CORS beveiligd, TypeScript types gedeeld via handmatige sync.' },
  'feState→fe':       { title: 'State → Framework',        desc: 'Pinia stores injecteren reactive state in Vue componenten. Router guards lezen auth en tenant state.' },
  'feUI→fe':          { title: 'UI → Framework',           desc: 'Tailwind utility classes via theme.ts. Lucide icons als Vue componenten. CSS custom properties voor thema-switching.' },
  'api→auth':         { title: 'API → Auth Tools',         desc: 'FastAPI dependencies: get_current_user (JWT validatie), require_permission (groep-check), get_data_scope (visibility).' },
  'api→obs':          { title: 'API → Observability',       desc: 'PrometheusMiddleware meet latency + errors. structlog bindt request-ID aan elke log entry via contextvars.' },
  'api→jobs':         { title: 'API → Job Queue',           desc: 'Routes enqueuen jobs via arq pool: send_email_job, process_notification_job, generate_invoices_job, etc.' },
  'api→db':           { title: 'API → Database ORM',        desc: 'Dependency injection: get_central_db() en get_tenant_db() leveren AsyncSession. SQLAlchemy queries met select().' },
  'jobs→cache':       { title: 'Jobs ↔ Redis',              desc: 'arq gebruikt Redis db=1 als job queue. Worker pollt, voert uit, schrijft resultaat. Retry deferred via Redis sorted set.' },
  'db→containers':    { title: 'ORM → Containers',          desc: 'asyncpg connecteert via PgBouncer (:6432) naar PostgreSQL. Prepared statements uitgeschakeld (transaction pooling).' },
  'cache→containers': { title: 'Cache → Containers',        desc: 'hiredis verbindt met Redis container via intern Docker netwerk. Twee databases: cache (db=0) en queue (db=1).' },
  'jobs→integrations': { title: 'Jobs → Integraties',       desc: 'Background jobs versturen emails via multi-provider systeem (SMTP/Resend/Brevo met auto-fallback), maken Stripe/Mollie API calls. 5 named circuit breakers + retry op transiente fouten.' },
  'testing→api':      { title: 'Testing → API',             desc: 'pytest met httpx AsyncClient voor API integration tests. factory-boy factories voor test data. In-memory SQLite of PostgreSQL.' },
}

const toolingZoneRects: ZoneRect[] = [
  { id: 'typescript', x: 2,  y: 4, w: 16, h: 90, fill: '#3b82f6', fillOpacity: '0.02', stroke: '#93c5fd' },
  { id: 'python',     x: 22, y: 4, w: 56, h: 90, fill: '#10b981', fillOpacity: '0.02', stroke: '#6ee7b7' },
  { id: 'devops',     x: 82, y: 4, w: 16, h: 90, fill: '#8b5cf6', fillOpacity: '0.02', stroke: '#c4b5fd' },
]

const toolingBadges: BadgeDef[] = [
  { id: 'asyncIO',    label: 'Async I/O',       x: 20,  y: 18, icon: Zap,         colorClass: 'badge-blue',   connIds: ['fe→api'] },
  { id: 'typeSafe',   label: 'Type Safety',     x: 10,  y: 33, icon: ShieldCheck, colorClass: 'badge-blue',   connIds: ['feState→fe', 'feUI→fe'] },
  { id: 'multiTenant', label: 'Multi-Tenant',   x: 60,  y: 18, icon: Lock,        colorClass: 'badge-amber',  connIds: ['api→db'] },
  { id: 'retryLogic', label: 'Retry + DLQ',     x: 60,  y: 48, icon: Activity,    colorClass: 'badge-red',    connIds: ['jobs→cache'] },
  { id: 'txPool',     label: 'Conn Pooling',    x: 80,  y: 18, icon: Layers,      colorClass: 'badge-violet', connIds: ['db→containers'] },
]

const toolingZoneLabels: ZoneLabelDef[] = [
  { id: 'typescript', label: 'TypeScript',          x: 10,  y: 8,  colorClass: 'zone-blue',  icon: Monitor },
  { id: 'python',     label: 'Python Ecosystem',    x: 50,  y: 8,  colorClass: 'zone-blue',  icon: Server },
  { id: 'devops',     label: 'DevOps & Ops',        x: 90,  y: 8,  colorClass: 'zone-blue',  icon: Container },
]

const toolingZoneTips: Record<string, { title: string; desc: string }> = {
  typescript: { title: 'TypeScript Ecosystem',  desc: 'Client-side stack: Vue 3 + TypeScript voor type-safe UI development. Vite voor instant HMR. Alle API calls getypeerd met shared interfaces.' },
  python:     { title: 'Python Ecosystem',       desc: 'Server-side stack: Python 3.12 async runtime. FastAPI + SQLAlchemy + arq vormen de core. Alle I/O is non-blocking (asyncpg, aiosmtplib, httpx, hiredis). Multi-provider email met auto-fallback.' },
  devops:     { title: 'DevOps & Operations',    desc: 'CI/CD: GitHub Actions → GHCR → SSH deploy (push to main = auto deploy). 4 CI jobs: lint, tests, frontend build, Docker build+scan+push. Trivy container scanning. Terraform (Hetzner). Makefile voor workflows.' },
}

const toolingBadgeTips: Record<string, { title: string; desc: string }> = {
  asyncIO:     { title: 'Async I/O Everywhere',  desc: 'Volledig async stack: FastAPI handlers, SQLAlchemy async sessions, asyncpg driver, aiosmtplib, httpx (Resend/Brevo), hiredis. Geen blocking I/O in de hot path.' },
  typeSafe:    { title: 'Type Safety',            desc: 'TypeScript 5 in de frontend (strict mode). Python type hints + Pydantic schemas in de backend. Types als documentatie en validatie.' },
  multiTenant: { title: 'Multi-Tenant ORM',       desc: 'TenantDatabaseManager: lazy-cached async engines per tenant. Dual-mode Alembic: central/ en tenant/ migraties. Database-per-tenant isolatie.' },
  retryLogic:  { title: 'Retry + Dead Letter',    desc: 'Exponential backoff (10s→270s). Retryable allowlist: alleen bekende transiente fouten (ConnectionError, SMTP timeout, etc.). Dead letter met Prometheus metric.' },
  txPool:      { title: 'Connection Pooling',      desc: 'PgBouncer transaction mode: prepared statements uitgeschakeld. Elke tenant database eigen pool. Voorkomt connectie-explosie bij multi-tenant scale.' },
}

// ════════════════════════════════════════════════════════════════════
// STACK OVERVIEW — Data
// ════════════════════════════════════════════════════════════════════

const hoveredStack = ref<string | null>(null)

interface StackLayer {
  id: string; label: string; icon: Component; items: string[]
  bg: string; borderClass: string; ringClass: string; iconColor: string; pillClass: string
  desc: string
}

const stackLayers: StackLayer[] = [
  {
    id: 'clients', label: 'Clients', icon: Globe,
    items: ['Browser', 'HTTPS', 'Mobile-ready'],
    bg: '#f5f3ff', borderClass: 'border-violet-200', ringClass: 'ring-violet-200', iconColor: 'text-violet-600', pillClass: 'text-violet-700 border-violet-200',
    desc: 'Gebruikers benaderen het platform via een moderne webbrowser. De Vue SPA draait volledig client-side — een onvertrouwde omgeving. Alle communicatie verloopt via HTTPS.',
  },
  {
    id: 'frontend', label: 'Frontend', icon: Monitor,
    items: ['Vue 3', 'TypeScript 5', 'Vite 7', 'Tailwind 4', 'Pinia 3'],
    bg: '#eff6ff', borderClass: 'border-blue-200', ringClass: 'ring-blue-200', iconColor: 'text-blue-600', pillClass: 'text-blue-700 border-blue-200',
    desc: 'Single Page Application met component-based UI, reactive state management (Pinia) en client-side routing met permission-based guards. Centraal theme systeem (theme.ts) met 5 actieve thema\'s.',
  },
  {
    id: 'ingress', label: 'Ingress', icon: Shield,
    items: ['Nginx', 'TLS 1.2/1.3', 'HSTS', 'CSP', 'COOP/CORP', 'Rate Limiting'],
    bg: '#eff6ff', borderClass: 'border-blue-300', ringClass: 'ring-blue-300', iconColor: 'text-blue-700', pillClass: 'text-blue-700 border-blue-200',
    desc: 'Enige public entrypoint. Nginx termineert TLS, zet 10 security headers, blokkeert /metrics en /docs, en routeert naar frontend of API. CSP strict met self-hosted fonts (Inter woff2); font-src \'self\' only.',
  },
  {
    id: 'api', label: 'API Layer', icon: Server,
    items: ['FastAPI', 'Python 3.12', 'uvicorn', 'Middleware stack'],
    bg: '#ecfdf5', borderClass: 'border-emerald-200', ringClass: 'ring-emerald-200', iconColor: 'text-emerald-600', pillClass: 'text-emerald-700 border-emerald-200',
    desc: 'Async REST API met middleware pipeline: RequestID → CORS → RateLimit → Prometheus → SecurityHeaders → MaxBodySize. Dependency injection voor DB sessies, Redis en permissies.',
  },
  {
    id: 'modules', label: 'Business Modules', icon: Package,
    items: ['Auth', 'Students', 'Attendance', 'Schedule', 'Notifications', 'Billing'],
    bg: '#fffbeb', borderClass: 'border-amber-200', ringClass: 'ring-amber-200', iconColor: 'text-amber-600', pillClass: 'text-amber-700 border-amber-200',
    desc: 'Platform modules (central DB): auth, admin, tenant management, billing. Tenant modules (per-org DB): students, attendance, schedule, notifications. 25 permissie-codenames, 4 default groepen (beheerder, docent, ouder, medewerker), DataScope filtering.',
  },
  {
    id: 'jobs', label: 'Background Jobs', icon: Cpu,
    items: ['arq Worker', 'Retry/Backoff', 'Dead Letter', 'Cron scheduling', 'Email Fallback'],
    bg: '#fffbeb', borderClass: 'border-amber-300', ringClass: 'ring-amber-300', iconColor: 'text-amber-700', pillClass: 'text-amber-700 border-amber-200',
    desc: 'Async job queue met 5 functies: email, notificaties, facturen, factuur-emails, cleanup. Multi-provider email (SMTP/Resend/Brevo) met auto-fallback. Exponential backoff retry (10s→270s) met retryable allowlist. Dead letter logging met Prometheus metric.',
  },
  {
    id: 'data', label: 'Data Layer', icon: Database,
    items: ['SQLAlchemy 2', 'Alembic', 'PgBouncer', 'asyncpg', 'Redis 7'],
    bg: '#fdf2f8', borderClass: 'border-pink-200', ringClass: 'ring-pink-200', iconColor: 'text-pink-600', pillClass: 'text-pink-700 border-pink-200',
    desc: 'Database-per-tenant isolatie via TenantDatabaseManager met lazy engine caching. PgBouncer transaction pooling. Dual-mode Alembic migraties (central/tenant). Redis db=0 cache, db=1 arq queue.',
  },
  {
    id: 'infra', label: 'Infrastructure', icon: Container,
    items: ['Docker Compose', 'PostgreSQL 16', 'Redis 7', 'Nginx Alpine'],
    bg: '#fdf2f8', borderClass: 'border-pink-300', ringClass: 'ring-pink-300', iconColor: 'text-pink-700', pillClass: 'text-pink-700 border-pink-200',
    desc: 'Docker Compose met 8 services. Non-root containers, resource limits (memory + CPU), health checks, restart policies. Alleen Nginx publiek bereikbaar (:80/:443). Alle andere services intern Docker netwerk.',
  },
]

const stackCrossCutting: StackLayer[] = [
  {
    id: 'security', label: 'Security', icon: Lock,
    items: ['JWT + HMAC', 'TOTP 2FA', 'Fernet Enc', 'Argon2', '5 Circuit Breakers', 'Tenant Isolatie', 'Email Fallback'],
    bg: '#fef2f2', borderClass: 'border-red-200', ringClass: 'ring-red-200', iconColor: 'text-red-600', pillClass: 'text-red-700 border-red-200',
    desc: 'Cross-cutting security: JWT access tokens + refresh rotation met HMAC-SHA256 hashing. TOTP 2FA. Fernet encryptie voor secrets at rest. Argon2id password hashing. 5 named circuit breakers (email_smtp, email_resend, email_brevo, stripe, mollie). Multi-provider email met auto-fallback. Database-per-tenant isolatie.',
  },
  {
    id: 'observability', label: 'Observability', icon: Eye,
    items: ['Prometheus', 'Grafana', 'Loki', 'Alertmanager', 'Uptime Kuma', 'structlog', 'Audit logging'],
    bg: '#f5f3ff', borderClass: 'border-violet-200', ringClass: 'ring-violet-200', iconColor: 'text-violet-600', pillClass: 'text-violet-700 border-violet-200',
    desc: 'Prometheus v3 + Grafana dashboards voor metrics. Loki + Promtail voor centralized logging. Alertmanager voor alerts. Uptime Kuma voor uptime monitoring. structlog JSON logging met request-ID correlatie. Tenant audit logging (23 mutation endpoints). Health checks: /health/live + /health/ready.',
  },
]

// ════════════════════════════════════════════════════════════════════
// COLUMN LABELS — Per view
// ════════════════════════════════════════════════════════════════════

interface ColLabel { text: string; x: number; chipClass: string }

const softwareColLabels: ColLabel[] = [
  { text: 'Clients',            x: 7.5,  chipClass: 'bg-violet-50 text-violet-600 border-violet-200' },
  { text: 'Presentatielaag',    x: 22.5, chipClass: 'bg-blue-50 text-blue-600 border-blue-200' },
  { text: 'API & Core',         x: 42,   chipClass: 'bg-emerald-50 text-emerald-600 border-emerald-200' },
  { text: 'Business Modules',   x: 65,   chipClass: 'bg-amber-50 text-amber-600 border-amber-200' },
  { text: 'Data & Integraties', x: 88,   chipClass: 'bg-pink-50 text-pink-600 border-pink-200' },
]
const infraColLabels: ColLabel[] = [
  { text: 'Extern',    x: 7.5,  chipClass: 'bg-violet-50 text-violet-600 border-violet-200' },
  { text: 'Ingress',   x: 22.5, chipClass: 'bg-blue-50 text-blue-600 border-blue-200' },
  { text: 'Compute',   x: 42,   chipClass: 'bg-emerald-50 text-emerald-600 border-emerald-200' },
  { text: 'Services',  x: 65,   chipClass: 'bg-amber-50 text-amber-600 border-amber-200' },
  { text: 'Opslag',    x: 88,   chipClass: 'bg-pink-50 text-pink-600 border-pink-200' },
]
const toolingColLabels: ColLabel[] = [
  { text: 'Frontend',       x: 10,  chipClass: 'bg-blue-50 text-blue-600 border-blue-200' },
  { text: 'API',            x: 30,  chipClass: 'bg-emerald-50 text-emerald-600 border-emerald-200' },
  { text: 'Core Services',  x: 50,  chipClass: 'bg-amber-50 text-amber-600 border-amber-200' },
  { text: 'Data',           x: 70,  chipClass: 'bg-pink-50 text-pink-600 border-pink-200' },
  { text: 'DevOps',         x: 90,  chipClass: 'bg-violet-50 text-violet-600 border-violet-200' },
]

// ════════════════════════════════════════════════════════════════════
// COMPUTED — Select data based on active view
// ════════════════════════════════════════════════════════════════════

function pick<T>(sw: T, infra: T, tool: T): T {
  return activeView.value === 'software' ? sw : activeView.value === 'infra' ? infra : tool
}

const nodes = computed(() => pick(softwareNodes, infraNodes, toolingNodes))
const connDefs = computed(() => pick(softwareConnDefs, infraConnDefs, toolingConnDefs))
const securityBadges = computed(() => pick(softwareBadges, infraBadges, toolingBadges))
const securityZoneLabels = computed(() => pick(softwareZoneLabels, infraZoneLabels, toolingZoneLabels))
const zoneRects = computed(() => pick(softwareZoneRects, infraZoneRects, toolingZoneRects))
const columnLabels = computed(() => pick(softwareColLabels, infraColLabels, toolingColLabels))

const nodeTips = computed(() => pick(softwareNodeTips, infraNodeTips, toolingNodeTips))
const connTipMap = computed(() => pick(softwareConnTips, infraConnTips, toolingConnTips))
const badgeTipMap = computed(() => pick(softwareBadgeTips, infraBadgeTips, toolingBadgeTips))
const zoneTipMap = computed(() => pick(softwareZoneTips, infraZoneTips, toolingZoneTips))

type ColBg = { x: number; w: number; fill: string; stroke: string }
const _defaultColBgs: ColBg[] = [
  { x: 1,  w: 13, fill: '#f5f3ff', stroke: '#ddd6fe' },
  { x: 16, w: 13, fill: '#eff6ff', stroke: '#bfdbfe' },
  { x: 31, w: 22, fill: '#ecfdf5', stroke: '#a7f3d0' },
  { x: 55, w: 20, fill: '#fefce8', stroke: '#fde68a' },
  { x: 77, w: 22, fill: '#fdf2f8', stroke: '#fbcfe8' },
]
const _toolingColBgs: ColBg[] = [
  { x: 2,  w: 16, fill: '#eff6ff', stroke: '#bfdbfe' },
  { x: 22, w: 16, fill: '#ecfdf5', stroke: '#a7f3d0' },
  { x: 42, w: 16, fill: '#fefce8', stroke: '#fde68a' },
  { x: 62, w: 16, fill: '#fdf2f8', stroke: '#fbcfe8' },
  { x: 82, w: 16, fill: '#f5f3ff', stroke: '#ddd6fe' },
]
const colBgs = computed(() => activeView.value === 'tooling' ? _toolingColBgs : _defaultColBgs)

// ════════════════════════════════════════════════════════════════════
// CONNECTION PATHS
// ════════════════════════════════════════════════════════════════════

const connStyles: Record<string, { color: string; colorKey: string; dash: string; animate: boolean }> = {
  http:     { color: '#34d399', colorKey: 'green',  dash: '3 2',           animate: true },
  queue:    { color: '#60a5fa', colorKey: 'blue',   dash: '1 1.5',         animate: false },
  webhook:  { color: '#a78bfa', colorKey: 'violet', dash: '4 1.5 1 1.5',  animate: true },
  internal: { color: '#9ca3af', colorKey: 'gray',   dash: '',              animate: false },
}

function getNode(id: string) { return nodes.value.find(n => n.id === id) }

const connections = computed(() => {
  return connDefs.value.map(def => {
    const from = getNode(def.from)
    const to = getNode(def.to)
    if (!from || !to) return null
    const x1 = from.x, y1 = from.y + (def.oY || 0)
    const x2 = to.x,   y2 = to.y + (def.oY || 0)
    const dx = x2 - x1
    return {
      id: def.id, fromId: def.from, toId: def.to, type: def.type,
      path: `M ${x1},${y1} C ${x1 + dx * 0.4},${y1} ${x2 - dx * 0.4},${y2} ${x2},${y2}`,
      ...(connStyles[def.type] || connStyles.http),
    }
  }).filter(Boolean) as Array<{ id: string; fromId: string; toId: string; type: string; path: string; color: string; colorKey: string; dash: string; animate: boolean }>
})

// ════════════════════════════════════════════════════════════════════
// TOOLTIP
// ════════════════════════════════════════════════════════════════════

const tooltipContent = computed(() => {
  if (hoveredZone.value && zoneTipMap.value[hoveredZone.value]) return zoneTipMap.value[hoveredZone.value]
  if (hoveredBadge.value && badgeTipMap.value[hoveredBadge.value]) return badgeTipMap.value[hoveredBadge.value]
  if (hoveredNode.value && nodeTips.value[hoveredNode.value]) return nodeTips.value[hoveredNode.value]
  if (hoveredConn.value && connTipMap.value[hoveredConn.value]) return connTipMap.value[hoveredConn.value]
  return null
})

const tooltipDotClass = computed(() => {
  if (hoveredZone.value) {
    const c: Record<string, string> = { public: 'bg-red-400', trust: 'bg-blue-400', tenant: 'bg-amber-400', dmz: 'bg-red-400', docker: 'bg-blue-400', storage: 'bg-amber-400' }
    return c[hoveredZone.value] || 'bg-gray-400'
  }
  if (hoveredBadge.value) return 'bg-orange-400'
  if (hoveredNode.value) return 'bg-gray-500'
  if (hoveredConn.value) {
    const conn = connections.value.find(c => c.id === hoveredConn.value)
    if (!conn) return 'bg-gray-400'
    const m: Record<string, string> = { green: 'bg-emerald-400', blue: 'bg-blue-400', violet: 'bg-violet-400', gray: 'bg-gray-400' }
    return m[conn.colorKey] || 'bg-gray-400'
  }
  return 'bg-gray-400'
})

const tooltipStyle = computed(() => {
  if (!containerRef.value || !hoveredEl.value) return {}
  const cRect = containerRef.value.getBoundingClientRect()
  const elRect = hoveredEl.value.getBoundingClientRect()
  const tipW = 290; const gap = 10

  const elCX = elRect.left + elRect.width / 2 - cRect.left
  const elTop = elRect.top - cRect.top
  const elBot = elRect.bottom - cRect.top
  const elLeft = elRect.left - cRect.left
  const elRight = elRect.right - cRect.left
  const elCY = elRect.top + elRect.height / 2 - cRect.top

  // Score directions to avoid overlapping highlighted connections
  const score: Record<string, number> = { top: 0, bottom: 0, left: 0, right: 0 }
  let hlConns: typeof connections.value = []
  if (hoveredNode.value) {
    hlConns = connections.value.filter(c => c.fromId === hoveredNode.value || c.toId === hoveredNode.value)
  } else if (hoveredBadge.value) {
    const badge = securityBadges.value.find(b => b.id === hoveredBadge.value)
    if (badge) hlConns = connections.value.filter(c => badge.connIds.includes(c.id))
  }
  for (const conn of hlConns) {
    const from = getNode(conn.fromId); const to = getNode(conn.toId)
    if (!from || !to) continue
    const def = connDefs.value.find(d => d.id === conn.id)
    const oY = def?.oY || 0
    const x1 = from.x, y1 = from.y + oY, x2 = to.x, y2 = to.y + oY, dx = x2 - x1
    const cx1 = x1 + dx * 0.4, cx2 = x2 - dx * 0.4
    for (const t of [0, 0.25, 0.5, 0.75, 1]) {
      const u = 1 - t
      const px = (u*u*u*x1 + 3*u*u*t*cx1 + 3*u*t*t*cx2 + t*t*t*x2) / 100 * cRect.width
      const py = (u*u*u*y1 + 3*u*u*t*y1 + 3*u*t*t*y2 + t*t*t*y2) / 100 * cRect.height
      const ddx = px - elCX, ddy = py - elCY
      const dist = Math.sqrt(ddx*ddx + ddy*ddy)
      if (dist < 1) continue
      const prox = 1 + 200 / (dist + 20)
      const wx = (Math.abs(ddx) / dist) * prox, wy = (Math.abs(ddy) / dist) * prox
      if (ddy < 0) score.top += wy; else score.bottom += wy
      if (ddx < 0) score.left += wx; else score.right += wx
    }
  }

  const candidates = [
    { pos: 'top',    s: score.top,    ok: elTop > 100 },
    { pos: 'bottom', s: score.bottom, ok: cRect.height - elBot > 100 },
    { pos: 'left',   s: score.left,   ok: elLeft > tipW + gap },
    { pos: 'right',  s: score.right,  ok: cRect.width - elRight > tipW + gap },
  ].sort((a, b) => { if (a.ok !== b.ok) return a.ok ? -1 : 1; return a.s - b.s })
  const pick = candidates[0].pos
  tooltipPlacement.value = pick

  let left: number, top: number
  if (pick === 'top')    { left = elCX - tipW / 2; top = elTop - gap }
  else if (pick === 'bottom') { left = elCX - tipW / 2; top = elBot + gap }
  else if (pick === 'left')   { left = elLeft - tipW - gap; top = elCY }
  else                        { left = elRight + gap; top = elCY }

  if (left + tipW > cRect.width - 8) left = cRect.width - tipW - 8
  if (left < 8) left = 8
  if (top < 4) top = 4
  return { left: left + 'px', top: top + 'px' }
})

// ════════════════════════════════════════════════════════════════════
// INTERACTION — Opacity helpers
// ════════════════════════════════════════════════════════════════════

function connOpacity(conn: typeof connections.value[0]) {
  if (hoveredBadge.value) {
    const badge = securityBadges.value.find(b => b.id === hoveredBadge.value)
    return badge?.connIds.includes(conn.id) ? 1 : 0.08
  }
  if (hoveredNode.value) return (conn.fromId === hoveredNode.value || conn.toId === hoveredNode.value) ? 1 : 0.08
  if (hoveredConn.value) return conn.id === hoveredConn.value ? 1 : 0.08
  return conn.colorKey === 'gray' ? 0.35 : 0.7
}

function nodeOpacity(node: NodeDef) {
  if (!hoveredNode.value && !hoveredConn.value && !hoveredBadge.value) return 'opacity-100'
  if (hoveredBadge.value) {
    const badge = securityBadges.value.find(b => b.id === hoveredBadge.value)
    if (!badge) return 'opacity-100'
    const related = new Set<string>()
    for (const cid of badge.connIds) {
      const c = connections.value.find(c => c.id === cid)
      if (c) { related.add(c.fromId); related.add(c.toId) }
    }
    return related.has(node.id) ? 'opacity-100' : 'opacity-20'
  }
  if (hoveredNode.value === node.id) return 'opacity-100'
  if (hoveredConn.value) {
    const c = connections.value.find(c => c.id === hoveredConn.value)
    return c && (c.fromId === node.id || c.toId === node.id) ? 'opacity-100' : 'opacity-20'
  }
  if (hoveredNode.value) {
    return connections.value.some(c =>
      (c.fromId === hoveredNode.value && c.toId === node.id) ||
      (c.toId === hoveredNode.value && c.fromId === node.id)
    ) ? 'opacity-100' : 'opacity-20'
  }
  return 'opacity-100'
}

function zoneOpacity(zone: ZoneLabelDef) {
  if (!hoveredNode.value && !hoveredConn.value && !hoveredBadge.value && !hoveredZone.value) return 'opacity-80'
  if (hoveredZone.value === zone.id) return 'opacity-100'
  if (hoveredZone.value) return 'opacity-30'
  return 'opacity-40'
}

function badgeOpacity(badge: BadgeDef) {
  if (!hoveredNode.value && !hoveredConn.value && !hoveredBadge.value) return 'opacity-100'
  if (hoveredBadge.value === badge.id) return 'opacity-100'
  if (hoveredBadge.value) return 'opacity-20'
  if (hoveredConn.value && badge.connIds.includes(hoveredConn.value)) return 'opacity-100'
  if (hoveredConn.value || hoveredNode.value) return 'opacity-30'
  return 'opacity-100'
}
</script>

<style scoped>
.topology-flow {
  animation: dash-flow 1.5s linear infinite;
}
@keyframes dash-flow {
  from { stroke-dashoffset: 10; }
  to { stroke-dashoffset: 0; }
}

svg { overflow: visible; }
svg path, svg line { vector-effect: non-scaling-stroke; }

.layer-chip {
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.03em;
  padding: 4px 12px;
  border-radius: 9999px;
  border-width: 1px;
  border-style: solid;
  white-space: nowrap;
  backdrop-filter: blur(4px);
}

.shield-badge {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 8px;
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 2px 6px;
  border-radius: 6px;
  border-width: 1px;
  border-style: solid;
  white-space: nowrap;
  cursor: pointer;
  backdrop-filter: blur(4px);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.badge-red    { background: #fef2f2; color: #dc2626; border-color: #fca5a5; }
.badge-blue   { background: #eff6ff; color: #2563eb; border-color: #93c5fd; }
.badge-violet { background: #f5f3ff; color: #7c3aed; border-color: #c4b5fd; }
.badge-amber  { background: #fffbeb; color: #d97706; border-color: #fcd34d; }

.zone-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 2.5px 8px;
  border-radius: 9999px;
  border-width: 1px;
  border-style: dashed;
  white-space: nowrap;
  cursor: pointer;
  backdrop-filter: blur(4px);
}
.zone-red   { background: #fef2f2cc; color: #dc2626; border-color: #fca5a5; }
.zone-blue  { background: #eff6ffcc; color: #2563eb; border-color: #93c5fd; }
.zone-amber { background: #fffbebcc; color: #d97706; border-color: #fcd34d; }

.tooltip-enter-active {
  transition: opacity 0.15s ease-out, transform 0.15s ease-out;
}
.tooltip-leave-active {
  transition: opacity 0.1s ease-in, transform 0.1s ease-in;
}
.tooltip-enter-from,
.tooltip-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
