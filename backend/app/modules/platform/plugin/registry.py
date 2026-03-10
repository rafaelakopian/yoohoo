"""ProductRegistry — manages all registered products.

Usage:
    from app.modules.platform.plugin import product_registry
    product_registry.register(school_manifest)
"""

import structlog

from app.modules.platform.plugin.manifest import (
    DefaultGroup,
    NavigationItem,
    ProductManifest,
)

logger = structlog.get_logger()


class ProductRegistry:
    def __init__(self) -> None:
        self._products: dict[str, ProductManifest] = {}

    def register(self, manifest: ProductManifest) -> None:
        """Register a product. Raises ValueError if slug already registered."""
        if manifest.slug in self._products:
            raise ValueError(f"Product '{manifest.slug}' is already registered")
        self._products[manifest.slug] = manifest
        logger.info(
            "product.registered",
            slug=manifest.slug,
            name=manifest.name,
            version=manifest.version,
        )

    def get(self, slug: str) -> ProductManifest | None:
        """Return manifest for given slug, or None."""
        return self._products.get(slug)

    def all(self) -> list[ProductManifest]:
        """Return all registered products."""
        return list(self._products.values())

    def get_all_navigation(self) -> list[tuple[str, NavigationItem]]:
        """Return all navigation items as (product_slug, item) tuples, sorted by order."""
        items: list[tuple[str, NavigationItem]] = []
        for manifest in self._products.values():
            for item in manifest.navigation:
                items.append((manifest.slug, item))
        items.sort(key=lambda x: x[1].order)
        return items

    def get_default_groups(self, product_slug: str) -> list[DefaultGroup]:
        """Return default groups for a product."""
        manifest = self._products.get(product_slug)
        if not manifest:
            return []
        return manifest.default_groups

    def get_all_default_groups(self) -> dict[str, list[DefaultGroup]]:
        """Return default groups per product slug."""
        return {
            slug: manifest.default_groups
            for slug, manifest in self._products.items()
            if manifest.default_groups
        }


# Singleton
product_registry = ProductRegistry()
