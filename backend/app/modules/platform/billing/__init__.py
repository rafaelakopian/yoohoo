"""Platform billing module — payment providers, subscriptions, invoices."""

from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="billing",
    label="Facturatie",
    permissions=[
        {"action": "view", "label": "Facturatie bekijken", "description": "Facturen en betalingen inzien"},
        {"action": "view_own", "label": "Eigen facturen bekijken", "description": "Alleen eigen facturen inzien (ouder)"},
        {"action": "manage", "label": "Facturatie beheren", "description": "Facturen aanmaken, verzenden, lesgeldplannen beheren"},
        {"action": "manage_provider", "label": "Betaalprovider beheren", "description": "Payment provider configuratie (API keys)"},
        {"action": "refund", "label": "Terugbetalingen", "description": "Betalingen terugbetalen"},
    ],
)
