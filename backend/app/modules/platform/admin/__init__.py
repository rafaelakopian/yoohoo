from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="platform",
    label="Platform Beheer",
    permissions=[
        {"action": "view_stats", "label": "Platform statistieken bekijken", "description": "Dashboard met platform-brede statistieken"},
        {"action": "view_orgs", "label": "Organisaties bekijken", "description": "Lijst van alle organisaties en hun details"},
        {"action": "manage_orgs", "label": "Organisaties beheren", "description": "Organisaties aanmaken, inrichten en verwijderen"},
        {"action": "view_users", "label": "Gebruikers bekijken", "description": "Lijst van alle platformgebruikers"},
        {"action": "edit_users", "label": "Gebruikers bewerken", "description": "Naam, email, actief-status wijzigen"},
        {"action": "manage_superadmin", "label": "Superadmin status beheren", "description": "Superadmin-vlag aan/uitzetten"},
        {"action": "manage_memberships", "label": "Lidmaatschappen beheren", "description": "Gebruikers aan organisaties koppelen/ontkoppelen"},
        {"action": "manage_groups", "label": "Permissiegroepen beheren", "description": "Groepen en rechten aanmaken, bewerken, verwijderen"},
        {"action": "view_audit_logs", "label": "Auditlogs bekijken", "description": "Audit trail van alle platformacties"},
        {"action": "manage_feature_catalog", "label": "Feature catalogus beheren", "description": "Feature definities, trial- en retentie-instellingen bewerken"},
        {"action": "manage_tenant_features", "label": "Tenant features beheren", "description": "Per-tenant feature overrides, force on/off, trial reset/extend"},
    ],
)
