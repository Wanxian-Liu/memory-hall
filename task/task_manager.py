# -*- coding: utf-8 -*-
"""
记忆殿堂v2.0 - 任务管理模块
基于织界中枢V2.0的任务管理系统

功能：
- 任务注册和状态机
- 熔断机制
- 阶段协议
"""

import time
import uuid
import asyncio
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"          # 待执行
    RUNNING = "running"          # 执行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消
    TIMEOUT = "timeout"          # 超时
    CIRCUIT_OPEN = "circuit_open"  # 熔断开启


class PhaseType(Enum):
    """阶段类型枚举"""
    PLANNING = "planning"        # 规划阶段
    EXECUTING = "executing"      # 执行阶段
    VERIFYING = "verifying"      # 验证阶段
    REPORTING = "reporting"      # 报告阶段


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"            # 关闭（正常）
    OPEN = "open"                # 开启（熔断）
    HALF_OPEN = "half_open"      # 半开（尝试恢复）


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str
    name: str
    description: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    status: TaskStatus = TaskStatus.PENDING
    current_phase: PhaseType = PhaseType.PLANNING
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    timeout: float = 300.0  # 默认超时300秒


@dataclass
class CircuitBreaker:
    """熔断器"""
    failure_count: int = 0
    success_count: int = 0
    state: CircuitState = CircuitState.CLOSED
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    failure_threshold: int = 5      # 失败阈值
    success_threshold: int = 2      # 恢复成功阈值
    timeout: float = 30.0           # 熔断超时（秒）
    half_open_max_calls: int = 3   # 半开状态最大调用数
    half_open_calls: int = 0        # 当前半开状态调用数


