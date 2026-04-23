"""
记忆殿堂v2.0 - 统一集成接口 (懒加载版本)
Capsule: 01-innovate + 01-optimize + 01-repair + 03-optimize-capsules

整合五个胶囊模块，提供统一的接入接口:
- evolve: 自进化闭环 (ProactiveKnowledgeCorrector, IntentPredictor, AutomatedRootCauseFixer)
- optimize: 自适应压缩 (AdaptiveCompressionScheduler, IncrementalMemoryIndex, PredictiveCompressor)
- repair: 备份恢复 (MemoryBackupManager, ImportanceAwareCompressor, verify_rag_source)
- sensory: 缓存失效 (HybridCacheInvalidator, MemorySensoryIndex) [Cache Invalidation Capsule]
- extractor: 自适应压缩 (AdaptiveCompressionController, AdaptiveExtractionPipeline) [Context Optimization Capsule]
- memory_layer: RL记忆访问 (RLMemoryLayerManager, MemoryTier) [RL Memory Access Capsule]

使用示例:
    from integrate import MemoryPalaceIntegration
    
    integration = MemoryPalaceIntegration()
    await integration.initialize()
    
    # 添加记忆
    await integration.add_memory(session_id, key, value)
    
    # 压缩调度
    should_compress, reason = integration.should_compress(session_context)
    
    # 备份
    snapshot = integration.backup_before_compress(session_id, memory_state)

⚠️ 懒加载设计:
    - 主类 MemoryPalaceIntegration 在 integration_core.py 中
    - 子模块的导入在第一次访问时才加载
    - 这避免了循环依赖炸弹问题
"""

import sys
from typing import TYPE_CHECKING

# 本地模块 - 始终可用
from .config import IntegrationConfig
from .stats import MemoryStats

# 主类 - 从 integration_core.py 导入
from .integration_core import MemoryPalaceIntegration, create_integration

