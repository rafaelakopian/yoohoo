"""Tests for TenantAuditHelper: best-effort audit logging."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.audit_dependency import TenantAuditHelper


def _make_helper(user_id: uuid.UUID | None = None, tenant_id: uuid.UUID | None = None):
    """Create a TenantAuditHelper with mocked dependencies."""
    db = AsyncMock()
    user = MagicMock()
    user.id = user_id or uuid.uuid4()

    request = MagicMock()
    request.state = MagicMock()
    request.state.tenant_id = tenant_id or uuid.uuid4()
    request.headers = {"User-Agent": "test-agent"}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"

    helper = TenantAuditHelper(db, user, request)
    return helper, db


@pytest.mark.asyncio
async def test_audit_log_success():
    """Successful audit log commits the session."""
    helper, db = _make_helper()

    await helper.log("student.created", entity_type="student", entity_id=uuid.uuid4())

    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_audit_log_failure_rolls_back():
    """Failed audit log rolls back and does NOT raise."""
    helper, db = _make_helper()

    # Make the internal audit service raise
    helper._audit = MagicMock()
    helper._audit.log = AsyncMock(side_effect=Exception("DB connection lost"))

    # Should NOT raise — best-effort
    await helper.log("student.created", entity_type="student")

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_audit_log_passes_tenant_context():
    """Audit log passes tenant_id, entity_type, entity_id to AuditService."""
    tenant_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    helper, db = _make_helper(tenant_id=tenant_id)

    helper._audit = MagicMock()
    helper._audit.log = AsyncMock()

    await helper.log(
        "attendance.created",
        entity_type="attendance",
        entity_id=entity_id,
        extra_field="value",
    )

    helper._audit.log.assert_awaited_once()
    call_kwargs = helper._audit.log.call_args[1]
    assert call_kwargs["action"] == "attendance.created"
    assert call_kwargs["tenant_id"] == tenant_id
    assert call_kwargs["entity_type"] == "attendance"
    assert call_kwargs["entity_id"] == entity_id
    assert call_kwargs["extra_field"] == "value"


@pytest.mark.asyncio
async def test_audit_failure_logged_as_warning():
    """Failed audit log should emit a warning log, not an error."""
    helper, db = _make_helper()
    helper._audit = MagicMock()
    helper._audit.log = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("app.core.audit_dependency.logger") as mock_logger:
        await helper.log("student.deleted", entity_type="student")

        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args
        assert call_kwargs[0][0] == "audit.write_failed"
        assert call_kwargs[1]["action"] == "student.deleted"
