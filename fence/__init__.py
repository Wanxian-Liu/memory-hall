"""
记忆殿堂 - 围栏隔离模块 V1.3
导出核心类和函数
"""

from .fence import (
    MemoryPalaceFence,
    SpaceType,
    Permission,
    SpaceBoundary,
    ViolationEvent,
    FenceAlert,
    get_fence,
    check_boundary,
    validate_access,
)

__version__ = "1.3.0"
__all__ = [
    "MemoryPalaceFence",
    "SpaceType",
    "Permission", 
    "SpaceBoundary",
    "ViolationEvent",
    "FenceAlert",
    "get_fence",
    "check_boundary",
    "validate_access",
]
