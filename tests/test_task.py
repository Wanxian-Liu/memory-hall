# -*- coding: utf-8 -*-
"""
测试 task 模块 - 任务管理系统
"""
import os
import sys
import pytest
import asyncio
import time

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from task.task_manager import (
    TaskManager, TaskContext, TaskStatus,
    PhaseType, CircuitBreaker, CircuitState,
    CircuitOpenError, TaskNotFoundError,
    create_task, get_default_manager
)


class TestTaskStatus:
    """测试TaskStatus枚举"""

    def test_statuses(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.TIMEOUT.value == "timeout"
        assert TaskStatus.CIRCUIT_OPEN.value == "circuit_open"


class TestPhaseType:
    """测试PhaseType枚举"""

    def test_phases(self):
        assert PhaseType.PLANNING.value == "planning"
        assert PhaseType.EXECUTING.value == "executing"
        assert PhaseType.VERIFYING.value == "verifying"
        assert PhaseType.REPORTING.value == "reporting"


class TestCircuitStateEnum:
    """测试CircuitState枚举"""

    def test_states(self):
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestTaskContext:
    """测试TaskContext类"""

    def test_context_creation(self):
        ctx = TaskContext(
            task_id="task_001",
            name="Test Task",
            description="A test task"
        )
        assert ctx.task_id == "task_001"
        assert ctx.name == "Test Task"
        assert ctx.status == TaskStatus.PENDING
        assert ctx.current_phase == PhaseType.PLANNING
        assert ctx.retry_count == 0

    def test_context_with_metadata(self):
        ctx = TaskContext(
            task_id="task_002",
            name="Task with Metadata",
            metadata={"priority": "high", "tags": ["urgent"]}
        )
        assert ctx.metadata["priority"] == "high"
        assert "urgent" in ctx.metadata["tags"]


class TestTaskManager:
    """测试TaskManager主类"""

    def test_manager_init(self):
        """测试管理器初始化"""
        manager = TaskManager()
        assert manager is not None
        assert len(manager._tasks) == 0

    def test_register_task(self):
        """测试注册任务"""
        manager = TaskManager()
        task_id = manager.register_task(
            name="Test Task",
            description="A test task",
            max_retries=3,
            timeout=60.0
        )
        assert task_id is not None
        assert task_id in manager._tasks

        task = manager.get_task(task_id)
        assert task is not None
        assert task.name == "Test Task"
        assert task.max_retries == 3

    def test_get_task(self):
        """测试获取任务"""
        manager = TaskManager()
        task_id = manager.register_task(name="Get Test")

        task = manager.get_task(task_id)
        assert task is not None
        assert task.task_id == task_id

        # 不存在的任务
        assert manager.get_task("nonexistent") is None

    def test_list_tasks(self):
        """测试列出任务"""
        manager = TaskManager()
        id1 = manager.register_task(name="Task 1")
        id2 = manager.register_task(name="Task 2")

        all_tasks = manager.list_tasks()
        assert len(all_tasks) >= 2

        # 按状态过滤
        pending = manager.list_tasks(status=TaskStatus.PENDING)
        assert all(t.status == TaskStatus.PENDING for t in pending)

    def test_cancel_task(self):
        """测试取消任务"""
        manager = TaskManager()
        task_id = manager.register_task(name="Cancel Test")

        result = manager.cancel_task(task_id)
        assert result is True

        task = manager.get_task(task_id)
        assert task.status == TaskStatus.CANCELLED

    def test_cancel_running_task(self):
        """测试取消RUNNING任务"""
        manager = TaskManager()
        task_id = manager.register_task(name="Already Running")
        manager.transition_to(task_id, TaskStatus.RUNNING)
        result = manager.cancel_task(task_id)
        assert result is True

    def test_delete_task(self):
        """测试删除任务"""
        manager = TaskManager()
        task_id = manager.register_task(name="Delete Test")

        result = manager.delete_task(task_id)
        assert result is True
        assert manager.get_task(task_id) is None

        # 删除不存在的任务
        result = manager.delete_task("nonexistent")
        assert result is False

    def test_transition_to(self):
        """测试状态转换"""
        manager = TaskManager()
        task_id = manager.register_task(name="Transition Test")

        # PENDING -> RUNNING
        result = manager.transition_to(task_id, TaskStatus.RUNNING)
        assert result is True
        task = manager.get_task(task_id)
        assert task.status == TaskStatus.RUNNING

        # RUNNING -> COMPLETED
        result = manager.transition_to(task_id, TaskStatus.COMPLETED)
        assert result is True

        # 无效转换
        result = manager.transition_to(task_id, TaskStatus.RUNNING)
        assert result is False

    def test_set_phase(self):
        """测试设置阶段"""
        manager = TaskManager()
        task_id = manager.register_task(name="Phase Test")

        result = manager.set_phase(task_id, PhaseType.EXECUTING)
        assert result is True

        task = manager.get_task(task_id)
        assert task.current_phase == PhaseType.EXECUTING

    def test_circuit_breaker_failure(self):
        """测试熔断器失败计数"""
        manager = TaskManager()
        task_id = manager.register_task(name="Circuit Test")

        # 模拟多次失败
        for _ in range(5):
            manager._record_failure(task_id)

        cb = manager._circuit_breakers[task_id]
        assert cb.state == CircuitState.OPEN

    def test_circuit_breaker_success(self):
        """测试熔断器成功恢复"""
        manager = TaskManager()
        task_id = manager.register_task(name="Recovery Test")

        # 打开熔断器
        for _ in range(5):
            manager._record_failure(task_id)

        # 模拟时间流逝
        cb = manager._circuit_breakers[task_id]
        cb.last_failure_time = time.time() - 100  # 很久之前

        # 半开状态
        cb.state = CircuitState.HALF_OPEN

        # 记录成功
        manager._record_success(task_id)

    def test_get_circuit_state(self):
        """测试获取熔断器状态"""
        manager = TaskManager()
        task_id = manager.register_task(name="State Test")

        state = manager.get_circuit_state(task_id)
        assert state == CircuitState.CLOSED

    def test_reset_circuit(self):
        """测试重置熔断器"""
        manager = TaskManager()
        task_id = manager.register_task(name="Reset Test")

        # 打开熔断器
        for _ in range(5):
            manager._record_failure(task_id)

        manager.reset_circuit(task_id)
        assert manager.get_circuit_state(task_id) == CircuitState.CLOSED

    def test_is_circuit_closed(self):
        """测试检查熔断器状态"""
        manager = TaskManager()
        task_id = manager.register_task(name="Closed Test")

        assert manager.is_circuit_closed(task_id) is True

        # 打开熔断器
        for _ in range(5):
            manager._record_failure(task_id)

        assert manager.is_circuit_closed(task_id) is False

    def test_register_observer(self):
        """测试注册观察者"""
        manager = TaskManager()
        notifications = []

        def observer(task, event, data):
            notifications.append((task.task_id, event))

        manager.register_observer(observer)
        task_id = manager.register_task(name="Observer Test")
        manager.transition_to(task_id, TaskStatus.RUNNING)

        assert len(notifications) >= 1

    def test_get_stats(self):
        """测试获取统计信息"""
        manager = TaskManager()

        manager.register_task(name="Stats 1")
        manager.register_task(name="Stats 2")
        manager.register_task(name="Stats 3")

        stats = manager.get_stats()
        assert stats["total_tasks"] >= 3
        assert "by_status" in stats
        assert "by_phase" in stats
        assert "circuit_states" in stats

    def test_phase_timeouts(self):
        """测试阶段超时配置"""
        manager = TaskManager()

        assert manager.phase_timeouts[PhaseType.PLANNING] == 300.0
        assert manager.phase_timeouts[PhaseType.EXECUTING] == 600.0
        assert manager.phase_timeouts[PhaseType.VERIFYING] == 180.0
        assert manager.phase_timeouts[PhaseType.REPORTING] == 60.0


class TestTaskManagerAsync:
    """测试TaskManager的异步功能"""

    def test_execute_phase(self):
        """测试执行阶段"""
        manager = TaskManager()
        task_id = manager.register_task(name="Async Phase Test")

        async def mock_executor():
            return {"result": "success"}

        async def run():
            result = await manager.execute_phase(task_id, PhaseType.EXECUTING, mock_executor)
            return result

        result = asyncio.run(run())
        assert result == {"result": "success"}

    def test_run_task(self):
        """测试运行完整任务"""
        manager = TaskManager()
        task_id = manager.register_task(name="Full Task Test")

        async def planning():
            return {"plan": "done"}

        async def executing():
            return {"executed": True}

        async def run():
            result = await manager.run_task(
                task_id,
                planning_fn=planning,
                executing_fn=executing
            )
            return result

        result = asyncio.run(run())
        assert result["success"] is True
        assert "phases" in result

    def test_run_task_with_circuit_open(self):
        """测试熔断开启时的任务执行"""
        manager = TaskManager()
        task_id = manager.register_task(name="Circuit Task")

        # 打开熔断器
        for _ in range(5):
            manager._record_failure(task_id)

        async def mock_executor():
            return {"result": "should not run"}

        async def run():
            try:
                result = await manager.execute_phase(task_id, PhaseType.EXECUTING, mock_executor)
                return result
            except CircuitOpenError:
                return {"error": "circuit_open"}

        result = asyncio.run(run())
        assert "error" in result


class TestGlobalFunctions:
    """测试全局函数"""

    def test_get_default_manager(self):
        """测试获取默认管理器"""
        manager = get_default_manager()
        assert manager is not None
        assert isinstance(manager, TaskManager)

    def test_create_task(self):
        """测试快捷创建任务"""
        task_id = create_task(name="Quick Task", description="Created quickly")
        assert task_id is not None
