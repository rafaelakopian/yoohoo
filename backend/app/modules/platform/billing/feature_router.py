"""Feature gating API: feature status per tenant, trial management.

Mounted under /orgs/{slug}/features (tenant-scoped, has request.state.tenant_id).
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import get_current_user
from app.modules.platform.auth.models import User
from app.modules.platform.billing.feature_gate import FeatureAccess, check_feature_access
from app.modules.platform.billing.plan_features import FeatureConfig, PlanFeatures
from app.modules.platform.billing.trial_service import TrialError, start_feature_trial

logger = structlog.get_logger()

router = APIRouter(prefix="/features", tags=["feature-gating"])


class FeatureStatusItem(BaseModel):
    name: str
    config: FeatureConfig
    access: FeatureAccess


class FeatureStatusResponse(BaseModel):
    features: list[FeatureStatusItem]


class TrialStartResponse(BaseModel):
    feature_name: str
    status: str
    trial_expires_at: str | None = None
    message: str


@router.get("", response_model=FeatureStatusResponse)
async def list_features(
    request: Request,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    """List all features with their access status for the current tenant."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context vereist")

    pf = PlanFeatures()
    features = []

    for field_name in pf.model_fields:
        config = pf.get_feature(field_name)
        if config is None:
            continue

        access = await check_feature_access(
            tenant_id=tenant_id,
            feature_name=field_name,
            db=db,
        )
        features.append(FeatureStatusItem(
            name=field_name,
            config=config,
            access=access,
        ))

    return FeatureStatusResponse(features=features)


@router.post("/{feature_name}/trial", response_model=TrialStartResponse)
async def start_trial(
    feature_name: str,
    request: Request,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    """Start a feature trial for the current tenant."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context vereist")

    try:
        trial = await start_feature_trial(
            db=db,
            tenant_id=tenant_id,
            feature_name=feature_name,
        )
        await db.commit()

        return TrialStartResponse(
            feature_name=feature_name,
            status=trial.status.value,
            trial_expires_at=trial.trial_expires_at.isoformat() if trial.trial_expires_at else None,
            message=f"Proefperiode voor '{feature_name}' gestart.",
        )
    except TrialError as e:
        raise HTTPException(status_code=400, detail=str(e))
