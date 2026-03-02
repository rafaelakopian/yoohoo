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
- **Slug-in-URL routing**: tenant context via URL path (`/api/v1/schools/{slug}/...`) i.p.v. headers
- **`resolve_tenant_from_path`** dependency op parent router: slug→UUID lookup met cache
- **TenantDatabaseManager** beheert async engines met lazy caching
- **PgBouncer** transaction pooling: app → PgBouncer → PostgreSQL (asyncpg prepared statements uitgeschakeld)
- **arq worker** voor achtergrondtaken: emails, notificaties, facturatie, cleanup (Redis db=1)

### Backend Architectuur

```
backend/app/
├── main.py              # FastAPI app factory + lifespan (startup/shutdown)
├── config.py            # Pydantic Settings (alle config via .env)
├── dependencies.py      # Dependency injection (Redis, arq, tenant DB sessions)
├── core/                # Infrastructure
│   ├── exceptions.py    # Centrale foutafhandeling
│   ├── health.py        # Health check endpoints (/health/live, /health/ready)
│   ├── logging_config.py # Structured logging (structlog)
│   ├── middleware.py     # RequestID, SecurityHeaders, MaxBodySize middleware
│   ├── rate_limiter.py   # Rate limiting middleware (X-Forwarded-For aware)
│   ├── login_throttle.py # Brute force login protection
│   ├── circuit_breaker.py # Circuit breaker patroon (named registry)
│   ├── encryption.py     # Shared Fernet encryption (PBKDF2 key derivation)
│   ├── event_bus.py      # Event publicatie/subscriptie
│   ├── worker.py         # arq WorkerSettings (background job runner)
│   ├── jobs/             # Background job definitions
│   │   ├── email.py      # send_email_job
│   │   ├── notification.py # process_notification_job
│   │   ├── billing.py    # generate_invoices_job, send_invoice_email_job
│   │   └── maintenance.py # cleanup_unverified_users_job
│   ├── permissions.py    # PermissionRegistry singleton (auto-discovery)
│   └── security.py       # JWT creatie en validatie
├── db/                  # Database layer
│   ├── base.py          # CentralBase / TenantBase (SQLAlchemy declarative)
│   ├── central.py       # Central engine + session factory
│   └── tenant.py        # TenantDatabaseManager (per-tenant engines)
└── modules/             # Feature modules (gescheiden per scope)
    ├── platform/        # ← SaaS-platformbreed (central DB)
    │   ├── admin/           # Platform admin API (stats, tenant/user beheer, membership CRUD)
    │   ├── auth/            # Authenticatie & User Management
    │   │   ├── constants.py     # Role enum (deprecated), ROLE_HIERARCHY
    │   │   ├── dependencies.py  # get_current_user, require_permission, require_any_permission, is_data_restricted
    │   │   ├── models.py        # User, TenantMembership, RefreshToken, Invitation, PasswordResetToken, AuditLog, PermissionGroup, GroupPermission, UserGroupAssignment
    │   │   ├── permissions_setup.py # Default groepen per tenant (schoolbeheerder, docent, ouder)
    │   │   ├── audit.py         # AuditService helper
    │   │   ├── core/            # Login, register, verify, refresh, logout, /me
    │   │   ├── invitation/      # Uitnodigingssysteem (invite-only per school, group_id support)
    │   │   ├── password/        # Wachtwoord reset + wijzigen
    │   │   ├── permissions/     # Groepen & rechten CRUD API (registry, groups, user assignments)
    │   │   ├── session/         # Sessiebeheer (list, revoke, logout-all)
    │   │   └── totp/            # 2FA (setup, verify, disable, login flow)
    │   ├── billing/         # Platform billing (Stripe/Mollie providers, plans, subscriptions, webhooks)
    │   ├── tenant_mgmt/     # Tenant/school CRUD, settings, db_provisioner
    │   ├── config_mgmt/     # (placeholder — Fase 4)
    │   └── plugin/          # (placeholder — Fase 4)
    └── tenant/          # ← Organisatie-specifiek (tenant DB, per school)
        ├── path_dependency.py # resolve_tenant_from_path (slug→UUID, cached)
        ├── student/         # Student CRUD, Excel import, guardian info, teacher assignment
        ├── attendance/      # Attendance CRUD, bulk registratie
        ├── schedule/        # Lesrooster: slots, instances, holidays, calendar
        ├── notification/    # E-mail notificaties, in-app meldingen, voorkeuren
        └── billing/         # Tenant billing: tuition plans, student billing, invoices
```