# ========== TYPE_CHECKING 专用导入 (静态分析用) ==========
if TYPE_CHECKING:
    from evolve.self_evolution import (
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
    )
    from evolve.three_ring_architecture import (
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
    from optimize.adaptive_compression import (
        AdaptiveCompressionScheduler,
        IncrementalMemoryIndex,
        PredictiveCompressor,
        CompressionTask,
        MemoryEntry,
        CompressionResult,
        IndexSearchResult,
        CompressionLevel,
    )
    from repair.backup_manager import (
        verify_rag_source,
        MemoryBackupManager,
        ImportanceAwareCompressor,
        BackupSnapshot,
        RestorationResult,
        RAGVerificationResult,
        CompressedItem,
        VerificationStatus,
        ImportanceLevel,
    )
    from sensory.cache_invalidation import (
        HybridCacheInvalidator,
        MemorySensoryIndex,
        CacheEntry,
    )
    from extractor.adaptive_compression import (
        CompressionLevel,
        AdaptiveThresholds,
        CompressionContext,
        AdaptiveCompressionController,
        AdaptiveExtractionPipeline,
    )
    from memory_layer.rl_access import (
        MemoryTier,
        MemoryAccessAction,
        MemoryAccessState,
        MemoryBlock,
        SimplePolicyNetwork,
        RLMemoryLayerManager,
    )

# ========== __getattr__ 懒加载 (运行时) ==========

def __getattr__(name: str):
    """
    懒加载子模块的类和函数
    这样可以避免在 import 时就加载所有依赖
    """
    # 自进化模块
    if name in (
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
    ):
        from evolve.self_evolution import (
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
        )
        return locals()[name]
    
    # 三环闭环架构
    if name in (
        "ThreeRingClosedLoop",
        "MonitorRing",
        "DecisionRing",
        "ExecutionRing",
        "RingStatus",
        "AnomalyType",
        "MonitorEvent",
        "DecisionOutput",
        "ExecutionOutput",
    ):
        from evolve.three_ring_architecture import (
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
        return locals()[name]
    
    # 优化模块
    if name in (
        "AdaptiveCompressionScheduler",
        "IncrementalMemoryIndex",
        "PredictiveCompressor",
        "CompressionTask",
        "MemoryEntry",
        "CompressionResult",
        "IndexSearchResult",
        "CompressionLevel",
    ):
        from optimize.adaptive_compression import (
            AdaptiveCompressionScheduler,
            IncrementalMemoryIndex,
            PredictiveCompressor,
            CompressionTask,
            MemoryEntry,
            CompressionResult,
            IndexSearchResult,
            CompressionLevel,
        )
        return locals()[name]
    
    # 修复模块
    if name in (
        "verify_rag_source",
        "MemoryBackupManager",
        "ImportanceAwareCompressor",
        "BackupSnapshot",
        "RestorationResult",
        "RAGVerificationResult",
        "CompressedItem",
        "VerificationStatus",
        "ImportanceLevel",
    ):
        from repair.backup_manager import (
            verify_rag_source,
            MemoryBackupManager,
            ImportanceAwareCompressor,
            BackupSnapshot,
            RestorationResult,
            RAGVerificationResult,
            CompressedItem,
            VerificationStatus,
            ImportanceLevel,
        )
        return locals()[name]
    
    # Cache Invalidation Capsule (sensory模块)
    if name in (
        "HybridCacheInvalidator",
        "MemorySensoryIndex",
        "CacheEntry",
    ):
        from sensory.cache_invalidation import (
            HybridCacheInvalidator,
            MemorySensoryIndex,
            CacheEntry,
        )
        return locals()[name]
    
    # Context Optimization Capsule (extractor模块)
    if name in (
        "AdaptiveThresholds",
        "CompressionContext",
        "AdaptiveCompressionController",
        "AdaptiveExtractionPipeline",
    ):
        from extractor.adaptive_compression import (
            CompressionLevel,
            AdaptiveThresholds,
            CompressionContext,
            AdaptiveCompressionController,
            AdaptiveExtractionPipeline,
        )
        return locals()[name]
    
    # RL Memory Access Capsule (memory_layer模块)
    if name in (
        "MemoryTier",
        "MemoryAccessAction",
        "MemoryAccessState",
        "MemoryBlock",
        "SimplePolicyNetwork",
        "RLMemoryLayerManager",
    ):
        from memory_layer.rl_access import (
            MemoryTier,
            MemoryAccessAction,
            MemoryAccessState,
            MemoryBlock,
            SimplePolicyNetwork,
            RLMemoryLayerManager,
        )
        return locals()[name]
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ========== 模块导出 ==========

__all__ = [
    # 集成主类
    "MemoryPalaceIntegration",
    "IntegrationConfig",
    "MemoryStats",
    "create_integration",
    
    # 自进化模块
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
    
    # 优化模块
    "AdaptiveCompressionScheduler",
    "IncrementalMemoryIndex",
    "PredictiveCompressor",
    "CompressionTask",
    "MemoryEntry",
    "CompressionResult",
    "IndexSearchResult",
    "CompressionLevel",
    
    # 修复模块
    "verify_rag_source",
    "MemoryBackupManager",
    "ImportanceAwareCompressor",
    "BackupSnapshot",
    "RestorationResult",
    "RAGVerificationResult",
    "CompressedItem",
    "VerificationStatus",
    "ImportanceLevel",
    
    # ============ Capsule v3新增: 03-optimize-capsules ============
    
    # Cache Invalidation Capsule (sensory模块)
    "HybridCacheInvalidator",
    "MemorySensoryIndex",
    "CacheEntry",
    
    # Context Optimization Capsule (extractor模块)
    "AdaptiveThresholds",
    "CompressionContext",
    "AdaptiveCompressionController",
    "AdaptiveExtractionPipeline",
    
    # RL Memory Access Capsule (memory_layer模块)
    "MemoryTier",
    "MemoryAccessAction",
    "MemoryAccessState",
    "MemoryBlock",
    "SimplePolicyNetwork",
    "RLMemoryLayerManager",
]
