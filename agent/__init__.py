"""
记忆殿堂v2.0 动态代理 DAME (Dynamic Agent Management Engine)
基于claw-code的TaskRegistry和生命周期管理设计

模块:
    - RoleRegistry: 角色注册表
    - AgentLifecycleManager: 代理生命周期管理器
    - TaskDispatcher: 任务分发器
"""

from .role_registry import RoleRegistry, Role, RoleType
from .lifecycle_manager import AgentLifecycleManager, Agent, AgentState
from .task_dispatcher import TaskDispatcher, Task, TaskStatus

__all__ = [
    "RoleRegistry",
    "Role",
    "RoleType", 
    "AgentLifecycleManager",
    "Agent",
    "AgentState",
    "TaskDispatcher",
    "Task",
    "TaskStatus",
]

__version__ = "2.0.0"