### Permissiesysteem

Dynamisch groepen/permissiesysteem vervangt de 4 vaste rollen. Elke module registreert permissies bij import via `PermissionRegistry` (singleton, `app/core/permissions.py`).

**Permissie-codenames** over 8 modules:

| Module | Permissies |
|--------|-----------|
| `students` | `view`, `view_own`, `view_assigned`, `create`, `edit`, `delete`, `import`, `manage_parents`, `assign` |
| `attendance` | `view`, `view_own`, `view_assigned`, `create`, `edit`, `delete` |
| `schedule` | `view`, `view_assigned`, `manage`, `substitute` |
| `notifications` | `view`, `manage` |
| `invitations` | `view`, `manage` |
| `school_settings` | `view`, `edit` |
| `billing` | `view`, `view_own`, `manage` |
| `collaborations` | `view`, `manage` |

**3 default groepen per tenant:**

| Groep | Permissies |
|-------|-----------|
| `schoolbeheerder` | Alle 25 permissies |
| `docent` | students.view_assigned/create/edit/delete/import/assign, attendance.view_assigned/create/edit/delete, schedule.view_assigned/manage/substitute, notifications.view |
| `ouder` | students.view_own, attendance.view_own, schedule.view, notifications.view |

**Super admin** (`is_superadmin=True`) bypassed alle permissiechecks.

**DataScope** (drie-weg zichtbaarheid):
- `DataScope.all` — schoolbeheerder/superadmin: ziet alles
- `DataScope.assigned` — docent: ziet alleen eigen toegewezen leerlingen
- `DataScope.own` — ouder: ziet alleen eigen kinderen

**Dependencies:**
- `require_permission("students.create")` — vereist specifieke permissie
- `require_any_permission("students.view", "students.view_assigned", "students.view_own")` — vereist minstens één
- `get_data_scope(user, tenant_id, "students")` — retourneert DataScope enum
- `is_data_restricted(user, tenant_id, "students.view")` — True als user alleen view_own heeft (legacy)

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), Alembic, structlog
- **Database:** PostgreSQL 16 (asyncpg), Redis 7 (hiredis)
- **Auth:** JWT (PyJWT) + refresh token rotation, pwdlib (Argon2 + bcrypt compat), email verificatie (aiosmtplib), 2FA/TOTP (pyotp, segno QR), Fernet encryption (cryptography)
- **Frontend:** Vue 3, TypeScript 5, Vite 7, Pinia 3, Tailwind CSS 4, Vue Router 5, Axios
- **Infra:** Docker Compose, Nginx, Makefile
- **Testing:** pytest 9, pytest-asyncio 1.x, pytest-cov 7, factory-boy
- **Linting:** ruff

## API Routes

