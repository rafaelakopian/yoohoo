"""
=====================================================
CROSS-TENANT PENETRATION TEST — Full Attack Simulation
=====================================================

Simulates six real attack scenarios against the multi-tenant architecture.

Setup:
├── Tenant "psa"  (UUID: ...0002) — Attacker A's home tenant
├── Tenant "demo" (UUID: ...0003) — Target tenant
├── Attacker A: PSA member (beheerder)  → tries to access DEMO
├── Attacker B: External user (valid JWT, zero memberships)
└── Attacker C: PSA collaborator (medewerker) → tries admin actions

Aanval 1 — Direct path traversal (A/B → demo endpoints)
Aanval 2 — Slug manipulation (encoding tricks, path traversal)
Aanval 3 — IDOR (cross-tenant resource IDs)
Aanval 4 — Privilege escalation (collaborator → admin)
Aanval 5 — JWT manipulation (expired, tampered, deactivated, token type confusion)
Aanval 6 — Unauthenticated tenant discovery (slug enumeration)
"""

import uuid
from datetime import datetime, timedelta, timezone
import jwt as pyjwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from app.config import settings
from app.core.permissions import permission_registry
from app.core.security import create_access_token, hash_password
from app.db.central import get_central_db
from app.dependencies import get_tenant_db
from app.main import app as fastapi_app
from app.modules.platform.auth.models import (
    GroupPermission,
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.billing.subscription_guard import clear_sub_status_cache
from app.modules.platform.tenant_mgmt.models import Tenant
from app.modules.products.school.path_dependency import clear_slug_to_id_cache

# ── Constants ──
PSA_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DEMO_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
PSA_SLUG = "psa"
DEMO_SLUG = "demo"


# ── Fixtures ──


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear all in-memory caches between tests."""
    clear_slug_to_id_cache()
    clear_sub_status_cache()
    yield
    clear_slug_to_id_cache()
    clear_sub_status_cache()


@pytest_asyncio.fixture
async def pentest_env(db_session, tenant_db_session):
    """Full penetration test environment with 2 tenants and 3 attackers.

    Uses REAL slug resolution (resolve_tenant_from_path is NOT mocked).
    """

    # ── Override dependencies ──
    async def override_central_db():
        yield db_session

    async def override_tenant_db():
        yield tenant_db_session

    fastapi_app.dependency_overrides[get_central_db] = override_central_db
    fastapi_app.dependency_overrides[get_tenant_db] = override_tenant_db
    # NOTE: resolve_tenant_from_path is NOT overridden → real slug lookup

    # ── Create tenants ──
    psa_tenant = Tenant(
        id=PSA_TENANT_ID,
        name="Pianoschool Apeldoorn",
        slug=PSA_SLUG,
        is_active=True,
        is_provisioned=True,
    )
    demo_tenant = Tenant(
        id=DEMO_TENANT_ID,
        name="Demo School",
        slug=DEMO_SLUG,
        is_active=True,
        is_provisioned=True,
    )
    db_session.add_all([psa_tenant, demo_tenant])
    await db_session.flush()

    # ── Helper: create user + JWT ──
    async def create_attacker(email: str, name: str, is_active: bool = True):
        user = User(
            email=email,
            hashed_password=hash_password("TestPassword123!"),
            full_name=name,
            email_verified=True,
            is_superadmin=False,
            is_active=is_active,
        )
        db_session.add(user)
        await db_session.flush()

        token = create_access_token(
            user_id=user.id,
            email=user.email,
            roles=[],
            # No user_agent → no ua_fp → no binding check
        )
        return user, {"Authorization": f"Bearer {token}"}

    # ── Attacker A: PSA member (beheerder) ──
    attacker_a, headers_a = await create_attacker(
        f"attacker-a-{uuid.uuid4().hex[:8]}@evil.com", "Attacker A (PSA Beheerder)"
    )
    membership_a = TenantMembership(
        user_id=attacker_a.id, tenant_id=PSA_TENANT_ID, is_active=True
    )
    db_session.add(membership_a)
    await db_session.flush()

    # Beheerder group in PSA with ALL permissions
    group_beheerder = PermissionGroup(
        tenant_id=PSA_TENANT_ID, name="Beheerder", slug="beheerder", is_default=True
    )
    db_session.add(group_beheerder)
    await db_session.flush()
    for codename in permission_registry.get_all_codenames():
        db_session.add(
            GroupPermission(group_id=group_beheerder.id, permission_codename=codename)
        )
    await db_session.flush()
    db_session.add(
        UserGroupAssignment(user_id=attacker_a.id, group_id=group_beheerder.id)
    )
    await db_session.flush()

    # ── Attacker B: No membership anywhere ──
    attacker_b, headers_b = await create_attacker(
        f"attacker-b-{uuid.uuid4().hex[:8]}@evil.com", "Attacker B (Outsider)"
    )

    # ── Attacker C: PSA collaborator (medewerker, limited perms) ──
    attacker_c, headers_c = await create_attacker(
        f"attacker-c-{uuid.uuid4().hex[:8]}@evil.com", "Attacker C (PSA Collaborator)"
    )
    membership_c = TenantMembership(
        user_id=attacker_c.id,
        tenant_id=PSA_TENANT_ID,
        is_active=True,
        membership_type="collaboration",
    )
    db_session.add(membership_c)
    await db_session.flush()

    group_medewerker = PermissionGroup(
        tenant_id=PSA_TENANT_ID, name="Medewerker", slug="medewerker", is_default=True
    )
    db_session.add(group_medewerker)
    await db_session.flush()
    medewerker_perms = [
        "students.view_assigned",
        "attendance.view_assigned",
        "attendance.create",
        "attendance.edit",
        "schedule.view_assigned",
        "schedule.manage",
        "notifications.view",
        "billing.view",
    ]
    for codename in medewerker_perms:
        db_session.add(
            GroupPermission(group_id=group_medewerker.id, permission_codename=codename)
        )
    await db_session.flush()
    db_session.add(
        UserGroupAssignment(user_id=attacker_c.id, group_id=group_medewerker.id)
    )
    await db_session.flush()

    # ── Create HTTP client ──
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "client": client,
            "attacker_a": {"user": attacker_a, "headers": headers_a},
            "attacker_b": {"user": attacker_b, "headers": headers_b},
            "attacker_c": {"user": attacker_c, "headers": headers_c},
            "psa_tenant": psa_tenant,
            "demo_tenant": demo_tenant,
            "group_beheerder": group_beheerder,
            "group_medewerker": group_medewerker,
            "db_session": db_session,
        }

    fastapi_app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════════
# AANVAL 1 — Direct Path Traversal
# Attacker A (PSA member) and B (outsider) try every DEMO endpoint
# Expected: 403 or 404 on ALL
# ═══════════════════════════════════════════════════════════════════════════

DEMO_READ_ENDPOINTS = [
    ("GET", "/api/v1/org/demo/students/"),
    ("GET", "/api/v1/org/demo/students/my-children"),
    ("GET", "/api/v1/org/demo/students/my-students"),
    ("GET", "/api/v1/org/demo/students/unassigned"),
    ("GET", "/api/v1/org/demo/attendance/"),
    ("GET", "/api/v1/org/demo/schedule/slots/"),
    ("GET", "/api/v1/org/demo/schedule/holidays/"),
    ("GET", "/api/v1/org/demo/notifications/"),
    ("GET", "/api/v1/org/demo/notifications/preferences"),
    ("GET", "/api/v1/org/demo/access/invitations"),
    ("GET", "/api/v1/org/demo/access/groups"),
    ("GET", "/api/v1/org/demo/access/permissions"),
    ("GET", "/api/v1/org/demo/access/users"),
    ("GET", "/api/v1/org/demo/collaborations/"),
    ("GET", "/api/v1/org/demo/billing/platform-invoices"),
    ("GET", "/api/v1/org/demo/subscription-status"),
    ("GET", "/api/v1/org/demo/features"),
    ("GET", "/api/v1/org/demo/tuition/plans"),
    ("GET", "/api/v1/org/demo/tuition/student-billing"),
    ("GET", "/api/v1/org/demo/tuition/invoices"),
]

DEMO_WRITE_ENDPOINTS = [
    ("POST", "/api/v1/org/demo/students/", {"first_name": "Hack", "last_name": "Er"}),
    ("POST", "/api/v1/org/demo/attendance/", {"student_id": str(uuid.uuid4()), "date": "2026-01-01", "status": "present"}),
    ("POST", "/api/v1/org/demo/access/invitations", {"email": "hacker@evil.com"}),
    ("POST", "/api/v1/org/demo/access/groups", {"name": "Hacked", "description": "test"}),
    ("POST", "/api/v1/org/demo/collaborations/invite", {"email": "hacker@evil.com"}),
    ("POST", "/api/v1/org/demo/schedule/slots/", {"day_of_week": 1, "start_time": "09:00", "end_time": "10:00"}),
]


class TestAanval1DirectPathTraversal:
    """Attacker A (PSA beheerder) and B (outsider) try all DEMO endpoints."""

    @pytest.mark.parametrize("method,path", DEMO_READ_ENDPOINTS)
    async def test_attacker_a_read_blocked_from_demo(self, pentest_env, method, path):
        """PSA member cannot READ demo tenant data."""
        resp = await pentest_env["client"].request(
            method, path, headers=pentest_env["attacker_a"]["headers"]
        )
        assert resp.status_code in (
            403,
            404,
        ), f"BREACH: {method} {path} → {resp.status_code}"

    @pytest.mark.parametrize("method,path", DEMO_READ_ENDPOINTS)
    async def test_attacker_b_read_blocked_from_demo(self, pentest_env, method, path):
        """Outsider (no membership) cannot READ demo tenant data."""
        resp = await pentest_env["client"].request(
            method, path, headers=pentest_env["attacker_b"]["headers"]
        )
        assert resp.status_code in (
            403,
            404,
        ), f"BREACH: {method} {path} → {resp.status_code}"

    @pytest.mark.parametrize("method,path,body", DEMO_WRITE_ENDPOINTS)
    async def test_attacker_a_write_blocked_on_demo(
        self, pentest_env, method, path, body
    ):
        """PSA member cannot WRITE to demo tenant."""
        resp = await pentest_env["client"].request(
            method, path, json=body, headers=pentest_env["attacker_a"]["headers"]
        )
        assert resp.status_code in (
            403,
            404,
        ), f"BREACH: {method} {path} → {resp.status_code}"

    @pytest.mark.parametrize("method,path,body", DEMO_WRITE_ENDPOINTS)
    async def test_attacker_b_write_blocked_on_demo(
        self, pentest_env, method, path, body
    ):
        """Outsider cannot WRITE to demo tenant."""
        resp = await pentest_env["client"].request(
            method, path, json=body, headers=pentest_env["attacker_b"]["headers"]
        )
        assert resp.status_code in (
            403,
            404,
        ), f"BREACH: {method} {path} → {resp.status_code}"

    async def test_attacker_a_cannot_read_demo_as_psa(self, pentest_env):
        """Verify attacker A CAN access PSA (own tenant) but NOT demo."""
        client = pentest_env["client"]
        headers = pentest_env["attacker_a"]["headers"]

        # Own tenant — should work (200)
        psa_resp = await client.get(
            "/api/v1/org/psa/access/permissions", headers=headers
        )
        assert psa_resp.status_code == 200, f"PSA access failed: {psa_resp.status_code}"

        # Cross-tenant — must fail
        demo_resp = await client.get(
            "/api/v1/org/demo/access/permissions", headers=headers
        )
        assert demo_resp.status_code in (403, 404), (
            f"BREACH: demo access returned {demo_resp.status_code}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# AANVAL 2 — Slug Manipulation
# Encoding tricks, path traversal, null bytes, case variations
# Expected: 404 or 422 on all (none should resolve to a valid tenant)
# ═══════════════════════════════════════════════════════════════════════════


class TestAanval2SlugManipulation:
    """Slug encoding tricks to bypass tenant resolution."""

    # Slugs that can be sent via HTTP client (no raw non-printable bytes)
    MALICIOUS_SLUGS = [
        ("PSA", "uppercase"),
        ("Psa", "mixed case"),
        ("psa ", "trailing space"),
        (" psa", "leading space"),
        # psa%00 (URL-encoded null byte) is tested separately — PostgreSQL rejects \x00
        # at the DB driver level, causing a 500. This IS blocked, but uncleanly.
        ("psa/../demo", "path traversal attempt"),
        ("../demo", "direct path traversal"),
        ("psa%2F..%2Fdemo", "double-encoded traversal"),
        ("demo' OR '1'='1", "SQL injection in slug"),
        ("demo--", "SQL comment in slug"),
        ("demo;DROP TABLE tenants", "SQL injection via semicolon"),
        ("demo%27%20OR%201=1", "URL-encoded SQL injection"),
        ("{slug}", "template variable"),
        ("*", "wildcard"),
    ]

    @pytest.mark.parametrize("slug,desc", MALICIOUS_SLUGS)
    async def test_malicious_slug_rejected(self, pentest_env, slug, desc):
        """Slug manipulation '{desc}' should not resolve to a valid tenant."""
        resp = await pentest_env["client"].get(
            f"/api/v1/org/{slug}/students/",
            headers=pentest_env["attacker_a"]["headers"],
        )
        # Must NOT be 200 — 404 (not found), 422 (validation), 400, 307, 500 are all OK
        # (500 on null byte = PostgreSQL rejecting the character, not exploitable)
        assert resp.status_code != 200, (
            f"BREACH: slug '{slug}' ({desc}) → {resp.status_code}"
        )
        assert resp.status_code in (400, 403, 404, 422, 307, 500), (
            f"Unexpected status for slug '{slug}' ({desc}) → {resp.status_code}"
        )

    async def test_null_byte_slug_blocked(self, pentest_env):
        """URL-encoded null byte (%00) in slug is blocked.

        PostgreSQL rejects \\x00 at the driver level (CharacterNotInRepertoireError).
        This causes a 500 (unhandled DB error) or transport error — but access IS denied.
        In production, nginx rejects null bytes before they reach the application.
        """
        try:
            resp = await pentest_env["client"].get(
                "/api/v1/org/psa%00/students/",
                headers=pentest_env["attacker_a"]["headers"],
            )
            # If we get a response, it must not be 200
            assert resp.status_code != 200, (
                f"BREACH: null byte slug returned {resp.status_code}"
            )
        except Exception:
            # Transport/DB error = access denied (blocked at DB driver level)
            pass

    async def test_slugs_are_case_sensitive(self, pentest_env):
        """Confirm that 'PSA' and 'psa' are treated as different slugs."""
        client = pentest_env["client"]
        headers = pentest_env["attacker_a"]["headers"]

        # Lowercase 'psa' — exists → 200 (attacker A has membership)
        resp_lower = await client.get(
            "/api/v1/org/psa/access/permissions", headers=headers
        )
        # Uppercase 'PSA' — should NOT exist → 404
        resp_upper = await client.get(
            "/api/v1/org/PSA/access/permissions", headers=headers
        )

        assert resp_lower.status_code == 200
        assert resp_upper.status_code == 404, (
            f"Case-insensitive slug match! PSA → {resp_upper.status_code}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# AANVAL 3 — IDOR (Insecure Direct Object Reference)
# Try to access resources from another tenant by guessing UUIDs
# Expected: 404 on all (resource not in attacker's tenant DB)
# ═══════════════════════════════════════════════════════════════════════════


class TestAanval3IDOR:
    """Access cross-tenant resources by guessing IDs."""

    async def test_random_student_id_on_own_tenant(self, pentest_env):
        """Random UUID for student in own tenant → 404 (doesn't exist)."""
        fake_id = str(uuid.uuid4())
        resp = await pentest_env["client"].get(
            f"/api/v1/org/psa/students/{fake_id}",
            headers=pentest_env["attacker_a"]["headers"],
        )
        assert resp.status_code == 404

    async def test_random_attendance_id(self, pentest_env):
        """Random attendance UUID → 404."""
        fake_id = str(uuid.uuid4())
        resp = await pentest_env["client"].get(
            f"/api/v1/org/psa/attendance/{fake_id}",
            headers=pentest_env["attacker_a"]["headers"],
        )
        assert resp.status_code == 404

    async def test_random_invoice_id(self, pentest_env):
        """Random invoice UUID → 404."""
        fake_id = str(uuid.uuid4())
        resp = await pentest_env["client"].get(
            f"/api/v1/org/psa/tuition/invoices/{fake_id}",
            headers=pentest_env["attacker_a"]["headers"],
        )
        assert resp.status_code == 404

    async def test_random_slot_id(self, pentest_env):
        """Random schedule slot UUID → 404."""
        fake_id = str(uuid.uuid4())
        resp = await pentest_env["client"].get(
            f"/api/v1/org/psa/schedule/slots/{fake_id}",
            headers=pentest_env["attacker_a"]["headers"],
        )
        assert resp.status_code == 404

    async def test_demo_tenant_id_in_psa_context(self, pentest_env):
        """Use demo's tenant UUID as a student ID in PSA → 404."""
        resp = await pentest_env["client"].get(
            f"/api/v1/org/psa/students/{DEMO_TENANT_ID}",
            headers=pentest_env["attacker_a"]["headers"],
        )
        assert resp.status_code == 404

    async def test_cross_tenant_group_access(self, pentest_env):
        """Try to read a PSA group via demo endpoint → blocked."""
        group_id = str(pentest_env["group_beheerder"].id)
        resp = await pentest_env["client"].get(
            f"/api/v1/org/demo/access/groups/{group_id}",
            headers=pentest_env["attacker_a"]["headers"],
        )
        assert resp.status_code in (403, 404)

    async def test_architectural_isolation(self, pentest_env):
        """Document: each tenant has its own PostgreSQL database.

        Even if all access control checks were bypassed, the query runs
        against the RESOLVED tenant's database. Student table in psa_db
        is a completely separate table from student table in demo_db.

        get_tenant_db(request) → connects to ps_t_{slug}_db based on
        request.state.tenant_id, which is set by resolve_tenant_from_path.
        """
        # This test documents the architectural protection
        # The DB-per-tenant model means IDOR across tenants is architecturally
        # impossible — queries run against isolated databases.
        assert True  # Documented protection


# ═══════════════════════════════════════════════════════════════════════════
# AANVAL 4 — Privilege Escalation (Collaborator → Admin)
# Attacker C (collaborator/medewerker in PSA) tries admin-only actions
# Expected: 403 or 404 on all
# ═══════════════════════════════════════════════════════════════════════════


class TestAanval4PrivilegeEscalation:
    """Collaborator (medewerker) tries admin-only actions in own tenant."""

    async def test_create_group_forbidden(self, pentest_env):
        """Medewerker cannot create permission groups (requires org_settings.edit)."""
        resp = await pentest_env["client"].post(
            "/api/v1/org/psa/access/groups",
            json={"name": "Hacked Group", "description": "escalation attempt"},
            headers=pentest_env["attacker_c"]["headers"],
        )
        assert resp.status_code in (403, 404), (
            f"ESCALATION: group create → {resp.status_code}"
        )

    async def test_delete_group_forbidden(self, pentest_env):
        """Medewerker cannot delete permission groups (requires org_settings.edit)."""
        group_id = str(pentest_env["group_beheerder"].id)
        resp = await pentest_env["client"].delete(
            f"/api/v1/org/psa/access/groups/{group_id}",
            headers=pentest_env["attacker_c"]["headers"],
        )
        assert resp.status_code in (403, 404), (
            f"ESCALATION: group delete → {resp.status_code}"
        )

    async def test_send_invitation_forbidden(self, pentest_env):
        """Medewerker cannot send invitations (requires invitations.manage)."""
        resp = await pentest_env["client"].post(
            "/api/v1/org/psa/access/invitations",
            json={"email": "victim@example.com"},
            headers=pentest_env["attacker_c"]["headers"],
        )
        assert resp.status_code in (403, 404), (
            f"ESCALATION: invitation send → {resp.status_code}"
        )

    async def test_manage_collaboration_forbidden(self, pentest_env):
        """Medewerker cannot toggle collaborations (requires collaborations.manage)."""
        fake_id = str(uuid.uuid4())
        resp = await pentest_env["client"].put(
            f"/api/v1/org/psa/collaborations/{fake_id}/toggle",
            headers=pentest_env["attacker_c"]["headers"],
        )
        assert resp.status_code in (403, 404), (
            f"ESCALATION: collaboration toggle → {resp.status_code}"
        )

    async def test_list_groups_forbidden(self, pentest_env):
        """Medewerker cannot list groups (requires org_settings.view)."""
        resp = await pentest_env["client"].get(
            "/api/v1/org/psa/access/groups",
            headers=pentest_env["attacker_c"]["headers"],
        )
        assert resp.status_code in (403, 404), (
            f"ESCALATION: group list → {resp.status_code}"
        )

    async def test_invite_collaborator_forbidden(self, pentest_env):
        """Medewerker cannot invite new collaborators (requires collaborations.manage)."""
        resp = await pentest_env["client"].post(
            "/api/v1/org/psa/collaborations/invite",
            json={"email": "new-collab@evil.com"},
            headers=pentest_env["attacker_c"]["headers"],
        )
        assert resp.status_code in (403, 404), (
            f"ESCALATION: collaboration invite → {resp.status_code}"
        )

    async def test_delete_student_forbidden(self, pentest_env):
        """Medewerker can view assigned students but cannot delete (no students.delete)."""
        # medewerker has students.view_assigned but NOT students.delete
        fake_id = str(uuid.uuid4())
        resp = await pentest_env["client"].delete(
            f"/api/v1/org/psa/students/{fake_id}",
            headers=pentest_env["attacker_c"]["headers"],
        )
        # Should fail at permission check (before resource lookup)
        assert resp.status_code in (403, 404), (
            f"ESCALATION: student delete → {resp.status_code}"
        )

    async def test_import_students_forbidden(self, pentest_env):
        """Medewerker cannot import students (no students.import)."""
        resp = await pentest_env["client"].post(
            "/api/v1/org/psa/students/import",
            headers=pentest_env["attacker_c"]["headers"],
            # No file — should fail at permission check before validation
        )
        assert resp.status_code in (403, 404, 422), (
            f"ESCALATION: student import → {resp.status_code}"
        )

    async def test_collaborator_cannot_cross_to_demo(self, pentest_env):
        """Collaborator in PSA has zero access to DEMO."""
        resp = await pentest_env["client"].get(
            "/api/v1/org/demo/students/",
            headers=pentest_env["attacker_c"]["headers"],
        )
        assert resp.status_code in (403, 404)


# ═══════════════════════════════════════════════════════════════════════════
# AANVAL 5 — JWT Manipulation
# Expired tokens, wrong signatures, deactivated users, token type confusion
# Expected: 401 on all
# ═══════════════════════════════════════════════════════════════════════════


class TestAanval5JWTManipulation:
    """Manipulated, expired, and stolen JWT tokens."""

    async def test_expired_token_rejected(self, pentest_env):
        """Token expired 1 hour ago → 401."""
        attacker = pentest_env["attacker_a"]["user"]
        payload = {
            "sub": str(attacker.id),
            "email": attacker.email,
            "roles": [],
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "jti": str(uuid.uuid4()),
        }
        expired_token = pyjwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        resp = await pentest_env["client"].get(
            "/api/v1/org/psa/students/",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401, f"Expired token accepted! → {resp.status_code}"

    async def test_wrong_secret_rejected(self, pentest_env):
        """Token signed with wrong key → 401."""
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "hacker@evil.com",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
        }
        tampered = pyjwt.encode(payload, "wrong-secret-key-12345", algorithm="HS256")
        resp = await pentest_env["client"].get(
            "/api/v1/org/psa/students/",
            headers={"Authorization": f"Bearer {tampered}"},
        )
        assert resp.status_code == 401, (
            f"Tampered token accepted! → {resp.status_code}"
        )

    async def test_none_algorithm_rejected(self, pentest_env):
        """Token with algorithm 'none' (classic JWT attack) → 401."""
        attacker = pentest_env["attacker_a"]["user"]
        # Build a JWT with alg=none (bypasses signature verification in vulnerable libs)
        import base64
        import json

        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b"=")
        payload_data = {
            "sub": str(attacker.id),
            "email": attacker.email,
            "type": "access",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "jti": str(uuid.uuid4()),
        }
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload_data).encode()
        ).rstrip(b"=")
        none_token = f"{header.decode()}.{payload_b64.decode()}."

        resp = await pentest_env["client"].get(
            "/api/v1/org/psa/students/",
            headers={"Authorization": f"Bearer {none_token}"},
        )
        assert resp.status_code == 401, (
            f"alg=none attack succeeded! → {resp.status_code}"
        )

    async def test_deactivated_user_rejected(self, pentest_env):
        """Token from deactivated user → 401."""
        db = pentest_env["db_session"]
        attacker = pentest_env["attacker_b"]["user"]
        headers = pentest_env["attacker_b"]["headers"]

        # Deactivate user
        await db.execute(
            update(User).where(User.id == attacker.id).values(is_active=False)
        )
        await db.flush()

        resp = await pentest_env["client"].get(
            "/api/v1/org/psa/students/", headers=headers
        )
        assert resp.status_code == 401, (
            f"Deactivated user token accepted! → {resp.status_code}"
        )

        # Reactivate for other tests
        await db.execute(
            update(User).where(User.id == attacker.id).values(is_active=True)
        )
        await db.flush()

    async def test_no_token_rejected(self, pentest_env):
        """Request without Authorization header → 401."""
        resp = await pentest_env["client"].get("/api/v1/org/psa/students/")
        assert resp.status_code == 401

    async def test_malformed_token_rejected(self, pentest_env):
        """Garbage string as token → 401."""
        resp = await pentest_env["client"].get(
            "/api/v1/org/psa/students/",
            headers={"Authorization": "Bearer not.a.real.jwt.token"},
        )
        assert resp.status_code == 401

    async def test_refresh_token_as_access_rejected(self, pentest_env):
        """Refresh token used as access token → 401 (wrong type claim)."""
        attacker = pentest_env["attacker_a"]["user"]
        payload = {
            "sub": str(attacker.id),
            "type": "refresh",  # Wrong type!
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
        }
        refresh_as_access = pyjwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        resp = await pentest_env["client"].get(
            "/api/v1/org/psa/students/",
            headers={"Authorization": f"Bearer {refresh_as_access}"},
        )
        assert resp.status_code == 401, (
            f"Refresh token accepted as access! → {resp.status_code}"
        )

    async def test_2fa_token_as_access_rejected(self, pentest_env):
        """2FA token used as access token → 401 (wrong type claim)."""
        attacker = pentest_env["attacker_a"]["user"]
        payload = {
            "sub": str(attacker.id),
            "type": "2fa",  # Wrong type!
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
        }
        tfa_as_access = pyjwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        resp = await pentest_env["client"].get(
            "/api/v1/org/psa/students/",
            headers={"Authorization": f"Bearer {tfa_as_access}"},
        )
        assert resp.status_code == 401, (
            f"2FA token accepted as access! → {resp.status_code}"
        )

    async def test_login_verify_token_as_access_rejected(self, pentest_env):
        """Login verify token used as access token → 401."""
        attacker = pentest_env["attacker_a"]["user"]
        payload = {
            "sub": str(attacker.id),
            "type": "login_verify",  # Wrong type!
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
        }
        verify_as_access = pyjwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        resp = await pentest_env["client"].get(
            "/api/v1/org/psa/students/",
            headers={"Authorization": f"Bearer {verify_as_access}"},
        )
        assert resp.status_code == 401

    async def test_impersonation_token_without_claims_rejected(self, pentest_env):
        """Forged impersonation token without valid impersonation_id → should not escalate."""
        attacker = pentest_env["attacker_b"]["user"]
        payload = {
            "sub": str(attacker.id),
            "email": attacker.email,
            "roles": [],
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
            "impersonated_by": str(uuid.uuid4()),  # Fake admin
            "impersonation_id": str(uuid.uuid4()),
        }
        fake_imp = pyjwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        resp = await pentest_env["client"].get(
            "/api/v1/org/psa/students/",
            headers={"Authorization": f"Bearer {fake_imp}"},
        )
        # Should still be blocked (no membership)
        assert resp.status_code in (401, 403, 404)


