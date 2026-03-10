"""Platform finance module — revenue dashboard, outstanding payments, dunning, tax reports."""

from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="finance",
    label="Finance",
    permissions=[
        {"action": "view_dashboard", "label": "Finance dashboard bekijken", "description": "Revenue, openstaande betalingen en lifecycle inzien"},
        {"action": "export_reports", "label": "Finance exporteren", "description": "BTW rapporten en CSV exports downloaden"},
        {"action": "manage_dunning", "label": "Betalingsherinneringen beheren", "description": "Dunning herinneringen bekijken en handmatig triggeren"},
    ],
)
