# Load .env variables (optional, no error if missing)
-include .env
export

.PHONY: dev dev-down up down build logs logs-api worker-logs \
	migrate-central migrate-tenant migrate-tenants \
	test test-local lint db-shell redis-shell audit \
	monitoring-up monitoring-down monitoring-logs backup \
	demo-up demo-down demo-reset \
	demo-status demo-dunning demo-trials demo-purge \
	demo-advance-7 demo-advance-14 demo-advance-30 \
	demo-generate-invoices demo-generate-invoices-current

# Development
dev:
	docker compose -f docker-compose.dev.yml up --build

dev-down:
	docker compose -f docker-compose.dev.yml down

# Production (images from GHCR — never build locally)
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

worker-logs:
	docker compose logs -f worker

# Database
migrate-central:
	docker compose exec api alembic -x mode=central upgrade central@head

migrate-tenant:
	@if [ -z "$(SLUG)" ]; then echo "Usage: make migrate-tenant SLUG=myschool"; exit 1; fi
	docker compose exec api alembic -x mode=tenant -x tenant_slug=$(SLUG) upgrade tenant@head

migrate-tenants:
	bash scripts/migrate-all-tenants.sh

# Testing
test:
	docker compose exec api pytest -v --cov=app

test-local:
	cd backend && python -m pytest -v --cov=app

# Linting
lint:
	cd backend && python -m ruff check .

# Database shell
db-shell:
	docker compose exec postgres psql -U $(POSTGRES_USER) $(POSTGRES_DB)

redis-shell:
	docker compose exec redis redis-cli

# Security
audit:
	docker compose exec api pip-audit

# Monitoring
monitoring-up:
	docker compose -f monitoring/docker-compose.monitoring.yml up -d
	docker compose -f monitoring/docker-compose.collector.yml up -d

monitoring-down:
	docker compose -f monitoring/docker-compose.monitoring.yml down
	docker compose -f monitoring/docker-compose.collector.yml down

monitoring-logs:
	docker compose -f monitoring/docker-compose.monitoring.yml logs -f

# Backup
backup:
	bash scripts/backup/backup.sh

# Demo seed
demo-up:
	docker compose -f docker-compose.dev.yml exec api python scripts/seed_demo.py

demo-down:
	docker compose -f docker-compose.dev.yml exec api python scripts/seed_demo.py --reset --no-seed

demo-reset:
	docker compose -f docker-compose.dev.yml exec api python scripts/seed_demo.py --reset

# Demo job triggers
demo-status:
	docker compose -f docker-compose.dev.yml exec api python scripts/demo_jobs.py status

demo-dunning:
	docker compose -f docker-compose.dev.yml exec api python scripts/demo_jobs.py dunning

demo-trials:
	docker compose -f docker-compose.dev.yml exec api python scripts/demo_jobs.py trials

demo-purge:
	docker compose -f docker-compose.dev.yml exec api python scripts/demo_jobs.py purge

demo-advance-7:
	docker compose -f docker-compose.dev.yml exec api python scripts/demo_jobs.py advance --days 7

demo-advance-14:
	docker compose -f docker-compose.dev.yml exec api python scripts/demo_jobs.py advance --days 14

demo-advance-30:
	docker compose -f docker-compose.dev.yml exec api python scripts/demo_jobs.py advance --days 30

demo-generate-invoices:
	docker compose -f docker-compose.dev.yml exec api python scripts/demo_jobs.py generate-invoices

demo-generate-invoices-current:
	docker compose -f docker-compose.dev.yml exec api python scripts/demo_jobs.py generate-invoices --month current
