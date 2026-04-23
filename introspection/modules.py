"""
Backward-compatibility re-export wrapper.
modules.py has moved to interfaces/modules.py.
"""
from interfaces.modules import (
    ModuleRegistry,
    ModuleType,
    ModuleDetail,
    ModuleSummary,
    ModuleQueryResult,
    get_registry,
    get_modules,
    get_module,
    get_dependencies,
    get_stats,
)

__all__ = [
    "ModuleRegistry",
    "ModuleType",
    "ModuleDetail",
    "ModuleSummary",
    "ModuleQueryResult",
    "get_registry",
    "get_modules",
    "get_module",
    "get_dependencies",
    "get_stats",
]
