"""Feature catalog & per-tenant feature admin endpoints.

catalog_router — /platform/features/catalog (requires platform.manage_feature_catalog)
tenant_feature_admin_router — /platform/orgs/{tenant_id}/features (requires platform.manage_tenant_features)
"""

import uuid as uuid_mod

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import require_permission
from app.modules.platform.auth.models import User
from app.modules.platform.billing.feature_gate import FeatureAccess, check_feature_access
from app.modules.platform.billing.models import (
    FeatureCatalog,
    FeatureTrialStatus,
    TenantFeatureOverride,
    TenantFeatureTrial,
)
from app.modules.platform.billing.plan_features import PlanFeatures
from app.modules.platform.billing.trial_service import (
    FeatureBlockedError,
    TrialError,
    extend_trial,
    force_off,
    force_on,
    lift_force_off,
    reset_trial,
)
from app.modules.platform.notifications.service import PlatformNotificationService

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CatalogItemResponse(BaseModel):
    id: str
    feature_name: str
    display_name: str
    description: str | None = None
    benefits: list | None = None
    preview_image_url: str | None = None
    default_trial_days: int
    default_retention_days: int
    is_active: bool


class UpsertCatalogItem(BaseModel):
    display_name: str
    description: str | None = None
    benefits: list | None = None
    preview_image_url: str | None = None
    default_trial_days: int = 14
    default_retention_days: int = 90
    is_active: bool = True


class TenantFeatureStatusItem(BaseModel):
    feature_name: str
    access: FeatureAccess
    override: dict | None = None
    trial: dict | None = None
    catalog: dict | None = None


class ForceOffBody(BaseModel):
    reason: str | None = None


class ExtendTrialBody(BaseModel):
    extra_days: int


class OverrideBody(BaseModel):
    trial_days: int | None = None
    retention_days: int | None = None


# ---------------------------------------------------------------------------
# Feature Catalog CRUD (platform-scoped)
# ---------------------------------------------------------------------------

catalog_router = APIRouter(prefix="/platform/features/catalog", tags=["feature-catalog"])


@catalog_router.get("", response_model=list[CatalogItemResponse])
async def list_catalog(
    _: User = Depends(require_permission("platform.manage_feature_catalog")),
    db: AsyncSession = Depends(get_central_db),
):
    result = await db.execute(
        select(FeatureCatalog).order_by(FeatureCatalog.feature_name)
    )
    return [
        CatalogItemResponse(
            id=str(item.id),
            feature_name=item.feature_name,
            display_name=item.display_name,
            description=item.description,
            benefits=item.benefits,
            preview_image_url=item.preview_image_url,
            default_trial_days=item.default_trial_days,
            default_retention_days=item.default_retention_days,
            is_active=item.is_active,
        )
        for item in result.scalars().all()
    ]


