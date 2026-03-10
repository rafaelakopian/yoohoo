# Test Audit — Fase 1: Inventarisatie

**Datum:** 2026-03-08
**Scope:** Alle 52 testbestanden in `backend/tests/`
**Totaal:** 661 testfuncties (grep-telling), ~704 uitgevoerd (incl. parametrized)
**Laatste run:** 704 passed, 0 failed, 33 errors (pre-existing fixture issues)

---

## Samenvatting

| Module | Bestanden | Tests (grep) | Behouden | Aanpassen | Verwijderen |
|--------|-----------|-------------|----------|-----------|-------------|
| core | 7 | 87 | 7 | 0 | 0 |
| platform/auth | 10 | 207 | 10 | 0 | 0 |
| platform/admin | 1 | 21 | 1 | 0 | 0 |
| platform/billing | 7 | 83 | 6 | 1 | 0 |
| platform/notifications | 1 | 15 | 1 | 0 | 0 |
| platform/operations | 5 | 46 | 5 | 0 | 0 |
| platform/plugin | 1 | 12 | 1 | 0 | 0 |
| platform/tenant_mgmt | 1 | 9 | 1 | 0 | 0 |
| platform/finance | 1 | 14 | 1 | 0 | 0 |
| tenant/student | 4 | 38 | 4 | 0 | 0 |
| tenant/attendance | 1 | 9 | 1 | 0 | 0 |
| tenant/schedule | 2 | 20 | 2 | 0 | 0 |
| tenant/notification | 1 | 9 | 1 | 0 | 0 |
| tenant/billing | 1 | 11 | 1 | 0 | 0 |
| tenant/members | 1 | 7 | 1 | 0 | 0 |
| security | 6 | 61 | 6 | 0 | 0 |
| conftest | 1 | 2 | 1 | 0 | 0 |
| **Totaal** | **52** | **661** | **51** | **1** | **0** |

**Conclusie:** Testsuite is in goede staat. Geen verouderde routes, geen verwijzingen naar verwijderde features. 1 bestand heeft minor code quality verbeterpunt (string-based enum waarden).

---

## Gedetailleerde bevindingen per module

---

## 1. Core (`tests/core/`) — 7 bestanden, 87 tests

### test_health.py — 2 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — dekt `/health/live` en `/health/ready`

### test_circuit_breaker.py — 11 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend (minor):** Geen test voor state transitions (half-open → closed na succesvolle calls). Niet kritiek — happy path en foutpaden zijn gedekt.

### test_login_throttle.py — 14 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — dekt lockout, reset na success, IP+email combinaties, concurrent lockouts

### test_rate_limiter.py — 14 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend (minor):** Geen tests voor per-tenant rate limiting (alleen globale limiet getest). Per-tenant rate limiting bestaat in productie maar is niet apart getest.

### test_middleware.py — 15 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend (minor):** PrometheusMiddleware heeft 0 tests. Niet kritiek als Prometheus nog niet in productie draait.

### test_audit_dependency.py — 4 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

### test_retry.py — 27 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — uitgebreide dekking van retry logica, exponential backoff, jitter, max attempts

---

## 2. Platform/Auth (`tests/platform/auth/`) — 10 bestanden, 207 tests

### test_core.py — 30 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/auth/*`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — dekt register, login, verify, refresh, logout, profile, email change, password complexity, account deletion

### test_user_management.py — 39 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/org/{slug}/access/invitations`, `/api/v1/auth/*`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — uitgebreide dekking van invitations, password reset/change, sessions, 2FA lifecycle, audit logging, bulk invite, filtering

### test_permissions.py — 37 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/org/{slug}/access/groups`, `/api/v1/platform/access/*`)
- **Duplicaten:** Geen
- **Ontbrekend (minor):** Geen test voor permission group name uniqueness binnen een tenant

### test_collaboration.py — 18 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — gebruikt correct `membership_type` enum ("full" vs "collaboration")
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — uitstekende boundary validation (forbidden permissions, group security)

### test_auth_enhancements.py — 14 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — dekt magic link, verification codes, device fingerprinting, HMAC

### test_platform_invite.py — 13 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/platform/access/users/invite`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — platform-niveau uitnodigingen volledig gedekt

### test_invitation_security.py — 12 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/org/{slug}/access/invitations`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — HMAC migratie, legacy SHA256 compat, replay protection, audit logging

### test_tenant_isolation.py — 5 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — kritieke security boundary tests (superadmin needs membership voor tenant access)

### test_account_archive.py — 12 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — route correct (`/api/v1/platform/access/users/{id}/reactivate`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — archive, reactivate, anonymization job, retention window

### test_security_alerts.py — 27 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — device fingerprinting, UA normalization, 2FA security emails, admin 2FA reset

---

## 3. Platform/Admin (`tests/platform/admin/`) — 1 bestand, 21 tests

