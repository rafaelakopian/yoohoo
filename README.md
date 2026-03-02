# Yoohoo

Multi-tenant SaaS platform voor muziekschoolbeheer. Leerlingadministratie, aanwezigheidsregistratie, roosterbeheer en oudercommunicatie — alles op één plek.

## Tech Stack

| Component | Technologie |
|-----------|-------------|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Alembic |
| Frontend | Vue 3, TypeScript, Vite, Pinia, Tailwind CSS |
| Database | PostgreSQL 16, Redis 7 |
| Infra | Docker Compose, Nginx, PgBouncer, GitHub Actions |
| Monitoring | Prometheus, Grafana, Loki, Uptime Kuma |

## Architectuur

```
                    ┌─────────┐
                    │  Nginx  │ :80 / :443
                    └────┬────┘
              ┌──────────┼──────────┐
              ▼                     ▼
        ┌───────────┐        ┌───────────┐
        │  FastAPI   │        │   Vue 3   │
        │  Backend   │        │  Frontend │
        └─────┬─────┘        └───────────┘
              │
     ┌────────┼────────┐
     ▼        ▼        ▼
┌─────────┐ ┌─────┐ ┌────────┐
│PgBouncer│ │Redis│ │  arq   │
│    ↓    │ │     │ │ Worker │
│PostgreSQL│ └─────┘ └────────┘
└─────────┘
```

**Multi-tenant:** Database-per-tenant isolatie. Elke school krijgt een eigen database. Tenant context via slug-in-URL (`/api/v1/schools/{slug}/...`).

## Snel starten

```bash
# 1. Environment instellen
cp .env.example .env

# 2. Development starten (Docker Compose met hot reload)
make dev

# 3. Migraties draaien
make migrate-central
make migrate-tenant SLUG=pianoschool-apeldoorn

# 4. Openen
# Frontend: http://localhost:2000
# API docs: http://localhost:8000/docs
# Mailpit:  http://localhost:8025
```

## Commando's

```bash
make dev              # Development starten
make dev-down         # Development stoppen
make up               # Productie starten
make down             # Productie stoppen
make test             # Tests draaien (Docker)
make test-local       # Tests draaien (lokaal)
make lint             # Linting (ruff)
make migrate-central  # Central DB migraties
make migrate-tenant SLUG=<slug>  # Tenant DB migraties
make worker-logs      # Worker logs bekijken
make db-shell         # PostgreSQL shell
make redis-shell      # Redis shell
```

## Projectstructuur

```
yoohoo/
├── backend/           # FastAPI backend + arq worker
│   ├── app/
│   │   ├── core/      # Infrastructure (health, middleware, jobs, metrics)
│   │   ├── db/        # Database layer (central + tenant)
│   │   └── modules/
│   │       ├── platform/   # Auth, admin, tenant management, billing
│   │       └── tenant/     # Students, attendance, schedule, notifications
│   ├── alembic/       # Migraties (central + tenant)
│   └── tests/         # ~148 tests
├── frontend/          # Vue 3 SPA
│   └── src/
│       ├── api/       # HTTP client layer
│       ├── components/
│       ├── stores/    # Pinia state management
│       └── views/     # Pagina's (platform + tenant)
├── nginx/             # Reverse proxy config
├── monitoring/        # Prometheus, Grafana, Loki, Promtail
├── infra/             # Terraform (Hetzner VPS)
├── scripts/           # Backup, SSL
└── docs/              # Deploy checklist
```

## Modules

| Module | Beschrijving |
|--------|-------------|
| **Auth** | Registratie, login, JWT, 2FA/TOTP, uitnodigingen, wachtwoord reset, sessiebeheer |
| **Permissions** | Dynamisch groepen/permissiesysteem (25 permissies, 3 default groepen per school) |
| **Students** | Leerling CRUD, Excel import, ouder-leerling koppelingen, docent toewijzing |
| **Attendance** | Aanwezigheidsregistratie, bulk registratie per klas |
| **Schedule** | Lesrooster, lesslots, lesinstanties, vakanties, vervanging |
| **Notifications** | E-mail + in-app notificaties, voorkeuren per gebruiker |
| **Billing** | Facturatie, lesgeldplannen, Stripe/Mollie integratie |
| **Admin** | Platform admin dashboard, tenant/user beheer |

## Deployment

CI/CD via GitHub Actions. Push naar `main` → automatische deploy naar Hetzner VPS.

Zie [`docs/deploy-checklist.md`](docs/deploy-checklist.md) voor de volledige go-live handleiding.

## Licentie

Proprietary. Alle rechten voorbehouden.