| Prefix | Router | Beschrijving |
|--------|--------|-------------|
| `/health/*` | `core/health.py` | Health checks (live + ready) |
| `/api/v1/auth/*` | `modules/platform/auth/core/router.py` | Register, login, refresh, logout, /me |
| `/api/v1/auth/*` | `modules/platform/auth/password/router.py` | Forgot/reset/change password |
| `/api/v1/auth/*` | `modules/platform/auth/session/router.py` | Sessiebeheer (list, revoke, logout-all) |
| `/api/v1/auth/*` | `modules/platform/auth/invitation/router.py` | Invite-info, accept-invite (public) |
| `/api/v1/auth/2fa/*` | `modules/platform/auth/totp/router.py` | 2FA setup, verify, disable |
| `/api/v1/permissions/registry` | `modules/platform/auth/permissions/router.py` | Permissie registry (platform-scoped) |
| `/api/v1/schools/*/invitations` | `modules/platform/auth/invitation/router.py` | Uitnodigingen per school (invitations.manage) |
| `/api/v1/schools/*` | `modules/platform/tenant_mgmt/router.py` | School CRUD, provisioning, settings |
| `/api/v1/schools/{slug}/students/*` | `modules/tenant/student/router.py` | Student CRUD, Excel import (tenant-scoped) |
| `/api/v1/schools/{slug}/attendance/*` | `modules/tenant/attendance/router.py` | Attendance CRUD, bulk registratie (tenant-scoped) |
| `/api/v1/schools/{slug}/schedule/*` | `modules/tenant/schedule/router.py` | Lesrooster: slots, instances, holidays, calendar (tenant-scoped) |
| `/api/v1/schools/{slug}/notifications/*` | `modules/tenant/notification/router.py` | Notificatie-instellingen, logs, in-app meldingen (tenant-scoped) |
| `/api/v1/schools/{slug}/permissions/*` | `modules/platform/auth/permissions/router.py` | Groepen & rechten CRUD (tenant-scoped) |
| `/api/v1/admin/*` | `modules/platform/admin/router.py` | Platform admin: stats, schools, users, memberships (superadmin only) |

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
| POST | `/api/v1/schools/{id}/invitations` | Uitnodiging aanmaken (invitations.manage) |
| GET | `/api/v1/schools/{id}/invitations` | Pending uitnodigingen ophalen (invitations.view) |
| POST | `/api/v1/schools/{id}/invitations/{inv_id}/resend` | Uitnodiging opnieuw versturen (invitations.manage) |
| DELETE | `/api/v1/schools/{id}/invitations/{inv_id}` | Uitnodiging revoking (invitations.manage) |
| GET | `/api/v1/auth/invite-info?token=...` | Uitnodigingsinfo ophalen (public) |
| POST | `/api/v1/auth/accept-invite` | Uitnodiging accepteren (public) |

### Permissions Endpoints

| Method | Path | Beschrijving |
|--------|------|-------------|
| GET | `/api/v1/permissions/registry` | Alle modules + permissies (platform-scoped, authenticated) |
| GET | `/api/v1/schools/{slug}/permissions/groups` | Groepen voor tenant (school_settings.view) |
| POST | `/api/v1/schools/{slug}/permissions/groups` | Groep aanmaken (school_settings.edit) |
| GET | `/api/v1/schools/{slug}/permissions/groups/{id}` | Groep detail + permissies (school_settings.view) |
| PUT | `/api/v1/schools/{slug}/permissions/groups/{id}` | Groep naam/beschrijving/permissies wijzigen (school_settings.edit) |
| DELETE | `/api/v1/schools/{slug}/permissions/groups/{id}` | Groep verwijderen, niet als is_default (school_settings.edit) |
| GET | `/api/v1/schools/{slug}/permissions/groups/{id}/users` | Users in groep (school_settings.view) |
| POST | `/api/v1/schools/{slug}/permissions/groups/{id}/users` | User aan groep toevoegen (school_settings.edit) |
| DELETE | `/api/v1/schools/{slug}/permissions/groups/{id}/users/{uid}` | User uit groep verwijderen (school_settings.edit) |
| GET | `/api/v1/schools/{slug}/permissions/my-permissions` | Effectieve permissies huidige user (authenticated) |

### 2FA/TOTP Endpoints

| Method | Path | Beschrijving |
|--------|------|-------------|
| POST | `/api/v1/auth/2fa/setup` | 2FA instellen (authenticated, retourneert QR) |
| POST | `/api/v1/auth/2fa/verify-setup` | 2FA activeren met code (retourneert backup codes) |
| POST | `/api/v1/auth/2fa/disable` | 2FA uitschakelen (vereist wachtwoord) |
| POST | `/api/v1/auth/2fa/verify` | 2FA code verifiëren bij login (public, rate limited) |

