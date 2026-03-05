from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="schedule",
    label="Rooster",
    permissions=[
        {"action": "view", "label": "Rooster bekijken"},
        {"action": "view_assigned", "label": "Rooster toegewezen leerlingen bekijken", "description": "Alleen rooster van eigen toegewezen leerlingen zien"},
        {"action": "manage", "label": "Rooster beheren", "description": "Lesslots, lesinstanties en vakanties aanmaken, bewerken en verwijderen"},
        {"action": "substitute", "label": "Vervanging registreren", "description": "Een vervangende docent registreren voor een les"},
    ],
)
