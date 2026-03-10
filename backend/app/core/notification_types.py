"""Central registry of platform notification types.

Platform notifications are messages sent from the platform to tenant organisations.
Each type has a label, description, and default severity.
"""


class PlatformNotificationType:
    """Single notification type definition."""

    def __init__(self, code: str, label: str, description: str, default_severity: str = "info"):
        self.code = code
        self.label = label
        self.description = description
        self.default_severity = default_severity


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PLATFORM_NOTIFICATION_TYPES: dict[str, PlatformNotificationType] = {}


def register_type(code: str, label: str, description: str, default_severity: str = "info") -> None:
    """Register a platform notification type."""
    PLATFORM_NOTIFICATION_TYPES[code] = PlatformNotificationType(
        code=code, label=label, description=description, default_severity=default_severity,
    )


def get_type(code: str) -> PlatformNotificationType | None:
    return PLATFORM_NOTIFICATION_TYPES.get(code)


def all_types() -> list[PlatformNotificationType]:
    return list(PLATFORM_NOTIFICATION_TYPES.values())


# ---------------------------------------------------------------------------
# Built-in types
# ---------------------------------------------------------------------------

register_type(
    "maintenance",
    label="Gepland onderhoud",
    description="Meldingen over gepland systeemonderhoud",
    default_severity="warning",
)
register_type(
    "feature_update",
    label="Functie-update",
    description="Nieuwe functies en verbeteringen",
    default_severity="info",
)
register_type(
    "security_alert",
    label="Beveiligingsmelding",
    description="Belangrijke beveiligingsupdates",
    default_severity="critical",
)
register_type(
    "billing_notice",
    label="Facturatie",
    description="Betalings- en factuurmeldingen",
    default_severity="warning",
)
register_type(
    "platform_announcement",
    label="Platformbericht",
    description="Algemene platformmededelingen",
    default_severity="info",
)

# ---------------------------------------------------------------------------
# Feature lifecycle types (Fase H-2)
# ---------------------------------------------------------------------------

register_type(
    "feature.blocked",
    label="Feature geblokkeerd",
    description="Een feature is handmatig uitgeschakeld door de beheerder",
    default_severity="warning",
)
register_type(
    "feature.unblocked",
    label="Feature gedeblokkeerd",
    description="Een feature-blokkade is opgeheven",
    default_severity="info",
)
register_type(
    "feature.force_on",
    label="Feature geactiveerd",
    description="Een feature is handmatig geactiveerd door de beheerder",
    default_severity="info",
)
register_type(
    "trial.reset",
    label="Proefperiode gereset",
    description="Een proefperiode is opnieuw ingesteld",
    default_severity="info",
)
register_type(
    "trial.extended",
    label="Proefperiode verlengd",
    description="Een proefperiode is verlengd",
    default_severity="info",
)
register_type(
    "trial.expiring",
    label="Proefperiode verloopt",
    description="Een proefperiode verloopt binnenkort",
    default_severity="warning",
)
register_type(
    "retention.warning",
    label="Bewaartermijn waarschuwing",
    description="Data-bewaartermijn nadert het einde",
    default_severity="warning",
)
register_type(
    "data.purged",
    label="Data verwijderd",
    description="Feature-data is verwijderd na afloop van de bewaartermijn",
    default_severity="critical",
)
register_type(
    "trial.blocked_attempt",
    label="Geblokkeerde proefpoging",
    description="Een poging om een geblokkeerde feature te proberen",
    default_severity="warning",
)