### School Endpoints (superadmin: create/provision/delete)

| Method | Path | Beschrijving |
|--------|------|-------------|
| POST | `/api/v1/schools/` | School aanmaken (superadmin) |
| GET | `/api/v1/schools/` | Scholen ophalen (admin: alle, user: eigen) |
| GET | `/api/v1/schools/{id}` | School details (admin of lid) |
| POST | `/api/v1/schools/{id}/provision` | School database aanmaken (superadmin) |
| DELETE | `/api/v1/schools/{id}` | School verwijderen (superadmin + wachtwoord) |
| GET | `/api/v1/schools/{id}/settings` | School instellingen (admin of school_admin) |
| PUT | `/api/v1/schools/{id}/settings` | School instellingen bijwerken (admin of school_admin) |

### Student Endpoints (tenant-scoped, slug-in-URL)

| Method | Path | Beschrijving |
|--------|------|-------------|
| GET | `/api/v1/schools/{slug}/students/` | Leerlingen ophalen (DataScope: all/assigned/own) |
| GET | `/api/v1/schools/{slug}/students/my-children` | Eigen kinderen (ouder) |
| GET | `/api/v1/schools/{slug}/students/my-students` | Toegewezen leerlingen (docent) |
| GET | `/api/v1/schools/{slug}/students/unassigned` | Niet-toegewezen leerlingen |
| POST | `/api/v1/schools/{slug}/students/self-assign/{id}` | Zelf-toewijzing (docent) |
| POST | `/api/v1/schools/{slug}/students/` | Leerling aanmaken |
| POST | `/api/v1/schools/{slug}/students/import` | Excel import (multipart file upload) |
| GET | `/api/v1/schools/{slug}/students/{id}` | Leerling details (DataScope check) |
| PUT | `/api/v1/schools/{slug}/students/{id}` | Leerling bijwerken (partial update) |
| DELETE | `/api/v1/schools/{slug}/students/{id}` | Leerling deactiveren (soft delete) |
| GET | `/api/v1/schools/{slug}/students/{id}/teachers` | Docent-koppelingen van leerling |
| POST | `/api/v1/schools/{slug}/students/{id}/teachers` | Docent toewijzen |
| DELETE | `/api/v1/schools/{slug}/students/{id}/teachers/{uid}` | Docentkoppeling verwijderen |
| POST | `/api/v1/schools/{slug}/students/{id}/transfer` | Transfer leerling tussen docenten |

### Attendance Endpoints (tenant-scoped, slug-in-URL)

| Method | Path | Beschrijving |
|--------|------|-------------|
| GET | `/api/v1/schools/{slug}/attendance/` | Aanwezigheidsrecords ophalen (paginated, ?student_id=&date_from=&date_to=) |
| POST | `/api/v1/schools/{slug}/attendance/` | Aanwezigheidsrecord aanmaken |
| POST | `/api/v1/schools/{slug}/attendance/bulk` | Bulk registratie (hele klas in één keer) |
| GET | `/api/v1/schools/{slug}/attendance/{id}` | Aanwezigheidsrecord details |
| PUT | `/api/v1/schools/{slug}/attendance/{id}` | Aanwezigheidsrecord bijwerken (partial update) |
| DELETE | `/api/v1/schools/{slug}/attendance/{id}` | Aanwezigheidsrecord verwijderen (hard delete) |

## Frontend Structuur

