"""
记忆殿堂v2.0 自适应压缩模块
Context Optimization Adaptive Compression Capsule

根据实时需求动态调整压缩阈值
在信息保留和资源效率之间取得平衡

场景：
- 简单查询：高压缩率，快速响应
- 复杂推理：低压缩率，保留细节
- 混合任务：自适应切换

作者: 织界中枢
版本: 1.0.0
"""

import time
import threading
from enum import Enum
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field


class CompressionLevel(Enum):
    """压缩级别"""
    MINIMAL = "minimal"   # 保留最多信息，低压缩率
    BALANCED = "balanced" # 平衡模式
    AGGRESSIVE = "aggressive"  # 高压缩率，快速响应
    ADAPTIVE = "adaptive"  # 自适应模式（默认）


@dataclass
class AdaptiveThresholds:
    """自适应阈值配置"""
    # 各压缩级别对应的目标压缩比
    minimal_ratio: float = 0.7    # 保留70%
    balanced_ratio: float = 0.4    # 保留40%
    aggressive_ratio: float = 0.2  # 保留20%
    
    # 自适应切换阈值
    complexity_threshold_high: float = 0.8   # 高复杂度切换到低压缩
    complexity_threshold_low: float = 0.3    # 低复杂度切换到高压缩
    
    # 时间窗口
    evaluation_window_seconds: float = 60.0   # 评估窗口


@dataclass
class CompressionContext:
    """压缩上下文"""
    query_complexity: float = 0.5  # 0-1，复杂度评分
    estimated_tokens: int = 0
    memory_type: str = "unknown"
    time_budget_ms: float = 100.0  # 时间预算
    quality_requirement: float = 0.8  # 质量要求
    is_realtime: bool = False  # 是否实时查询


