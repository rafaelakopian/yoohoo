"""Tests for ProductRegistry and plugin router."""

import pytest
from fastapi import APIRouter
from httpx import AsyncClient

from app.modules.platform.plugin.manifest import (
    DefaultGroup,
    NavigationItem,
    ProductManifest,
)
from app.modules.platform.plugin.registry import ProductRegistry, product_registry


# ---------------------------------------------------------------------------
# Unit tests — ProductRegistry
# ---------------------------------------------------------------------------


class TestProductRegistry:
    def test_register_and_get(self):
        reg = ProductRegistry()
        manifest = ProductManifest(
            slug="test-prod",
            name="Test Product",
            description="A test product",
            version="0.1.0",
            router=APIRouter(),
        )
        reg.register(manifest)
        assert reg.get("test-prod") is manifest
        assert reg.get("nonexistent") is None

    def test_register_duplicate_raises(self):
        reg = ProductRegistry()
        manifest = ProductManifest(
            slug="dup",
            name="Dup",
            description="Duplicate",
            version="1.0.0",
            router=APIRouter(),
        )
        reg.register(manifest)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(manifest)

    def test_all_returns_list(self):
        reg = ProductRegistry()
        m1 = ProductManifest(slug="a", name="A", description="", version="1.0.0", router=APIRouter())
        m2 = ProductManifest(slug="b", name="B", description="", version="1.0.0", router=APIRouter())
        reg.register(m1)
        reg.register(m2)
        assert len(reg.all()) == 2
        assert m1 in reg.all()
        assert m2 in reg.all()

    def test_get_all_navigation_sorted(self):
        reg = ProductRegistry()
        nav1 = NavigationItem(label="Z-First", route_suffix="z", icon="X", permissions=[], order=0)
        nav2 = NavigationItem(label="A-Second", route_suffix="a", icon="Y", permissions=["p.view"], order=5)
        m = ProductManifest(
            slug="nav-test",
            name="Nav",
            description="",
            version="1.0.0",
            router=APIRouter(),
            navigation=[nav2, nav1],
        )
        reg.register(m)
        items = reg.get_all_navigation()
        assert len(items) == 2
        assert items[0][1].label == "Z-First"  # order=0 first
        assert items[1][1].label == "A-Second"  # order=5 second
        assert items[0][0] == "nav-test"  # product slug

    def test_get_default_groups(self):
        reg = ProductRegistry()
        grp = DefaultGroup(slug="admin", label="Admin", description="Full access", permissions=None)
        m = ProductManifest(
            slug="grp-test",
            name="Grp",
            description="",
            version="1.0.0",
            router=APIRouter(),
            default_groups=[grp],
        )
        reg.register(m)
        groups = reg.get_default_groups("grp-test")
        assert len(groups) == 1
        assert groups[0].slug == "admin"
        assert reg.get_default_groups("nonexistent") == []

    def test_get_all_default_groups(self):
        reg = ProductRegistry()
        grp = DefaultGroup(slug="x", label="X", description="", permissions=["a.b"])
        m = ProductManifest(
            slug="all-grp",
            name="G",
            description="",
            version="1.0.0",
            router=APIRouter(),
            default_groups=[grp],
        )
        reg.register(m)
        result = reg.get_all_default_groups()
        assert "all-grp" in result
        assert len(result["all-grp"]) == 1


# ---------------------------------------------------------------------------
# Singleton — school product is registered
# ---------------------------------------------------------------------------


class TestSchoolProductRegistered:
    def test_school_registered_in_singleton(self):
        """The school product is registered at import time."""
        school = product_registry.get("school")
        assert school is not None
        assert school.name == "School"
        assert school.version == "1.0.0"

    def test_school_has_navigation(self):
        school = product_registry.get("school")
        assert len(school.navigation) >= 7  # Dashboard, Leerlingen, etc.
        labels = [n.label for n in school.navigation]
        assert "Dashboard" in labels
        assert "Leerlingen" in labels
        assert "Facturatie" in labels

    def test_school_has_default_groups(self):
        school = product_registry.get("school")
        slugs = [g.slug for g in school.default_groups]
        assert "beheerder" in slugs
        assert "docent" in slugs
        assert "ouder" in slugs

    def test_school_has_startup_hook(self):
        school = product_registry.get("school")
        assert school.on_app_startup is not None


# ---------------------------------------------------------------------------
# API tests — /products/registry endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_products_registry_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/platform/products/registry")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_products_registry_returns_data(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/platform/products/registry", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "products" in data
    assert "navigation" in data
    assert len(data["products"]) >= 1
    # School product present
    slugs = [p["slug"] for p in data["products"]]
    assert "school" in slugs
    # Navigation items present and sorted
    assert len(data["navigation"]) >= 7
    orders = [n["order"] for n in data["navigation"]]
    assert orders == sorted(orders)
