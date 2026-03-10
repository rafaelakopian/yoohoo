"""ProductManifest — declarative description of a product plugin.

A product fills this in. The framework doesn't know what the product does —
only HOW it registers itself.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from fastapi import APIRouter


@dataclass
class NavigationItem:
    label: str                         # "Leerlingen"
    route_suffix: str                  # "students" — frontend builds full path via orgPath()
    icon: str                          # "Users" (lucide icon name)
    permissions: list[str]             # ["students.view", "students.view_assigned"] — OR logic
    order: int = 0
    active_paths: list[str] | None = None  # Extra paths that highlight this item


@dataclass
class DefaultGroup:
    slug: str                          # "beheerder"
    label: str                         # "Beheerder"
    description: str
    permissions: list[str] | None      # None = all registered permissions


@dataclass
class ProductManifest:
    # Identity
    slug: str                          # "school" — unique, URL-safe
    name: str                          # "School"
    description: str
    version: str                       # "1.0.0"

    # Framework integration
    router: APIRouter                  # Mounted under /orgs/{slug}/

    # Navigation (product-specific items only, NOT framework items like Toegangsbeheer)
    navigation: list[NavigationItem] = field(default_factory=list)

    # Default permission groups created for new tenants
    default_groups: list[DefaultGroup] = field(default_factory=list)

    # Lifecycle hooks
    on_app_startup: Callable | None = None
    # Called during app lifespan startup with app state
    # Use: register notification handlers, init product-specific services

    on_tenant_provisioned: Callable | None = None
    # Called after DB provisioning of a new tenant

    data_export_provider: Callable | None = None
    # GDPR data export hook — async def export(user_id: uuid) -> dict

    on_feature_data_purge: Callable | None = None
    # Called when a feature trial's retention period expires.
    # async def purge(tenant_id: uuid, feature_name: str) -> None
