"""School product — registers with the framework via ProductManifest.

Importing this module registers the School product with the ProductRegistry.
Sub-module permissions register automatically via router imports.
"""

from app.modules.platform.plugin import (
    DefaultGroup,
    NavigationItem,
    ProductManifest,
    product_registry,
)
from app.modules.products.school.router import school_router
from app.modules.products.school.notification.setup import register_notification_handlers


def _school_startup(app_state) -> None:
    """Called during app lifespan startup. Registers notification handlers."""
    arq_pool = getattr(app_state, "arq", None)
    register_notification_handlers(arq_pool=arq_pool)


async def _school_feature_data_purge(tenant_id, feature_name: str) -> None:
    """Called when a feature trial's retention period expires.

    Per-feature purge logic. Currently logs the event — actual data deletion
    will be implemented per feature as needed.
    """
    import structlog
    logger = structlog.get_logger()
    logger.info(
        "school.feature_data_purge",
        tenant_id=str(tenant_id),
        feature=feature_name,
    )


school_manifest = ProductManifest(
    slug="school",
    name="School",
    description="Muziekschoolbeheer — leerlingen, aanwezigheid, rooster, lesgeld",
    version="1.0.0",
    router=school_router,
    navigation=[
        NavigationItem(
            label="Dashboard",
            route_suffix="dashboard",
            icon="LayoutDashboard",
            permissions=[],
            order=0,
        ),
        NavigationItem(
            label="Leerlingen",
            route_suffix="students",
            icon="Users",
            permissions=["students.view", "students.view_assigned", "students.view_own"],
            order=1,
        ),
        NavigationItem(
            label="Aanwezigheid",
            route_suffix="attendance",
            icon="ClipboardCheck",
            permissions=["attendance.view", "attendance.view_assigned", "attendance.view_own"],
            order=2,
        ),
        NavigationItem(
            label="Rooster",
            route_suffix="schedule",
            icon="CalendarDays",
            permissions=["schedule.view", "schedule.view_assigned"],
            order=3,
        ),
        NavigationItem(
            label="Vakanties",
            route_suffix="holidays",
            icon="CalendarOff",
            permissions=["schedule.view", "schedule.view_assigned"],
            order=4,
        ),
        NavigationItem(
            label="Notificaties",
            route_suffix="notifications",
            icon="Bell",
            permissions=["notifications.view"],
            order=5,
        ),
        NavigationItem(
            label="Facturatie",
            route_suffix="billing",
            icon="Receipt",
            permissions=["billing.view", "billing.view_own"],
            order=6,
            active_paths=["billing", "billing/plans", "billing/students", "billing/invoices"],
        ),
    ],
    default_groups=[
        DefaultGroup(
            slug="beheerder",
            label="Beheerder",
            description="Volledige toegang tot alle organisatiefuncties",
            permissions=None,  # All registered permissions
        ),
        DefaultGroup(
            slug="docent",
            label="Docent",
            description="Leerlingen, aanwezigheid en roosters beheren",
            permissions=[
                "students.view_assigned", "students.create", "students.edit",
                "students.delete", "students.import", "students.assign",
                "attendance.view_assigned", "attendance.create",
                "attendance.edit", "attendance.delete",
                "schedule.view_assigned", "schedule.manage", "schedule.substitute",
                "notifications.view", "billing.view",
            ],
        ),
        DefaultGroup(
            slug="ouder",
            label="Ouder",
            description="Gegevens van eigen kinderen inzien",
            permissions=[
                "students.view_own", "attendance.view_own",
                "schedule.view", "notifications.view", "billing.view_own",
            ],
        ),
        DefaultGroup(
            slug="medewerker",
            label="Medewerker",
            description="Externe medewerker - beperkte toegang tot toegewezen leerlingen",
            permissions=[
                "students.view_assigned",
                "attendance.view_assigned", "attendance.create", "attendance.edit",
                "schedule.view_assigned", "schedule.manage",
                "notifications.view",
            ],
        ),
    ],
    on_app_startup=_school_startup,
    on_feature_data_purge=_school_feature_data_purge,
)

product_registry.register(school_manifest)