```
frontend/src/
├── main.ts              # Vue app entry
├── App.vue              # Root component
├── api/                 # HTTP client layer (gescheiden per scope)
│   ├── client.ts        # Axios instance + JWT interceptor + tenantUrl() helper
│   ├── platform/        # ← SaaS-platformbreed
│   │   ├── auth.ts      # Auth API calls (login, register, password, sessions, 2FA, invites)
│   │   ├── branding.ts  # Platform branding API
│   │   ├── admin.ts     # Platform admin API calls
│   │   └── schools.ts   # School/tenant API calls
│   └── tenant/          # ← Organisatie-specifiek
│       ├── students.ts  # Student API calls
│       ├── attendance.ts # Attendance API calls
│       ├── schedule.ts  # Schedule API calls
│       ├── notifications.ts # Notification API calls
│       ├── invitations.ts # School invitation management API
│       ├── permissions.ts # Permissions/groups CRUD API
│       ├── collaborations.ts # Collaboration management API
│       └── billing.ts    # Tuition plans, student billing, invoices API
├── composables/
│   └── usePermissions.ts # hasPermission(), hasAnyPermission(), hasAllPermissions()
├── components/
│   ├── layout/          # AppHeader, AppSidebar (permissie-gebaseerde nav)
│   ├── ui/              # IconButton, ConfirmModal, TenantSwitcher
│   └── tenant/          # ← Organisatie-specifieke componenten
│       ├── schedule/    # WeekCalendar, LessonCard, LessonSlotForm, etc.
│       └── notification/ # NotificationBell, PreferenceToggle, LogTable
├── router/              # Vue Router + auth/tenant/superadmin guards
├── stores/              # Pinia: auth.ts, tenant.ts, notification.ts, branding.ts
├── types/               # TypeScript types (gesplitst per domein)
│   ├── models.ts        # Barrel re-export (auth + school)
│   ├── auth.ts          # Auth types: User, Role, Token, GroupSummary, PermissionGroup, etc.
│   ├── school.ts        # School types: Tenant, Student, Attendance, Schedule, Notification
│   └── enums.ts         # Legacy enums
├── utils/               # Validators
└── views/               # Georganiseerd per scope
    ├── platform/        # ← SaaS-platformbreed
    │   ├── auth/        # LoginView, RegisterView, VerifyEmailView, ForgotPasswordView, ResetPasswordView, AcceptInviteView, AccountSettingsView
    │   └── admin/       # AdminDashboardView, AdminTenantsView, AdminUsersView, AdminUserDetailView, AdminAuditLogsView, ServiceTopologyView
    └── tenant/          # ← Organisatie-specifiek
        # DashboardView, StudentsView, AttendanceView, ScheduleView, HolidaysView,
        # NotificationSettingsView, InvitationsView, PermissionsView, CollaborationsView,
        # BillingDashboardView, TuitionPlansView, StudentBillingView, InvoicesView
```

## Projectstructuur

```
yoohoo/
├── backend/
│   ├── app/                    ← Applicatiecode (zie Backend Architectuur)
│   ├── alembic/                ← Migraties (dual-mode: central/tenant)
│   │   └── versions/
│   │       ├── central/        # Central DB schema
│   │       └── tenant/         # Tenant DB schema (per tenant)
│   ├── tests/                  ← ~148 tests (auth, tenant, health, student, attendance, schedule, notification, admin, UMS, permissions)
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
│   ├── tailwind.config.js
│   └── nginx.conf              ← Frontend prod serving
├── nginx/
│   └── nginx.conf              ← Reverse proxy configuratie
├── pgbouncer/
│   ├── pgbouncer.ini           ← PgBouncer configuratie (transaction pooling)
│   └── userlist.txt            ← PgBouncer authenticatie
├── docker-compose.yml          ← Productie (api, worker, pgbouncer, postgres, redis, nginx)
├── docker-compose.dev.yml      ← Development (+ hot reload, mailpit)
├── Makefile                    ← Build/deploy commands
├── .env.example                ← Environment template
└── CLAUDE.md                   ← Dit bestand
```

## Starten

```bash
# Development (Docker Compose met hot reload)
make dev

# Stoppen
make dev-down

# Productie
make up
make down

# Migraties
make migrate-central
make migrate-tenant SLUG=myschool

# Tests
make test              # In Docker
make test-local        # Lokaal

# Linting
make lint

# Worker logs
make worker-logs

# Database shell
make db-shell
make redis-shell
```