class TaskManager:
    """
    任务管理器 - 基于织界中枢V2.0
    
    特性：
    - 任务状态机管理
    - 熔断机制（指数退避+Jitter）
    - 阶段协议（规划→执行→验证→报告）
    - 异步任务支持
    """
    
    def __init__(self):
        self._tasks: Dict[str, TaskContext] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(CircuitBreaker)
        self._phase_handlers: Dict[PhaseType, List[Callable]] = defaultdict(list)
        self._task_observers: List[Callable] = []
        self._lock = asyncio.Lock()
        
        # 熔断配置
        self.circuit_failure_threshold = 5
        self.circuit_success_threshold = 2
        self.circuit_timeout = 30.0
        
        # 阶段超时配置
        self.phase_timeouts = {
            PhaseType.PLANNING: 300.0,   # 规划阶段 300秒
            PhaseType.EXECUTING: 600.0,  # 执行阶段 600秒
            PhaseType.VERIFYING: 180.0,  # 验证阶段 180秒
            PhaseType.REPORTING: 60.0,   # 报告阶段 60秒
        }
    
    # ==================== 任务注册与管理 ====================
    
    def register_task(self, name: str, description: str = "", 
                     max_retries: int = 3, timeout: float = 300.0,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        注册新任务
        
        Args:
            name: 任务名称
            description: 任务描述
            max_retries: 最大重试次数
            timeout: 任务超时时间（秒）
            metadata: 额外元数据
            
        Returns:
            task_id: 任务ID
        """
        task_id = str(uuid.uuid4())
        ctx = TaskContext(
            task_id=task_id,
            name=name,
            description=description,
            max_retries=max_retries,
            timeout=timeout,
            metadata=metadata or {}
        )
        self._tasks[task_id] = ctx
        
        # 初始化熔断器
        if task_id not in self._circuit_breakers:
            self._circuit_breakers[task_id] = CircuitBreaker(
                failure_threshold=self.circuit_failure_threshold,
                success_threshold=self.circuit_success_threshold,
                timeout=self.circuit_timeout
            )
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[TaskContext]:
        """获取任务上下文"""
        return self._tasks.get(task_id)
    
    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[TaskContext]:
        """列出任务"""
        if status is None:
            return list(self._tasks.values())
        return [t for t in self._tasks.values() if t.status == status]
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if task and task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task.status = TaskStatus.CANCELLED
            task.updated_at = time.time()
            return True
        return False
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False
    
    # ==================== 状态机管理 ====================
    
    def transition_to(self, task_id: str, new_status: TaskStatus) -> bool:
        """
        状态转换
        
        合法转换：
        - PENDING → RUNNING, CANCELLED
        - RUNNING → COMPLETED, FAILED, TIMEOUT, CANCELLED, CIRCUIT_OPEN
        - COMPLETED/FAILED/TIMEOUT/CANCELLED → PENDING (重试)
        """
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        valid_transitions = {
            TaskStatus.PENDING: [TaskStatus.RUNNING, TaskStatus.CANCELLED],
            TaskStatus.RUNNING: [TaskStatus.COMPLETED, TaskStatus.FAILED, 
                               TaskStatus.TIMEOUT, TaskStatus.CANCELLED, 
                               TaskStatus.CIRCUIT_OPEN],
            TaskStatus.COMPLETED: [TaskStatus.PENDING],  # 重试
            TaskStatus.FAILED: [TaskStatus.PENDING],     # 重试
            TaskStatus.TIMEOUT: [TaskStatus.PENDING],   # 重试
            TaskStatus.CANCELLED: [TaskStatus.PENDING], # 重试
            TaskStatus.CIRCUIT_OPEN: [TaskStatus.PENDING],  # 重试
        }
        
        if new_status in valid_transitions.get(task.status, []):
            old_status = task.status
            task.status = new_status
            task.updated_at = time.time()
            self._notify_observers(task, "status_changed", {
                "old": old_status.value,
                "new": new_status.value
            })
            return True
        return False
    
    # ==================== 阶段协议 ====================
    
    def set_phase(self, task_id: str, phase: PhaseType) -> bool:
        """设置任务阶段"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        task.current_phase = phase
        task.updated_at = time.time()
        self._notify_observers(task, "phase_changed", {
            "phase": phase.value
        })
        return True
    
    def register_phase_handler(self, phase: PhaseType, handler: Callable) -> None:
        """注册阶段处理器"""
        self._phase_handlers[phase].append(handler)
    
    async def execute_phase(self, task_id: str, phase: PhaseType, 
                           executor: Callable) -> Any:
        """
        执行阶段
        
        Args:
            task_id: 任务ID
            phase: 阶段类型
            executor: 阶段执行函数
            
        Returns:
            执行结果
            
        Raises:
            TimeoutError: 阶段超时
            CircuitOpenError: 熔断开启
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # 检查熔断
        cb = self._circuit_breakers[task_id]
        if cb.state == CircuitState.OPEN:
            if time.time() - cb.last_failure_time > cb.timeout:
                # 转为半开
                cb.state = CircuitState.HALF_OPEN
                cb.half_open_calls = 0
            else:
                self.transition_to(task_id, TaskStatus.CIRCUIT_OPEN)
                raise CircuitOpenError(f"Circuit is open for task {task_id}")
        
        # 设置阶段
        self.set_phase(task_id, phase)
        
        # 执行阶段处理器
        for handler in self._phase_handlers[phase]:
            await handler(task, phase)
        
        # 执行主逻辑（带超时）
        timeout = self.phase_timeouts.get(phase, 300.0)
        try:
            result = await asyncio.wait_for(executor(), timeout=timeout)
            
            # 成功记录
            self._record_success(task_id)
            return result
            
        except asyncio.TimeoutError:
            self._record_failure(task_id)
            self.transition_to(task_id, TaskStatus.TIMEOUT)
            raise TimeoutError(f"Phase {phase.value} timed out for task {task_id}")
        except Exception as e:
            self._record_failure(task_id)
            self.transition_to(task_id, TaskStatus.FAILED)
            raise
    
    # ==================== 熔断机制 ====================
    
    def _record_success(self, task_id: str) -> None:
        """记录成功"""
        cb = self._circuit_breakers[task_id]
        cb.success_count += 1
        cb.failure_count = 0  # 重置失败计数
        cb.last_success_time = time.time()
        
        if cb.state == CircuitState.HALF_OPEN:
            if cb.success_count >= cb.success_threshold:
                cb.state = CircuitState.CLOSED
                cb.success_count = 0
    
    def _record_failure(self, task_id: str) -> None:
        """记录失败"""
        cb = self._circuit_breakers[task_id]
        cb.failure_count += 1
        cb.success_count = 0  # 重置成功计数
        cb.last_failure_time = time.time()
        
        if cb.state == CircuitState.HALF_OPEN:
            # 半开状态失败，直接断开
            cb.state = CircuitState.OPEN
            cb.half_open_calls = 0
        elif cb.failure_count >= cb.failure_threshold:
            # 达到阈值，开启熔断
            cb.state = CircuitState.OPEN
    
    def get_circuit_state(self, task_id: str) -> CircuitState:
        """获取熔断器状态"""
        return self._circuit_breakers[task_id].state
    
    def reset_circuit(self, task_id: str) -> None:
        """重置熔断器"""
        cb = self._circuit_breakers[task_id]
        cb.state = CircuitState.CLOSED
        cb.failure_count = 0
        cb.success_count = 0
        cb.half_open_calls = 0
    
    def is_circuit_closed(self, task_id: str) -> bool:
        """检查熔断器是否关闭"""
        cb = self._circuit_breakers[task_id]
        return cb.state == CircuitState.CLOSED
    
    # ==================== 观察者模式 ====================
    
    def register_observer(self, observer: Callable) -> None:
        """注册任务观察者"""
        self._task_observers.append(observer)
    
    def _notify_observers(self, task: TaskContext, event: str, data: Dict) -> None:
        """通知观察者"""
        for observer in self._task_observers:
            try:
                observer(task, event, data)
            except Exception:
                pass  # 观察者错误不影响主流程
    
    # ==================== 任务执行流程 ====================
    
    async def run_task(self, task_id: str, 
                      planning_fn: Optional[Callable] = None,
                      executing_fn: Optional[Callable] = None,
                      verifying_fn: Optional[Callable] = None,
                      reporting_fn: Optional[Callable] = None) -> Dict[str, Any]:
        """
        运行完整任务流程
        
        阶段协议流程：
        1. PLANNING (规划) - 理解任务，制定计划
        2. EXECUTING (执行) - 按计划执行
        3. VERIFYING (验证) - 确认结果
        4. REPORTING (报告) - 输出结果
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        results = {
            "task_id": task_id,
            "task_name": task.name,
            "phases": {},
            "success": False,
            "error": None
        }
        
        try:
            # 阶段1: 规划
            if planning_fn:
                results["phases"]["planning"] = await self.execute_phase(
                    task_id, PhaseType.PLANNING, planning_fn
                )
            
            # 阶段2: 执行
            if executing_fn:
                results["phases"]["executing"] = await self.execute_phase(
                    task_id, PhaseType.EXECUTING, executing_fn
                )
            
            # 阶段3: 验证
            if verifying_fn:
                results["phases"]["verifying"] = await self.execute_phase(
                    task_id, PhaseType.VERIFYING, verifying_fn
                )
            
            # 阶段4: 报告
            if reporting_fn:
                results["phases"]["reporting"] = await self.execute_phase(
                    task_id, PhaseType.REPORTING, reporting_fn
                )
            
            # 任务完成
            self.transition_to(task_id, TaskStatus.COMPLETED)
            results["success"] = True
            
        except CircuitOpenError as e:
            results["error"] = str(e)
            self.transition_to(task_id, TaskStatus.CIRCUIT_OPEN)
        except TimeoutError as e:
            results["error"] = str(e)
            self.transition_to(task_id, TaskStatus.TIMEOUT)
        except Exception as e:
            results["error"] = str(e)
            self.transition_to(task_id, TaskStatus.FAILED)
        
        return results
    
    # ==================== 批量操作 ====================
    
    async def run_tasks_batch(self, task_ids: List[str],
                             planning_fn: Optional[Callable] = None,
                             executing_fn: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """批量运行任务"""
        results = []
        for task_id in task_ids:
            result = await self.run_task(
                task_id,
                planning_fn=planning_fn,
                executing_fn=executing_fn
            )
            results.append(result)
        return results
    
    # ==================== 统计信息 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._tasks)
        by_status = defaultdict(int)
        by_phase = defaultdict(int)
        circuit_states = defaultdict(int)
        
        for task in self._tasks.values():
            by_status[task.status.value] += 1
            by_phase[task.current_phase.value] += 1
            circuit_states[self._circuit_breakers[task.task_id].state.value] += 1
        
        return {
            "total_tasks": total,
            "by_status": dict(by_status),
            "by_phase": dict(by_phase),
            "circuit_states": dict(circuit_states)
        }


class CircuitOpenError(Exception):
    """熔断开启异常"""
    pass


class TaskNotFoundError(Exception):
    """任务不存在异常"""
    pass


# ==================== 便捷函数 ====================

_default_manager: Optional[TaskManager] = None


def get_default_manager() -> TaskManager:
    """获取默认任务管理器实例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = TaskManager()
    return _default_manager


def create_task(name: str, description: str = "", **kwargs) -> str:
    """快捷创建任务"""
    return get_default_manager().register_task(name, description, **kwargs)
