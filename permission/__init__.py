"""
记忆殿堂v2.0 - 权限引擎模块

五级权限模型:
- ReadOnly: 只读访问
- WorkspaceWrite: 工作区写入
- DangerFullAccess: 危险操作完全访问
- Prompt: 需要确认提示
- Allow: 完全允许

规则引擎:
- allow: 允许操作
- deny: 拒绝操作
- ask: 需要用户确认

Usage:
    from permission import PermissionEngine, PermissionLevel, RuleAction, check_permission
    
    engine = get_engine()
    result = engine.check(context, PermissionLevel.WORKSPACE_WRITE)
"""

from .engine import (
    PermissionEngine,
    PermissionLevel,
    RuleAction,
    Rule,
    PermissionContext,
    PermissionResult,
    get_engine,
    check_permission
)

__all__ = [
    # 引擎
    "PermissionEngine",
    "get_engine",
    "check_permission",
    # 枚举
    "PermissionLevel",
    "RuleAction",
    # 数据类
    "Rule",
    "PermissionContext",
    "PermissionResult",
]

__version__ = "2.0.0"
