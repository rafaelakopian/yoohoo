# CLAUDE.md — Yoohoo SaaS

## BELANGRIJK: Scope

Dit is het **Yoohoo SaaS** project — een multi-tenant muziekschoolverwerkingsplatform.
Wijzig NOOIT bestanden buiten deze repository. Alle wijzigingen blijven binnen `yoohoo/`.

## Project

Yoohoo SaaS is een multi-tenant platform voor muziekschoolbeheer: leerlingadministratie, aanwezigheidsregistratie, roosterbeheer en oudercommunicatie.
Databron: `Aanwezigheidsoverzicht Leerlingen Pianoschool.xlsx` (37 leerlingen, docent Mignon Gotzsch).

## Architectuur

Monolithische backend + SPA frontend, gedeployed via Docker Compose met Nginx reverse proxy.

| Component | Poort (default) | Directory | Technologie |
|-----------|----------------|-----------|-------------|
| API Backend | `${API_PORT}` → 8000 | `backend/` | FastAPI (Python 3.12) |
| Worker | — | `backend/` | arq (async job queue via Redis) |
| Frontend | `${FRONTEND_PORT}` → 1000 (dev) / 3000 (prod) | `frontend/` | Vue 3 + Vite |
| PostgreSQL | `${POSTGRES_PORT}` → 5432 | — | PostgreSQL 16 |
| PgBouncer | 6432 | `pgbouncer/` | Connection pooling (transaction mode) |
| Redis | `${REDIS_PORT}` → 6379 | — | Redis 7 (db=0 app, db=1 arq) |
| Nginx | `${NGINX_PORT}` → 80 | `nginx/` | Reverse proxy |
| Mailpit | 1025 (SMTP) / 8025 (Web) | — | Dev email catcher |

Alle poorten zijn configureerbaar via `.env` (single source of truth). Wijzig alleen `.env` om poorten aan te passen.

### Multi-Tenant Architectuur

- **Database-per-tenant isolatie**: elke tenant krijgt een eigen PostgreSQL database (`ps_t_{slug}_db`)
- **Central database** (`ps_core_db`): gebruikers, tenants, globale configuratie
- **Slug-in-URL routing**: tenant context via URL path (`/api/v1/org/{slug}/...`) i.p.v. headers
- **`resolve_tenant_from_path`** dependency op parent router: slug→UUID lookup met cache
- **TenantDatabaseManager** beheert async engines met lazy caching
- **PgBouncer** transaction pooling: app → PgBouncer → PostgreSQL (asyncpg prepared statements uitgeschakeld)
- **arq worker** voor achtergrondtaken: emails, notificaties, facturatie, cleanup (Redis db=1)

### Backend Architectuur

```
backend/app/
├── main.py              # FastAPI app factory + lifespan (startup/shutdown)
├── config.py            # Pydantic Settings (102 variabelen via .env)
├── dependencies.py      # Dependency injection (Redis, arq, tenant DB sessions)
├── core/                # Infrastructure (31 bestanden)
│   ├── exceptions.py    # Centrale foutafhandeling
│   ├── health.py        # Health, metrics, branding endpoints
│   ├── logging_config.py # Structured logging (structlog)
│   ├── middleware.py     # RequestID, SecurityHeaders, MaxBodySize, Prometheus middleware
│   ├── rate_limiter.py   # Rate limiting (per-tenant, X-Forwarded-For aware)
│   ├── login_throttle.py # Brute force login protection
│   ├── circuit_breaker.py # Circuit breaker patroon (named registry)
│   ├── encryption.py     # Shared Fernet encryption (PBKDF2 key derivation)
│   ├── event_bus.py      # Event publicatie/subscriptie
│   ├── email.py          # EmailSender, send_email_safe() helper
│   ├── email_providers/  # smtp.py, resend.py, brevo.py
│   ├── sms.py            # SMS sending interface
│   ├── sms_providers/    # twilio.py, vonage.py, brevo.py
│   ├── security.py       # JWT creatie en validatie
│   ├── security_emails.py # Security event email builders
│   ├── permissions.py    # PermissionRegistry singleton (auto-discovery)
│   ├── notification_types.py # 14 platformmeldingstypen
│   ├── audit_dependency.py # Audit context dependency
│   ├── metrics.py        # Prometheus metrics
│   ├── geoip.py          # GeoIP lookup for security
│   ├── worker.py         # arq WorkerSettings (9 jobs, 5 cron schedules)
│   └── jobs/             # Background job definitions
│       ├── email.py      # send_email_job
│       ├── notification.py # process_notification_job
│       ├── billing.py    # generate_invoices_job, send_invoice_email_job, send_dunning_reminders_job
│       ├── maintenance.py # cleanup_unverified_users_job, anonymize_archived_accounts_job
│       ├── feature_trials.py # expire_trials_job (02:00), purge_expired_retention_job (02:30)
│       └── retry.py      # Exponential backoff helper, NonRetryableJobError
├── db/                  # Database layer
│   ├── base.py          # CentralBase / TenantBase (SQLAlchemy declarative)
│   ├── central.py       # Central engine + session factory
│   └── tenant.py        # TenantDatabaseManager (per-tenant engines)
└── modules/             # Feature modules (gescheiden per scope)
    ├── platform/        # ← SaaS-platformbreed (central DB)
    │   ├── admin/           # Platform admin (dashboard, users, groups, audit-logs, memberships)
    │   ├── auth/            # Authenticatie & User Management
    │   │   ├── constants.py     # MembershipType enum
    │   │   ├── dependencies.py  # get_current_user, require_permission, get_data_scope
    │   │   ├── models.py        # User, TenantMembership, RefreshToken, Invitation, AuditLog, PermissionGroup, etc.
    │   │   ├── permissions_setup.py # Default groepen (4 tenant + 3 platform)
    │   │   ├── audit.py         # AuditService helper
    │   │   ├── core/            # Login, register, verify, refresh, logout, /me, profile, email-change, delete-account
    │   │   ├── invitation/      # Uitnodigingen (org-scoped + auth-scoped accept/info)
    │   │   ├── collaboration/   # Samenwerkingsverbanden (list, invite, toggle)
    │   │   ├── password/        # Wachtwoord reset + wijzigen
    │   │   ├── permissions/     # Groepen & rechten CRUD (platform_router + tenant_router)
    │   │   ├── session/         # Sessiebeheer (list, revoke, logout-all)
    │   │   └── totp/            # 2FA (TOTP setup, verify, disable, email/SMS codes, phone verify)
    │   ├── billing/         # Platform billing + feature gating
    │   │   ├── router.py        # Plans, subscriptions, providers, invoices, payments (14 endpoints)
    │   │   ├── webhooks/        # Mollie + Stripe webhook handlers + verificatie
    │   │   ├── feature_gate.py  # check_feature_access(), require_feature() dependency
    │   │   ├── feature_router.py # Tenant-scoped: list features, start trial
    │   │   ├── catalog_router.py # Admin: feature catalog CRUD + tenant feature overrides
    │   │   ├── plan_features.py # PlanFeatures schema (4 base + 6 expandable features)
    │   │   ├── trial_service.py # Trial lifecycle (start, reset, extend, expire, purge, force_on/off)
    │   │   └── providers/       # Stripe + Mollie payment provider implementations
    │   ├── tenant_mgmt/     # Tenant/org CRUD, settings, db_provisioner
    │   ├── operations/      # Tenant360, support notes, impersonation, job monitor (19 endpoints)
    │   ├── finance/         # Revenue, outstanding payments, tax reports, dunning (6 endpoints)
    │   ├── notifications/   # Platform notifications (admin CRUD, user inbox, tenant preferences)
    │   ├── members/         # Org member listing (/org/{slug}/access/users)
    │   ├── plugin/          # ProductRegistry, ProductManifest, NavigationRegistry
    │   ├── analytics/       # (placeholder)
    │   └── config_mgmt/     # (placeholder)
    └── products/        # ← Product modules (tenant DB, per org)
        └── school/      # School product (via ProductRegistry)
            ├── router.py        # Parent router (mounts sub-routers)
            ├── path_dependency.py # resolve_tenant_from_path (slug→UUID, cached)
            ├── student/         # Student CRUD, Excel import, parents, teacher assignment (17 endpoints)
            ├── attendance/      # Attendance CRUD, bulk registratie (6 endpoints)
            ├── schedule/        # Slots, lessons, holidays, calendar (19 endpoints)
            ├── notification/    # School-notificaties, voorkeuren, in-app (9 endpoints)
            └── billing/         # Tuition plans, student billing, invoices (12 endpoints)
```

