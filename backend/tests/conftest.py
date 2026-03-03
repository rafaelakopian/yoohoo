import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pyotp
import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.base import CentralBase, TenantBase
from app.db.central import get_central_db
from app.dependencies import get_tenant_db
from app.main import app as fastapi_app
from app.core.rate_limiter import _memory_buckets
from app.modules.tenant.path_dependency import resolve_tenant_from_path

# Fixed test tenant UUID for path dependency override
TEST_TENANT_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Fixed TOTP secret for test superadmin users
TEST_TOTP_SECRET = "JBSWY3DPEHPK3PXP"

# Ensure all models are imported so metadata is populated
import app.modules.tenant.student.models  # noqa: F401, E402
import app.modules.tenant.attendance.models  # noqa: F401, E402
import app.modules.tenant.schedule.models  # noqa: F401, E402
import app.modules.tenant.notification.models  # noqa: F401, E402
import app.modules.tenant.billing.models  # noqa: F401, E402
import app.modules.platform.billing.models  # noqa: F401, E402

# Use a test database — always connect directly to PostgreSQL (bypass PgBouncer)
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}_test"
)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(CentralBase.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(CentralBase.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="session")
async def tenant_test_engine():
    """Separate engine for TenantBase tables (students, etc.)."""
    tenant_test_url = TEST_DATABASE_URL  # Reuse the same test DB for simplicity
    engine = create_async_engine(tenant_test_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(TenantBase.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(TenantBase.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def tenant_db_session(tenant_test_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        tenant_test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear in-memory rate limit buckets between tests."""
    _memory_buckets.clear()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_central_db] = override_get_db

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def tenant_client(
    db_session: AsyncSession, tenant_db_session: AsyncSession
) -> AsyncGenerator[AsyncClient, None]:
    """Client with both central and tenant DB overrides."""

    async def override_central_db():
        yield db_session

    async def override_tenant_db():
        yield tenant_db_session

    async def mock_resolve_tenant(slug: str, request: Request):
        """Override: skip DB lookup, set test tenant context from URL slug."""
        request.state.tenant_id = TEST_TENANT_UUID
        request.state.tenant_slug = slug

    fastapi_app.dependency_overrides[get_central_db] = override_central_db
    fastapi_app.dependency_overrides[get_tenant_db] = override_tenant_db
    fastapi_app.dependency_overrides[resolve_tenant_from_path] = mock_resolve_tenant

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def test_user_data() -> dict:
    return {
        "email": f"test-{uuid.uuid4().hex[:8]}@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User",
    }


@pytest_asyncio.fixture
async def verified_user(client: AsyncClient, db_session: AsyncSession, test_user_data: dict) -> dict:
    """Register a user and mark them as verified, ready for login."""
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        response = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == 201
    data = response.json()

    # Directly verify the user in DB and make superadmin for role checks.
    # Also enable TOTP (superadmin accounts require 2FA for login).
    from app.modules.platform.auth.models import User
    from app.modules.platform.auth.totp.service import _encrypt_secret
    from sqlalchemy import update

    encrypted_secret = _encrypt_secret(TEST_TOTP_SECRET)
    await db_session.execute(
        update(User).where(User.id == uuid.UUID(data["id"])).values(
            email_verified=True,
            is_superadmin=True,
            totp_enabled=True,
            totp_secret_encrypted=encrypted_secret,
        )
    )
    await db_session.flush()

    return test_user_data


async def _login_with_2fa(client: AsyncClient, email: str, password: str) -> dict:
    """Login helper that handles the 2FA flow for superadmin users."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    login_data = login_resp.json()

    # If 2FA is required, complete the flow
    if login_data.get("requires_2fa"):
        totp = pyotp.TOTP(TEST_TOTP_SECRET)
        verify_resp = await client.post(
            "/api/v1/auth/2fa/verify",
            json={
                "two_factor_token": login_data["two_factor_token"],
                "code": totp.now(),
            },
        )
        return verify_resp.json()

    return login_data


@pytest.fixture
def login_with_2fa():
    """Returns the async login helper that handles 2FA for superadmin users.

    Usage in tests:
        tokens = await login_with_2fa(client, email, password)
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    """
    return _login_with_2fa


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, verified_user: dict) -> dict:
    """Authorization headers for a verified user (central client)."""
    tokens = await _login_with_2fa(client, verified_user["email"], verified_user["password"])
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest_asyncio.fixture
async def tenant_auth_headers(tenant_client: AsyncClient, verified_user: dict) -> dict:
    """Authorization headers for a verified user (tenant client)."""
    tokens = await _login_with_2fa(tenant_client, verified_user["email"], verified_user["password"])
    return {"Authorization": f"Bearer {tokens['access_token']}"}
