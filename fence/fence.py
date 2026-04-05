"""
记忆殿堂 - 围栏隔离模块 V1.3
空间隔离、权限边界检查、越界检测和告警
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
import hashlib


class SpaceType(Enum):
    """空间类型枚举"""
    PRIVATE = "private"      # 私人空间
    LIBRARY = "library"      # 图书馆
    PUBLIC = "public"        # 公共空间


class Permission(Enum):
    """权限级别枚举"""
    NONE = 0
    READ = 1
    WRITE = 2
    ADMIN = 3


@dataclass
class SpaceBoundary:
    """空间边界定义"""
    space_type: SpaceType
    path: str
    permission: Permission
    parent_space: Optional['SpaceBoundary'] = None
    allowed_extensions: List[str] = field(default_factory=list)
    max_size_mb: int = 100


@dataclass
class ViolationEvent:
    """越界事件记录"""
    timestamp: float
    source_space: SpaceType
    target_space: SpaceType
    action: str
    details: str
    severity: str  # low, medium, high, critical


class FenceAlert:
    """围栏告警系统"""
    
    def __init__(self):
        self._handlers: List[Callable[[ViolationEvent], None]] = []
        self._log_path = Path.home() / ".openclaw" / "projects" / "记忆殿堂v2.0" / "fence" / "violations.log"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def register_handler(self, handler: Callable[[ViolationEvent], None]):
        """注册告警处理器"""
        self._handlers.append(handler)
    
    def trigger(self, event: ViolationEvent):
        """触发告警"""
        # 记录到日志
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": event.timestamp,
                "source": event.source_space.value,
                "target": event.target_space.value,
                "action": event.action,
                "details": event.details,
                "severity": event.severity
            }, ensure_ascii=False) + "\n")
        
        # 调用所有处理器
        for handler in self._handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"[FenceAlert] Handler error: {e}")
    
    def get_recent_violations(self, limit: int = 50) -> List[Dict]:
        """获取最近的越界记录"""
        if not self._log_path.exists():
            return []
        
        violations = []
        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    violations.append(json.loads(line.strip()))
                except:
                    continue
        
        return violations[-limit:]


class MemoryPalaceFence:
    """记忆殿堂围栏 - V1.3"""
    
    VERSION = "1.3.0"
    
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else Path.home() / ".openclaw" / "projects" / "记忆殿堂v2.0"
        self.alert = FenceAlert()
        self._current_user = "default"
        self._current_space = SpaceType.PRIVATE
        
        # 初始化空间边界
        self._spaces: Dict[SpaceType, SpaceBoundary] = {
            SpaceType.PRIVATE: SpaceBoundary(
                space_type=SpaceType.PRIVATE,
                path=str(self.base_path / "private"),
                permission=Permission.ADMIN,
                allowed_extensions=[".md", ".txt", ".json"]
            ),
            SpaceType.LIBRARY: SpaceBoundary(
                space_type=SpaceType.LIBRARY,
                path=str(self.base_path / "library"),
                permission=Permission.WRITE,
                allowed_extensions=[".md", ".txt", ".json", ".pdf"]
            ),
            SpaceType.PUBLIC: SpaceBoundary(
                space_type=SpaceType.PUBLIC,
                path=str(self.base_path / "public"),
                permission=Permission.READ,
                allowed_extensions=[".md", ".txt"]
            ),
        }
        
        # 权限矩阵: (source, target) -> allowed
        self._permission_matrix: Dict[tuple, bool] = {
            # 私人空间可以访问图书馆和公共空间
            (SpaceType.PRIVATE, SpaceType.LIBRARY): True,
            (SpaceType.PRIVATE, SpaceType.PUBLIC): True,
            # 图书馆只能访问公共空间
            (SpaceType.LIBRARY, SpaceType.PUBLIC): True,
            # 公共空间不能访问其他空间
            (SpaceType.PUBLIC, SpaceType.PRIVATE): False,
            (SpaceType.PUBLIC, SpaceType.LIBRARY): False,
            # 同级访问需要检查
            (SpaceType.PRIVATE, SpaceType.PRIVATE): True,
            (SpaceType.LIBRARY, SpaceType.LIBRARY): True,
            (SpaceType.PUBLIC, SpaceType.PUBLIC): False,  # 公共空间之间隔离
        }
        
        # 越界计数 (用于阈值告警)
        self._violation_counts: Dict[str, int] = {}
        self._violation_threshold = 5  # 5次越界后触发高危告警
        
        # 创建目录结构
        self._init_spaces()
    
    def _init_spaces(self):
        """初始化空间目录"""
        for space_type, boundary in self._spaces.items():
            Path(boundary.path).mkdir(parents=True, exist_ok=True)
    
    def set_current_context(self, user: str, space: SpaceType):
        """设置当前上下文"""
        old_space = self._current_space
        self._current_user = user
        self._current_space = space
        
        # 记录上下文切换
        if old_space != space:
            print(f"[Fence] Context switched: {self._current_user} @ {space.value}")
    
    def _check_permission(self, source: SpaceType, target: SpaceType, action: str) -> bool:
        """检查权限矩阵"""
        return self._permission_matrix.get((source, target), False)
    
    def _get_space_from_path(self, path: str) -> Optional[SpaceType]:
        """从路径判断目标空间"""
        path_lower = path.lower()
        if "private" in path_lower:
            return SpaceType.PRIVATE
        elif "library" in path_lower:
            return SpaceType.LIBRARY
        elif "public" in path_lower:
            return SpaceType.PUBLIC
        return None
    
    def _create_violation_event(self, source: SpaceType, target: SpaceType, action: str, details: str) -> ViolationEvent:
        """创建越界事件"""
        severity = "low"
        if self._is_critical_violation(source, target, action):
            severity = "critical"
        elif self._is_high_violation(source, target, action):
            severity = "high"
        elif self._is_medium_violation(source, target, action):
            severity = "medium"
        
        return ViolationEvent(
            timestamp=time.time(),
            source_space=source,
            target_space=target,
            action=action,
            details=details,
            severity=severity
        )
    
    def _is_critical_violation(self, source: SpaceType, target: SpaceType, action: str) -> bool:
        """判断严重越界"""
        # 公共空间访问私人空间 = 严重
        return source == SpaceType.PUBLIC and target == SpaceType.PRIVATE
    
    def _is_high_violation(self, source: SpaceType, target: SpaceType, action: str) -> bool:
        """判断高危越界"""
        # 图书馆访问私人空间 = 高危
        return source == SpaceType.LIBRARY and target == SpaceType.PRIVATE
    
    def _is_medium_violation(self, source: SpaceType, target: SpaceType, action: str) -> bool:
        """判断中等越界"""
        return source == SpaceType.PUBLIC and target == SpaceType.LIBRARY
    
    def check_boundary(self, path: str, action: str = "access") -> tuple[bool, Optional[ViolationEvent]]:
        """
        检查边界访问
        返回: (allowed, violation_event_if_denied)
        """
        target_space = self._get_space_from_path(path)
        if target_space is None:
            target_space = self._current_space  # 默认当前空间
        
        # 检查权限
        allowed = self._check_permission(self._current_space, target_space, action)
        
        if not allowed:
            # 创建越界事件
            violation = self._create_violation_event(
                self._current_space, target_space, action,
                f"{self._current_user} attempted to {action} {path}"
            )
            
            # 更新计数
            key = f"{self._current_space.value}->{target_space.value}"
            self._violation_counts[key] = self._violation_counts.get(key, 0) + 1
            
            # 如果超过阈值，升级为高危
            if self._violation_counts[key] >= self._violation_threshold:
                violation.severity = "critical"
            
            # 触发告警
            self.alert.trigger(violation)
            
            return False, violation
        
        return True, None
    
    def validate_access(self, path: str, action: str = "read") -> bool:
        """
        验证访问权限（高层接口）
        权限级别: ADMIN > WRITE > READ > NONE
        """
        allowed, _ = self.check_boundary(path, action)
        if not allowed:
            return False
        
        # 检查权限级别
        current_perm = self._spaces[self._current_space].permission
        target_space = self._get_space_from_path(path) or self._current_space
        target_perm = self._spaces[target_space].permission
        
        # 写操作需要WRITE以上权限
        if action in ("write", "create", "delete"):
            return current_perm.value >= Permission.WRITE.value
        
        # 读操作需要READ以上权限
        return current_perm.value >= Permission.READ.value
    
    def enforce_isolation(self) -> Dict[str, any]:
        """
        强制隔离检查
        返回隔离状态报告
        """
        report = {
            "version": self.VERSION,
            "timestamp": time.time(),
            "current_context": {
                "user": self._current_user,
                "space": self._current_space.value
            },
            "spaces": {},
            "violations": self.alert.get_recent_violations(10),
            "isolation_status": "active"
        }
        
        # 检查各空间状态
        for space_type, boundary in self._spaces.items():
            report["spaces"][space_type.value] = {
                "path": boundary.path,
                "permission": boundary.permission.name,
                "exists": Path(boundary.path).exists()
            }
        
        return report
    
    def get_fence_status(self) -> Dict:
        """获取围栏状态摘要"""
        return {
            "version": self.VERSION,
            "current_space": self._current_space.value,
            "current_user": self._current_user,
            "active_spaces": [s.value for s in self._spaces.keys()],
            "violation_threshold": self._violation_threshold,
            "recent_violations_count": len(self.alert.get_recent_violations())
        }


# 全局围栏实例
_global_fence: Optional[MemoryPalaceFence] = None


def get_fence() -> MemoryPalaceFence:
    """获取全局围栏实例"""
    global _global_fence
    if _global_fence is None:
        _global_fence = MemoryPalaceFence()
    return _global_fence


def check_boundary(path: str, action: str = "access") -> tuple[bool, Optional[ViolationEvent]]:
    """便捷函数：检查边界"""
    return get_fence().check_boundary(path, action)


def validate_access(path: str, action: str = "read") -> bool:
    """便捷函数：验证访问权限"""
    return get_fence().validate_access(path, action)
