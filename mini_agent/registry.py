"""
任务注册表模块 - 简单任务管理

实现功能：
1. 任务注册与跟踪
2. 状态管理
3. 优先级队列
4. 简单调度
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any, List, Dict
from datetime import datetime
import json
import uuid


# ============================================================================
# 数据结构
# ============================================================================

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Task:
    """任务结构"""
    id: str
    name: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    dependencies: list = field(default_factory=list)  # 依赖的任务ID列表
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": str(self.result) if self.result else None,
            "error": self.error,
            "metadata": self.metadata,
            "dependencies": self.dependencies,
        }


# ============================================================================
# 任务注册表
# ============================================================================

class TaskRegistry:
    """任务注册表"""
    
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._task_queue: list[str] = []  # 优先级队列
        self._callbacks: dict[str, list[Callable]] = {
            "on_create": [],
            "on_start": [],
            "on_complete": [],
            "on_fail": [],
            "on_cancel": [],
        }
    
    # =========================================================================
    # 基础CRUD操作
    # =========================================================================
    
    def create(
        self,
        name: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        dependencies: Optional[list] = None,
        metadata: Optional[dict] = None,
    ) -> Task:
        """创建新任务"""
        task_id = str(uuid.uuid4())[:8]
        task = Task(
            id=task_id,
            name=name,
            description=description,
            priority=priority,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        
        self._tasks[task_id] = task
        self._add_to_queue(task_id)
        self._trigger_callbacks("on_create", task)
        
        return task
    
    def get(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def list(
        self,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
    ) -> list[Task]:
        """列出任务"""
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        if priority:
            tasks = [t for t in tasks if t.priority == priority]
        
        return sorted(tasks, key=lambda t: (-t.priority.value, t.created_at))
    
    def update(self, task_id: str, **kwargs) -> Optional[Task]:
        """更新任务"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        task.updated_at = datetime.now()
        return task
    
    def delete(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._queue_remove(task_id)
            return True
        return False
    
    # =========================================================================
    # 状态管理
    # =========================================================================
    
    def start(self, task_id: str) -> bool:
        """开始任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        if task.status != TaskStatus.PENDING:
            return False
        
        # 检查依赖是否完成
        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if not dep or dep.status != TaskStatus.COMPLETED:
                return False
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.updated_at = datetime.now()
        self._trigger_callbacks("on_start", task)
        
        return True
    
    def complete(self, task_id: str, result: Any = None) -> bool:
        """完成任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        # 允许从 PENDING 或 RUNNING 状态完成（支持直接完成任务）
        if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            return False
            return False
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.result = result
        task.updated_at = datetime.now()
        self._queue_remove(task_id)
        self._trigger_callbacks("on_complete", task)
        
        return True
    
    def fail(self, task_id: str, error: str) -> bool:
        """任务失败"""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False
        
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now()
        task.error = error
        task.updated_at = datetime.now()
        self._queue_remove(task_id)
        self._trigger_callbacks("on_fail", task)
        
        return True
    
    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task or task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            return False
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        task.updated_at = datetime.now()
        self._queue_remove(task_id)
        self._trigger_callbacks("on_cancel", task)
        
        return True
    
    # =========================================================================
    # 队列管理
    # =========================================================================
    
    def _add_to_queue(self, task_id: str) -> None:
        """添加到优先级队列"""
        task = self._tasks[task_id]
        
        # 按优先级插入
        inserted = False
        for i, qid in enumerate(self._task_queue):
            qtask = self._tasks[qid]
            if task.priority.value > qtask.priority.value:
                self._task_queue.insert(i, task_id)
                inserted = True
                break
        
        if not inserted:
            self._task_queue.append(task_id)
    
    def _queue_remove(self, task_id: str) -> None:
        """从队列中移除"""
        if task_id in self._task_queue:
            self._task_queue.remove(task_id)
    
    def next_task(self) -> Optional[Task]:
        """获取下一个可执行任务"""
        for task_id in self._task_queue:
            task = self._tasks[task_id]
            if task.status == TaskStatus.PENDING:
                # 再次检查依赖
                deps_met = all(
                    self._tasks.get(dep_id) and 
                    self._tasks[dep_id].status == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                )
                if deps_met:
                    return task
        return None
    
    def get_queue(self) -> list[Task]:
        """获取队列中的所有任务"""
        return [self._tasks[tid] for tid in self._task_queue 
                if tid in self._tasks and self._tasks[tid].status == TaskStatus.PENDING]
    
    # =========================================================================
    # 回调管理
    # =========================================================================
    
    def on(self, event: str, callback: Callable) -> None:
        """注册回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _trigger_callbacks(self, event: str, task: Task) -> None:
        """触发回调"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(task)
            except Exception:
                pass  # 静默处理回调错误
    
    # =========================================================================
    # 统计与导出
    # =========================================================================
    
    def stats(self) -> dict:
        """获取统计信息"""
        tasks = list(self._tasks.values())
        return {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING),
            "running": sum(1 for t in tasks if t.status == TaskStatus.RUNNING),
            "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
            "cancelled": sum(1 for t in tasks if t.status == TaskStatus.CANCELLED),
        }
    
    def to_json(self) -> str:
        """导出为JSON"""
        return json.dumps({
            "tasks": [t.to_dict() for t in self._tasks.values()],
            "stats": self.stats(),
        }, indent=2, ensure_ascii=False)
    
    def load_from_json(self, json_str: str) -> None:
        """从JSON加载"""
        data = json.loads(json_str)
        self._tasks.clear()
        self._task_queue.clear()
        
        for tdata in data.get("tasks", []):
            task = Task(
                id=tdata["id"],
                name=tdata["name"],
                description=tdata.get("description", ""),
                status=TaskStatus(tdata["status"]),
                priority=TaskPriority(tdata.get("priority", 1)),
                result=tdata.get("result"),
                error=tdata.get("error"),
                metadata=tdata.get("metadata", {}),
                dependencies=tdata.get("dependencies", []),
            )
            self._tasks[task.id] = task
            
            if task.status == TaskStatus.PENDING:
                self._add_to_queue(task.id)


# ============================================================================
# 便捷函数
# ============================================================================

def create_task_registry() -> TaskRegistry:
    """创建任务注册表"""
    return TaskRegistry()