class AdaptiveCompressionController:
    """
    自适应压缩控制器
    
    根据上下文动态选择最优压缩级别和阈值：
    1. 评估查询复杂度
    2. 计算最优压缩比
    3. 动态调整阈值
    """
    
    def __init__(
        self,
        thresholds: Optional[AdaptiveThresholds] = None,
        complexity_evaluator: Optional[Callable[[str], float]] = None,
    ):
        """
        初始化自适应压缩控制器
        
        Args:
            thresholds: 阈值配置
            complexity_evaluator: 复杂度评估函数
        """
        self.thresholds = thresholds or AdaptiveThresholds()
        self.complexity_evaluator = complexity_evaluator or self._default_complexity_evaluator
        
        # 当前状态
        self._current_level = CompressionLevel.ADAPTIVE
        self._complexity_history: list[float] = []
        self._last_switch_time = time.time()
        
        # 统计
        self._stats = {
            "total_compressions": 0,
            "level_switches": 0,
            "complexity_avg": 0.5,
        }
        
        self._lock = threading.RLock()
    
    def _default_complexity_evaluator(self, text: str) -> float:
        """
        默认复杂度评估函数
        
        基于：
        - 文本长度
        - 特殊字符密度
        - 嵌套结构
        - 专业术语密度
        """
        if not text:
            return 0.0
        
        # 长度评分（越长越复杂）
        length_score = min(len(text) / 2000, 1.0)
        
        # 嵌套括号评分
        nest_count = text.count('(') + text.count('[') + text.count('{')
        nest_score = min(nest_count / 20, 1.0)
        
        # 术语密度（简化：基于常见分隔符）
        term_chars = set('():{}[],;|')
        term_score = sum(1 for c in text if c in term_chars) / max(len(text), 1)
        term_score = min(term_score * 10, 1.0)
        
        # 代码/结构标记
        code_markers = ['```', 'def ', 'class ', 'import ', 'return ', 'if ', 'for ']
        code_score = sum(1 for m in code_markers if m in text) / len(code_markers)
        
        # 综合评分
        complexity = (
            length_score * 0.3 +
            nest_score * 0.2 +
            term_score * 0.2 +
            code_score * 0.3
        )
        
        return min(max(complexity, 0.0), 1.0)
    
    def evaluate_complexity(self, text: str) -> float:
        """评估文本复杂度"""
        return self.complexity_evaluator(text)
    
    def determine_compression_level(
        self,
        context: CompressionContext,
    ) -> CompressionLevel:
        """
        根据上下文确定压缩级别
        
        Args:
            context: 压缩上下文
            
        Returns:
            CompressionLevel: 最优压缩级别
        """
        with self._lock:
            # 如果是自适应模式，基于复杂度计算
            if self._current_level == CompressionLevel.ADAPTIVE:
                complexity = context.query_complexity
                
                # 更新历史
                self._complexity_history.append(complexity)
                if len(self._complexity_history) > 100:
                    self._complexity_history.pop(0)
                
                # 基于复杂度选择级别
                if complexity >= self.thresholds.complexity_threshold_high:
                    return CompressionLevel.MINIMAL
                elif complexity <= self.thresholds.complexity_threshold_low:
                    return CompressionLevel.AGGRESSIVE
                else:
                    return CompressionLevel.BALANCED
            
            return self._current_level
    
    def get_target_ratio(self, level: CompressionLevel) -> float:
        """获取目标压缩比"""
        ratios = {
            CompressionLevel.MINIMAL: self.thresholds.minimal_ratio,
            CompressionLevel.BALANCED: self.thresholds.balanced_ratio,
            CompressionLevel.AGGRESSIVE: self.thresholds.aggressive_ratio,
            CompressionLevel.ADAPTIVE: self.thresholds.balanced_ratio,  # 自适应默认用平衡
        }
        return ratios.get(level, self.thresholds.balanced_ratio)
    
    def set_level(self, level: CompressionLevel) -> None:
        """
        设置压缩级别
        
        Args:
            level: 压缩级别
        """
        with self._lock:
            if self._current_level != level:
                self._current_level = level
                self._last_switch_time = time.time()
                self._stats["level_switches"] += 1
    
    def calculate_optimal_tokens(
        self,
        original_tokens: int,
        context: CompressionContext,
    ) -> int:
        """
        计算最优目标token数
        
        Args:
            original_tokens: 原始token数
            context: 压缩上下文
            
        Returns:
            int: 目标token数
        """
        level = self.determine_compression_level(context)
        target_ratio = self.get_target_ratio(level)
        
        # 考虑时间预算
        if context.time_budget_ms < 50 and context.is_realtime:
            # 实时模式，提高压缩率
            target_ratio *= 0.8
        
        # 考虑质量要求
        if context.quality_requirement > 0.9:
            # 高质量要求，降低压缩率
            target_ratio = min(target_ratio * 1.3, 1.0)
        
        return int(original_tokens * target_ratio)
    
    def record_compression(self, level: CompressionLevel, ratio: float) -> None:
        """记录压缩结果"""
        with self._lock:
            self._stats["total_compressions"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            if self._complexity_history:
                avg = sum(self._complexity_history) / len(self._complexity_history)
            else:
                avg = 0.5
            
            return {
                **self._stats,
                "current_level": self._current_level.value,
                "complexity_avg": avg,
                "complexity_window_size": len(self._complexity_history),
                "time_since_last_switch": time.time() - self._last_switch_time,
            }


class AdaptiveExtractionPipeline:
    """
    自适应萃取流水线
    
    将自适应压缩控制器与萃取流程结合：
    1. 评估上下文复杂度
    2. 确定压缩级别
    3. 动态调整萃取参数
    4. 执行萃取
    """
    
    def __init__(
        self,
        controller: Optional[AdaptiveCompressionController] = None,
    ):
        self.controller = controller or AdaptiveCompressionController()
    
    def create_context(
        self,
        text: str,
        memory_type: str = "unknown",
        is_realtime: bool = False,
        **kwargs,
    ) -> CompressionContext:
        """
        创建压缩上下文
        
        Args:
            text: 待处理文本
            memory_type: 记忆类型
            is_realtime: 是否实时处理
            **kwargs: 其他参数
            
        Returns:
            CompressionContext: 压缩上下文
        """
        complexity = self.controller.evaluate_complexity(text)
        estimated_tokens = self._estimate_tokens(text)
        
        return CompressionContext(
            query_complexity=complexity,
            estimated_tokens=estimated_tokens,
            memory_type=memory_type,
            is_realtime=is_realtime,
            **kwargs,
        )
    
    def _estimate_tokens(self, text: str) -> int:
        """估算token数"""
        # 简单估算：中文按字符，英文按单词
        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        return chinese_chars + english_words
    
    def should_use_llm(
        self,
        context: CompressionContext,
    ) -> bool:
        """
        判断是否应该使用LLM进行萃取
        
        Args:
            context: 压缩上下文
            
        Returns:
            bool: 是否使用LLM
        """
        level = self.controller.determine_compression_level(context)
        
        # 简单查询或实时处理不使用LLM
        if context.is_realtime and context.query_complexity < 0.5:
            return False
        
        # 高质量要求且复杂度高使用LLM
        if context.quality_requirement > 0.9 and context.query_complexity > 0.6:
            return True
        
        return False
    
    def get_extraction_config(
        self,
        context: CompressionContext,
    ) -> Dict[str, Any]:
        """
        获取萃取配置
        
        Args:
            context: 压缩上下文
            
        Returns:
            Dict: 萃取配置参数
        """
        level = self.controller.determine_compression_level(context)
        target_tokens = self.controller.calculate_optimal_tokens(
            context.estimated_tokens,
            context,
        )
        
        return {
            "compression_level": level,
            "target_tokens": target_tokens,
            "use_llm": self.should_use_llm(context),
            "max_tokens": target_tokens,
            "quality_requirement": context.quality_requirement,
        }


# ============ 模块导出 ============

__all__ = [
    "CompressionLevel",
    "AdaptiveThresholds",
    "CompressionContext",
    "AdaptiveCompressionController",
    "AdaptiveExtractionPipeline",
]
