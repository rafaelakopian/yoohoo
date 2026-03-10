"""Feature trial lifecycle cron jobs.

expire_trials_job — 02:00 daily: expires trials past their trial_expires_at + trial expiring warnings.
purge_expired_retention_job — 02:30 daily: purges data past retention_until + retention warnings.
"""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select

from app.core.jobs.retry import retry_or_fail
from app.core.metrics import job_completed_total, job_failed_total, job_started_total

logger = structlog.get_logger()

MAX_TRIES = 3


async def _send_trial_expiring_warnings(session, arq_pool=None) -> int:
    """Send 7-day trial expiry warnings."""
    from app.modules.platform.billing.models import FeatureTrialStatus, TenantFeatureTrial
    from app.modules.platform.notifications.service import PlatformNotificationService

    now = datetime.now(timezone.utc)
    warning_threshold = now + timedelta(days=7)

    result = await session.execute(
        select(TenantFeatureTrial).where(
            TenantFeatureTrial.status == FeatureTrialStatus.trialing,
            TenantFeatureTrial.trial_expires_at != None,  # noqa: E711
            TenantFeatureTrial.trial_expires_at <= warning_threshold,
            TenantFeatureTrial.trial_expires_at > now,
            TenantFeatureTrial.warning_sent_at == None,  # noqa: E711
        )
    )
    trials = result.scalars().all()

    notif_service = PlatformNotificationService(session)
    count = 0
    for trial in trials:
        days_left = (trial.trial_expires_at - now).days
        await notif_service.send_system(
            tenant_id=trial.tenant_id,
            notification_type="trial.expiring",
            title=f"Proefperiode '{trial.feature_name}' verloopt over {days_left} dagen",
            message=f"Uw proefperiode voor {trial.feature_name} verloopt op {trial.trial_expires_at.strftime('%d-%m-%Y')}. Upgrade om toegang te behouden.",
            extra_data={"feature_name": trial.feature_name, "days_left": days_left},
            arq_pool=arq_pool,
        )
        trial.warning_sent_at = now
        count += 1

    return count


async def _send_retention_warnings(session, arq_pool=None) -> int:
    """Send 60% and 90% retention progress warnings."""
    from app.modules.platform.billing.models import FeatureTrialStatus, TenantFeatureTrial
    from app.modules.platform.notifications.service import PlatformNotificationService

    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(TenantFeatureTrial).where(
            TenantFeatureTrial.status == FeatureTrialStatus.retention,
            TenantFeatureTrial.retention_until != None,  # noqa: E711
            TenantFeatureTrial.retention_until > now,
            TenantFeatureTrial.expired_at != None,  # noqa: E711
        )
    )
    trials = result.scalars().all()

    notif_service = PlatformNotificationService(session)
    count = 0
    for trial in trials:
        total_days = (trial.retention_until - trial.expired_at).total_seconds() / 86400
        if total_days <= 0:
            continue
        elapsed_days = (now - trial.expired_at).total_seconds() / 86400
        progress = elapsed_days / total_days
        days_left = max(0, int((trial.retention_until - now).total_seconds() / 86400))

        # 60% warning
        if progress >= 0.6 and not trial.warning_60_sent:
            await notif_service.send_system(
                tenant_id=trial.tenant_id,
                notification_type="retention.warning",
                title=f"Bewaartermijn '{trial.feature_name}': {days_left} dagen resterend",
                message=f"De bewaartermijn voor uw {trial.feature_name}-data is voor 60% verlopen. Nog {days_left} dagen tot verwijdering.",
                extra_data={"feature_name": trial.feature_name, "days_left": days_left, "urgency": "medium"},
                arq_pool=arq_pool,
            )
            trial.warning_60_sent = True
            count += 1

        # 90% warning
        if progress >= 0.9 and not trial.warning_90_sent:
            await notif_service.send_system(
                tenant_id=trial.tenant_id,
                notification_type="retention.warning",
                title=f"Bewaartermijn '{trial.feature_name}': {days_left} dagen resterend!",
                message=f"De bewaartermijn voor uw {trial.feature_name}-data is voor 90% verlopen. Nog {days_left} dagen tot definitieve verwijdering!",
                extra_data={"feature_name": trial.feature_name, "days_left": days_left, "urgency": "high"},
                arq_pool=arq_pool,
            )
            trial.warning_90_sent = True
            count += 1

    return count


