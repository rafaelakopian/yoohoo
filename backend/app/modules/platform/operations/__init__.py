"""Platform Operations module — monitoring, insights & support tooling."""

from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="operations",
    label="Operaties",
    permissions=[
        {"action": "view_dashboard", "label": "Klantoverzicht bekijken", "description": "Operations dashboard met tenant health overview"},
        {"action": "view_tenant_detail", "label": "Klant 360° bekijken", "description": "Gedetailleerd overzicht per organisatie"},
        {"action": "view_users", "label": "Gebruikers opzoeken", "description": "Cross-tenant user lookup"},
        {"action": "view_onboarding", "label": "Onboarding bekijken", "description": "Onboarding voortgang per organisatie"},
        {"action": "manage_notes", "label": "Notities beheren", "description": "Interne support-notities aanmaken en beheren"},
        {"action": "manage_users", "label": "Gebruikersacties uitvoeren", "description": "Wachtwoord reset, sessies revoking, 2FA uitschakelen"},
        {"action": "impersonate", "label": "Inloggen als klant", "description": "Als een andere gebruiker inloggen voor troubleshooting"},
    ],
)
