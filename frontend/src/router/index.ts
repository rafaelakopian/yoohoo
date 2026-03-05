import { createRouter, createWebHistory } from 'vue-router'
import { setupGuards } from './guards'
import { AUTH, PLATFORM, ORG, WELCOME, OPS } from './routes'

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

    // --- Platform Admin ---
    {
      path: PLATFORM,
      name: 'platform',
      component: () => import('@/views/platform/admin/AdminDashboardView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${PLATFORM}/orgs`,
      name: 'platform-orgs',
      component: () => import('@/views/platform/admin/tenants/AdminTenantsView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${PLATFORM}/users`,
      name: 'platform-users',
      component: () => import('@/views/platform/admin/users/AdminUsersView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${PLATFORM}/users/:userId`,
      name: 'platform-user-detail',
      component: () => import('@/views/platform/admin/users/AdminUserDetailView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${PLATFORM}/audit-logs`,
      name: 'platform-audit-logs',
      component: () => import('@/views/platform/admin/audit/AdminAuditLogsView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
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
      path: `${PLATFORM}/groups`,
      name: 'platform-groups',
      component: () => import('@/views/platform/admin/groups/AdminPlatformGroupsView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${PLATFORM}/groups/:groupId`,
      name: 'platform-group-detail',
      component: () => import('@/views/platform/admin/groups/AdminPlatformGroupDetailView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${PLATFORM}/topology`,
      name: 'platform-topology',
      component: () => import('@/views/platform/admin/infra/ServiceTopologyView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },

    // --- Platform Operations ---
    {
      path: OPS,
      name: 'ops-dashboard',
      component: () => import('@/views/platform/operations/OperationsDashboardView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${OPS}/tenants/:tenantId`,
      name: 'ops-tenant-360',
      component: () => import('@/views/platform/operations/Tenant360View.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${OPS}/users`,
      name: 'ops-user-lookup',
      component: () => import('@/views/platform/operations/UserLookupView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
    },
    {
      path: `${OPS}/onboarding`,
      name: 'ops-onboarding',
      component: () => import('@/views/platform/operations/OnboardingView.vue'),
      meta: { requiresAuth: true, requiresTenant: false, requiresSuperAdmin: true },
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