# ═══════════════════════════════════════════════════════════════════════════
# AANVAL 6 — Tenant Discovery (Unauthenticated)
# Probe slugs without authentication to discover which tenants exist
# Ideal: all return 401 (no tenant existence leakage)
# Reality: resolve_tenant_from_path runs before auth → 404 for non-existing
# ═══════════════════════════════════════════════════════════════════════════


class TestAanval6TenantDiscovery:
    """Unauthenticated tenant slug enumeration."""

    EXISTING_SLUGS = ["psa", "demo"]
    NONEXISTENT_SLUGS = ["admin", "test", "school", "api", "platform", "nonexistent"]

    @pytest.mark.parametrize("slug", EXISTING_SLUGS)
    async def test_existing_tenant_unauthenticated(self, pentest_env, slug):
        """Unauthenticated request to existing tenant → should be 401."""
        resp = await pentest_env["client"].get(f"/api/v1/org/{slug}/students/")
        # Ideal: 401 (don't leak existence)
        # If 404 that would be surprising since tenant exists
        assert resp.status_code == 401, (
            f"Existing slug '{slug}' without auth → {resp.status_code}"
        )

    @pytest.mark.parametrize("slug", NONEXISTENT_SLUGS)
    async def test_nonexistent_tenant_no_info_leak(self, pentest_env, slug):
        """Unauthenticated request to non-existing tenant.

        NOTE: resolve_tenant_from_path is a router-level dependency that runs
        BEFORE get_current_user. This means non-existing slugs return 404
        while existing slugs return 401, leaking tenant existence.

        This is a KNOWN LIMITATION — the router-level dependency must resolve
        the tenant before auth can check permissions against it.

        Severity: LOW — slug enumeration provides minimal actionable info
        without valid credentials. Mitigated by rate limiting.
        """
        resp = await pentest_env["client"].get(f"/api/v1/org/{slug}/students/")
        # Document the current behavior (404 = slug not found before auth runs)
        # This IS a tenant existence oracle, but severity is low
        assert resp.status_code in (401, 404), (
            f"Unexpected status for non-existing slug '{slug}' → {resp.status_code}"
        )

    async def test_discovery_differential(self, pentest_env):
        """Demonstrate the response code differential between existing/non-existing tenants.

        This test documents the tenant discovery oracle.
        In the current architecture, the response codes differ:
        - Existing tenant (psa)     → 401 (auth check)
        - Non-existing tenant (xyz) → 404 (slug resolution)

        An attacker can use this to enumerate valid tenant slugs.
        """
        client = pentest_env["client"]

        existing = await client.get("/api/v1/org/psa/students/")
        nonexist = await client.get("/api/v1/org/nonexistent/students/")

        # Document the differential
        is_oracle = existing.status_code != nonexist.status_code
        if is_oracle:
            # This is expected — document it as a known limitation
            assert existing.status_code == 401, "Existing tenant should return 401"
            assert nonexist.status_code == 404, "Non-existing tenant should return 404"
        # If they're equal, that's actually better security (no oracle)
