"""
Permission Registry — auto-discovery of module permissions.

Modules register their permissions at import time via the singleton
`permission_registry`. The registry is code-only (never persisted to DB).
Groups in the database reference permission codenames as strings.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PermissionDef:
    """A single permission definition."""

    codename: str  # e.g. "students.view"
    module: str  # e.g. "students"
    label: str  # Dutch display label, e.g. "Leerlingen bekijken"
    description: str = ""


@dataclass
class ModulePermissions:
    """All permissions for a module."""

    module_name: str  # e.g. "students"
    label: str  # Dutch label, e.g. "Leerlingen"
    permissions: list[PermissionDef] = field(default_factory=list)


class PermissionRegistry:
    """Singleton registry that collects module permissions at import time."""

    _instance: "PermissionRegistry | None" = None

    def __new__(cls) -> "PermissionRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._modules: dict[str, ModulePermissions] = {}
        return cls._instance

    def register_module(
        self,
        module_name: str,
        label: str,
        permissions: list[dict[str, str]],
    ) -> None:
        """Register a module with its permissions.

        Args:
            module_name: Unique module identifier (e.g. "students").
            label: Dutch display label (e.g. "Leerlingen").
            permissions: List of dicts with keys: action, label, description (optional).
        """
        perms = [
            PermissionDef(
                codename=f"{module_name}.{p['action']}",
                module=module_name,
                label=p["label"],
                description=p.get("description", ""),
            )
            for p in permissions
        ]
        self._modules[module_name] = ModulePermissions(
            module_name=module_name,
            label=label,
            permissions=perms,
        )

    def get_all_modules(self) -> list[ModulePermissions]:
        """Return all registered modules with their permissions."""
        return list(self._modules.values())

    def get_all_codenames(self) -> set[str]:
        """Return a set of all registered permission codenames."""
        result: set[str] = set()
        for mod in self._modules.values():
            for p in mod.permissions:
                result.add(p.codename)
        return result

    def get_permission(self, codename: str) -> PermissionDef | None:
        """Look up a single permission by codename."""
        module_name = codename.split(".")[0]
        mod = self._modules.get(module_name)
        if mod:
            for p in mod.permissions:
                if p.codename == codename:
                    return p
        return None

    def is_valid_codename(self, codename: str) -> bool:
        """Check if a codename is registered."""
        return self.get_permission(codename) is not None


permission_registry = PermissionRegistry()