### Permissiesysteem

Dynamisch groepen/permissiesysteem. Elke module registreert permissies bij import via `PermissionRegistry` (singleton, `app/core/permissions.py`).

**51 permissie-codenames** over 11 modules:

| Module | Scope | Permissies |
|--------|-------|-----------|
| `students` | tenant | `view`, `view_own`, `view_assigned`, `create`, `edit`, `delete`, `import`, `manage_parents`, `assign` |
| `attendance` | tenant | `view`, `view_own`, `view_assigned`, `create`, `edit`, `delete` |
| `schedule` | tenant | `view`, `view_assigned`, `manage`, `substitute` |
| `notifications` | tenant | `view`, `manage` |
| `invitations` | tenant | `view`, `manage` |
| `org_settings` | tenant | `view`, `edit` |
| `billing` | platform | `view`, `view_own`, `manage`, `manage_provider`, `refund` |
| `collaborations` | tenant | `view`, `manage` |
| `platform` | platform | `view_stats`, `view_orgs`, `manage_orgs`, `view_users`, `edit_users`, `manage_superadmin`, `manage_memberships`, `manage_groups`, `view_audit_logs`, `manage_feature_catalog`, `manage_tenant_features` |
| `operations` | platform | `view_dashboard`, `view_tenant_detail`, `view_users`, `view_onboarding`, `manage_notes`, `manage_users`, `impersonate`, `view_jobs` |
| `finance` | platform | `view_dashboard`, `export_reports`, `manage_dunning` |
| `platform_notifications` | platform | `view`, `manage`, `manage_preferences` |

**7 default groepen** (4 tenant + 3 platform):

| Groep | Scope | Permissies |
|-------|-------|-----------|
| `beheerder` | tenant | Alle tenant-permissies |
| `docent` | tenant | students.view_assigned/create/edit/delete/import/assign, attendance.view_assigned/create/edit/delete, schedule.view_assigned/manage/substitute, notifications.view, billing.view |
| `ouder` | tenant | students.view_own, attendance.view_own, schedule.view, notifications.view, billing.view_own |
| `medewerker` | tenant | students.view_assigned, attendance.view_assigned/create/edit, schedule.view_assigned/manage, notifications.view |
| `platform-admin` | platform | Alle platform-permissies |
| `support` | platform | platform.view_stats/view_orgs/view_users/view_audit_logs |
| `nieuw` | platform | Geen rechten (landing-groep voor uitgenodigde platformgebruikers) |

**Super admin** (`is_superadmin=True`) bypassed alle permissiechecks.

**DataScope** (drie-weg zichtbaarheid):
- `DataScope.all` — beheerder/superadmin: ziet alles
- `DataScope.assigned` — docent: ziet alleen eigen toegewezen leerlingen
- `DataScope.own` — ouder: ziet alleen eigen kinderen

**Dependencies:**
- `require_permission("students.create")` — vereist specifieke permissie
- `require_any_permission("students.view", "students.view_assigned", "students.view_own")` — vereist minstens één
- `get_data_scope(user, tenant_id, "students")` — retourneert DataScope enum
- `is_data_restricted(user, tenant_id, "students.view")` — True als user alleen view_own heeft (legacy)

