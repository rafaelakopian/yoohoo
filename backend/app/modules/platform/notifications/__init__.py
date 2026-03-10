from app.core.permissions import permission_registry

permission_registry.register_module(
    module_name="platform_notifications",
    label="Platformmeldingen",
    permissions=[
        {
            "action": "view",
            "label": "Platformmeldingen bekijken",
            "description": "Ontvangen platformmeldingen bekijken in inbox",
        },
        {
            "action": "manage",
            "label": "Platformmeldingen beheren",
            "description": "Platformmeldingen aanmaken, publiceren en verwijderen",
        },
        {
            "action": "manage_preferences",
            "label": "Meldingsvoorkeuren beheren",
            "description": "Platform notificatievoorkeuren voor de organisatie instellen",
        },
    ],
)