async def expire_trials_job(ctx: dict) -> bool:
    """Cron job (02:00 daily) — expire feature trials + send expiry warnings."""
    job_try = ctx.get("job_try", 1)
    job_started_total.labels(job_name="expire_trials_job").inc()
    logger.info("job.expire_trials.start", attempt=job_try)

    try:
        central_session_factory = ctx["central_session_factory"]
        arq_pool = ctx.get("arq_pool")

        async with central_session_factory() as session:
            from app.modules.platform.billing.trial_service import expire_trials

            # 1. Send 7-day warnings (before expiry)
            warning_count = await _send_trial_expiring_warnings(session, arq_pool=arq_pool)

            # 2. Expire trials past their expiry date
            count = await expire_trials(session)

            await session.commit()
            logger.info("job.expire_trials.done", expired_count=count, warnings_sent=warning_count)

        job_completed_total.labels(job_name="expire_trials_job").inc()
        return True
    except Exception as exc:
        job_failed_total.labels(job_name="expire_trials_job").inc()
        retry_or_fail(
            job_try=job_try,
            max_tries=MAX_TRIES,
            error=exc,
            job_name="expire_trials_job",
        )
        return False


async def purge_expired_retention_job(ctx: dict) -> bool:
    """Cron job (02:30 daily) — purge data past retention + send retention warnings + purge notifications."""
    job_try = ctx.get("job_try", 1)
    job_started_total.labels(job_name="purge_expired_retention_job").inc()
    logger.info("job.purge_retention.start", attempt=job_try)

    try:
        central_session_factory = ctx["central_session_factory"]
        arq_pool = ctx.get("arq_pool")

        async with central_session_factory() as session:
            from app.modules.platform.billing.trial_service import purge_expired_retention
            from app.modules.platform.notifications.service import PlatformNotificationService

            # 1. Send retention progress warnings (60% / 90%)
            retention_warning_count = await _send_retention_warnings(session, arq_pool=arq_pool)

            # 2. Purge expired retention data
            count = await purge_expired_retention(session)

            # 3. Send purge notifications for just-purged trials
            if count > 0:
                from app.modules.platform.billing.models import FeatureTrialStatus, TenantFeatureTrial

                notif_service = PlatformNotificationService(session)
                purged_result = await session.execute(
                    select(TenantFeatureTrial).where(
                        TenantFeatureTrial.status == FeatureTrialStatus.purged,
                        TenantFeatureTrial.purged_at != None,  # noqa: E711
                    )
                )
                for trial in purged_result.scalars().all():
                    # Only notify if recently purged (within last 24h — this job runs daily)
                    if trial.purged_at and (datetime.now(timezone.utc) - trial.purged_at).total_seconds() < 86400:
                        await notif_service.send_system(
                            tenant_id=trial.tenant_id,
                            notification_type="data.purged",
                            title=f"Data verwijderd: {trial.feature_name}",
                            message=f"De bewaartermijn voor {trial.feature_name} is verlopen. Alle bijbehorende data is definitief verwijderd.",
                            extra_data={"feature_name": trial.feature_name},
                            arq_pool=arq_pool,
                        )

            await session.commit()
            logger.info("job.purge_retention.done", purged_count=count, retention_warnings=retention_warning_count)

        job_completed_total.labels(job_name="purge_expired_retention_job").inc()
        return True
    except Exception as exc:
        job_failed_total.labels(job_name="purge_expired_retention_job").inc()
        retry_or_fail(
            job_try=job_try,
            max_tries=MAX_TRIES,
            error=exc,
            job_name="purge_expired_retention_job",
        )
        return False
