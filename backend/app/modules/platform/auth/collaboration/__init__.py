"""Collaboration module — registers collaboration permissions at import time."""

from app.core.permissions import permission_registry

permission_registry.register_module(
    "collaborations",
    "Samenwerkingen",
    [
        {"action": "view", "label": "Samenwerkingen bekijken", "description": "Externe medewerkers inzien"},
        {"action": "manage", "label": "Samenwerkingen beheren", "description": "Medewerkers uitnodigen en beheren"},
    ],
)
