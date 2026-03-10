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
    content: 'mt-5 md:mt-15',
  },

  // === Page Header (titel links, acties rechts) ===
  pageHeader: {
    row: 'flex items-center justify-between mb-6',
    rowResponsive: 'flex flex-col md:flex-row md:items-center justify-between gap-3 mb-6',
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
    sectionLabel: 'px-3 pt-5 pb-1 text-[10px] font-semibold uppercase tracking-widest text-muted select-none',
  },

  // === Lijsten ===
  list: {
    divider: 'divide-y divide-navy-100',
    item: 'p-4 md:p-6 flex items-center justify-between hover:bg-surface transition-colors',
    sectionHeader: 'flex items-center justify-between p-4 md:p-6 lg:p-8 border-b border-navy-100',
    empty: 'p-12 text-center',
  },

  // === Empty State ===
  emptyState: {
    wrapper: 'flex flex-col items-center justify-center py-16 px-6 text-center',
    iconWrap: 'w-14 h-14 rounded-2xl bg-navy-50 flex items-center justify-center mb-4',
    icon: 'text-navy-300',
    title: 'text-base font-semibold text-navy-900 mb-1',
    description: 'text-sm text-body max-w-sm',
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

  // === Stat Cards (Platform Widgets) ===
  stat: {
    card: 'rounded-xl border border-navy-100 bg-white p-5 flex items-start gap-4 transition-shadow',
    cardClickable: 'hover:shadow-md cursor-pointer',
    iconWrap: 'rounded-xl p-2.5 flex-shrink-0 flex items-center justify-center',
    iconVariant: {
      primary: 'bg-primary-50 text-primary-600',
      accent: 'bg-accent-50 text-accent-700',
      green: 'bg-green-50 text-green-600',
      red: 'bg-red-50 text-red-600',
      default: 'bg-navy-50 text-navy-400',
    } as Record<string, string>,
    value: 'text-2xl font-bold text-navy-900',
    label: 'text-sm text-body mt-0.5',
    sub: 'text-xs text-muted mt-1',
    skeleton: 'h-6 w-24 bg-navy-50 rounded animate-pulse',
  },

  // === Pulse Bar (Platform Widgets) ===
  pulse: {
    bar: 'flex flex-wrap gap-2 mb-4',
    item: 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium',
    dot: 'w-2 h-2 rounded-full flex-shrink-0',
    severity: {
      error: 'bg-red-50 text-red-700',
      warning: 'bg-yellow-50 text-yellow-700',
      ok: 'bg-green-50 text-green-700',
    } as Record<string, string>,
    dotColor: {
      error: 'bg-red-500',
      warning: 'bg-yellow-500',
      ok: 'bg-green-500',
    } as Record<string, string>,
  },

  // === Expandable Chip (inline badge met icon, klapt open on click) ===
  chip: {
    base: 'inline-flex items-center gap-1 translate-y-px rounded-full transition-all duration-300 cursor-pointer',
    expanded: 'px-2 py-0.5',
    icon: 'shrink-0',
    label: 'text-[10px] font-medium whitespace-nowrap overflow-hidden transition-all duration-300',
    variant: {
      error: { bg: 'bg-red-50', text: 'text-red-700' },
      purple: { bg: 'bg-purple-50', text: 'text-purple-800' },
      success: { bg: 'bg-green-50', text: 'text-green-700' },
      warning: { bg: 'bg-yellow-50', text: 'text-yellow-700' },
      info: { bg: 'bg-accent-50', text: 'text-accent-700' },
      default: { bg: 'bg-navy-50', text: 'text-navy-600' },
    } as Record<string, { bg: string; text: string }>,
  },

  // === Export Buttons ===
  export: {
    btn: 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed',
    csv: 'bg-green-50 text-green-700 hover:bg-green-100',
    csvIcon: 'text-green-600',
    pdf: 'bg-red-50 text-red-700 hover:bg-red-100',
    pdfIcon: 'text-red-600',
  },

  // === Tabellen ===
  table: {
    wrapper: 'overflow-x-auto',
    base: 'min-w-full divide-y divide-navy-200 text-sm table-fixed',
    thead: 'bg-white text-navy-700 font-semibold',
    th: 'px-4 h-[42px] text-left',
    thRight: 'text-right',
    thCenter: 'text-center',
    thSortable: 'cursor-pointer select-none hover:text-navy-900',
    tbody: 'bg-white divide-y divide-navy-50',
    row: 'hover:bg-surface transition-colors',
    rowClickable: 'cursor-pointer',
    td: 'px-4 py-3',
    tdRight: 'text-right',
    tdCenter: 'text-center',
    tdMuted: 'text-body',
    tdBold: 'font-medium text-navy-900',
    expandedRow: 'bg-surface px-6 py-4',
    expandedLabel: 'text-muted text-xs uppercase tracking-wide mb-1',
    pagination: 'flex items-center justify-between px-4 py-3 border-t border-navy-100',
    tfoot: 'bg-navy-50 border-t-2 border-navy-200',
    tfootCell: 'px-4 py-3 font-bold text-navy-900',
  },

  // === Bottom Navigation (Mobile) ===
  bottomNav: {
    bar: 'fixed bottom-0 left-0 right-0 z-40 bg-white border-t border-navy-100 flex items-center justify-around px-2 py-2 md:hidden',
    item: 'flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg transition-colors min-w-0',
    itemActive: 'text-primary-600',
    itemInactive: 'text-navy-300 hover:text-navy-600',
    label: 'text-[10px] font-medium truncate',
  },
}
