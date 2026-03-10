"""Demo feature trials and force-off overrides."""

import sys
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.billing.trial_service import force_off, start_feature_trial


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


async def create_demo_features(
    db: AsyncSession,
    tenants: dict[str, uuid.UUID],
    actor_id: uuid.UUID,
) -> None:
    """Create demo feature trial (hartman) and force_off (vos).

    Args:
        tenants: mapping of org key ("hartman", "vos") to tenant UUID.
        actor_id: user UUID to record as the actor for force_off.
    """
    # Hartman: actieve trial voor rapportage
    hartman_id = tenants.get("hartman")
    if hartman_id:
        await start_feature_trial(db, hartman_id, "reporting", product_slug="school")
        await db.flush()
        _log("  Feature trial 'reporting' gestart voor Hartman")

    # Vos: facturatie geblokkeerd
    vos_id = tenants.get("vos")
    if vos_id:
        await force_off(
            db,
            vos_id,
            "billing",
            reason="Demo: geforceerd geblokkeerd voor demonstratie",
            actor_id=actor_id,
        )
        await db.flush()
        _log("  Feature force_off 'billing' ingesteld voor Vos")
