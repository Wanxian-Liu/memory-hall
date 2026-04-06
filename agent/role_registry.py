"""
角色注册表 (RoleRegistry) - 记忆殿堂v2.0 DAME
基于claw-code TaskRegistry设计模式

功能:
    - 注册/注销角色
    - 角色查询与匹配
    - 并发控制
"""

import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from .models import Role, RoleType


@dataclass
class RegistryInner:
    """注册表内部状态"""
    roles: Dict[str, Role] = field(default_factory=dict)
    roles_by_type: Dict[RoleType, List[str]] = field(default_factory=dict)
    counter: int = 0  # 全局递增ID
    
    def next_id(self) -> int:
        """生成下一个ID"""
        self.counter += 1
        return self.counter


class RoleRegistry:
    """
    角色注册表
    
    管理所有可用角色的注册、查询和匹配。
    线程安全，支持并发访问。
    
    设计参考: claw-code runtime/task_registry.rs
    """
    
    def __init__(self):
        self._inner = RegistryInner()
        self._lock = threading.RLock()
        self._default_roles_initialized = False
    
    def _ensure_default_roles(self) -> None:
        """初始化默认角色"""
        if self._default_roles_initialized:
            return
            
        default_roles = [
            Role(
                name="研究员",
                role_type=RoleType.RESEARCHER,
                description="负责深度调研和信息收集",
                capabilities=["research", "investigation", "analysis"],
                max_concurrent=3,
                timeout_seconds=300
            ),
            Role(
                name="开发者",
                role_type=RoleType.DEVELOPER,
                description="负责代码实现和开发任务",
                capabilities=["code", "implementation", "debug", "refactor"],
                max_concurrent=5,
                timeout_seconds=600
            ),
            Role(
                name="验证者",
                role_type=RoleType.VALIDATOR,
                description="负责测试验证和质量检查",
                capabilities=["test", "verify", "validation", "review"],
                max_concurrent=3,
                timeout_seconds=180
            ),
            Role(
                name="记录员",
                role_type=RoleType.RECORDER,
                description="负责文档记录和知识整理",
                capabilities=["documentation", "record", "summarize", "organize"],
                max_concurrent=4,
                timeout_seconds=120
            ),
            Role(
                name="协调者",
                role_type=RoleType.COORDINATOR,
                description="负责任务协调和进度跟踪",
                capabilities=["coordinate", "schedule", "monitor", "dispatch"],
                max_concurrent=2,
                timeout_seconds=240
            ),
        ]
        
        for role in default_roles:
            self.register(role)
        
        self._default_roles_initialized = True
    
    def register(self, role: Role) -> bool:
        """
        注册一个新角色
        
        Args:
            role: 要注册的角色
            
        Returns:
            bool: 注册是否成功
        """
        with self._lock:
            if role.name in self._inner.roles:
                return False  # 角色已存在
            
            self._inner.roles[role.name] = role
            
            # 按类型索引
            if role.role_type not in self._inner.roles_by_type:
                self._inner.roles_by_type[role.role_type] = []
            self._inner.roles_by_type[role.role_type].append(role.name)
            
            return True
    
    def unregister(self, name: str) -> bool:
        """
        注销角色
        
        Args:
            name: 角色名称
            
        Returns:
            bool: 注销是否成功
        """
        with self._lock:
            if name not in self._inner.roles:
                return False
            
            role = self._inner.roles[name]
            del self._inner.roles[name]
            
            # 从类型索引中移除
            if role.role_type in self._inner.roles_by_type:
                type_roles = self._inner.roles_by_type[role.role_type]
                if name in type_roles:
                    type_roles.remove(name)
            
            return True
    
    def get(self, name: str) -> Optional[Role]:
        """
        获取指定名称的角色
        
        Args:
            name: 角色名称
            
        Returns:
            Optional[Role]: 角色对象或None
        """
        with self._lock:
            return self._inner.roles.get(name)
    
    def get_by_type(self, role_type: RoleType) -> List[Role]:
        """
        获取指定类型的所有角色
        
        Args:
            role_type: 角色类型
            
        Returns:
            List[Role]: 角色列表
        """
        with self._lock:
            names = self._inner.roles_by_type.get(role_type, [])
            return [self._inner.roles[name] for name in names if name in self._inner.roles]
    
    def find_can_handle(self, task_type: str) -> List[Role]:
        """
        查找能处理指定任务类型的角色
        
        Args:
            task_type: 任务类型
            
        Returns:
            List[Role]: 能处理该任务类型的角色列表
        """
        self._ensure_default_roles()
        with self._lock:
            result = []
            for role in self._inner.roles.values():
                if role.can_handle(task_type):
                    result.append(role)
            return result
    
    def list_all(self) -> List[Role]:
        """
        列出所有已注册的角色
        
        Returns:
            List[Role]: 所有角色列表
        """
        self._ensure_default_roles()
        with self._lock:
            return list(self._inner.roles.values())
    
    def list_types(self) -> Set[RoleType]:
        """
        列出所有已注册的角色类型
        
        Returns:
            Set[RoleType]: 角色类型集合
        """
        with self._lock:
            return set(self._inner.roles_by_type.keys())
    
    def count(self) -> int:
        """
        获取已注册角色的数量
        
        Returns:
            int: 角色数量
        """
        with self._lock:
            return len(self._inner.roles)
    
    def clear(self) -> None:
        """清空所有已注册的角色"""
        with self._lock:
            self._inner.roles.clear()
            self._inner.roles_by_type.clear()
            self._default_roles_initialized = False


# 全局单例
_global_registry: Optional[RoleRegistry] = None
_registry_lock = threading.Lock()


def get_global_registry() -> RoleRegistry:
    """获取全局角色注册表单例"""
    global _global_registry
    with _registry_lock:
        if _global_registry is None:
            _global_registry = RoleRegistry()
        return _global_registry
