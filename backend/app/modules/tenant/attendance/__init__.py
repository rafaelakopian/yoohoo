from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="attendance",
    label="Aanwezigheid",
    permissions=[
        {"action": "view", "label": "Alle aanwezigheid bekijken"},
        {"action": "view_own", "label": "Aanwezigheid eigen kinderen bekijken"},
        {"action": "view_assigned", "label": "Aanwezigheid toegewezen leerlingen bekijken", "description": "Alleen aanwezigheid van eigen toegewezen leerlingen zien"},
        {"action": "create", "label": "Aanwezigheid registreren"},
        {"action": "edit", "label": "Aanwezigheid bewerken"},
        {"action": "delete", "label": "Aanwezigheid verwijderen"},
    ],
)
