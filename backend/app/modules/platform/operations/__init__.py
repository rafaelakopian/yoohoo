"""Platform Operations module — monitoring & insights (Fase A)."""

from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="operations",
    label="Operaties",
    permissions=[
        {"action": "view_dashboard", "label": "Klantoverzicht bekijken", "description": "Operations dashboard met tenant health overview"},
        {"action": "view_tenant_detail", "label": "Klant 360° bekijken", "description": "Gedetailleerd overzicht per organisatie"},
        {"action": "view_users", "label": "Gebruikers opzoeken", "description": "Cross-tenant user lookup"},
        {"action": "view_onboarding", "label": "Onboarding bekijken", "description": "Onboarding voortgang per organisatie"},
    ],
)