@catalog_router.get("/{feature_name}", response_model=CatalogItemResponse)
async def get_catalog_item(
    feature_name: str,
    _: User = Depends(require_permission("platform.manage_feature_catalog")),
    db: AsyncSession = Depends(get_central_db),
):
    result = await db.execute(
        select(FeatureCatalog).where(FeatureCatalog.feature_name == feature_name)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Feature niet gevonden")
    return CatalogItemResponse(
        id=str(item.id),
        feature_name=item.feature_name,
        display_name=item.display_name,
        description=item.description,
        benefits=item.benefits,
        preview_image_url=item.preview_image_url,
        default_trial_days=item.default_trial_days,
        default_retention_days=item.default_retention_days,
        is_active=item.is_active,
    )


@catalog_router.put("/{feature_name}", response_model=CatalogItemResponse)
async def upsert_catalog_item(
    feature_name: str,
    data: UpsertCatalogItem,
    _: User = Depends(require_permission("platform.manage_feature_catalog")),
    db: AsyncSession = Depends(get_central_db),
):
    result = await db.execute(
        select(FeatureCatalog).where(FeatureCatalog.feature_name == feature_name)
    )
    item = result.scalar_one_or_none()

    if item:
        item.display_name = data.display_name
        item.description = data.description
        item.benefits = data.benefits
        item.preview_image_url = data.preview_image_url
        item.default_trial_days = data.default_trial_days
        item.default_retention_days = data.default_retention_days
        item.is_active = data.is_active
    else:
        item = FeatureCatalog(
            feature_name=feature_name,
            display_name=data.display_name,
            description=data.description,
            benefits=data.benefits,
            preview_image_url=data.preview_image_url,
            default_trial_days=data.default_trial_days,
            default_retention_days=data.default_retention_days,
            is_active=data.is_active,
        )
        db.add(item)

    await db.flush()
    await db.commit()

    return CatalogItemResponse(
        id=str(item.id),
        feature_name=item.feature_name,
        display_name=item.display_name,
        description=item.description,
        benefits=item.benefits,
        preview_image_url=item.preview_image_url,
        default_trial_days=item.default_trial_days,
        default_retention_days=item.default_retention_days,
        is_active=item.is_active,
    )


# ---------------------------------------------------------------------------
# Per-tenant feature admin (platform admin, uses UUID)
# ---------------------------------------------------------------------------

tenant_feature_admin_router = APIRouter(
    prefix="/platform/orgs/{tenant_id}/features",
    tags=["tenant-feature-admin"],
)


def _parse_tenant_id(tenant_id: str) -> uuid_mod.UUID:
    try:
        return uuid_mod.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Ongeldig tenant ID")


@tenant_feature_admin_router.get("", response_model=list[TenantFeatureStatusItem])
async def list_tenant_features(
    tenant_id: str,
    _: User = Depends(require_permission("platform.manage_tenant_features")),
    db: AsyncSession = Depends(get_central_db),
):
    """Overview of all features with their status for a specific tenant."""
    tid = _parse_tenant_id(tenant_id)
    pf = PlanFeatures()
    items = []

    for field_name in pf.model_fields:
        config = pf.get_feature(field_name)
        if config is None:
            continue

        access = await check_feature_access(tenant_id=tid, feature_name=field_name, db=db)

        # Get override
        override_result = await db.execute(
            select(TenantFeatureOverride).where(
                TenantFeatureOverride.tenant_id == tid,
                TenantFeatureOverride.feature_name == field_name,
            )
        )
        override = override_result.scalar_one_or_none()
        override_dict = None
        if override:
            override_dict = {
                "trial_days": override.trial_days,
                "retention_days": override.retention_days,
                "force_on": override.force_on,
                "force_off": override.force_off,
                "force_off_reason": override.force_off_reason,
                "force_off_since": override.force_off_since.isoformat() if override.force_off_since else None,
                "forced_at": override.forced_at.isoformat() if override.forced_at else None,
            }

        # Get trial
        trial_result = await db.execute(
            select(TenantFeatureTrial).where(
                TenantFeatureTrial.tenant_id == tid,
                TenantFeatureTrial.feature_name == field_name,
            )
        )
        trial = trial_result.scalar_one_or_none()
        trial_dict = None
        if trial:
            trial_dict = {
                "status": trial.status.value,
                "trial_started_at": trial.trial_started_at.isoformat() if trial.trial_started_at else None,
                "trial_expires_at": trial.trial_expires_at.isoformat() if trial.trial_expires_at else None,
                "trial_days_snapshot": trial.trial_days_snapshot,
                "reset_count": trial.reset_count,
                "last_reset_at": trial.last_reset_at.isoformat() if trial.last_reset_at else None,
            }

        # Get catalog
        catalog_result = await db.execute(
            select(FeatureCatalog).where(FeatureCatalog.feature_name == field_name)
        )
        catalog = catalog_result.scalar_one_or_none()
        catalog_dict = None
        if catalog:
            catalog_dict = {
                "display_name": catalog.display_name,
                "default_trial_days": catalog.default_trial_days,
                "default_retention_days": catalog.default_retention_days,
                "is_active": catalog.is_active,
            }

        items.append(TenantFeatureStatusItem(
            feature_name=field_name,
            access=access,
            override=override_dict,
            trial=trial_dict,
            catalog=catalog_dict,
        ))

    return items


@tenant_feature_admin_router.post("/{feature_name}/force-on")
async def force_on_feature(
    tenant_id: str,
    feature_name: str,
    current_user: User = Depends(require_permission("platform.manage_tenant_features")),
    db: AsyncSession = Depends(get_central_db),
):
    tid = _parse_tenant_id(tenant_id)
    override = await force_on(db, tid, feature_name, current_user.id)

    # Send notification
    notif_service = PlatformNotificationService(db)
    await notif_service.send_system(
        tenant_id=tid,
        notification_type="feature.force_on",
        title=f"Feature '{feature_name}' geactiveerd",
        message=f"De feature '{feature_name}' is handmatig geactiveerd door een platform beheerder.",
        extra_data={"feature_name": feature_name},
    )

    await db.commit()
    return {"message": f"Feature '{feature_name}' is geactiveerd."}


@tenant_feature_admin_router.post("/{feature_name}/force-off")
async def force_off_feature(
    tenant_id: str,
    feature_name: str,
    body: ForceOffBody,
    current_user: User = Depends(require_permission("platform.manage_tenant_features")),
    db: AsyncSession = Depends(get_central_db),
):
    tid = _parse_tenant_id(tenant_id)
    override = await force_off(db, tid, feature_name, body.reason, current_user.id)

    notif_service = PlatformNotificationService(db)
    await notif_service.send_system(
        tenant_id=tid,
        notification_type="feature.blocked",
        title=f"Feature '{feature_name}' geblokkeerd",
        message=body.reason or f"De feature '{feature_name}' is uitgeschakeld door een platform beheerder.",
        extra_data={"feature_name": feature_name, "reason": body.reason},
    )

    await db.commit()
    return {"message": f"Feature '{feature_name}' is geblokkeerd."}


@tenant_feature_admin_router.post("/{feature_name}/lift")
async def lift_force_off_feature(
    tenant_id: str,
    feature_name: str,
    current_user: User = Depends(require_permission("platform.manage_tenant_features")),
    db: AsyncSession = Depends(get_central_db),
):
    tid = _parse_tenant_id(tenant_id)
    try:
        await lift_force_off(db, tid, feature_name, current_user.id)
    except TrialError as e:
        raise HTTPException(status_code=400, detail=str(e))

    notif_service = PlatformNotificationService(db)
    await notif_service.send_system(
        tenant_id=tid,
        notification_type="feature.unblocked",
        title=f"Feature '{feature_name}' gedeblokkeerd",
        message=f"De blokkade op feature '{feature_name}' is opgeheven.",
        extra_data={"feature_name": feature_name},
    )

    await db.commit()
    return {"message": f"Force-off op '{feature_name}' is opgeheven."}


@tenant_feature_admin_router.post("/{feature_name}/reset-trial")
async def reset_trial_endpoint(
    tenant_id: str,
    feature_name: str,
    current_user: User = Depends(require_permission("platform.manage_tenant_features")),
    db: AsyncSession = Depends(get_central_db),
):
    tid = _parse_tenant_id(tenant_id)
    try:
        trial = await reset_trial(db, tid, feature_name, current_user.id)
    except FeatureBlockedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except TrialError as e:
        raise HTTPException(status_code=400, detail=str(e))

    notif_service = PlatformNotificationService(db)
    await notif_service.send_system(
        tenant_id=tid,
        notification_type="trial.reset",
        title=f"Proefperiode '{feature_name}' gereset",
        message=f"Uw proefperiode voor {feature_name} is opnieuw ingesteld ({trial.trial_days_snapshot} dagen).",
        extra_data={"feature_name": feature_name, "trial_days": trial.trial_days_snapshot},
    )

    await db.commit()
    return {
        "message": f"Trial voor '{feature_name}' is gereset.",
        "reset_count": trial.reset_count,
        "trial_expires_at": trial.trial_expires_at.isoformat() if trial.trial_expires_at else None,
    }


@tenant_feature_admin_router.post("/{feature_name}/extend-trial")
async def extend_trial_endpoint(
    tenant_id: str,
    feature_name: str,
    body: ExtendTrialBody,
    current_user: User = Depends(require_permission("platform.manage_tenant_features")),
    db: AsyncSession = Depends(get_central_db),
):
    tid = _parse_tenant_id(tenant_id)
    try:
        trial = await extend_trial(db, tid, feature_name, body.extra_days, current_user.id)
    except TrialError as e:
        raise HTTPException(status_code=400, detail=str(e))

    notif_service = PlatformNotificationService(db)
    await notif_service.send_system(
        tenant_id=tid,
        notification_type="trial.extended",
        title=f"Proefperiode '{feature_name}' verlengd",
        message=f"Uw proefperiode voor {feature_name} is verlengd met {body.extra_days} dagen.",
        extra_data={"feature_name": feature_name, "extra_days": body.extra_days},
    )

    await db.commit()
    return {
        "message": f"Trial voor '{feature_name}' is verlengd met {body.extra_days} dagen.",
        "trial_expires_at": trial.trial_expires_at.isoformat() if trial.trial_expires_at else None,
    }


@tenant_feature_admin_router.put("/{feature_name}/override")
async def update_feature_override(
    tenant_id: str,
    feature_name: str,
    body: OverrideBody,
    _: User = Depends(require_permission("platform.manage_tenant_features")),
    db: AsyncSession = Depends(get_central_db),
):
    tid = _parse_tenant_id(tenant_id)

    result = await db.execute(
        select(TenantFeatureOverride).where(
            TenantFeatureOverride.tenant_id == tid,
            TenantFeatureOverride.feature_name == feature_name,
        )
    )
    override = result.scalar_one_or_none()

    if override:
        if body.trial_days is not None:
            override.trial_days = body.trial_days
        if body.retention_days is not None:
            override.retention_days = body.retention_days
    else:
        override = TenantFeatureOverride(
            tenant_id=tid,
            feature_name=feature_name,
            trial_days=body.trial_days,
            retention_days=body.retention_days,
        )
        db.add(override)

    await db.flush()
    await db.commit()

    return {
        "message": f"Override voor '{feature_name}' bijgewerkt.",
        "trial_days": override.trial_days,
        "retention_days": override.retention_days,
    }
