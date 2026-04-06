"""
记忆殿堂v2.0 - 自适应压缩优化模块
Capsule: 01-optimize-memory-palace-v2
GDI: 65.7 | 性能优化 | 自适应压缩 | 增量索引 | 预测压缩

包含:
- AdaptiveCompressionScheduler: 自适应压缩间隔调度器
- IncrementalMemoryIndex: 增量内存索引
- PredictiveCompressor: 预测性压缩器
"""

import time
import asyncio
import logging
import hashlib
import bisect
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class CompressionLevel(Enum):
    """压缩级别"""
    NONE = "none"
    LIGHT = "light"      # 保留大部分信息
    MEDIUM = "medium"    # 平衡压缩
    AGGRESSIVE = "aggressive"  # 最大压缩


@dataclass
class CompressionTask:
    """压缩任务"""
    session_id: str
    scheduled_at: float
    priority: int = 0
    estimated_benefit: float = 0.0
    status: str = "pending"  # pending, running, completed, skipped


@dataclass
class MemoryEntry:
    """记忆条目"""
    key: str
    value: Any
    timestamp: float
    access_count: int = 1
    last_access: float = field(default_factory=time.time)
    importance_score: float = 0.5  # 0.0-1.0
    compressed: bool = False
    compressed_value: Optional[Any] = None


@dataclass
class CompressionResult:
    """压缩结果"""
    session_id: str
    original_size: int
    compressed_size: int
    compression_ratio: float
    time_taken_ms: float
    quality_score: float  # 0.0-1.0
    items_preserved: int
    items_dropped: int


@dataclass
class IndexSearchResult:
    """索引搜索结果"""
    key: str
    value: Any
    score: float
    source: str = "main"  # main, delta, merged


