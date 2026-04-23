"""
记忆殿堂归一模块 V2.5
去重引擎：SimHash指纹 + LLM语义去重 + 任务注册追踪

导出:
- Deduplicator: 归一化去重主引擎
- TaskRegistry: 任务注册追踪器
- TaskRecord: 任务记录数据结构
- TaskStatus: 任务状态枚举
- SimHash: SimHash指纹算法
"""

# Re-export from deduplication/ for backward compatibility.
# The canonical location is now deduplication.deduplicator.
try:
    from deduplication.deduplicator import (
        Deduplicator,
        TaskRegistry,
        TaskRecord,
        TaskStatus,
        SimHash,
        LLMSemanticDeduplicator,
    )
except ImportError:
    # Fallback for direct normalizer/ usage before full migration completes
    from .deduplicator import (
        Deduplicator,
        TaskRegistry,
        TaskRecord,
        TaskStatus,
        SimHash,
        LLMSemanticDeduplicator,
    )

__version__ = "2.5.0"
__all__ = [
    "Deduplicator",
    "TaskRegistry",
    "TaskRecord",
    "TaskStatus",
    "SimHash",
    "LLMSemanticDeduplicator",
]
