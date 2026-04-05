# -*- coding: utf-8 -*-
"""
记忆殿堂v2.0 - 任务管理模块

基于织界中枢V2.0的任务管理系统
"""

from .task_manager import (
    TaskManager,
    TaskStatus,
    PhaseType,
    CircuitState,
    TaskContext,
    CircuitBreaker,
    CircuitOpenError,
    TaskNotFoundError,
    get_default_manager,
    create_task,
)

__all__ = [
    # 核心类
    "TaskManager",
    "TaskContext",
    "CircuitBreaker",
    # 枚举
    "TaskStatus",
    "PhaseType",
    "CircuitState",
    # 异常
    "CircuitOpenError",
    "TaskNotFoundError",
    # 便捷函数
    "get_default_manager",
    "create_task",
]

__version__ = "2.0.0"