class AdaptiveCompressionScheduler:
    """
    自适应压缩调度器
    
    根据实时负载动态调整压缩间隔，而非固定5分钟。
    
    策略:
    - CPU负载高 → 延长间隔
    - 消息密集 → 缩短间隔
    - 平滑过渡 → 引入移动平均
    """
    
    def __init__(
        self,
        base_interval: float = 300.0,  # 5分钟基础
        min_interval: float = 60.0,    # 1分钟最小
        max_interval: float = 600.0,   # 10分钟最大
        smoothing_factor: float = 0.3
    ):
        self.base_interval = base_interval
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.smoothing_factor = smoothing_factor
        
        # 当前实际间隔 (带平滑)
        self._current_interval = base_interval
        self._last_calculated_interval = base_interval
        
        # 负载追踪
        self._cpu_load_history: List[float] = []
        self._message_count_history: List[int] = []
        self._max_history_size = 20
        
        # 统计
        self._stats = {
            "schedules_requested": 0,
            "intervals_calculated": 0,
            "compressions_executed": 0,
            "compressions_skipped": 0
        }
    
    def calculate_interval(self, session_context: Any) -> float:
        """
        根据会话上下文计算最优压缩间隔
        
        考虑因素:
        1. CPU负载 (越高 → 越长间隔)
        2. 消息密度 (越高 → 越短间隔)
        3. 时间趋势 (平滑过渡)
        
        Returns:
            float: 推荐压缩间隔 (秒)
        """
        self._stats["schedules_requested"] += 1
        
        try:
            # 提取指标
            cpu_load = self._get_cpu_load(session_context)
            message_count = self._get_message_count(session_context)
            
            # 记录历史
            self._cpu_load_history.append(cpu_load)
            self._message_count_history.append(message_count)
            
            if len(self._cpu_load_history) > self._max_history_size:
                self._cpu_load_history.pop(0)
            if len(self._message_count_history) > self._max_history_size:
                self._message_count_history.pop(0)
            
            # 计算原始推荐间隔
            raw_interval = self._calculate_raw_interval(cpu_load, message_count)
            
            # 平滑过渡
            smoothed_interval = (
                self.smoothing_factor * raw_interval +
                (1 - self.smoothing_factor) * self._last_calculated_interval
            )
            
            # 限制范围
            final_interval = max(
                self.min_interval,
                min(self.max_interval, smoothed_interval)
            )
            
            self._last_calculated_interval = raw_interval
            self._current_interval = final_interval
            self._stats["intervals_calculated"] += 1
            
            return final_interval
            
        except Exception as e:
            logger.warning(f"Interval calculation failed: {e}, using base interval")
            return self.base_interval
    
    def _calculate_raw_interval(
        self, 
        cpu_load: float, 
        message_count: int
    ) -> float:
        """
        计算原始间隔 (无平滑)
        
        公式:
        interval = base * (1 - cpu_load * 0.5) * activity_factor
        """
        # CPU影响因子: 0.5-1.0
        cpu_factor = 1.0 - (cpu_load * 0.5)
        
        # 活动因子: 消息越多，间隔越短
        if message_count > 50:
            activity_factor = 0.3  # 高活动 → 短间隔
        elif message_count > 20:
            activity_factor = 0.6  # 中等活动
        elif message_count > 5:
            activity_factor = 0.8
        else:
            activity_factor = 1.0  # 低活动 → 基础间隔
        
        raw = self.base_interval * cpu_factor * activity_factor
        
        return max(self.min_interval, min(self.max_interval, raw))
    
    def _get_cpu_load(self, session_context: Any) -> float:
        """从上下文获取CPU负载"""
        if hasattr(session_context, "get_cpu_load"):
            return session_context.get_cpu_load()
        if isinstance(session_context, dict):
            return session_context.get("cpu_load", 0.3)
        return 0.3  # 默认中等负载
    
    def _get_message_count(self, session_context: Any) -> int:
        """从上下文获取消息计数"""
        if hasattr(session_context, "get_message_count"):
            return session_context.get_message_count()
        if isinstance(session_context, dict):
            return session_context.get("message_count", 0)
        
        # 尝试从recent_items推断
        if hasattr(session_context, "get_recent_items"):
            return len(session_context.get_recent_items(100))
        if isinstance(session_context, dict):
            recent = session_context.get("recent_items", [])
            return len(recent) if isinstance(recent, list) else 0
        
        return 0
    
    def get_current_interval(self) -> float:
        """获取当前(平滑后的)压缩间隔"""
        return self._current_interval
    
    def get_next_compress_time(self, last_compress_time: float) -> float:
        """
        计算下次压缩时间
        
        Args:
            last_compress_time: 上次压缩时间戳
            
        Returns:
            float: 下次压缩的时间戳
        """
        return last_compress_time + self._current_interval
    
    def should_compress_now(
        self, 
        session_context: Any,
        last_compress_time: float
    ) -> Tuple[bool, str]:
        """
        判断当前是否应该执行压缩
        
        Returns:
            Tuple[bool, str]: (是否压缩, 原因)
        """
        self._stats["schedules_requested"] += 1
        
        current_time = time.time()
        recommended_interval = self.calculate_interval(session_context)
        time_since_last = current_time - last_compress_time
        
        if time_since_last >= recommended_interval:
            self._stats["compressions_executed"] += 1
            reason = f"Interval exceeded: {time_since_last:.0f}s >= {recommended_interval:.0f}s"
            return True, reason
        
        # 紧急情况检查
        if isinstance(session_context, dict):
            if session_context.get("force_compress"):
                self._stats["compressions_executed"] += 1
                return True, "Force compress requested"
            
            # 内存压力检查
            memory_pressure = session_context.get("memory_pressure", 0)
            if memory_pressure > 0.9:
                self._stats["compressions_executed"] += 1
                return True, f"High memory pressure: {memory_pressure:.2f}"
        
        self._stats["compressions_skipped"] += 1
        return False, f"Interval not reached: {time_since_last:.0f}s < {recommended_interval:.0f}s"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取调度统计"""
        stats = self._stats.copy()
        stats["current_interval"] = self._current_interval
        stats["last_calculated_interval"] = self._last_calculated_interval
        stats["cpu_load_avg"] = (
            sum(self._cpu_load_history) / len(self._cpu_load_history)
            if self._cpu_load_history else 0.0
        )
        stats["message_count_avg"] = (
            sum(self._message_count_history) / len(self._message_count_history)
            if self._message_count_history else 0.0
        )
        return stats


class IncrementalMemoryIndex:
    """
    增量内存索引
    
    区别于全量索引，增量索引只记录变更，
    通过delta_index + main_index合并实现高效检索。
    
    设计:
    - main_index: 主索引 (全量)
    - delta_index: 增量索引 (变更)
    - 定期合并: delta → main
    """
    
    def __init__(
        self,
        delta_threshold: int = 100,
        merge_interval: float = 300.0,
        max_delta_size: int = 1000
    ):
        self.delta_threshold = delta_threshold
        self.merge_interval = merge_interval
        self.max_delta_size = max_delta_size
        
        # 主索引
        self.main_index: Dict[str, MemoryEntry] = {}
        
        # 增量索引
        self.delta_index: Dict[str, MemoryEntry] = {}
        
        # 合并锁
        self._merge_lock = asyncio.Lock()
        self._last_merge_time = time.time()
        
        # 统计
        self._stats = {
            "entries_added": 0,
            "entries_merged": 0,
            "merges_performed": 0,
            "searches_performed": 0,
            "search_hits": 0,
            "search_misses": 0
        }
    
    def add_entry(self, key: str, value: Any, importance: float = 0.5) -> bool:
        """
        添加记忆条目 (优先进入增量索引)
        
        Args:
            key: 记忆键
            value: 记忆值
            importance: 重要性评分 0.0-1.0
            
        Returns:
            bool: 是否添加成功
        """
        entry = MemoryEntry(
            key=key,
            value=value,
            timestamp=time.time(),
            importance_score=importance
        )
        
        # 优先添加到增量索引
        self.delta_index[key] = entry
        self._stats["entries_added"] += 1
        
        # 检查是否需要合并
        if len(self.delta_index) >= self.delta_threshold:
            asyncio.create_task(self.merge_delta())
        
        return True
    
    async def merge_delta(self) -> int:
        """
        将增量索引合并到主索引
        
        使用事务性合并:
        1. 加锁
        2. 批量更新
        3. 清空增量
        4. 解锁
        
        Returns:
            int: 合并的条目数量
        """
        async with self._merge_lock:
            merged_count = len(self.delta_index)
            
            if merged_count == 0:
                return 0
            
            # 批量更新主索引
            for key, entry in self.delta_index.items():
                # 增量优先：相同key时使用较新的
                if key not in self.main_index:
                    self.main_index[key] = entry
                else:
                    existing = self.main_index[key]
                    if entry.timestamp > existing.timestamp:
                        self.main_index[key] = entry
            
            self._stats["entries_merged"] += merged_count
            self._stats["merges_performed"] += 1
            
            # 清空增量
            self.delta_index.clear()
            self._last_merge_time = time.time()
            
            logger.debug(f"Delta merged: {merged_count} entries")
            
            return merged_count
    
    async def ensure_merge_if_needed(self) -> None:
        """必要时触发合并 (时间驱动)"""
        time_since_merge = time.time() - self._last_merge_time
        
        if time_since_merge >= self.merge_interval and self.delta_index:
            await self.merge_delta()
    
    def search(self, query: str, limit: int = 10) -> List[IndexSearchResult]:
        """
        搜索记忆
        
        同时检索 main_index 和 delta_index，
        结果合并后按相关性排序。
        
        Args:
            query: 搜索查询
            limit: 返回数量上限
            
        Returns:
            List[IndexSearchResult]: 搜索结果列表
        """
        self._stats["searches_performed"] += 1
        
        results: List[IndexSearchResult] = []
        
        # 主索引搜索
        for key, entry in self.main_index.items():
            score = self._calculate_relevance(key, entry, query)
            if score > 0:
                results.append(IndexSearchResult(
                    key=key,
                    value=entry.value,
                    score=score,
                    source="main"
                ))
        
        # 增量索引搜索
        for key, entry in self.delta_index.items():
            # 跳过已在主索引中的(增量优先)
            if key in self.main_index:
                continue
            score = self._calculate_relevance(key, entry, query)
            if score > 0:
                results.append(IndexSearchResult(
                    key=key,
                    value=entry.value,
                    score=score,
                    source="delta"
                ))
        
        # 按相关性排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        # 更新统计
        if results:
            self._stats["search_hits"] += 1
        else:
            self._stats["search_misses"] += 1
        
        return results[:limit]
    
    def _calculate_relevance(
        self, 
        key: str, 
        entry: MemoryEntry, 
        query: str
    ) -> float:
        """
        计算相关性分数
        
        考虑因素:
        - 关键词匹配
        - 访问频率
        - 时间衰减
        - 重要性评分
        """
        score = 0.0
        query_lower = query.lower()
        key_lower = key.lower()
        
        # 精确匹配
        if query_lower == key_lower:
            score += 1.0
        # 前缀匹配
        elif key_lower.startswith(query_lower):
            score += 0.8
        # 包含匹配
        elif query_lower in key_lower:
            score += 0.6
        # 值内容匹配
        elif isinstance(entry.value, str) and query_lower in entry.value.lower():
            score += 0.4
        
        # 访问频率加成 (最多+0.2)
        access_boost = min(0.2, entry.access_count * 0.02)
        score += access_boost
        
        # 时间衰减 (最近1小时为1.0，每小时-0.1，最低0.3)
        age_hours = (time.time() - entry.last_access) / 3600
        time_decay = max(0.3, 1.0 - age_hours * 0.1)
        score *= time_decay
        
        # 重要性加成
        score = score * (0.5 + entry.importance_score * 0.5)
        
        return score
    
    def update_access(self, key: str) -> bool:
        """更新访问记录"""
        # 先在增量中查找
        if key in self.delta_index:
            entry = self.delta_index[key]
            entry.access_count += 1
            entry.last_access = time.time()
            return True
        
        # 再在主索引中查找
        if key in self.main_index:
            entry = self.main_index[key]
            entry.access_count += 1
            entry.last_access = time.time()
            
            # 标记为已修改，移到增量
            self.delta_index[key] = entry
            return True
        
        return False
    
    def delete_entry(self, key: str) -> bool:
        """删除记忆条目"""
        deleted = False
        
        if key in self.delta_index:
            del self.delta_index[key]
            deleted = True
        
        if key in self.main_index:
            del self.main_index[key]
            deleted = True
        
        return deleted
    
    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计"""
        return {
            **self._stats,
            "main_index_size": len(self.main_index),
            "delta_index_size": len(self.delta_index),
            "hit_rate": (
                self._stats["search_hits"] / self._stats["searches_performed"]
                if self._stats["searches_performed"] > 0 else 0.0
            )
        }