## Tech Stack

- **Backend:** Python 3.12, FastAPI 0.135.1, SQLAlchemy 2.0.48 (async), Alembic 1.18.4, structlog 25.5.0, Pydantic 2.12.5
- **Database:** PostgreSQL 16 (asyncpg 0.31.0), Redis 7 (hiredis), PgBouncer 1.23.1
- **Auth:** JWT (PyJWT 2.11.0) + refresh token rotation, pwdlib 0.3.0 (Argon2 + bcrypt), email verificatie (aiosmtplib 5.1.0), 2FA/TOTP (pyotp 2.9.0, segno QR), Fernet encryption (cryptography 46.0.5)
- **Payments:** Stripe 14.4.0, Mollie 3.9.1
- **Frontend:** Vue 3.5.29, TypeScript 5.9.3, Vite 7.3.1, Pinia 3.0.4, Tailwind CSS 4.2.1, Vue Router 5.0.3, Axios 1.13.6
- **Monitoring:** Sentry (sentry-sdk 2.26.1, @sentry/vue 10.41.0), Prometheus (prometheus-client 0.24.1), GeoIP (geoip2 4.8.1)
- **Infra:** Docker Compose, Nginx, PgBouncer, arq 0.27.0 (async job queue), Makefile
- **Testing:** pytest 9.0.2, pytest-asyncio 1.3.0, pytest-cov 7.0.0, factory-boy 3.3.3
- **Security:** pip-audit 2.7.3, ruff (linting)

## API Routes (253 endpoints totaal)

| Prefix | Router | Endpoints | Beschrijving |
|--------|--------|-----------|-------------|
| `/health/*` | `core/health.py` | 3 | Health checks (live, ready, circuit-breakers) |
| `/metrics` | `core/health.py` | 1 | Prometheus metrics |
| `/branding` | `core/health.py` | 1 | Platform branding config |
| `/api/v1/auth/*` | `auth/core/router.py` | 12 | Register, login, refresh, logout, /me, profile, email-change, delete |
| `/api/v1/auth/*` | `auth/password/router.py` | 3 | Forgot/reset/change password |
| `/api/v1/auth/*` | `auth/session/router.py` | 3 | Sessiebeheer (list, revoke, logout-all) |
| `/api/v1/auth/*` | `auth/invitation/router.py` | 2 | Invite-info, accept-invite (public) |
| `/api/v1/auth/2fa/*` | `auth/totp/router.py` | 8 | TOTP, email code, SMS code, phone verify |
| `/api/v1/platform/access/permissions/*` | `auth/permissions/router.py` | 1 | Permissie registry |
| `/api/v1/platform/*` | `admin/router.py` | 28 | Dashboard, users, groups (platform + tenant), audit-logs, memberships |
| `/api/v1/platform/orgs/*` | `tenant_mgmt/router.py` | 9 | Org CRUD, provisioning, settings, self-service |
| `/api/v1/platform/operations/*` | `operations/router.py` | 19 | Tenant360, notes, user actions, impersonate, jobs |
| `/api/v1/platform/billing/*` | `billing/router.py` | 14 | Plans, subscriptions, providers, invoices, payments |
| `/api/v1/webhooks/*` | `billing/webhooks/router.py` | 2 | Mollie + Stripe webhooks |
| `/api/v1/platform/finance/*` | `finance/router.py` | 6 | Revenue, outstanding, tax, dunning |
| `/api/v1/platform/notifications/*` | `notifications/router.py` | 11 | Admin CRUD + user inbox + unread count |
| `/api/v1/platform/features/catalog/*` | `billing/catalog_router.py` | 3 | Feature catalog admin |
| `/api/v1/platform/orgs/{id}/features/*` | `billing/catalog_router.py` | 7 | Tenant feature overrides (force on/off, reset, extend) |
| `/api/v1/platform/products/*` | `plugin/router.py` | 1 | Product registry |
| `/api/v1/org/{slug}/access/invitations/*` | `auth/invitation/router.py` | 5 | Uitnodigingen per org |
| `/api/v1/org/{slug}/collaborations/*` | `auth/collaboration/router.py` | 3 | Samenwerkingen (list, invite, toggle) |
| `/api/v1/org/{slug}/access/*` | `auth/permissions/router.py` | 9 | Groepen & rechten CRUD + my-permissions |
| `/api/v1/org/{slug}/access/users` | `members/router.py` | 1 | Ledenlijst |
| `/api/v1/org/{slug}/features/*` | `billing/feature_router.py` | 2 | Feature status + start trial |
| `/api/v1/org/{slug}/notifications/platform-preferences/*` | `notifications/router.py` | 2 | Platform notification preferences |
| `/api/v1/org/{slug}/students/*` | `products/school/student/router.py` | 17 | Student CRUD, import, parents, teachers |
| `/api/v1/org/{slug}/attendance/*` | `products/school/attendance/router.py` | 6 | Attendance CRUD, bulk |
| `/api/v1/org/{slug}/schedule/*` | `products/school/schedule/router.py` | 19 | Slots, lessons, holidays, calendar |
| `/api/v1/org/{slug}/notifications/*` | `products/school/notification/router.py` | 9 | School-notificaties, voorkeuren, in-app |
| `/api/v1/org/{slug}/tuition/*` | `products/school/billing/router.py` | 12 | Tuition plans, student billing, invoices |

### Auth Endpoints (Core)

| Method | Path | Beschrijving |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Account aanmaken (stuurt verificatie-email) |
| POST | `/api/v1/auth/verify-email` | E-mailadres verifiëren met token |
| POST | `/api/v1/auth/resend-verification` | Verificatie-email opnieuw versturen |
| POST | `/api/v1/auth/login` | Inloggen → JWT tokens of 2FA challenge |
| POST | `/api/v1/auth/refresh` | Token verversing |
| POST | `/api/v1/auth/logout` | Uitloggen (revoke refresh token) |
| GET | `/api/v1/auth/me` | Huidige gebruiker + memberships |

