from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="org_settings",
    label="Organisatie-instellingen",
    permissions=[
        {"action": "view", "label": "Organisatie-instellingen bekijken"},
        {"action": "edit", "label": "Organisatie-instellingen bewerken"},
    ],
)