class PredictiveCompressor:
    """
    预测性压缩器
    
    基于机器学习模型预测下次压缩的收益，
    仅在收益超过阈值时执行压缩，节省资源。
    
    核心逻辑:
    predict_benefit → if benefit > threshold: compress → record_result
    """
    
    def __init__(
        self,
        benefit_threshold: float = 0.7,
        compression_model: Optional[Any] = None,
        base_compressor=None,
        min_interval: float = 60.0
    ):
        self.benefit_threshold = benefit_threshold
        self.compression_model = compression_model
        self.base_compressor = base_compressor
        self.min_interval = min_interval
        
        # 特征提取器
        self._feature_extractors: List[Callable] = []
        
        # 预测历史
        self._prediction_history: List[Dict[str, Any]] = []
        self._max_history = 500
        
        # 统计
        self._stats = {
            "predictions_made": 0,
            "compressions_scheduled": 0,
            "compressions_skipped": 0,
            "total_benefit_predicted": 0.0,
            "actual_benefit_achieved": 0.0
        }
    
    def add_feature_extractor(self, extractor: Callable[[Any], float]) -> None:
        """添加特征提取器"""
        self._feature_extractors.append(extractor)
    
    def predict_next_compress_time(
        self, 
        session_state: Any
    ) -> float:
        """
        预测下次压缩时间
        
        流程:
        1. 提取特征
        2. 预测压缩收益
        3. 判断是否值得压缩
        4. 若值得，返回提前的时间
        
        Returns:
            float: 推荐的下次压缩时间戳
        """
        self._stats["predictions_made"] += 1
        
        try:
            # 提取特征
            features = self._extract_features(session_state)
            
            # 预测收益
            predicted_benefit = self._predict_benefit(features)
            
            self._stats["total_benefit_predicted"] += predicted_benefit
            
            # 记录预测
            self._prediction_history.append({
                "timestamp": time.time(),
                "features": features,
                "predicted_benefit": predicted_benefit
            })
            if len(self._prediction_history) > self._max_history:
                self._prediction_history.pop(0)
            
            # 判断是否提前压缩
            if predicted_benefit > self.benefit_threshold:
                self._stats["compressions_scheduled"] += 1
                # 提前1分钟执行
                return time.time() + 60.0
            else:
                self._stats["compressions_skipped"] += 1
                # 返回正常间隔
                return time.time() + self._calculate_next_interval(session_state)
                
        except Exception as e:
            logger.warning(f"Prediction failed: {e}")
            return time.time() + self.min_interval
    
    def _extract_features(self, session_state: Any) -> Dict[str, float]:
        """
        从会话状态提取特征
        
        特征列表:
        - message_velocity: 消息速度 (条/分钟)
        - context_size: 上下文大小
        - memory_pressure: 内存压力
        - session_age: 会话年龄
        - user_activity: 用户活跃度
        """
        features = {}
        
        # 消息速度
        if hasattr(session_state, "get_message_velocity"):
            features["message_velocity"] = session_state.get_message_velocity()
        elif isinstance(session_state, dict):
            features["message_velocity"] = session_state.get("message_velocity", 0.0)
        else:
            features["message_velocity"] = 0.0
        
        # 上下文大小
        if hasattr(session_state, "get_context_size"):
            features["context_size"] = session_state.get_context_size()
        elif isinstance(session_state, dict):
            features["context_size"] = session_state.get("context_size", 0)
        else:
            features["context_size"] = 0
        
        # 内存压力
        if hasattr(session_state, "get_memory_pressure"):
            features["memory_pressure"] = session_state.get_memory_pressure()
        elif isinstance(session_state, dict):
            features["memory_pressure"] = session_state.get("memory_pressure", 0.3)
        else:
            features["memory_pressure"] = 0.3
        
        # 会话年龄
        if hasattr(session_state, "get_session_age"):
            features["session_age"] = session_state.get_session_age()
        elif isinstance(session_state, dict):
            features["session_age"] = session_state.get("session_age", 0.0)
        else:
            features["session_age"] = 0.0
        
        # 用户活跃度
        if hasattr(session_state, "get_user_activity"):
            features["user_activity"] = session_state.get_user_activity()
        elif isinstance(session_state, dict):
            features["user_activity"] = session_state.get("user_activity", 0.5)
        else:
            features["user_activity"] = 0.5
        
        # 自定义特征
        for extractor in self._feature_extractors:
            try:
                custom_features = extractor(session_state)
                if isinstance(custom_features, dict):
                    features.update(custom_features)
                elif isinstance(custom_features, (int, float)):
                    features["custom"] = custom_features
            except Exception as e:
                logger.debug(f"Feature extractor failed: {e}")
        
        return features
    
    def _predict_benefit(self, features: Dict[str, float]) -> float:
        """
        预测压缩收益
        
        若有模型，使用模型预测
        否则使用规则计算
        """
        if self.compression_model:
            try:
                return self.compression_model.predict(features)
            except Exception as e:
                logger.warning(f"Model prediction failed: {e}")
        
        # 规则计算
        return self._rule_based_benefit(features)
    
    def _rule_based_benefit(self, features: Dict[str, float]) -> float:
        """
        基于规则的收益计算
        
        公式:
        benefit = w1*velocity + w2*pressure + w3*context_size_norm - w4*session_age_decay
        """
        velocity = features.get("message_velocity", 0)
        pressure = features.get("memory_pressure", 0.3)
        context_size = features.get("context_size", 0)
        session_age = features.get("session_age", 0)
        activity = features.get("user_activity", 0.5)
        
        # 归一化上下文大小 (假设10MB为上限)
        context_norm = min(1.0, context_size / (10 * 1024 * 1024))
        
        # 会话年龄衰减 (每小时降低10%)
        age_decay = max(0.3, 1.0 - session_age / 3600 * 0.1)
        
        # 加权计算
        benefit = (
            0.3 * (velocity / 10) +      # 消息速度
            0.4 * pressure +              # 内存压力
            0.2 * context_norm +          # 上下文大小
            0.1 * activity               # 用户活跃度
        ) * age_decay
        
        return max(0.0, min(1.0, benefit))
    
    def _calculate_next_interval(self, session_state: Any) -> float:
        """计算下次常规压缩间隔"""
        features = self._extract_features(session_state)
        
        # 间隔与收益成反比
        benefit = self._rule_based_benefit(features)
        base_interval = 300.0
        
        # 收益越高，间隔越短
        interval = base_interval / (1 + benefit * 2)
        
        return max(self.min_interval, min(600.0, interval))
    
    async def compress_if_beneficial(
        self,
        session_state: Any,
        memory_items: List[Any]
    ) -> Optional[CompressionResult]:
        """
        仅在收益充足时执行压缩
        
        Returns:
            CompressionResult if compressed, None if skipped
        """
        predicted_benefit = self._predict_benefit(
            self._extract_features(session_state)
        )
        
        if predicted_benefit < self.benefit_threshold:
            logger.debug(f"Compression skipped: benefit {predicted_benefit:.2f} < threshold {self.benefit_threshold}")
            return None
        
        # 执行压缩
        if self.base_compressor:
            return await self.base_compressor.compress(memory_items)
        
        # 默认实现
        return await self._default_compress(memory_items)
    
    async def _default_compress(
        self, 
        memory_items: List[Any]
    ) -> CompressionResult:
        """默认压缩实现"""
        start_time = time.time()
        
        # 简单压缩：只保留重要条目
        original_size = len(str(memory_items))
        
        # 筛选重要性 > 0.5 的条目
        preserved = [
            item for item in memory_items
            if getattr(item, "importance_score", 0.5) > 0.5
        ]
        
        compressed_size = len(str(preserved))
        compression_ratio = compressed_size / original_size if original_size > 0 else 1.0
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return CompressionResult(
            session_id="predictive",
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=compression_ratio,
            time_taken_ms=elapsed_ms,
            quality_score=0.85,
            items_preserved=len(preserved),
            items_dropped=len(memory_items) - len(preserved)
        )
    
    def record_actual_benefit(self, achieved_benefit: float) -> None:
        """记录实际收益，用于校准模型"""
        if not self._prediction_history:
            return
        
        latest = self._prediction_history[-1]
        latest["actual_benefit"] = achieved_benefit
        
        # 更新统计
        self._stats["actual_benefit_achieved"] += achieved_benefit
    
    def get_prediction_accuracy(self) -> float:
        """获取预测准确率 (如果有实际收益数据)"""
        predictions_with_actual = [
            p for p in self._prediction_history 
            if "actual_benefit" in p
        ]
        
        if not predictions_with_actual:
            return 0.0
        
        # 计算误差
        errors = [
            abs(p["predicted_benefit"] - p["actual_benefit"])
            for p in predictions_with_actual
        ]
        avg_error = sum(errors) / len(errors)
        
        # 转换为准确率 (1 - avg_error)
        return max(0.0, 1.0 - avg_error)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        stats["prediction_accuracy"] = self.get_prediction_accuracy()
        stats["avg_predicted_benefit"] = (
            self._stats["total_benefit_predicted"] / self._stats["predictions_made"]
            if self._stats["predictions_made"] > 0 else 0.0
        )
        stats["compression_rate"] = (
            self._stats["compressions_scheduled"] / self._stats["predictions_made"]
            if self._stats["predictions_made"] > 0 else 0.0
        )
        return stats


# ========== 模块导出 ==========

__all__ = [
    "AdaptiveCompressionScheduler",
    "IncrementalMemoryIndex",
    "PredictiveCompressor",
    "CompressionTask",
    "MemoryEntry",
    "CompressionResult",
    "IndexSearchResult",
    "CompressionLevel",
]
