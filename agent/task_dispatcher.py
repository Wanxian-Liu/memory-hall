"""
任务分发器 (TaskDispatcher) - 记忆殿堂v2.0 DAME
基于claw-code任务调度设计

功能:
    - 任务提交与排队
    - 任务分配给合适的代理
    - 优先级调度
    - 任务状态追踪
"""

import threading
import uuid
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from heapq import heappush, heappop

from .models import Task, TaskStatus, TaskResult, RoleType, AgentState
from .role_registry import RoleRegistry, get_global_registry
from .lifecycle_manager import AgentLifecycleManager, get_global_lifecycle_manager


@dataclass
class DispatcherConfig:
    """分发器配置"""
    max_pending_tasks: int = 1000       # 最大待处理任务数
    default_priority: int = 0            # 默认优先级
    assign_timeout_seconds: int = 60    # 任务分配超时
    retry_delay_seconds: int = 5         # 重试延迟


class TaskDispatcher:
    """
    任务分发器
    
    负责任务的接收、排队、分配和追踪。
    支持优先级调度和自动重试。
    
    设计参考: claw-code 任务调度系统
    """
    
    def __init__(
        self,
        registry: Optional[RoleRegistry] = None,
        lifecycle_manager: Optional[AgentLifecycleManager] = None,
        config: Optional[DispatcherConfig] = None
    ):
        self.registry = registry or get_global_registry()
        self.lifecycle = lifecycle_manager or get_global_lifecycle_manager()
        self.config = config or DispatcherConfig()
        
        self._tasks: Dict[str, Task] = {}
        self._pending_queue: List[Task] = []  # 优先级队列
        self._lock = threading.RLock()
        
        # 回调函数
        self._on_task_assigned: Optional[Callable[[Task, str], None]] = None
        self._on_task_completed: Optional[Callable[[Task, TaskResult], None]] = None
        self._on_task_failed: Optional[Callable[[Task, str], None]] = None
        
        # 分发线程
        self._dispatch_thread: Optional[threading.Thread] = None
        self._running = False
    
    def set_callbacks(
        self,
        on_task_assigned: Optional[Callable[[Task, str], None]] = None,
        on_task_completed: Optional[Callable[[Task, TaskResult], None]] = None,
        on_task_failed: Optional[Callable[[Task, str], None]] = None,
    ) -> None:
        """设置任务回调函数"""
        self._on_task_assigned = on_task_assigned
        self._on_task_completed = on_task_completed
        self._on_task_failed = on_task_failed
    
    def submit(
        self,
        task_type: str,
        description: str,
        priority: int = 0,
        required_role: Optional[RoleType] = None,
        payload: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None
    ) -> Optional[str]:
        """
        提交新任务
        
        Args:
            task_type: 任务类型
            description: 任务描述
            priority: 优先级
            required_role: 要求的角色类型
            payload: 任务负载
            task_id: 指定任务ID
            
        Returns:
            Optional[str]: 任务ID或None（队列已满）
        """
        with self._lock:
            # 检查队列容量
            if len(self._tasks) >= self.config.max_pending_tasks:
                return None
            
            # 生成task_id
            if task_id is None:
                task_id = f"task_{uuid.uuid4().hex[:12]}"
            
            # 创建任务
            task = Task(
                task_id=task_id,
                task_type=task_type,
                description=description,
                priority=priority,
                required_role=required_role,
                payload=payload or {}
            )
            
            self._tasks[task_id] = task
            heappush(self._pending_queue, task)
            
            return task_id
    
    def dispatch(self, task_id: str) -> bool:
        """
        分发任务给合适的代理
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功分发
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status != TaskStatus.PENDING:
                return False
            
            # 查找合适的代理
            agent = self._find_available_agent(task)
            if agent is None:
                return False
            
            # 分配任务
            return self._assign_to_agent(task, agent)
    
    def _find_available_agent(self, task: Task) -> Optional[Any]:
        """查找可用的代理"""
        # 首先尝试查找空闲代理
        idle_agents = self.lifecycle.list_by_state(AgentState.IDLE)
        for agent in idle_agents:
            if task.required_role is None or agent.role.role_type == task.required_role:
                if agent.role.can_handle(task.task_type):
                    return agent

        # 如果没有空闲代理，查找运行中的代理
        running_agents = self.lifecycle.list_by_state(AgentState.RUNNING)
        for agent in running_agents:
            if agent.current_task_id is None:  # 没有分配任务
                if task.required_role is None or agent.role.role_type == task.required_role:
                    if agent.role.can_handle(task.task_type):
                        return agent
        
        return None
    
    def _assign_to_agent(self, task: Task, agent: Any) -> bool:
        """将任务分配给代理"""
        task.status = TaskStatus.RUNNING
        task.assigned_agent_id = agent.agent_id
        task.started_at = datetime.now()
        
        # 更新代理状态
        self.lifecycle.assign_task(agent.agent_id, task.task_id)
        
        # 触发回调
        if self._on_task_assigned:
            try:
                self._on_task_assigned(task, agent.agent_id)
            except Exception:
                pass
        
        return True
    
    def complete(
        self,
        task_id: str,
        result: Any = None,
        error: Optional[str] = None
    ) -> bool:
        """
        标记任务完成
        
        Args:
            task_id: 任务ID
            result: 执行结果
            error: 错误信息
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            
            if error:
                task.status = TaskStatus.FAILED
                task.error = error
                task.completed_at = datetime.now()
                
                # 尝试重试
                if task.can_retry():
                    task.retry_count += 1
                    task.status = TaskStatus.PENDING
                    heappush(self._pending_queue, task)
                    
                    if self._on_task_failed:
                        try:
                            self._on_task_failed(task, error)
                        except Exception:
                            pass
                    return True
            else:
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now()
            
            # 释放代理
            if task.assigned_agent_id:
                self.lifecycle.set_idle(task.assigned_agent_id)
            
            # 触发回调
            if task.status == TaskStatus.COMPLETED and self._on_task_completed:
                task_result = TaskResult(
                    task_id=task.task_id,
                    agent_id=task.assigned_agent_id or "",
                    success=True,
                    result=result
                )
                try:
                    self._on_task_completed(task, task_result)
                except Exception:
                    pass
            
            return True
    
    def cancel(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
                return False
            
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            
            # 释放代理
            if task.assigned_agent_id:
                self.lifecycle.terminate(task.assigned_agent_id, reason="task_cancelled")
            
            return True
    
    def get(self, task_id: str) -> Optional[Task]:
        """
        获取任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[Task]: 任务对象
        """
        with self._lock:
            return self._tasks.get(task_id)
    
    def list_all(self) -> List[Task]:
        """列出所有任务"""
        with self._lock:
            return list(self._tasks.values())
    
    def list_pending(self) -> List[Task]:
        """列出待处理任务"""
        with self._lock:
            return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
    
    def list_running(self) -> List[Task]:
        """列出运行中任务"""
        with self._lock:
            return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]
    
    def list_completed(self) -> List[Task]:
        """列出已完成任务"""
        with self._lock:
            return [t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]
    
    def count(self) -> int:
        """获取任务总数"""
        with self._lock:
            return len(self._tasks)
    
    def count_pending(self) -> int:
        """获取待处理任务数"""
        return len(self.list_pending())
    
    def _dispatch_loop(self) -> None:
        """分发循环"""
        while self._running:
            try:
                self._process_dispatch()
            except Exception:
                pass
            time.sleep(1)
    
    def _process_dispatch(self) -> None:
        """处理分发"""
        with self._lock:
            # 获取所有待处理任务
            pending = [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
        
        for task in pending:
            if self.dispatch(task.task_id):
                break  # 每次循环只分发一个任务
    
    def start_dispatch_thread(self) -> None:
        """启动分发线程"""
        if self._running:
            return
        
        self._running = True
        
        def dispatch_loop():
            while self._running:
                try:
                    self._process_dispatch()
                except Exception:
                    pass
                time.sleep(1)
        
        self._dispatch_thread = threading.Thread(target=dispatch_loop, daemon=True)
        self._dispatch_thread.start()
    
    def stop_dispatch_thread(self) -> None:
        """停止分发线程"""
        self._running = False
        if self._dispatch_thread:
            self._dispatch_thread.join(timeout=5)
            self._dispatch_thread = None


# 全局单例
_global_dispatcher: Optional[TaskDispatcher] = None
_dispatcher_lock = threading.Lock()


def get_global_dispatcher() -> TaskDispatcher:
    """获取全局任务分发器单例"""
    global _global_dispatcher
    with _dispatcher_lock:
        if _global_dispatcher is None:
            _global_dispatcher = TaskDispatcher()
        return _global_dispatcher
