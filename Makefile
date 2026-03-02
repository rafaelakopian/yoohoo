# Load .env variables (optional, no error if missing)
-include .env
export

.PHONY: dev up down build logs test migrate-central migrate-tenant lint worker-logs audit

# Development
dev:
	docker compose -f docker-compose.dev.yml up --build

dev-down:
	docker compose -f docker-compose.dev.yml down

# Production
up:
	docker compose up -d --build

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
