from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="notifications",
    label="Notificaties",
    permissions=[
        {"action": "view", "label": "Notificaties bekijken"},
        {"action": "manage", "label": "Notificaties beheren", "description": "Voorkeuren en logs beheren"},
    ],
)