### Password Endpoints

| Method | Path | Beschrijving |
|--------|------|-------------|
| POST | `/api/v1/auth/forgot-password` | Wachtwoord reset aanvragen (rate limited, anti-email-enumeratie) |
| POST | `/api/v1/auth/reset-password` | Wachtwoord resetten met token (rate limited) |
| POST | `/api/v1/auth/change-password` | Wachtwoord wijzigen (authenticated, revoket alle sessies) |

### Session Endpoints

| Method | Path | Beschrijving |
|--------|------|-------------|
| GET | `/api/v1/auth/sessions` | Actieve sessies ophalen (authenticated) |
| DELETE | `/api/v1/auth/sessions/{id}` | Sessie revoking (authenticated) |
| POST | `/api/v1/auth/logout-all` | Alle sessies revoking (authenticated) |

### Invitation Endpoints

| Method | Path | Beschrijving |
|--------|------|-------------|
| POST | `/api/v1/org/{slug}/access/invitations` | Uitnodiging aanmaken (invitations.manage) |
| GET | `/api/v1/org/{slug}/access/invitations` | Pending uitnodigingen ophalen (invitations.view) |
| POST | `/api/v1/org/{slug}/access/invitations/{inv_id}/resend` | Uitnodiging opnieuw versturen (invitations.manage) |
| DELETE | `/api/v1/org/{slug}/access/invitations/{inv_id}` | Uitnodiging revoking (invitations.manage) |
| GET | `/api/v1/auth/invite-info?token=...` | Uitnodigingsinfo ophalen (public) |
| POST | `/api/v1/auth/accept-invite` | Uitnodiging accepteren (public) |

### Permissions Endpoints

| Method | Path | Beschrijving |
|--------|------|-------------|
| GET | `/api/v1/platform/access/permissions/registry` | Alle modules + permissies (platform-scoped, authenticated) |
| GET | `/api/v1/org/{slug}/access/groups` | Groepen voor tenant (org_settings.view) |
| POST | `/api/v1/org/{slug}/access/groups` | Groep aanmaken (org_settings.edit) |
| GET | `/api/v1/org/{slug}/access/groups/{id}` | Groep detail + permissies (org_settings.view) |
| PUT | `/api/v1/org/{slug}/access/groups/{id}` | Groep naam/beschrijving/permissies wijzigen (org_settings.edit) |
| DELETE | `/api/v1/org/{slug}/access/groups/{id}` | Groep verwijderen, niet als is_default (org_settings.edit) |
| GET | `/api/v1/org/{slug}/access/groups/{id}/users` | Users in groep (org_settings.view) |
| POST | `/api/v1/org/{slug}/access/groups/{id}/users` | User aan groep toevoegen (org_settings.edit) |
| DELETE | `/api/v1/org/{slug}/access/groups/{id}/users/{uid}` | User uit groep verwijderen (org_settings.edit) |
| GET | `/api/v1/org/{slug}/access/permissions` | Effectieve permissies huidige user (authenticated) |

### 2FA/TOTP Endpoints

| Method | Path | Beschrijving |
|--------|------|-------------|
| POST | `/api/v1/auth/2fa/setup` | 2FA instellen (authenticated, retourneert QR) |
| POST | `/api/v1/auth/2fa/verify-setup` | 2FA activeren met code |
| POST | `/api/v1/auth/2fa/disable` | 2FA uitschakelen (vereist wachtwoord) |
| POST | `/api/v1/auth/2fa/verify` | 2FA code verifiëren bij login (public, rate limited) |

### Org Endpoints (superadmin: create/provision/delete)

| Method | Path | Beschrijving |
|--------|------|-------------|
| POST | `/api/v1/platform/orgs/` | Organisatie aanmaken (superadmin) |
| GET | `/api/v1/platform/orgs/` | Organisaties ophalen (admin: alle, user: eigen) |
| GET | `/api/v1/platform/orgs/{id}` | Organisatie details (admin of lid) |
| POST | `/api/v1/platform/orgs/{id}/provision` | Organisatie database aanmaken (superadmin) |
| DELETE | `/api/v1/platform/orgs/{id}` | Organisatie verwijderen (superadmin + wachtwoord) |
| GET | `/api/v1/platform/orgs/{id}/settings` | Organisatie-instellingen (admin of org_admin) |
| PUT | `/api/v1/platform/orgs/{id}/settings` | Organisatie-instellingen bijwerken (admin of org_admin) |

### Student Endpoints (tenant-scoped, slug-in-URL)

| Method | Path | Beschrijving |
|--------|------|-------------|
| GET | `/api/v1/org/{slug}/students/` | Leerlingen ophalen (DataScope: all/assigned/own) |
| GET | `/api/v1/org/{slug}/students/my-children` | Eigen kinderen (ouder) |
| GET | `/api/v1/org/{slug}/students/my-students` | Toegewezen leerlingen (docent) |
| GET | `/api/v1/org/{slug}/students/unassigned` | Niet-toegewezen leerlingen |
| POST | `/api/v1/org/{slug}/students/self-assign/{id}` | Zelf-toewijzing (docent) |
| POST | `/api/v1/org/{slug}/students/` | Leerling aanmaken |
| POST | `/api/v1/org/{slug}/students/import` | Excel import (multipart file upload) |
| GET | `/api/v1/org/{slug}/students/{id}` | Leerling details (DataScope check) |
| PUT | `/api/v1/org/{slug}/students/{id}` | Leerling bijwerken (partial update) |
| DELETE | `/api/v1/org/{slug}/students/{id}` | Leerling deactiveren (soft delete) |
| GET | `/api/v1/org/{slug}/students/{id}/teachers` | Docent-koppelingen van leerling |
| POST | `/api/v1/org/{slug}/students/{id}/teachers` | Docent toewijzen |
| DELETE | `/api/v1/org/{slug}/students/{id}/teachers/{uid}` | Docentkoppeling verwijderen |
| POST | `/api/v1/org/{slug}/students/{id}/transfer` | Transfer leerling tussen docenten |