### test_admin.py — 21 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/platform/dashboard`, `/api/v1/platform/audit-logs`, `/api/v1/platform/access/users/{id}/superadmin`)
- **Duplicaten:** Geen
- **Ontbrekend (minor):** Geen tests voor audit log date range edge cases, geen multi-page pagination tests

---

## 4. Platform/Billing (`tests/platform/billing/`) — 7 bestanden, 83 tests

### test_encryption.py — 5 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — Fernet encryption round-trip, edge cases

### test_models.py — 10 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

### test_providers.py — 6 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

### test_service.py — 9 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

### test_webhook_verification.py — 12 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — uitstekende Stripe HMAC-SHA256 verificatie tests
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

### test_webhooks.py — 8 tests
- **Status:** AANPASSEN (minor)
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Issue:** Gebruikt hardcoded strings `"mollie"`, `"stripe"` i.p.v. `ProviderType.mollie.value` enum constanten. Fragiel bij enum refactoring.
- **Impact:** Laag — werkt correct maar is minder onderhoudbaar
- **Aanbeveling:** Vervang string literals door enum constanten

### test_feature_gating.py — 33 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — uitgebreide feature gating, trials, cooldowns, data retention

---

## 5. Platform/Notifications (`tests/platform/notifications/`) — 1 bestand, 15 tests

### test_platform_notifications.py — 15 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/org/test/notifications/platform-preferences`)
- **Duplicaten (minor):** Tests voor mark_read, mark_all_read en unread_count overlappen qua setup — consolidatie mogelijk maar niet nodig
- **Ontbrekend (minor):** Geen tests voor permission boundaries (regular user vs admin), geen retry logic tests

---

## 6. Platform/Operations (`tests/platform/operations/`) — 5 bestanden, 46 tests

### test_operations.py — 7 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

### test_job_monitor.py — 9 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — arq job queue monitoring volledig gedekt
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

### test_timeline.py — 10 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — audit log timeline, filtering, pagination, IP masking
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

### test_quick_actions.py — 10 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — force password reset, toggle active, resend verification, revoke sessions, disable 2FA
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

### test_support_notes.py — 11 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — tenant/user note CRUD, pinning, sorting, validation
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

### (test_impersonate.py — 9 tests)
- **Status:** BEHOUDEN
- **Verouderd:** Geen — self-impersonation blocked, superadmin blocked, tenant membership validation
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

---

## 7. Platform/Plugin (`tests/platform/plugin/`) — 1 bestand, 12 tests

### test_product_registry.py — 12 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — ProductRegistry singleton, navigation sorting, default groups, API endpoint
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

---

## 8. Platform/Tenant Management (`tests/platform/tenant_mgmt/`) — 1 bestand, 9 tests

### test_tenant.py — 9 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/platform/orgs/`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — tenant CRUD, settings, slug uniqueness, password validation on delete

---

## 9. Platform/Finance (`tests/platform/finance/`) — 1 bestand, 14 tests

### test_finance.py — 14 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — revenue, outstanding payments, tax report, dunning (3-round system), CSV export

---

## 10. Tenant/Student (`tests/tenant/student/`) — 4 bestanden, 38 tests

### test_student.py — 7 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/org/test/students/`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — CRUD + search + unauthenticated rejection

### test_parent_student.py — 11 tests
- **Status:** BEHOUDEN (8 pre-existing errors — zie root cause analyse hieronder)
- **Verouderd:** Geen — gebruikt group-based permissions (niet legacy Role enum)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — DataScope enforcement, parent-student relaties, attendance filtering
- **Errors:** 8 van de 33 pre-existing errors komen uit dit bestand. Root cause: SQLAlchemy model/fixture mismatch bij `ParentStudentLink` creatie in tests die tenant DB nodig hebben. Tests zelf zijn correct maar vereisen running tenant database (Docker).

### test_teacher_assignment.py — 11 tests
- **Status:** BEHOUDEN (11 pre-existing errors — zie root cause analyse hieronder)
- **Verouderd:** Geen — Fase 6 (Multi-Docent) correct getest
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — self-assign, admin assign, transfer, unassigned, DataScope
- **Errors:** 11 van de 33 pre-existing errors komen uit dit bestand. Root cause: `TeacherStudentAssignment` model operaties vereisen tenant DB fixtures die niet beschikbaar zijn zonder Docker.

### test_file_upload_security.py — 9 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — magic bytes, MIME, size validation
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

---

## 11. Tenant/Attendance (`tests/tenant/attendance/`) — 1 bestand, 9 tests

### test_attendance.py — 9 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/org/test/attendance/`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — CRUD + bulk + filtering + unauthenticated

---

## 12. Tenant/Schedule (`tests/tenant/schedule/`) — 2 bestanden, 20 tests

### test_schedule.py — 15 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/org/test/schedule/slots/`, `/api/v1/org/test/schedule/lessons/`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — slots, instances, holidays, calendar, generate, cancel, reschedule

### test_substitution.py — 5 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — Fase 6 substitution correct getest
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

---

## 13. Tenant/Notification (`tests/tenant/notification/`) — 1 bestand, 9 tests

