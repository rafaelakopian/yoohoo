import { createRouter, createWebHistory } from 'vue-router'
import { setupGuards } from './guards'
import { AUTH, PLATFORM, ORG, WELCOME, OPS, FINANCE } from './routes'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // --- Auth ---
    {
      path: `${AUTH}/login`,
      name: 'login',
      component: () => import('@/views/platform/auth/LoginView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: `${AUTH}/register`,
      name: 'register',
      component: () => import('@/views/platform/auth/RegisterView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: `${AUTH}/register-success`,
      name: 'register-success',
      component: () => import('@/views/platform/auth/RegisterSuccessView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: `${AUTH}/verify-email`,
      name: 'verify-email',
      component: () => import('@/views/platform/auth/VerifyEmailView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: `${AUTH}/verify-session`,
      name: 'verify-session',
      component: () => import('@/views/platform/auth/VerifySessionView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: `${AUTH}/forgot-password`,
      name: 'forgot-password',
      component: () => import('@/views/platform/auth/ForgotPasswordView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: `${AUTH}/reset-password`,
      name: 'reset-password',
      component: () => import('@/views/platform/auth/ResetPasswordView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: `${AUTH}/account-recovery`,
      name: 'account-recovery',
      component: () => import('@/views/platform/auth/AccountRecoveryView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: `${AUTH}/accept-invite`,
      name: 'accept-invite',
      component: () => import('@/views/platform/auth/AcceptInviteView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: `${AUTH}/confirm-email-change`,
      name: 'confirm-email-change',
      component: () => import('@/views/platform/auth/ConfirmEmailChangeView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: `${AUTH}/account`,
      name: 'account',
      component: () => import('@/views/platform/auth/AccountSettingsView.vue'),
      meta: { requiresAuth: true, requiresTenant: false },
    },

    // --- Welcome (org / collaboration selection) ---
    {
      path: WELCOME,
      name: 'welcome',
      component: () => import('@/views/platform/WelcomeView.vue'),
      meta: { requiresAuth: true, requiresTenant: false },
    },
    {
      path: '/create-org',
      name: 'create-org',
      component: () => import('@/views/platform/CreateOrgWizardView.vue'),
      meta: { requiresAuth: true, requiresTenant: false },
    },

    // --- Platform Admin ---
    {
      path: PLATFORM,
      name: 'platform',
      component: () => import('@/views/platform/admin/AdminDashboardView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true },
    },
    {
      path: `${PLATFORM}/orgs`,
      name: 'platform-orgs',
      component: () => import('@/views/platform/admin/tenants/AdminTenantsView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${PLATFORM}/access`,
      component: () => import('@/views/platform/admin/PlatformAccessView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['platform.view_users'] },
      redirect: `${PLATFORM}/access/users`,
      children: [
        {
          path: 'users',
          name: 'platform-access-users',
          component: () => import('@/views/platform/admin/PlatformUsersView.vue'),
        },
        {
          path: 'groups',
          name: 'platform-access-groups',
          component: () => import('@/views/platform/admin/groups/AdminPlatformGroupsView.vue'),
          meta: { requiresSuperAdmin: true },
        },
        {
          path: 'groups/:groupId',
          name: 'platform-access-group-detail',
          component: () => import('@/views/platform/admin/groups/AdminPlatformGroupDetailView.vue'),
          meta: { requiresSuperAdmin: true },
        },
      ],
    },
    // Legacy redirects
    {
      path: `${PLATFORM}/users`,
      redirect: `${PLATFORM}/access/users`,
    },
    {
      path: `${PLATFORM}/groups`,
      redirect: `${PLATFORM}/access/groups`,
    },
    {
      path: `${PLATFORM}/groups/:groupId`,
      redirect: (to) => `${PLATFORM}/access/groups/${to.params.groupId}`,
    },
    {
      path: `${PLATFORM}/audit-logs`,
      name: 'platform-audit-logs',
      component: () => import('@/views/platform/admin/audit/AdminAuditLogsView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['platform.view_audit_logs'] },
    },
    {
      path: `${PLATFORM}/orgs/:tenantId/groups`,
      name: 'platform-tenant-groups',
      component: () => import('@/views/platform/admin/groups/AdminTenantGroupsView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${PLATFORM}/orgs/:tenantId/groups/:groupId`,
      name: 'platform-tenant-group-detail',
      component: () => import('@/views/platform/admin/groups/AdminTenantGroupDetailView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${PLATFORM}/topology`,
      name: 'platform-topology',
      component: () => import('@/views/platform/admin/infra/ServiceTopologyView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },

    // --- Platform Notifications ---
    {
      path: `${PLATFORM}/notifications`,
      name: 'platform-notifications-admin',
      component: () => import('@/views/platform/admin/PlatformNotificationsAdminView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['platform_notifications.manage'] },
    },
    {
      path: `${PLATFORM}/notifications/inbox`,
      name: 'platform-notifications-inbox',
      component: () => import('@/views/platform/PlatformNotificationInboxView.vue'),
      meta: { requiresAuth: true, requiresTenant: false },
    },

    // --- Platform Operations ---
    {
      path: `${PLATFORM}/orgs/:tenantId/detail`,
      name: 'platform-org-detail',
      component: () => import('@/views/platform/operations/Tenant360View.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['operations.view_tenant_detail'] },
    },
    {
      path: `${PLATFORM}/orgs/onboarding`,
      name: 'platform-orgs-onboarding',
      component: () => import('@/views/platform/operations/OnboardingView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['operations.view_onboarding'] },
    },
    {
      path: `${OPS}/jobs`,
      name: 'ops-jobs',
      component: () => import('@/views/platform/operations/JobMonitorView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['operations.view_jobs'] },
    },
    // Legacy redirects
    { path: OPS, redirect: `${PLATFORM}/orgs` },
    { path: `${OPS}/tenants/:tenantId`, redirect: to => ({ name: 'platform-org-detail', params: { tenantId: to.params.tenantId } }) },
    { path: `${OPS}/onboarding`, redirect: `${PLATFORM}/orgs/onboarding` },
    { path: `${OPS}/users`, redirect: `${PLATFORM}/orgs` },

    // --- Platform Finance ---
    {
      path: `${FINANCE}/revenue`,
      name: 'finance-revenue',
      component: () => import('@/views/platform/finance/RevenueView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['finance.view_dashboard'] },
    },
    {
      path: `${FINANCE}/invoices`,
      name: 'finance-invoices',
      component: () => import('@/views/platform/finance/InvoicesView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['billing.view'] },
    },
    {
      path: `${FINANCE}/outstanding`,
      name: 'finance-outstanding',
      component: () => import('@/views/platform/finance/OutstandingPaymentsView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['finance.view_dashboard'] },
    },
    {
      path: `${FINANCE}/tax`,
      name: 'finance-tax',
      component: () => import('@/views/platform/finance/TaxReportView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['finance.export_reports'] },
    },
    {
      path: `${FINANCE}/plans`,
      name: 'finance-plans',
      component: () => import('@/views/platform/finance/PlanManagerView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['platform.manage_orgs'] },
    },
    {
      path: `${FINANCE}/subscriptions`,
      name: 'finance-subscriptions',
      component: () => import('@/views/platform/finance/SubscriptionsView.vue'),
      meta: {
        requiresAuth: true,
        requiresTenant: false,
        requiresPlatformAccess: true,
        requiresAnyPermission: ['billing.view'],
      },
    },
    {
      path: '/platform/features/catalog',
      name: 'platform-feature-catalog',
      component: () => import('@/views/platform/admin/FeatureCatalogView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['platform.manage_feature_catalog'] },
    },
    {
      path: '/platform/orgs/:tenantId/features',
      name: 'platform-tenant-features',
      component: () => import('@/views/platform/admin/TenantFeatureAdminView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresPlatformAccess: true, requiresAnyPermission: ['platform.manage_tenant_features'] },
    },

    // --- Org (tenant-scoped, slug in URL) ---
    {
      path: `${ORG}/:slug/dashboard`,
      name: 'org-dashboard',
      component: () => import('@/views/products/school/DashboardView.vue'),
      meta: { requiresAuth: true, requiresTenant: true },
    },
    {
      path: `${ORG}/:slug/students`,
      name: 'org-students',
      component: () => import('@/views/products/school/StudentsView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['students.view', 'students.view_assigned', 'students.view_own'] },
    },
    {
      path: `${ORG}/:slug/attendance`,
      name: 'org-attendance',
      component: () => import('@/views/products/school/AttendanceView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['attendance.view', 'attendance.view_assigned', 'attendance.view_own'] },
    },
    {
      path: `${ORG}/:slug/schedule`,
      name: 'org-schedule',
      component: () => import('@/views/products/school/ScheduleView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['schedule.view', 'schedule.view_assigned'] },
    },
    {
      path: `${ORG}/:slug/holidays`,
      name: 'org-holidays',
      component: () => import('@/views/products/school/HolidaysView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['schedule.view', 'schedule.view_assigned'] },
    },
    {
      path: `${ORG}/:slug/notifications`,
      name: 'org-notifications',
      component: () => import('@/views/products/school/NotificationSettingsView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['notifications.view'] },
    },
    {
      path: `${ORG}/:slug/users`,
      name: 'org-users',
      component: () => import('@/views/products/school/InvitationsView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['invitations.view', 'invitations.manage', 'org_settings.view'] },
    },
    {
      path: `${ORG}/:slug/collaborations`,
      name: 'org-collaborations',
      component: () => import('@/views/products/school/CollaborationsView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['collaborations.view', 'collaborations.manage'] },
    },
    {
      path: `${ORG}/:slug/permissions`,
      name: 'org-permissions',
      component: () => import('@/views/products/school/PermissionsView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['org_settings.view'] },
    },
    {
      path: `${ORG}/:slug/permissions/:groupId`,
      name: 'org-permission-detail',
      component: () => import('@/views/products/school/PermissionDetailView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['org_settings.view'] },
    },

    // --- Features & Upgrades ---
    {
      path: `${ORG}/:slug/upgrade`,
      name: 'org-upgrade',
      component: () => import('@/views/products/school/UpgradeView.vue'),
      meta: { requiresAuth: true, requiresTenant: true },
    },
    {
      path: `${ORG}/:slug/subscription/paused`,
      name: 'org-subscription-paused',
      component: () => import('@/views/products/school/SubscriptionPausedView.vue'),
      meta: { requiresAuth: true, requiresTenant: true },
    },

    // --- Billing ---
    {
      path: `${ORG}/:slug/billing`,
      name: 'org-billing',
      component: () => import('@/views/products/school/BillingDashboardView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['billing.view', 'billing.view_own'] },
    },
    {
      path: `${ORG}/:slug/billing/plans`,
      name: 'org-billing-plans',
      component: () => import('@/views/products/school/TuitionPlansView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['billing.manage'] },
    },
    {
      path: `${ORG}/:slug/billing/students`,
      name: 'org-billing-students',
      component: () => import('@/views/products/school/StudentBillingView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['billing.manage'] },
    },
    {
      path: `${ORG}/:slug/billing/invoices`,
      name: 'org-billing-invoices',
      component: () => import('@/views/products/school/InvoicesView.vue'),
      meta: { requiresAuth: true, requiresTenant: true, requiresAnyPermission: ['billing.view', 'billing.view_own'] },
    },

    // --- Smart root redirect (handled by guard) ---
    {
      path: '/',
      name: 'root',
      component: { render: () => null },
      meta: { requiresAuth: false },
    },

    // --- Fallback ---
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
    },
  ],
})

setupGuards(router)

export default router