### Attendance Endpoints (tenant-scoped, slug-in-URL)

| Method | Path | Beschrijving |
|--------|------|-------------|
| GET | `/api/v1/org/{slug}/attendance/` | Aanwezigheidsrecords ophalen (paginated, ?student_id=&date_from=&date_to=) |
| POST | `/api/v1/org/{slug}/attendance/` | Aanwezigheidsrecord aanmaken |
| POST | `/api/v1/org/{slug}/attendance/bulk` | Bulk registratie (hele klas in één keer) |
| GET | `/api/v1/org/{slug}/attendance/{id}` | Aanwezigheidsrecord details |
| PUT | `/api/v1/org/{slug}/attendance/{id}` | Aanwezigheidsrecord bijwerken (partial update) |
| DELETE | `/api/v1/org/{slug}/attendance/{id}` | Aanwezigheidsrecord verwijderen (hard delete) |

## Frontend Structuur

```
frontend/src/
├── main.ts, App.vue, style.css, theme.ts
├── api/                 # HTTP client layer (gescheiden per scope)
│   ├── client.ts        # Axios instance + JWT interceptor + tenantUrl() helper
│   ├── platform/        # ← SaaS-platformbreed (13 bestanden)
│   │   ├── auth.ts      # Auth API (login, register, password, sessions, 2FA, invites)
│   │   ├── admin.ts     # Platform admin (users, groups, audit, memberships)
│   │   ├── orgs.ts      # Org/tenant CRUD
│   │   ├── billing.ts   # Platform billing (plans, subscriptions, providers)
│   │   ├── operations.ts # Operations (tenant360, notes, user actions, impersonate)
│   │   ├── finance.ts   # Finance (revenue, outstanding, tax, dunning)
│   │   ├── features.ts  # Feature catalog admin + tenant feature overrides
│   │   ├── notifications.ts # Platform notifications (admin + user inbox)
│   │   ├── branding.ts  # Platform branding
│   │   ├── analytics.ts # Analytics (placeholder)
│   │   ├── products.ts  # Product registry
│   │   └── schools.ts   # School-specific platform API
│   └── products/school/ # ← School product (10 bestanden)
│       ├── students.ts, attendance.ts, schedule.ts, notifications.ts
│       ├── invitations.ts, permissions.ts, collaborations.ts, members.ts
│       ├── billing.ts   # Tuition plans, student billing, invoices
│       └── features.ts  # Feature status + start trial
├── composables/         # useMobile, usePermissions, useProductRegistry
├── components/
│   ├── layout/          # AppHeader, AppSidebar, PlatformNotificationBell
│   ├── ui/              # ConfirmModal, IconButton, TenantSwitcher, OtpInput, RouteTabs, etc.
│   ├── operations/      # CustomerTimeline, QuickActions, SupportNotes
│   ├── platform/        # MobileBottomNav
│   │   └── widgets/     # StatCard, ActivityFeed, FinanceSnapshot, PulseBar
│   └── products/school/ # Product-specifieke componenten
│       ├── schedule/    # WeekCalendar, LessonCard, LessonSlotForm, RescheduleModal, GenerateLessonsModal
│       ├── notification/ # NotificationBell, NotificationLogTable, PreferenceToggle
│       └── billing/     # PaymentStatusBadge
├── router/              # index.ts, guards.ts, routes.ts
├── stores/              # Pinia: auth, tenant, notification, platformNotification, billing, branding
├── types/               # auth.ts, billing.ts, school.ts, models.ts (barrel), enums.ts
├── constants/           # collaboration.ts
├── directives/          # inputMasks.ts
├── utils/               # validators.ts, errors.ts
└── views/
    ├── NotFoundView.vue
    ├── platform/
    │   ├── WelcomeView, CreateOrgWizardView, PlatformNotificationInboxView
    │   ├── auth/        # Login, Register, RegisterSuccess, VerifyEmail, VerifySession,
    │   │                # ForgotPassword, ResetPassword, AccountRecovery, AcceptInvite,
    │   │                # ConfirmEmailChange, AccountSettings (11 views)
    │   ├── admin/       # AdminDashboard, PlatformUsers, PlatformAccess,
    │   │   │            # PlatformNotificationsAdmin, FeatureCatalog, TenantFeatureAdmin
    │   │   ├── audit/   # AdminAuditLogs
    │   │   ├── groups/  # AdminPlatformGroups, AdminPlatformGroupDetail,
    │   │   │            # AdminTenantGroups, AdminTenantGroupDetail
    │   │   ├── infra/   # ServiceTopology
    │   │   └── tenants/ # AdminTenants
    │   ├── operations/  # Tenant360, Onboarding, JobMonitor
    │   └── finance/     # Revenue, OutstandingPayments, TaxReport, PlanManager
    └── products/school/ # 15 views
        # Dashboard, Students, Attendance, Schedule, Holidays,
        # NotificationSettings, Invitations, Permissions, PermissionDetail,
        # Collaborations, BillingDashboard, TuitionPlans, StudentBilling,
        # Invoices, Upgrade
```

## Projectstructuur