## Configuratie

**`.env` is de single source of truth** voor alle configuratie. Kopieer `.env.example` → `.env`.
Docker Compose, Makefile en vite.config.ts lezen allemaal uit `.env`. Wijzig alleen dit bestand.

| Variabele | Beschrijving | Default |
|-----------|-------------|---------|
| `APP_ENV` | development / staging / production | development |
| `DEBUG` | Swagger docs aan/uit | true |
| `SECRET_KEY` | Applicatie secret | (wijzigen!) |
| `API_PORT` | Host-poort voor API backend | 8000 |
| `FRONTEND_PORT` | Host-poort voor frontend dev server | 1000 |
| `NGINX_PORT` | Host-poort voor nginx reverse proxy | 80 |
| `POSTGRES_*` | PostgreSQL connectie | yoohoo/ps_core_db |
| `REDIS_*` | Redis connectie | localhost:6379 |
| `JWT_SECRET_KEY` | JWT signing secret | (wijzigen!) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token geldigheid | 30 |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token geldigheid | 7 |
| `CORS_ORIGINS` | Toegestane origins | localhost:3000,1000 |
| `SMTP_*` | E-mail configuratie (SMTP) | Mailpit dev |
| `FRONTEND_URL` | Frontend URL voor verificatie-links | http://localhost:2000 |
| `EMAIL_VERIFICATION_EXPIRE_HOURS` | Verificatie token geldigheid | 48 |
| `UNVERIFIED_CLEANUP_DAYS` | Dagen voor cleanup onverifieerde accounts | 7 |
| `RATE_LIMIT_PER_MINUTE` | Rate limiet | 60 |
| `INVITATION_EXPIRE_HOURS` | Uitnodiging geldigheid | 72 |
| `PASSWORD_RESET_EXPIRE_MINUTES` | Wachtwoord reset token geldigheid | 30 |
| `TOTP_ISSUER_NAME` | 2FA issuer naam | Yoohoo |
| `MAX_ACTIVE_SESSIONS` | Max actieve sessies per user | 10 |
| `PGBOUNCER_HOST` | PgBouncer hostname | pgbouncer |
| `PGBOUNCER_PORT` | PgBouncer poort | 6432 |
| `USE_PGBOUNCER` | PgBouncer inschakelen | true |
| `ARQ_REDIS_DB` | Redis database voor arq worker | 1 |
| `ARQ_MAX_JOBS` | Max gelijktijdige arq jobs | 10 |
| `ARQ_JOB_TIMEOUT` | Job timeout in seconden | 300 |
| `LOG_LEVEL` / `LOG_FORMAT` | Logging configuratie | INFO / console |

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
| **5. Billing** | Voltooid | Platform billing (Stripe/Mollie), tenant billing (tuition plans, invoices) |
| **5.5. Collaborations** | Voltooid | Samenwerkingsverbanden tussen scholen, collaborator management |
| **5.6. Security Hardening** | Voltooid | 11 fasen: headers, CORS, HTTPS, encryption, HMAC tokens, circuit breakers, resource limits |
| **6. Multi-Docent** | In uitvoering | Docent-leerling koppeling, DataScope filtering, vervanging, audit trail |
| **4. Plugins & API** | Gepland | Plugin systeem, webhooks, API keys |

---

## Conventies

- Python bestanden: `snake_case`
- Vue componenten: `PascalCase`
- API routes: kebab-case
- Taal in code/comments: Engels
- Taal in UI/klantcommunicatie: Nederlands (primair)
- Module structuur: elke module heeft `__init__.py`, `models.py`, `schemas.py`, `router.py`, `service.py`
- Module scope: platform-modules (auth, admin, tenant_mgmt) in `modules/platform/`, organisatie-modules (student, attendance, schedule, notification) in `modules/tenant/`
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
