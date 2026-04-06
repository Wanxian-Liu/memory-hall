"""
记忆殿堂v2.0 Mini Agent - 精简Claude Code实现

基于claw-code源码设计，实现小模型代理功能：
- 上下文压缩 (compact)
- Hook机制 (before_tool_call, tool_result_persist)
- 任务注册表 (registry)
"""

from .compact import (
    CompactionConfig,
    CompactionResult,
    should_compact,
    compact_session,
    format_compact_summary,
    estimate_session_tokens,
)
from .hooks import (
    HookEvent,
    HookResult,
    HookManager,
    BeforeToolCallHook,
    ToolResultPersistHook,
)
from .registry import (
    Task,
    TaskStatus,
    TaskRegistry,
)

__all__ = [
    # compact
    "CompactionConfig",
    "CompactionResult",
    "should_compact",
    "compact_session",
    "format_compact_summary",
    "estimate_session_tokens",
    # hooks
    "HookEvent",
    "HookResult",
    "HookManager",
    "BeforeToolCallHook",
    "ToolResultPersistHook",
    # registry
    "Task",
    "TaskStatus",
    "TaskRegistry",
]
