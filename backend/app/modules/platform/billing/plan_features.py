"""PlanFeatures — typed schema for the features JSONB column on PlatformPlan.

Each feature has:
- enabled: bool (on/off for this plan)
- trial_days: int | None (free trial period, None = no trial available)
- data_retention_days: int | None (retention period after expiry/cancellation)
  None = permanent, 0 = immediate purge, X = X days then purge

Superadmin configures this per plan via the plan management UI.
Limits (max_students, max_teachers) stay on PlatformPlan columns — not duplicated here.
"""

from pydantic import BaseModel, Field


class FeatureConfig(BaseModel):
    enabled: bool = False
    trial_days: int | None = None
    data_retention_days: int | None = None  # None = permanent


class PlanFeatures(BaseModel):
    """Independently configurable per plan by superadmin."""

    # --- School module features ---
    # Base features — always on in every plan
    student_management: FeatureConfig = Field(
        default_factory=lambda: FeatureConfig(enabled=True)
    )
    attendance: FeatureConfig = Field(
        default_factory=lambda: FeatureConfig(enabled=True)
    )
    schedule: FeatureConfig = Field(
        default_factory=lambda: FeatureConfig(enabled=True)
    )
    notifications: FeatureConfig = Field(
        default_factory=lambda: FeatureConfig(enabled=True)
    )

    # Expandable features — superadmin configures per plan
    billing: FeatureConfig = Field(default_factory=FeatureConfig)
    collaborations: FeatureConfig = Field(default_factory=FeatureConfig)
    reporting: FeatureConfig = Field(default_factory=FeatureConfig)
    api_access: FeatureConfig = Field(default_factory=FeatureConfig)
    custom_branding: FeatureConfig = Field(default_factory=FeatureConfig)
    priority_support: FeatureConfig = Field(default_factory=FeatureConfig)

    def get_feature(self, feature_name: str) -> FeatureConfig | None:
        val = getattr(self, feature_name, None)
        return val if isinstance(val, FeatureConfig) else None

    def is_feature_enabled(self, feature_name: str) -> bool:
        feature = self.get_feature(feature_name)
        return feature.enabled if feature else False

    def trial_days_for(self, feature_name: str) -> int | None:
        feature = self.get_feature(feature_name)
        return feature.trial_days if feature else None

    def retention_days_for(self, feature_name: str) -> int | None:
        feature = self.get_feature(feature_name)
        return feature.data_retention_days if feature else None
