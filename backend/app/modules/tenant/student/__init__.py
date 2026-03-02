from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="students",
    label="Leerlingen",
    permissions=[
        {"action": "view", "label": "Alle leerlingen bekijken"},
        {"action": "view_own", "label": "Eigen kinderen bekijken"},
        {"action": "create", "label": "Leerlingen aanmaken"},
        {"action": "edit", "label": "Leerlingen bewerken"},
        {"action": "delete", "label": "Leerlingen verwijderen"},
        {"action": "import", "label": "Leerlingen importeren (Excel)"},
        {"action": "manage_parents", "label": "Ouder-koppelingen beheren"},
        {"action": "view_assigned", "label": "Toegewezen leerlingen bekijken", "description": "Alleen eigen toegewezen leerlingen zien (docent)"},
        {"action": "assign", "label": "Docent-leerling koppelingen beheren", "description": "Leerlingen toewijzen aan docenten"},
    ],
)
