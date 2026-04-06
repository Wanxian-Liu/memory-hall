"""
数据模型定义 - 记忆殿堂v2.0 DAME
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


class RoleType(Enum):
    """角色类型枚举"""
    RESEARCHER = "researcher"      # 研究员 - 深度调研
    DEVELOPER = "developer"        # 开发者 - 代码实现
    VALIDATOR = "validator"       # 验证者 - 测试审查
    RECORDER = "recorder"         # 记录员 - 文档记录
    COORDINATOR = "coordinator"    # 协调者 - 任务协调


class AgentState(Enum):
    """代理状态枚举"""
    CREATED = "created"           # 已创建
    RUNNING = "running"           # 运行中
    IDLE = "idle"                 # 空闲等待
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"             # 失败
    STOPPED = "stopped"           # 已停止


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 待处理
    RUNNING = "running"           # 执行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"       # 已取消


@dataclass
class Role:
    """角色定义"""
    name: str
    role_type: RoleType
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    max_concurrent: int = 3
    timeout_seconds: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def can_handle(self, task_type: str) -> bool:
        """检查角色是否能处理指定类型的任务"""
        return task_type in self.capabilities


@dataclass
class Agent:
    """代理实例"""
    agent_id: str
    role: Role
    state: AgentState = AgentState.CREATED
    current_task_id: Optional[str] = None
    heartbeat_count: int = 0
    last_heartbeat: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    
    def is_alive(self) -> bool:
        """检查代理是否存活"""
        return self.state in (AgentState.CREATED, AgentState.RUNNING, AgentState.IDLE)
    
    def mark_heartbeat(self) -> None:
        """更新心跳"""
        self.heartbeat_count += 1
        self.last_heartbeat = datetime.now()


@dataclass
class Task:
    """任务定义"""
    task_id: str
    task_type: str  # 任务类型，匹配role.capabilities
    description: str
    priority: int = 0  # 优先级，数字越大优先级越高
    required_role: Optional[RoleType] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __lt__(self, other: 'Task') -> bool:
        """支持heapq比较 - 优先级高的先出队"""
        # 注意：heapq是最小堆，所以我们用负优先级实现最大堆效果
        if not isinstance(other, Task):
            return NotImplemented
        return -self.priority < -other.priority
    
    def can_retry(self) -> bool:
        """检查任务是否可以重试"""
        return self.retry_count < self.max_retries and self.status == TaskStatus.FAILED


@dataclass 
class TaskResult:
    """任务执行结果"""
    task_id: str
    agent_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