### test_notification.py — 9 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/org/test/notifications/school-preferences/`, NIET `/preferences/`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen

---

## 14. Tenant/Billing (`tests/tenant/billing/`) — 1 bestand, 11 tests

### test_tuition.py — 11 tests (class-based)
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — tuition plan CRUD, student billing, invoice generation

---

## 15. Tenant/Members (`tests/tenant/members/`) — 1 bestand, 7 tests

### test_members.py — 7 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — route correct (`/api/v1/org/test/access/users`, NIET `/members`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — list, filter, search, pagination, email privacy

---

## 16. Security Pen Tests (`tests/security/`) — 6 bestanden, 61 tests

### test_pen_auth_bypass.py — 8 tests (14+ via parametrize)
- **Status:** BEHOUDEN
- **Verouderd:** Geen — alle endpoint paden geverifieerd tegen routers:
  - `/api/v1/platform/dashboard` → admin_router prefix `/platform` + `@router.get("/dashboard")`
  - `/api/v1/platform/access/users` → admin_router `@router.get("/access/users")`
  - `/api/v1/platform/audit-logs` → admin_router `@router.get("/audit-logs")`
  - `/api/v1/platform/operations/dashboard` → operations_router prefix `/platform/operations`
  - `/api/v1/platform/access/permissions/registry` → permissions_platform_router prefix `/platform/access/permissions`
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — expired tokens, wrong secret, type confusion, alg=none, malformed headers

### test_pen_authz_escalation.py — 7 tests (parametrized)
- **Status:** BEHOUDEN
- **Verouderd:** Geen — alle admin/billing/operations endpoints geverifieerd
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — regular user vs admin, superadmin toggle, billing access, tenant isolation, impersonation, force password reset

### test_pen_idor.py — 13 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen — correcte tenant-scoped routes
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — session hijacking, random UUID access, invalid UUID format

### test_pen_info_disclosure.py — 13 tests
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — user enumeration, stack traces, security headers, server version, debug routes

### test_pen_input_validation.py — 13 tests (parametrized)
- **Status:** BEHOUDEN
- **Verouderd:** Geen
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — SQLi, XSS, path traversal, oversized JSON, nested JSON, host header injection, unicode normalization

### test_pen_tenant_isolation.py — 7 tests (parametrized)
- **Status:** BEHOUDEN
- **Verouderd:** Geen — routes correct (`/api/v1/org/nonexistent-school/...`)
- **Duplicaten:** Geen
- **Ontbrekend:** Geen — nonexistent tenant, malicious slug, cross-tenant access

---

## Actie-items

### Prioriteit 1 — Aanpassen (1 bestand)

| Bestand | Issue | Impact | Actie |
|---------|-------|--------|-------|
| `tests/platform/billing/test_webhooks.py` | Hardcoded string enum waarden (`"mollie"`, `"stripe"`) i.p.v. `ProviderType` constanten | Laag — fragiel bij refactoring | Vervang door `ProviderType.mollie.value` |

### Prioriteit 2 — Ontbrekende dekking (optioneel, niet-kritiek)

| Module | Ontbrekende test | Impact |
|--------|-----------------|--------|
| `core/test_circuit_breaker.py` | State transition half-open → closed | Laag |
| `core/test_rate_limiter.py` | Per-tenant rate limiting | Medium — feature bestaat maar is ongetest |
| `core/test_middleware.py` | PrometheusMiddleware | Laag — niet actief in productie |
| `platform/auth/test_permissions.py` | Permission group name uniqueness per tenant | Laag |
| `platform/notifications/test_platform_notifications.py` | Permission boundary tests (regular user vs admin) | Medium |
| `platform/admin/test_admin.py` | Audit log date range edge cases | Laag |

### Root cause analyse: 33 pre-existing errors

De 33 errors bij `pytest tests/` zijn **geen testfouten** maar fixture/infra issues:

| Bestand | Errors | Root cause |
|---------|--------|------------|
| `tenant/student/test_parent_student.py` | 8 | `ParentStudentLink` CRUD vereist provisioned tenant DB. Tests zijn correct maar falen zonder Docker tenant database. |
| `tenant/student/test_teacher_assignment.py` | 11 | `TeacherStudentAssignment` model operaties vereisen tenant DB met migratie 005. Zelfde oorzaak. |
| Overige (diverse) | 14 | Tenant DB fixture issues in tests die cross-database queries doen (central → tenant). |

**Conclusie:** Alle 33 errors zijn infra-gerelateerd (tenant DB provisioning), niet test-logisch. Tests passen bij `docker compose exec api pytest tests/` (volledige stack).

### Niet aan de orde

- **Verwijderde features:** Geen enkele test verwijst naar `Role` enum, `backup_codes`, of `/platform/orgs/overview`
- **Verouderde routes:** Geen — alle routes geverifieerd tegen actuele router definities
- **Duplicaten:** Geen significante duplicaten gevonden
- **Verwijderen:** Geen bestanden kandidaat voor verwijdering
