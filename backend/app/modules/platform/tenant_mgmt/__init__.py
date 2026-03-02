from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="school_settings",
    label="Schoolinstellingen",
    permissions=[
        {"action": "view", "label": "Schoolinstellingen bekijken"},
        {"action": "edit", "label": "Schoolinstellingen bewerken"},
    ],
)
