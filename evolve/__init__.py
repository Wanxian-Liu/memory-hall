"""
记忆殿堂v2.0 - 自进化闭环模块
Capsule: 01-innovate-memory-palace-v2 + 02-innovate-proactive-evolution-engine

导出:
- ProactiveKnowledgeCorrector: 主动式知识纠错器
- IntentPredictor: 意图预测与预加载器
- AutomatedRootCauseFixer: 自动化根因修复执行器
- AutonomousRepairExecutor: 自主修复执行器 (胶囊v2新增)
- ThreeRingClosedLoop: 三环闭环架构 (胶囊v2新增)
- MonitorRing: 监控环
- DecisionRing: 决策环
- ExecutionRing: 执行环
- MonitorCollector: 指标采集器 (Phase 0新增)
"""

from .self_evolution import (
    ProactiveKnowledgeCorrector,
    IntentPredictor,
    AutomatedRootCauseFixer,
    AutonomousRepairExecutor,
    GenerationItem,
    VerificationResult,
    CorrectionResult,
    Intent,
    RootCauseAnalysis,
    FixExecutionResult,
    ConfidenceLevel,
)

from .three_ring_architecture import (
    ThreeRingClosedLoop,
    MonitorRing,
    DecisionRing,
    ExecutionRing,
    RingStatus,
    AnomalyType,
    MonitorEvent,
    DecisionOutput,
    ExecutionOutput,
)

from .monitor_collector import (
    MonitorCollector,
    MetricType,
    MetricSample,
    MetricsSnapshot,
    create_default_collector,
    create_lightweight_collector,
)

__all__ = [
    # 自进化核心
    "ProactiveKnowledgeCorrector",
    "IntentPredictor",
    "AutomatedRootCauseFixer",
    "AutonomousRepairExecutor",
    "GenerationItem",
    "VerificationResult",
    "CorrectionResult",
    "Intent",
    "RootCauseAnalysis",
    "FixExecutionResult",
    "ConfidenceLevel",
    
    # 三环闭环架构 (胶囊v2)
    "ThreeRingClosedLoop",
    "MonitorRing",
    "DecisionRing",
    "ExecutionRing",
    "RingStatus",
    "AnomalyType",
    "MonitorEvent",
    "DecisionOutput",
    "ExecutionOutput",
    
    # 指标采集器 (Phase 0)
    "MonitorCollector",
    "MetricType",
    "MetricSample",
    "MetricsSnapshot",
    "create_default_collector",
    "create_lightweight_collector",
]
