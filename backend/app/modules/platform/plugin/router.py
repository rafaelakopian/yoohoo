"""Plugin API — exposes registered product navigation to the frontend."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.platform.auth.dependencies import get_current_user
from app.modules.platform.auth.models import User
from app.modules.platform.plugin.registry import product_registry

router = APIRouter(prefix="/platform/products", tags=["products"])


class NavigationItemOut(BaseModel):
    product: str
    label: str
    route_suffix: str
    icon: str
    permissions: list[str]
    order: int
    active_paths: list[str] | None = None


class ProductOut(BaseModel):
    slug: str
    name: str
    description: str
    version: str


class ProductRegistryOut(BaseModel):
    products: list[ProductOut]
    navigation: list[NavigationItemOut]


@router.get("/registry", response_model=ProductRegistryOut)
async def get_product_registry(
    current_user: User = Depends(get_current_user),
):
    """Return all registered products and their navigation items."""
    products = [
        ProductOut(
            slug=m.slug,
            name=m.name,
            description=m.description,
            version=m.version,
        )
        for m in product_registry.all()
    ]
    navigation = [
        NavigationItemOut(
            product=product_slug,
            label=item.label,
            route_suffix=item.route_suffix,
            icon=item.icon,
            permissions=item.permissions,
            order=item.order,
            active_paths=item.active_paths,
        )
        for product_slug, item in product_registry.get_all_navigation()
    ]
    return ProductRegistryOut(products=products, navigation=navigation)
