"""Job monitoring service — reads arq queue status from Redis.

Uses arq's own ArqRedis API to query job state. arq stores data in Redis db=1:
- arq:queue               → sorted set of queued job_ids (score = enqueue ms)
- arq:job:{job_id}        → pickled JobDef
- arq:in-progress:{id}    → exists while job is running
- arq:result:{job_id}     → pickled JobResult (TTL-based, default 24h)
"""

from datetime import datetime, timezone
from enum import Enum

import structlog
from arq import ArqRedis
from pydantic import BaseModel

logger = structlog.get_logger()


class JobStatusEnum(str, Enum):
    queued = "queued"
    deferred = "deferred"
    in_progress = "in_progress"
    complete = "complete"
    failed = "failed"


class JobInfo(BaseModel):
    job_id: str | None
    function: str
    status: JobStatusEnum
    enqueue_time: datetime | None = None
    start_time: datetime | None = None
    finish_time: datetime | None = None
    execution_duration_ms: int | None = None
    try_count: int = 0
    success: bool | None = None
    error: str | None = None


class JobQueueSummary(BaseModel):
    queued_count: int = 0
    in_progress_count: int = 0
    complete_count: int = 0
    failed_count: int = 0
    jobs: list[JobInfo] = []
    checked_at: datetime


async def get_job_summary(
    arq_pool: ArqRedis | None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> JobQueueSummary:
    """Read arq job queue status. Never raises — returns empty summary on error."""
    now = datetime.now(timezone.utc)

    if arq_pool is None:
        logger.warning("job_monitor.no_arq_pool")
        return JobQueueSummary(checked_at=now)

    try:
        return await _read_job_data(arq_pool, now, date_from, date_to)
    except Exception:
        logger.warning("job_monitor.redis_error", exc_info=True)
        return JobQueueSummary(checked_at=now)


async def _read_job_data(
    arq_pool: ArqRedis,
    now: datetime,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> JobQueueSummary:
    jobs: list[JobInfo] = []

    # 1. Queued/deferred jobs
    try:
        queued_defs = await arq_pool.queued_jobs()
    except Exception:
        queued_defs = []

    in_progress_count = 0
    for jd in queued_defs:
        # Check if this job is actually in-progress
        is_running = await arq_pool.exists(f"arq:in-progress:{jd.job_id}")
        if is_running:
            status = JobStatusEnum.in_progress
            in_progress_count += 1
        elif jd.score and jd.score > now.timestamp() * 1000:
            status = JobStatusEnum.deferred
        else:
            status = JobStatusEnum.queued

        jobs.append(JobInfo(
            job_id=jd.job_id,
            function=jd.function,
            status=status,
            enqueue_time=jd.enqueue_time,
            try_count=jd.job_try,
        ))

    # 2. Completed/failed jobs (results stored with TTL)
    try:
        results = await arq_pool.all_job_results()
    except Exception:
        results = []

    # Filter completed/failed results by date range (queued/in-progress are always live)
    if date_from or date_to:
        filtered = []
        for jr in results:
            et = jr.enqueue_time
            if et:
                if date_from and et < date_from:
                    continue
                if date_to and et > date_to:
                    continue
            filtered.append(jr)
        results = filtered

    complete_count = 0
    failed_count = 0
    for jr in results:
        duration_ms = None
        if jr.start_time and jr.finish_time:
            duration_ms = int((jr.finish_time - jr.start_time).total_seconds() * 1000)

        error = None
        if not jr.success:
            failed_count += 1
            status = JobStatusEnum.failed
            if jr.result is not None:
                error = str(jr.result)
        else:
            complete_count += 1
            status = JobStatusEnum.complete

        jobs.append(JobInfo(
            job_id=jr.job_id,
            function=jr.function,
            status=status,
            enqueue_time=jr.enqueue_time,
            start_time=jr.start_time,
            finish_time=jr.finish_time,
            execution_duration_ms=duration_ms,
            try_count=jr.job_try,
            success=jr.success,
            error=error,
        ))

    # Sort by enqueue_time desc, limit to 100
    jobs.sort(key=lambda j: j.enqueue_time or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    jobs = jobs[:100]

    queued_count = sum(1 for j in jobs if j.status in (JobStatusEnum.queued, JobStatusEnum.deferred))

    return JobQueueSummary(
        queued_count=queued_count,
        in_progress_count=in_progress_count,
        complete_count=complete_count,
        failed_count=failed_count,
        jobs=jobs,
        checked_at=datetime.now(timezone.utc),
    )
