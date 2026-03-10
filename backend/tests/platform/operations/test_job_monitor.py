"""Tests for job monitoring endpoint and service."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.modules.platform.operations.job_monitor import (
    JobQueueSummary,
    JobStatusEnum,
    get_job_summary,
)


# --- Service unit tests ---


@pytest.mark.asyncio
async def test_job_summary_returns_empty_when_no_pool():
    """Returns empty summary when arq pool is None."""
    result = await get_job_summary(None)
    assert isinstance(result, JobQueueSummary)
    assert result.queued_count == 0
    assert result.in_progress_count == 0
    assert result.complete_count == 0
    assert result.failed_count == 0
    assert result.jobs == []
    assert result.checked_at is not None


@pytest.mark.asyncio
async def test_job_summary_handles_redis_error():
    """Returns empty summary on Redis error (no crash)."""
    mock_pool = AsyncMock()
    mock_pool.queued_jobs = AsyncMock(side_effect=ConnectionError("Redis down"))

    result = await get_job_summary(mock_pool)
    assert isinstance(result, JobQueueSummary)
    assert result.queued_count == 0
    assert result.checked_at is not None


@pytest.mark.asyncio
async def test_job_summary_parses_queued_jobs():
    """Parses queued jobs from arq."""
    from arq.jobs import JobDef

    now = datetime.now(timezone.utc)
    mock_job = JobDef(
        function="send_email_job",
        args=(),
        kwargs={},
        job_try=1,
        enqueue_time=now,
        score=int(now.timestamp() * 1000) - 1000,  # in the past = queued
        job_id="test-job-1",
    )

    mock_pool = AsyncMock()
    mock_pool.queued_jobs = AsyncMock(return_value=[mock_job])
    mock_pool.exists = AsyncMock(return_value=False)
    mock_pool.all_job_results = AsyncMock(return_value=[])

    result = await get_job_summary(mock_pool)
    assert result.queued_count == 1
    assert len(result.jobs) == 1
    assert result.jobs[0].function == "send_email_job"
    assert result.jobs[0].status == JobStatusEnum.queued
    assert result.jobs[0].job_id == "test-job-1"


@pytest.mark.asyncio
async def test_job_summary_parses_in_progress_jobs():
    """Detects in-progress jobs via arq:in-progress:{id} key."""
    from arq.jobs import JobDef

    now = datetime.now(timezone.utc)
    mock_job = JobDef(
        function="generate_invoices_job",
        args=(),
        kwargs={},
        job_try=1,
        enqueue_time=now,
        score=int(now.timestamp() * 1000),
        job_id="running-job-1",
    )

    mock_pool = AsyncMock()
    mock_pool.queued_jobs = AsyncMock(return_value=[mock_job])
    mock_pool.exists = AsyncMock(return_value=True)  # in-progress key exists
    mock_pool.all_job_results = AsyncMock(return_value=[])

    result = await get_job_summary(mock_pool)
    assert result.in_progress_count == 1
    assert result.jobs[0].status == JobStatusEnum.in_progress


@pytest.mark.asyncio
async def test_job_summary_parses_failed_jobs():
    """Parses failed jobs from results with success=False."""
    from arq.jobs import JobResult

    now = datetime.now(timezone.utc)
    mock_result = JobResult(
        function="cleanup_unverified_users_job",
        args=(),
        kwargs={},
        job_try=3,
        enqueue_time=now,
        score=None,
        job_id="dead-job-1",
        success=False,
        result=RuntimeError("DB connection lost"),
        start_time=now,
        finish_time=now,
        queue_name="arq:queue",
    )

    mock_pool = AsyncMock()
    mock_pool.queued_jobs = AsyncMock(return_value=[])
    mock_pool.all_job_results = AsyncMock(return_value=[mock_result])

    result = await get_job_summary(mock_pool)
    assert result.failed_count == 1
    assert result.complete_count == 0
    assert len(result.jobs) == 1
    assert result.jobs[0].status == JobStatusEnum.failed
    assert result.jobs[0].error is not None
    assert "DB connection lost" in result.jobs[0].error


@pytest.mark.asyncio
async def test_job_summary_calculates_duration():
    """Calculates execution_duration_ms from start and finish times."""
    from datetime import timedelta
    from arq.jobs import JobResult

    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=1, milliseconds=500)
    mock_result = JobResult(
        function="send_email_job",
        args=(),
        kwargs={},
        job_try=1,
        enqueue_time=now - timedelta(seconds=2),
        score=None,
        job_id="done-job-1",
        success=True,
        result=None,
        start_time=start,
        finish_time=now,
        queue_name="arq:queue",
    )

    mock_pool = AsyncMock()
    mock_pool.queued_jobs = AsyncMock(return_value=[])
    mock_pool.all_job_results = AsyncMock(return_value=[mock_result])

    result = await get_job_summary(mock_pool)
    assert result.complete_count == 1
    job = result.jobs[0]
    assert job.execution_duration_ms is not None
    assert job.execution_duration_ms == 1500


# --- API endpoint tests ---


@pytest.mark.asyncio
async def test_job_monitor_returns_summary(client: AsyncClient, auth_headers: dict):
    """GET /platform/operations/jobs returns 200 with summary structure."""
    resp = await client.get(
        "/api/v1/platform/operations/jobs",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "queued_count" in data
    assert "in_progress_count" in data
    assert "complete_count" in data
    assert "failed_count" in data
    assert "jobs" in data
    assert "checked_at" in data


@pytest.mark.asyncio
async def test_job_monitor_requires_auth(client: AsyncClient):
    """Unauthenticated request returns 401."""
    resp = await client.get("/api/v1/platform/operations/jobs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_job_monitor_redis_unavailable(client: AsyncClient, auth_headers: dict):
    """Returns 200 with empty summary when arq pool is None."""
    from app.dependencies import get_arq

    async def override_arq():
        return None

    from app.main import app as fastapi_app
    original = fastapi_app.dependency_overrides.get(get_arq)
    fastapi_app.dependency_overrides[get_arq] = override_arq

    try:
        resp = await client.get(
            "/api/v1/platform/operations/jobs",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["queued_count"] == 0
        assert data["failed_count"] == 0
        assert data["jobs"] == []
    finally:
        if original is not None:
            fastapi_app.dependency_overrides[get_arq] = original
        else:
            fastapi_app.dependency_overrides.pop(get_arq, None)
