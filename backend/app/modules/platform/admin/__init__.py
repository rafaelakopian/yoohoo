from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="platform",
    label="Platform Beheer",
    permissions=[
        {"action": "view_stats", "label": "Platform statistieken bekijken", "description": "Dashboard met platform-brede statistieken"},
        {"action": "view_schools", "label": "Scholen bekijken", "description": "Lijst van alle scholen en hun details"},
        {"action": "manage_schools", "label": "Scholen beheren", "description": "Scholen aanmaken, inrichten en verwijderen"},
        {"action": "view_users", "label": "Gebruikers bekijken", "description": "Lijst van alle platformgebruikers"},
        {"action": "edit_users", "label": "Gebruikers bewerken", "description": "Naam, email, actief-status wijzigen"},
        {"action": "manage_superadmin", "label": "Superadmin status beheren", "description": "Superadmin-vlag aan/uitzetten"},
        {"action": "manage_memberships", "label": "Lidmaatschappen beheren", "description": "Gebruikers aan scholen koppelen/ontkoppelen"},
        {"action": "manage_groups", "label": "Permissiegroepen beheren", "description": "Groepen en rechten aanmaken, bewerken, verwijderen"},
        {"action": "view_audit_logs", "label": "Auditlogs bekijken", "description": "Audit trail van alle platformacties"},
    ],
)
