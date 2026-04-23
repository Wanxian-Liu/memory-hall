"""
记忆殿堂v2.0 - 核心集成类 (懒加载版本)

提供统一的接入接口:
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
"""

import time
import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field

from .config import IntegrationConfig
from .stats import MemoryStats

logger = logging.getLogger(__name__)


class MemoryPalaceIntegration:
    """
    记忆殿堂v2.0 统一集成接口
    
    整合三个胶囊的核心功能，提供单一入口:
    1. 自进化 (evolve): 主动纠错、意图预测、根因修复
    2. 自适应压缩 (optimize): 调度器、增量索引、预测压缩
    3. 备份恢复 (repair): 备份管理、重要性压缩、RAG验证
    
    核心流程:
    add_memory → should_compress → compress_with_backup → search_with_index
    """
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        self.config = config or IntegrationConfig()
        
        # 懒加载标志 - 在__getattr__中设置为True
        self._lazy_loaded = False
        self._lazy_errors: List[str] = []
        
        # ========== 初始化各模块 (懒加载) ==========
        # 这些会在第一次访问时加载
        self._corrector = None
        self._intent_predictor = None
        self._root_cause_fixer = None
        self._autonomous_repair_executor = None
        self._three_ring_loop = None
        self._compression_scheduler = None
        self._memory_index = None
        self._predictive_compressor = None
        self._backup_manager = None
        self._importance_compressor = None
        self._cache_invalidator = None
        self._sensory_index = None
        self._adaptive_compression_controller = None
        self._adaptive_extraction_pipeline = None
        self._rl_memory_manager = None
        
        # ========== 会话状态 ==========
        self._session_states: Dict[str, Dict[str, Any]] = {}
        self._last_compress_times: Dict[str, float] = {}
        
        # ========== 统计 ==========
        self._stats = MemoryStats()
        
        # ========== 钩子函数 ==========
        self._hooks: Dict[str, List[Callable]] = {
            "on_memory_add": [],
            "on_compress": [],
            "on_correct": [],
            "on_backup": [],
            "on_restore": []
        }
    
    def _ensure_lazy_modules(self) -> None:
        """懒加载所有子模块"""
        if self._lazy_loaded:
            return
        
        try:
            # --- 自进化模块 ---
            from evolve.self_evolution import (
                ProactiveKnowledgeCorrector,
                IntentPredictor,
                AutomatedRootCauseFixer,
                AutonomousRepairExecutor,
            )
            
            self._corrector = ProactiveKnowledgeCorrector(
                confidence_threshold=self.config.confidence_threshold,
                correction_window=self.config.correction_window,
                rag_verifier=None  # 后续注入
            )
            
            self._intent_predictor = IntentPredictor(
                n_predictions=self.config.n_predictions,
                preload_limit=self.config.preload_limit,
                memory_retriever=None  # 后续注入
            )
            
            self._root_cause_fixer = AutomatedRootCauseFixer(
                max_retries=3
            )
            
            self._autonomous_repair_executor = AutonomousRepairExecutor(
                max_retries=3
            )
            
            # --- 三环闭环架构 ---
            from evolve.three_ring_architecture import ThreeRingClosedLoop
            self._three_ring_loop = ThreeRingClosedLoop()
            
            # --- 优化模块 ---
            from optimize.adaptive_compression import (
                AdaptiveCompressionScheduler,
                IncrementalMemoryIndex,
                PredictiveCompressor,
            )
            
            self._compression_scheduler = AdaptiveCompressionScheduler(
                base_interval=self.config.base_compression_interval,
                min_interval=self.config.min_compression_interval,
                max_interval=self.config.max_compression_interval
            )
            
            self._memory_index = IncrementalMemoryIndex(
                delta_threshold=self.config.delta_threshold,
                merge_interval=self.config.delta_merge_interval
            )
            
            self._predictive_compressor = PredictiveCompressor(
                benefit_threshold=self.config.benefit_threshold
            )
            
            # --- 修复模块 ---
            from repair.backup_manager import (
                MemoryBackupManager,
                ImportanceAwareCompressor,
            )
            
            self._backup_manager = MemoryBackupManager(
                backup_dir=self.config.backup_dir,
                max_backups_per_session=self.config.max_backups_per_session,
                retention_hours=self.config.backup_retention_hours
            )
            
            self._importance_compressor = ImportanceAwareCompressor(
                target_ratio=self.config.compression_target_ratio,
                backup_manager=self._backup_manager
            )
            
            # --- Cache Invalidation Capsule ---
            from sensory.cache_invalidation import (
                HybridCacheInvalidator,
                MemorySensoryIndex,
            )
            
            self._cache_invalidator = HybridCacheInvalidator(
                ttl_base=self.config.base_compression_interval,
                max_size=1000
            )
            
            self._sensory_index = MemorySensoryIndex(
                ttl_base=self.config.base_compression_interval,
                max_size=1000
            )
            
            # --- Context Optimization Capsule ---
            from extractor.adaptive_compression import (
                AdaptiveCompressionController,
                AdaptiveExtractionPipeline,
            )
            
            self._adaptive_compression_controller = AdaptiveCompressionController()
            
            self._adaptive_extraction_pipeline = AdaptiveExtractionPipeline(
                controller=self._adaptive_compression_controller
            )
            
            # --- RL Memory Access Capsule ---
            from memory_layer.rl_access import RLMemoryLayerManager
            
            self._rl_memory_manager = RLMemoryLayerManager(
                hot_size=100,
                warm_size=500,
                cold_size=2000,
                training_interval=100
            )
            
            self._lazy_loaded = True
            logger.info("MemoryPalaceIntegration: All lazy modules loaded successfully")
            
        except Exception as e:
            logger.error(f"MemoryPalaceIntegration: Lazy module loading failed: {e}")
            self._lazy_errors.append(str(e))
            raise
    
    # ========== 属性访问 (懒加载代理) ==========
    
    @property
    def corrector(self):
        if self._corrector is None:
            self._ensure_lazy_modules()
        return self._corrector
    
    @property
    def intent_predictor(self):
        if self._intent_predictor is None:
            self._ensure_lazy_modules()
        return self._intent_predictor
    
    @property
    def root_cause_fixer(self):
        if self._root_cause_fixer is None:
            self._ensure_lazy_modules()
        return self._root_cause_fixer
    
    @property
    def autonomous_repair_executor(self):
        if self._autonomous_repair_executor is None:
            self._ensure_lazy_modules()
        return self._autonomous_repair_executor
    
    @property
    def three_ring_loop(self):
        if self._three_ring_loop is None:
            self._ensure_lazy_modules()
        return self._three_ring_loop
    
    @property
    def compression_scheduler(self):
        if self._compression_scheduler is None:
            self._ensure_lazy_modules()
        return self._compression_scheduler
    
    @property
    def memory_index(self):
        if self._memory_index is None:
            self._ensure_lazy_modules()
        return self._memory_index
    
    @property
    def predictive_compressor(self):
        if self._predictive_compressor is None:
            self._ensure_lazy_modules()
        return self._predictive_compressor
    
    @property
    def backup_manager(self):
        if self._backup_manager is None:
            self._ensure_lazy_modules()
        return self._backup_manager
    
    @property
    def importance_compressor(self):
        if self._importance_compressor is None:
            self._ensure_lazy_modules()
        return self._importance_compressor
    
    @property
    def cache_invalidator(self):
        if self._cache_invalidator is None:
            self._ensure_lazy_modules()
        return self._cache_invalidator
    
    @property
    def sensory_index(self):
        if self._sensory_index is None:
            self._ensure_lazy_modules()
        return self._sensory_index
    
    @property
    def adaptive_compression_controller(self):
        if self._adaptive_compression_controller is None:
            self._ensure_lazy_modules()
        return self._adaptive_compression_controller
    
    @property
    def adaptive_extraction_pipeline(self):
        if self._adaptive_extraction_pipeline is None:
            self._ensure_lazy_modules()
        return self._adaptive_extraction_pipeline
    
    @property
    def rl_memory_manager(self):
        if self._rl_memory_manager is None:
            self._ensure_lazy_modules()
        return self._rl_memory_manager
    
    # ========== 生命周期方法 ==========
    
    async def initialize(self) -> None:
        """初始化集成系统"""
        logger.info("Initializing MemoryPalaceIntegration v2.0")
        
        # 确保模块已加载
        self._ensure_lazy_modules()
        
        # 清理过期备份
        cleaned = self.backup_manager.cleanup_expired()
        logger.info(f"Cleanup: removed {cleaned} expired backups")
        
        self._initialized = True
    
    async def shutdown(self) -> None:
        """关闭集成系统"""
        logger.info("Shutting down MemoryPalaceIntegration")
        
        # 合并所有增量索引
        await self.memory_index.merge_delta()
        
        # 清理过期快照
        self.backup_manager.cleanup_expired()
        
        self._initialized = False
    
    # ========== 注册钩子 ==========
    
    def register_hook(self, event: str, callback: Callable) -> None:
        """注册事件钩子"""
        if event in self._hooks:
            self._hooks[event].append(callback)
    
    async def _trigger_hook(self, event: str, *args, **kwargs) -> None:
        """触发事件钩子"""
        for callback in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Hook {event} failed: {e}")
    
    # ========== 记忆操作 ==========
    
    async def add_memory(
        self,
        session_id: str,
        key: str,
        value: Any,
        importance: float = 0.5,
        memory_type: Optional[str] = None
    ) -> bool:
        """
        添加记忆条目
        
        Args:
            session_id: 会话ID
            key: 记忆键
            value: 记忆值
            importance: 重要性评分
            memory_type: 记忆类型 (decision_point, user_preference, tool_result等)
            
        Returns:
            bool: 是否添加成功
        """
        if not self._initialized:
            await self.initialize()
        
        # 获取 MemoryEntry 类型 (懒加载)
        from optimize.adaptive_compression import MemoryEntry
        
        # 创建记忆条目
        entry = MemoryEntry(
            key=key,
            value=value,
            timestamp=time.time(),
            importance_score=importance
        )
        
        # 添加到索引
        self.memory_index.add_entry(key, entry.value, importance)
        
        # 更新会话状态
        if session_id not in self._session_states:
            self._session_states[session_id] = {
                "memory_count": 0,
                "first_seen": time.time(),
                "message_count": 0
            }
        
        self._session_states[session_id]["memory_count"] += 1
        self._stats.total_memories += 1
        
        # 触发钩子
        await self._trigger_hook("on_memory_add", session_id, key, entry)
        
        return True
    
    async def search_memories(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List:
        """
        搜索记忆
        
        使用增量索引进行高效搜索。
        
        Args:
            query: 搜索查询
            session_id: 可选，限定会话
            limit: 返回数量
            
        Returns:
            List[IndexSearchResult]: 搜索结果
        """
        if not self._initialized:
            await self.initialize()
        
        # 获取类型 (懒加载)
        from optimize.adaptive_compression import IndexSearchResult
        
        # 确保合并增量
        await self.memory_index.ensure_merge_if_needed()
        
        # 搜索
        results = self.memory_index.search(query, limit)
        
        # 按会话过滤
        if session_id:
            # TODO: 实现会话过滤
            pass
        
        return results
    
    # ========== 压缩相关 ==========
    
    async def should_compress(
        self,
        session_id: str,
        session_context: Any
    ) -> Tuple[bool, str]:
        """
        判断是否应该执行压缩
        
        使用自适应调度器计算最优时机。
        
        Returns:
            Tuple[bool, str]: (是否压缩, 原因)
        """
        last_time = self._last_compress_times.get(session_id, 0)
        
        should, reason = self.compression_scheduler.should_compress_now(
            session_context,
            last_time
        )
        
        if should:
            self._last_compress_times[session_id] = time.time()
        
        return should, reason
    
    async def compress_session(
        self,
        session_id: str,
        memory_items: List[Any],
        memory_state: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Any:
        """
        执行会话压缩
        
        流程:
        1. 检查是否需要压缩 (或force=True)
        2. 创建备份
        3. 使用重要性压缩
        4. 记录结果
        
        Args:
            session_id: 会话ID
            memory_items: 待压缩的记忆条目
            memory_state: 完整记忆状态 (用于备份)
            force: 强制压缩 (跳过调度检查)
            
        Returns:
            CompressionResult: 压缩结果
        """
        # 获取类型 (懒加载)
        from optimize.adaptive_compression import CompressionResult
        
        if not self._initialized:
            await self.initialize()
        
        # 检查是否该压缩
        if not force:
            should, reason = await self.should_compress(
                session_id,
                {"message_count": len(memory_items)}
            )
            if not should:
                logger.debug(f"Compression skipped: {reason}")
                return CompressionResult(
                    session_id=session_id,
                    original_size=0,
                    compressed_size=0,
                    compression_ratio=1.0,
                    time_taken_ms=0,
                    quality_score=1.0,
                    items_preserved=len(memory_items),
                    items_dropped=0
                )
        
        start_time = time.time()
        
        # 使用重要性压缩 (带备份)
        preserved, snapshot = self.importance_compressor.compress_with_backup(
            session_id=session_id,
            memory_items=memory_items,
            memory_state=memory_state
        )
        
        # 计算压缩结果
        original_size = sum(len(str(i)) for i in memory_items)
        compressed_size = sum(len(str(p)) for p in preserved)
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        result = CompressionResult(
            session_id=session_id,
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=compressed_size / original_size if original_size > 0 else 1.0,
            time_taken_ms=elapsed_ms,
            quality_score=0.85,  # 简化计算
            items_preserved=len(preserved),
            items_dropped=len(memory_items) - len(preserved)
        )
        
        # 更新统计
        self._stats.total_compressions += 1
        self._last_compress_times[session_id] = time.time()
        
        # 触发钩子
        await self._trigger_hook("on_compress", session_id, result)
        
        if snapshot:
            await self._trigger_hook("on_backup", session_id, snapshot)
        
        return result
    
    # ========== 备份恢复 ==========
    
    async def create_backup(
        self,
        session_id: str,
        memory_state: Dict[str, Any],
        critical_keys: Optional[List[str]] = None
    ) -> Any:
        """
        创建记忆备份
        
        Args:
            session_id: 会话ID
            memory_state: 当前记忆状态
            critical_keys: 关键记忆键列表
            
        Returns:
            BackupSnapshot: 备份快照
        """
        # 获取类型 (懒加载)
        from repair.backup_manager import BackupSnapshot
        
        snapshot = self.backup_manager.backup_before_compress(
            session_id=session_id,
            memory_state=memory_state,
            critical_keys=critical_keys
        )
        
        self._stats.total_backups += 1
        await self._trigger_hook("on_backup", session_id, snapshot)
        
        return snapshot
    
    async def restore(
        self,
        snapshot_id: str,
        target_keys: Optional[List[str]] = None
    ) -> Any:
        """
        从备份恢复
        
        Args:
            snapshot_id: 快照ID
            target_keys: 可选，指定要恢复的键
            
        Returns:
            RestorationResult: 恢复结果
        """
        result = self.backup_manager.restore(snapshot_id, target_keys)
        
        if result.success:
            self._stats.total_restores += 1
            await self._trigger_hook("on_restore", snapshot_id, result)
        
        return result
    
    # ========== RAG 验证 ==========
    
    async def verify_rag(
        self,
        retrieved_chunk: Any,
        claim: str
    ) -> Any:
        """
        验证RAG检索结果
        
        Args:
            retrieved_chunk: RAG检索返回的chunk
            claim: 待验证的声明
            
        Returns:
            RAGVerificationResult: 验证结果
        """
        from repair.backup_manager import verify_rag_source
        
        return await verify_rag_source(
            retrieved_chunk=retrieved_chunk,
            claim=claim,
            similarity_threshold=self.config.rag_similarity_threshold
        )
    
    # ========== 自进化 ==========
    
    async def correct_knowledge(
        self,
        session_context: Any
    ) -> List[Any]:
        """
        执行主动知识纠错
        
        监控会话上下文中的生成内容，评估置信度，
        对低置信度内容进行验证和纠错。
        
        Args:
            session_context: 会话上下文
            
        Returns:
            List[CorrectionResult]: 纠错结果列表
        """
        corrections = await self.corrector.monitor_and_correct(session_context)
        
        self._stats.total_corrections += len(corrections)
        await self._trigger_hook("on_correct", corrections)
        
        return corrections
    
    async def predict_intents(
        self,
        current_context: Any
    ) -> List[Any]:
        """
        预测用户意图并预加载
        
        Args:
            current_context: 当前上下文
            
        Returns:
            List[Intent]: 预测的意图列表
        """
        return await self.intent_predictor.predict_and_preload(current_context)
    
    async def diagnose_and_fix(
        self,
        error_context: Any
    ) -> Any:
        """
        诊断并修复问题
        
        Args:
            error_context: 错误上下文
            
        Returns:
            FixExecutionResult: 修复结果
        """
        return await self.root_cause_fixer.diagnose_and_fix(error_context)
    
    # ========== 统计与健康检查 ==========
    
    def get_stats(self) -> MemoryStats:
        """获取统一统计信息"""
        # 如果还没加载模块，返回基础统计
        if not self._lazy_loaded:
            self._stats.sessions_tracked = len(self._session_states)
            return self._stats
        
        # 聚合各模块统计
        self._stats.sessions_tracked = len(self._session_states)
        
        scheduler_stats = self.compression_scheduler.get_stats()
        corrector_stats = self.corrector.get_stats()
        fixer_stats = self.root_cause_fixer.get_stats()
        index_stats = self.memory_index.get_stats()
        backup_stats = self.backup_manager.get_stats()
        compressor_stats = self.importance_compressor.get_stats()
        
        # 更新计算比率
        if self._stats.total_compressions > 0:
            self._stats.compression_ratio_avg = (
                compressor_stats.get("bytes_saved", 0) / 
                max(1, self._stats.total_compressions)
            )
        
        if self._stats.total_corrections > 0:
            self._stats.correction_success_rate = (
                corrector_stats.get("corrections_injected", 0) / 
                self._stats.total_corrections
            )
        
        return self._stats
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取健康检查报告"""
        return {
            "initialized": getattr(self, "_initialized", False),
            "sessions": len(self._session_states),
            "stats": self.get_stats().__dict__,
            "modules": {
                "compression_scheduler": self.compression_scheduler.get_stats(),
                "memory_index": self.memory_index.get_stats(),
                "predictive_compressor": self.predictive_compressor.get_stats(),
                "corrector": self.corrector.get_stats(),
                "intent_predictor": self.intent_predictor.get_stats(),
                "root_cause_fixer": self.root_cause_fixer.get_stats(),
                "autonomous_repair_executor": self.autonomous_repair_executor.get_stats(),
                "three_ring_loop": self.three_ring_loop.get_status(),
                "backup_manager": self.backup_manager.get_stats(),
                "importance_compressor": self.importance_compressor.get_stats(),
                # Capsule v3新增模块
                "cache_invalidator": self.cache_invalidator.get_stats(),
                "sensory_index": self.sensory_index.cache.get_stats() if hasattr(self.sensory_index, 'cache') else {},
                "adaptive_compression_controller": self.adaptive_compression_controller.get_stats(),
                "rl_memory_manager": self.rl_memory_manager.get_stats(),
            },
            "timestamp": time.time()
        }
    
    # ========== 三环闭环 (胶囊v2新增) ==========
    
    async def run_evolution_cycle(
        self,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行一次三环闭环进化周期 (胶囊v2核心)
        
        流程: 监控 → 决策 → 执行 → 验证
        
        Args:
            context: 上下文数据
            
        Returns:
            Dict: 周期执行结果
        """
        return await self.three_ring_loop.run_cycle(context)
    
    async def autonomous_repair(
        self,
        error_context: Any
    ) -> Dict[str, Any]:
        """
        自主修复执行 (胶囊v2新增)
        
        Args:
            error_context: 错误上下文
            
        Returns:
            Dict: 修复结果 {status, root_cause, fix_applied}
        """
        return await self.autonomous_repair_executor.diagnose_and_fix(error_context)
    
    def get_all_snapshots(
        self,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Any]:
        """获取备份快照列表"""
        return self.backup_manager.list_snapshots(session_id, limit)


# ========== 便捷函数 ==========

def create_integration(config: Optional[IntegrationConfig] = None) -> MemoryPalaceIntegration:
    """创建集成实例的便捷函数"""
    return MemoryPalaceIntegration(config)