```
yoohoo/
├── backend/
│   ├── app/                    ← Applicatiecode (zie Backend Architectuur)
│   ├── alembic/                ← Migraties (dual-mode: central/tenant)
│   │   └── versions/
│   │       ├── central/        # 27 migraties (001-027)
│   │       └── tenant/         # 6 migraties (001-006)
│   ├── tests/                  ← ~682 test functies (core, platform, tenant, security)
│   │   ├── conftest.py         # Session + function fixtures (DB, client, tenant setup)
│   │   ├── core/               # 83 tests (health, circuit_breaker, middleware, rate_limiter, retry)
│   │   ├── platform/           # 291 tests (admin, auth, billing, finance, notifications, operations, plugin, tenant_mgmt)
│   │   ├── tenant/             # 84 tests (student, attendance, schedule, notification, billing, members)
│   │   └── security/           # 61 tests (pentest: auth_bypass, authz, IDOR, info_disclosure, input_validation, tenant_isolation)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── pytest.ini
│   └── alembic.ini
├── frontend/
│   ├── src/                    ← Vue 3 applicatie (zie Frontend Structuur)
│   ├── public/
│   ├── package.json
│   ├── Dockerfile / Dockerfile.dev
│   ├── vite.config.ts
│   └── tailwind.config.js
├── nginx/
│   ├── nginx.conf              ← HTTP reverse proxy configuratie
│   ├── nginx.ssl.conf          ← HTTPS/SSL configuratie template
│   └── www/                    ← Static web files (productie frontend)
├── pgbouncer/
│   ├── pgbouncer.ini           ← PgBouncer configuratie (transaction pooling)
│   └── userlist.txt            ← PgBouncer authenticatie
├── infra/                      ← Terraform Infrastructure-as-Code
├── monitoring/                 ← Prometheus, Grafana, Alertmanager, Loki, Promtail
├── scripts/                    ← Utility scripts (migrations, provisioning, backup, SSL)
├── .github/                    ← GitHub Actions workflows
├── docker-compose.yml          ← Productie (api, worker, pgbouncer, postgres, redis, nginx)
├── docker-compose.dev.yml      ← Development (+ hot reload, mailpit)
├── Makefile                    ← Build/deploy commands (dev, test, migrate, lint, monitoring, backup)
├── .env.example                ← Environment template (102 variabelen)
├── CLAUDE.md                   ← Dit bestand
├── SECURITY.md                 ← Security documentatie
├── API_INVENTORY.md            ← Complete API endpoint referentie
└── TEST_AUDIT.md               ← Test coverage audit
```

## Starten

```bash
# Development (Docker Compose met hot reload)
make dev                    # Start alle services
make dev-down               # Stop development

# Productie (images van GHCR — nooit lokaal bouwen)
make up                     # Start productie
make down                   # Stop productie
make build                  # Docker images bouwen

# Logs
make logs                   # Alle services
make logs-api               # Alleen API
make worker-logs            # Alleen arq worker

# Migraties
make migrate-central        # Central DB migraties
make migrate-tenant SLUG=x  # Eén tenant migreren
make migrate-tenants        # Alle tenants migreren (scripts/migrate-all-tenants.sh)

# Tests
make test                   # In Docker
make test-local             # Lokaal

# Linting & Security
make lint                   # ruff check
make audit                  # pip-audit (dependency vulnerabilities)

# Database shell
make db-shell               # PostgreSQL
make redis-shell            # Redis

# Monitoring (Prometheus, Grafana, Alertmanager, Loki, Promtail)
make monitoring-up          # Start monitoring stack
make monitoring-down        # Stop monitoring stack
make monitoring-logs        # Monitoring logs

# Backup
make backup                 # Database backup (scripts/backup/backup.sh)
```

## Configuratie

**`.env` is de single source of truth** voor alle configuratie (102 variabelen). Kopieer `.env.example` → `.env`.
Docker Compose, Makefile en vite.config.ts lezen allemaal uit `.env`. Wijzig alleen dit bestand.

