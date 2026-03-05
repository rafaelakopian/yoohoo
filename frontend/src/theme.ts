/**
 * Yoohoo — Centraal Thema
 *
 * Kleuren afgeleid van yoohoo.nl:
 *   navy-900  (#202b40)  — donker grijs/navy, headers & titels
 *   primary-600 (#cd095b) — magenta/roze, CTAs & knoppen
 *   accent-700  (#066aab) — teal blauw, secundaire acties & links
 *   bg-surface  (#f6f7fa) — lichte achtergrond secties
 *   text-body   (#767a81) — standaard bodytekst
 *   text-muted  (#979da8) — secundaire tekst
 */
export const theme = {
  // === Pagina achtergronden ===
  page: {
    bg: 'min-h-screen bg-surface',
    bgCenter: 'min-h-screen flex items-center justify-center bg-surface px-4',
  },

  // === Typografie ===
  text: {
    h1: 'text-3xl font-bold text-navy-900',
    h2: 'text-2xl font-bold text-navy-900',
    h3: 'text-lg font-semibold text-navy-900',
    h4: 'font-medium text-navy-900',
    subtitle: 'text-body mt-2',
    body: 'text-sm text-body',
    muted: 'text-muted',
  },

  // === Knoppen ===
  btn: {
    primary: 'bg-primary-600 text-white py-2.5 px-5 rounded-lg hover:bg-primary-700 active:bg-primary-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-sm',
    primarySm: 'bg-primary-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-primary-700 active:bg-primary-800 transition-colors shadow-sm',
    secondary: 'bg-accent-700 text-white py-2.5 px-5 rounded-lg hover:bg-accent-800 active:bg-accent-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-sm',
    secondarySm: 'bg-accent-700 text-white px-4 py-2 rounded-lg text-sm hover:bg-accent-800 active:bg-accent-900 transition-colors shadow-sm',
    link: 'text-sm text-accent-700 hover:text-accent-800 font-medium transition-colors',
    danger: 'text-sm text-navy-300 hover:text-primary-400 transition-colors',
    dangerFill: 'px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 active:bg-red-800 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
    dangerOutline: 'px-4 py-2 rounded-lg text-sm text-red-600 hover:bg-red-50 transition-colors',
    ghost: 'px-4 py-2 rounded-lg text-sm font-medium text-navy-700 bg-navy-50 hover:bg-navy-100 active:bg-navy-200 transition-colors',
    addInline: 'flex items-center gap-1.5 text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors',
    addInlineIcon: 'w-6 h-6 rounded-full bg-primary-600 text-white flex items-center justify-center',
  },

  // === Formulier ===
  form: {
    label: 'block text-sm font-medium text-navy-700 mb-1',
    input: 'w-full px-3 py-2.5 border border-navy-200 rounded-lg focus:ring-2 focus:ring-accent-200 focus:border-accent-700 outline-none transition bg-white placeholder:text-muted',
    group: 'mb-4',
    groupLast: 'mb-6',
  },

  // === Cards & Containers ===
  card: {
    base: 'bg-white rounded-xl border border-navy-100',
    padded: 'bg-white p-4 md:p-6 lg:p-8 rounded-xl border border-navy-100',
    form: 'bg-white p-6 md:p-8 lg:p-10 rounded-xl border border-navy-100',
  },

  // === Alerts ===
  alert: {
    error: 'mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm',
    success: 'mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm',
    errorInline: 'mt-2 text-sm text-red-600',
  },

  // === Badges ===
  badge: {
    base: 'px-3 py-1 rounded-full text-xs font-medium',
    success: 'bg-green-50 text-green-700 ring-1 ring-green-200',
    warning: 'bg-yellow-50 text-yellow-700 ring-1 ring-yellow-200',
    error: 'bg-red-50 text-red-700 ring-1 ring-red-200',
    default: 'bg-navy-50 text-navy-600 ring-1 ring-navy-200',
    info: 'text-sm text-accent-100 bg-navy-800',
  },

  // === Links ===
  link: {
    primary: 'text-accent-700 hover:text-accent-800 font-medium transition-colors',
  },

  // === Header ===
  header: {
    bar: 'bg-navy-900 shadow-lg',
    title: 'text-xl font-bold text-white',
    userName: 'text-sm text-navy-300',
  },

  // === Sidebar ===
  sidebar: {
    container: 'w-64 bg-white border-r border-navy-100 min-h-[calc(100vh-57px)]',
    navItem: 'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
    navActive: 'bg-accent-50 text-accent-700 font-medium',
    navInactive: 'text-body hover:bg-surface hover:text-navy-900',
  },

  // === Lijsten ===
  list: {
    divider: 'divide-y divide-navy-100',
    item: 'p-4 md:p-6 flex items-center justify-between hover:bg-surface transition-colors',
    sectionHeader: 'flex items-center justify-between p-4 md:p-6 lg:p-8 border-b border-navy-100',
    empty: 'p-12 text-center',
  },

  // === Secties ===
  section: {
    formArea: 'p-4 md:p-6 lg:p-8 border-b border-navy-100 bg-surface',
  },

  // === Timeline (B3) ===
  timeline: {
    line: 'border-l-2 border-navy-200',
    node: 'w-2.5 h-2.5 rounded-full ring-2 ring-white',
    dateHeader: 'text-xs font-semibold text-navy-700 uppercase tracking-wide',
  },

  // === Banner (B1) ===
  banner: {
    warning: 'bg-amber-500 text-white px-4 py-2.5 text-sm font-medium',
  },

  // === Action items (B2) ===
  action: {
    item: 'flex items-center gap-3 px-4 py-3 text-sm rounded-lg transition-colors hover:bg-surface text-body hover:text-navy-900 cursor-pointer',
    itemDanger: 'flex items-center gap-3 px-4 py-3 text-sm rounded-lg transition-colors hover:bg-red-50 text-body hover:text-red-700 cursor-pointer',
    itemDisabled: 'flex items-center gap-3 px-4 py-3 text-sm rounded-lg text-muted cursor-not-allowed opacity-50',
  },
}
