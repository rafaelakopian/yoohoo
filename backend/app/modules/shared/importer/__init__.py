"""Generic importer registry.

Modules register their import configuration at startup. The shared importer
service uses these configurations to handle file upload, column mapping,
duplicate detection, and rollback generically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Coroutine
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class FieldInfo:
    """Describes one mappable field for an entity type."""

    name: str        # e.g. "first_name"
    label: str       # e.g. "Voornaam"
    required: bool = False


@dataclass
class ImporterConfig:
    """Configuration for a single importable entity type."""

    entity_type: str
    fields: list[FieldInfo]
    handler: Callable[
        [dict[str, Any], UUID | None, str, dict[str, Any] | None, AsyncSession],
        Coroutine[Any, Any, tuple[UUID, str, dict[str, Any] | None]],
    ]
    finder: Callable[
        [dict[str, Any], AsyncSession],
        Coroutine[Any, Any, tuple[UUID | None, dict[str, Any] | None]],
    ]
    permission: str


_registry: dict[str, ImporterConfig] = {}


def register(
    entity_type: str,
    fields: list[FieldInfo],
    handler: Callable,
    finder: Callable,
    permission: str,
) -> None:
    """Register an entity type for import."""
    _registry[entity_type] = ImporterConfig(
        entity_type=entity_type,
        fields=fields,
        handler=handler,
        finder=finder,
        permission=permission,
    )


def get_config(entity_type: str) -> ImporterConfig:
    """Get import configuration for an entity type."""
    if entity_type not in _registry:
        raise ValueError(f"Unknown entity type: {entity_type}")
    return _registry[entity_type]


def list_entity_types() -> list[str]:
    """Return all registered entity types."""
    return list(_registry.keys())