| Groep | Variabelen | Beschrijving |
|-------|-----------|-------------|
| **App** | `APP_ENV`, `DEBUG`, `SECRET_KEY`, `API_V1_PREFIX` | development/staging/production, Swagger docs, app secret |
| **Branding** | `PLATFORM_NAME`, `PLATFORM_NAME_SHORT`, `PLATFORM_URL` | Platform-naamgeving en URL |
| **Poorten** | `API_PORT`, `FRONTEND_PORT`, `NGINX_PORT` | Host-poorten (8000, 1000, 80) |
| **PostgreSQL** | `POSTGRES_HOST/PORT/USER/PASSWORD/DB`, `POSTGRES_ADMIN_DB`, `TENANT_DB_PREFIX/SUFFIX` | Central DB + tenant DB naampatroon (ps_t_{slug}_db) |
| **PgBouncer** | `PGBOUNCER_HOST/PORT`, `USE_PGBOUNCER` | Connection pooling (transaction mode) |
| **Redis** | `REDIS_HOST/PORT/DB/PASSWORD` | App cache (db=0) |
| **arq Worker** | `ARQ_REDIS_DB`, `ARQ_MAX_JOBS`, `ARQ_JOB_TIMEOUT` | Job queue (db=1, max 10 concurrent, 300s timeout) |
| **JWT** | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Token signing (HS256, 30min access, 7d refresh) |
| **CORS** | `CORS_ORIGINS` | Kommagescheiden allowed origins |
| **Email (SMTP)** | `SMTP_HOST/PORT/USER/PASSWORD/FROM/USE_TLS` | SMTP transport (Mailpit dev) |
| **Email Provider** | `EMAIL_PROVIDER`, `EMAIL_FALLBACK_PROVIDER`, `RESEND_API_KEY`, `BREVO_API_KEY` | smtp/resend/brevo met fallback |
| **Email Senders** | `EMAIL_{ACCOUNT,SECURITY,NOTIFICATION,BILLING}_FROM/_NAME` | Per-type afzender adressen (8 vars) |
| **SMS** | `SMS_PROVIDER`, `SMS_FALLBACK_PROVIDER`, `SMS_SENDER_NAME` | twilio/vonage/brevo (niet actief) |
| **SMS Credentials** | `TWILIO_ACCOUNT_SID/AUTH_TOKEN`, `VONAGE_API_KEY/API_SECRET` | Provider credentials |
| **Frontend** | `FRONTEND_URL` | URL voor verificatie-links (http://localhost:2000) |
| **Verificatie** | `EMAIL_VERIFICATION_EXPIRE_HOURS`, `UNVERIFIED_CLEANUP_DAYS` | 48h token, 7d cleanup |
| **Uitnodigingen** | `INVITATION_EXPIRE_HOURS`, `INVITATION_MAX_PENDING_PER_ORG` | 72h, max 50 pending |
| **Wachtwoord** | `PASSWORD_RESET_EXPIRE_MINUTES`, `PASSWORD_RESET_RATE_LIMIT_PER_HOUR` | 30min token, 3/uur |
| **2FA** | `TOTP_ISSUER_NAME` | Issuer in authenticator app |
| **Sessies** | `MAX_ACTIVE_SESSIONS`, `SESSION_REMEMBER_ME_DAYS`, `SESSION_DEFAULT_HOURS` | 10 max, 30d remember, 8h default |
| **Impersonation** | `IMPERSONATION_TOKEN_EXPIRE_MINUTES` | 60 min |
| **Verificatie codes** | `VERIFICATION_CODE_EXPIRE_MINUTES/MAX_ATTEMPTS/COOLDOWN_SECONDS` | 10min, 5 pogingen, 60s cooldown |
| **Login verificatie** | `LOGIN_REQUIRE_EMAIL_VERIFICATION`, `LOGIN_EMAIL_VERIFICATION_EXPIRE_MINUTES` | Magic link optie (standaard uit) |
| **Rate Limiting** | `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_PER_TENANT_PER_MINUTE` | 60/min globaal, 300/min per tenant |
| **Request Size** | `MAX_REQUEST_BODY_SIZE` | 10MB (defense-in-depth naast nginx) |
| **Brute Force** | `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_SECONDS` | 5 pogingen, 15 min lockout |
| **Billing** | `BILLING_WEBHOOK_BASE_URL`, `BILLING_INVOICE_PREFIX`, `BILLING_DEFAULT_CURRENCY`, `BILLING_TAX_RATE_PERCENT`, `BILLING_TRIAL_DAYS`, `BILLING_INVOICE_DUE_DAYS`, `MOLLIE/STRIPE_TEST_MODE` | EUR, 21% BTW, 30d trial, 14d betaaltermijn |
| **Dunning** | `BILLING_DUNNING_ENABLED`, `BILLING_DUNNING_{FIRST,SECOND,THIRD}_REMINDER_DAYS` | 7/14/30 dagen herinneringen |
| **Sentry** | `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_ENVIRONMENT` | Error tracking (10% sampling) |
| **Logging** | `LOG_LEVEL`, `LOG_FORMAT` | INFO, json (structlog) |
| **Data Retention** | `DATA_RETENTION_ACCOUNT_ARCHIVE_DAYS`, `..._AUTO_ANONYMIZE`, `..._ALLOW_REACTIVATION`, `..._REACTIVATION_WINDOW_DAYS`, `..._FINANCIAL_RECORDS_DAYS`, `..._REQUIRE_DATA_EXPORT` | AVG-compliant: 1,5j archief, 7j financieel |

## Alembic Migraties

Dual-mode systeem:

```bash
# Central database (gebruikers, tenants)
alembic -x mode=central upgrade head

# Tenant database (leerlingen, aanwezigheid, etc.)
alembic -x mode=tenant -x tenant_slug=mijnschool upgrade head
```

Nieuwe migratie aanmaken:
```bash
alembic -x mode=central revision --autogenerate -m "beschrijving"
alembic -x mode=tenant revision --autogenerate -m "beschrijving"
```

## Fasering

| Fase | Status | Inhoud |
|------|--------|--------|
| **1. Core Foundation** | Voltooid | Auth, tenants, DB, Docker, frontend basis |
| **2a. Students** | Voltooid | Student CRUD, Excel import, guardian info |
| **2b. Attendance** | Voltooid | Aanwezigheidsregistratie, bulk registratie |
| **3. Schedule & Notifications** | Voltooid | Roosterbeheer, lesslots, lesinstanties, vakanties, notificaties, circuit breaker |
| **3.5. User Management** | Voltooid | Uitnodigingen, wachtwoord reset/wijzigen, sessiebeheer, 2FA/TOTP, audit logging |
| **3.6. Permissions** | Voltooid | Dynamisch groepen/permissiesysteem, PermissionRegistry, auto-discovery, per-tenant groepen |
| **4a. arq + PgBouncer** | Voltooid | arq worker (9 jobs, 5 cron), PgBouncer transaction pooling, health checks |
| **5. Billing** | Voltooid | Platform billing (Stripe/Mollie), tenant billing (tuition plans, invoices) |
| **5.5. Collaborations** | Voltooid | Samenwerkingsverbanden tussen organisaties, collaborator management |
| **5.6. Security Hardening** | Voltooid | v1 + v2 (11 fasen): headers, CORS, HTTPS, encryption, HMAC tokens, circuit breakers, resource limits |
| **6. Multi-Docent** | Voltooid | Docent-leerling koppeling, DataScope filtering, vervanging, audit trail |
| **Slug-in-URL** | Voltooid | Tenant context via URL path (/org/{slug}/...) i.p.v. headers |
| **Organisatie Refactor** | Voltooid | GDPR-driven cleanup, dead code removal, route consolidatie |
| **ProductRegistry** | Voltooid | Plugin systeem, declaratieve manifests, NavigationRegistry, auto-discovery |
| **Finance Dashboard** | Voltooid | Revenue, outstanding payments, tax reports, dunning cron |
| **Feature Gating** | Voltooid | PlanFeatures, trial lifecycle, feature catalog, tenant overrides, data purge hooks |
| **Platform Toegangsbeheer** | Voltooid | Platform users lijst, permissiegroepen, user search |
| **Legacy Role Cleanup** | Voltooid | Role enum verwijderd, DB migratie 020, puur permissie-gebaseerd |

---

## Conventies

- Python bestanden: `snake_case`
- Vue componenten: `PascalCase`
- API routes: kebab-case
- Taal in code/comments: Engels
- Taal in UI/klantcommunicatie: Nederlands (primair)
- Module structuur: elke module heeft `__init__.py`, `models.py`, `schemas.py`, `router.py`, `service.py`
- Module scope: platform-modules (auth, admin, tenant_mgmt, billing, operations, finance, notifications, members, plugin) in `modules/platform/`, product-modules (student, attendance, schedule, notification, billing) in `modules/products/school/`
- Auth module: sub-mappen (core/, invitation/, password/, permissions/, session/, totp/) met elk eigen schemas/service/router; gedeelde models.py, constants.py, dependencies.py, permissions_setup.py, audit.py op root

## Frontend Styling Regels

**NOOIT hardcoded Tailwind klassen voor herbruikbare patronen in templates.** Alle styling gaat via het centraal theme systeem (`src/theme.ts`).

**5 thema's actief:** default (Yoohoo), yoohoo, pastel, violet — CSS overrides in `src/style.css` werken via CSS custom properties en class selectors. Hardcoded kleuren in templates breken andere thema's.

### Verplicht via theme.ts

| Categorie | Theme class | Voorbeeld |
|-----------|------------|-----------|
| Knoppen | `theme.btn.primary`, `.primarySm`, `.secondary`, `.secondarySm`, `.dangerFill`, `.dangerOutline`, `.ghost`, `.link`, `.danger` | `:class="theme.btn.primary"` |
| Formulier | `theme.form.label`, `.input` | `:class="theme.form.input"` |
| Cards | `theme.card.base`, `.padded`, `.form` | `:class="theme.card.padded"` |
| Alerts | `theme.alert.error`, `.success`, `.errorInline` | `:class="theme.alert.success"` |
| Badges | `theme.badge.base` + `.success` / `.warning` / `.error` / `.default` / `.info` | `:class="[theme.badge.base, theme.badge.success]"` |
| Tekst | `theme.text.h1` t/m `.h4`, `.body`, `.muted`, `.subtitle` | `:class="theme.text.h3"` |
| Pagina | `theme.page.bg`, `.bgCenter` | `:class="theme.page.bgCenter"` |
| Lijsten | `theme.list.divider`, `.item`, `.sectionHeader`, `.empty` | `:class="theme.list.sectionHeader"` |
| Links | `theme.link.primary` | `:class="theme.link.primary"` |
| Sidebar | `theme.sidebar.navItem`, `.navActive`, `.navInactive` | — |

### Wat WEL inline mag

- Layout utilities: `flex`, `grid`, `gap-*`, `mt-*`, `mb-*`, `w-full`, `max-w-*`
- Responsive breakpoints: `md:flex-row`, `lg:grid-cols-4`, `hidden md:table-cell`
- Positionering: `absolute`, `relative`, `fixed`, `z-*`
- Component-specifieke structuur: `overflow-x-auto`, `min-h-[120px]`
- Eenmalige layout-afwijkingen met `class="..."` naast `:class="theme.*"`

### Wat NIET inline mag

- Kleuren (`bg-primary-600`, `text-navy-900`, `border-navy-100`) → gebruik theme class
- Button styling (`rounded-lg hover:bg-*`) → gebruik `theme.btn.*`
- Formulier styling (`border focus:ring-*`) → gebruik `theme.form.*`
- Alert/success/error patronen → gebruik `theme.alert.*`
- Badge patronen → gebruik `theme.badge.*`

### Bij nieuwe UI-patronen

Als een nieuw patroon 2+ keer voorkomt: voeg het toe aan `theme.ts` in plaats van inline te schrijven. Eénmalige uitzonderingen mogen inline, maar documenteer waarom.

## Architectuur Regels

**1. Dependency injection via FastAPI `Depends()`**
- Services ontvangen hun dependencies via constructor of `Depends()`
- Database sessies via `get_central_db()` of `get_tenant_db()`
- Redis via `get_redis()`

**2. Module isolatie**
- Elke module (`auth`, `tenant`, `student`, etc.) is zelfstandig
- Cross-module communicatie via dependencies of event bus, niet via directe imports van interne services

**3. Database toegang alleen via SQLAlchemy**
- NOOIT raw SQL in routers of services
- Alle queries via SQLAlchemy ORM of `text()` in repositories
- Central data → `CentralBase` models, Tenant data → `TenantBase` models

**4. Async everywhere**
- Alle database operaties zijn async (asyncpg)
- Alle route handlers zijn `async def`
- Gebruik `AsyncSession`, niet `Session`

## Workflow

### Plan Mode
- Gebruik plan mode voor elke niet-triviale taak (3+ stappen of architectuur beslissingen)
- Als iets niet werkt: STOP en herplan — niet doorduwen
- Schrijf een duidelijke aanpak voordat je code schrijft

### Subagents
- Gebruik subagents om de hoofd-context schoon te houden
- Research, exploratie en parallelle analyse naar subagents delegeren
- Eenmalige taak per subagent voor gerichte uitvoering

### Verificatie
- Markeer een taak NOOIT als klaar zonder te bewijzen dat het werkt
- Importeer, run of test de wijziging voordat je klaar meldt
- Vraag jezelf: "Zou een senior developer dit goedkeuren?"

### Kwaliteit
- **Simplicity first:** Maak elke wijziging zo simpel mogelijk. Minimale impact.
- **Geen lazy fixes:** Zoek de root cause. Geen tijdelijke oplossingen.
- **Minimale impact:** Raak alleen aan wat nodig is. Voorkom het introduceren van bugs.

### Bug Fixing
- Bij een bugreport: gewoon fixen. Niet om hulp vragen.
- Logs, errors en failing tests opsporen en zelf oplossen.
- Zo min mogelijk context switching van de gebruiker nodig.
