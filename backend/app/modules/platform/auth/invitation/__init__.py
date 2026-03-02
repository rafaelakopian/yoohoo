from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="invitations",
    label="Uitnodigingen",
    permissions=[
        {"action": "view", "label": "Uitnodigingen bekijken"},
        {"action": "manage", "label": "Uitnodigingen beheren", "description": "Uitnodigingen aanmaken, opnieuw versturen en intrekken"},
    ],
)
