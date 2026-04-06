"""
记忆殿堂v2.0 基因图谱映射器 V1.0

功能:
1. 信号提取: 从问题中提取信号
2. 基因匹配: 匹配适合的基因类型
3. 胶囊选择: 根据信号选择胶囊类型

作者: engineering_software_architect
版本: 1.0.0
"""

import re
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class GeneType(Enum):
    """基因类型"""
    REPAIR = "repair"       # 修复基因
    OPTIMIZE = "optimize"  # 优化基因
    INNOVATE = "innovate"  # 创新基因


class CapsuleType(Enum):
    """胶囊类型"""
    REPAIR = "repair"       # 修复胶囊
    OPTIMIZE = "optimize"  # 优化胶囊
    INNOVATE = "innovate"  # 创新胶囊


@dataclass
class GeneSignal:
    """基因信号"""
    raw_signal: str           # 原始信号文本
    signal_type: str          # 信号类型
    confidence: float = 0.0   # 信号置信度
    matched_keywords: List[str] = field(default_factory=list)


@dataclass
class GeneMatch:
    """基因匹配结果"""
    gene_type: GeneType
    confidence: float
    matched_signals: List[GeneSignal]
    reasoning: str


# 信号提取模式
SIGNAL_PATTERNS = {
    # 问题/错误信号
    "problem_indicators": [
        (r'错误|bug|报错|失败|异常|问题', 1.0),
        (r'不能|无法|不行|失败', 0.8),
        (r'不对|不正确|有误|失效', 0.7),
        (r'崩溃|卡死|无响应|超时', 0.9),
        (r'缺失|缺少|没有|找不到', 0.7),
    ],
    
    # 优化信号
    "optimize_indicators": [
        (r'优化|改进|提升|增强', 1.0),
        (r'更快|更高效|更省|更低', 0.8),
        (r'性能|效率|速度|延迟', 0.7),
        (r'简化|精简|减肥|压缩', 0.6),
        (r'重构|重写|改写|升级', 0.7),
    ],
    
    # 创新信号
    "innovate_indicators": [
        (r'新功能|新特性|新方案', 1.0),
        (r'创新|创造|发明|设计', 0.9),
        (r'探索|尝试|实验|研究', 0.7),
        (r'集成|融合|结合|混合', 0.6),
        (r'自动化|智能化|自主', 0.7),
    ],
    
    # 紧急信号
    "urgent_indicators": [
        (r'紧急|急需|立刻|马上', 1.0),
        (r'Critical|紧急|重要', 0.9),
        (r'立即|即时|马上', 0.8),
    ],
}

# 胶囊类型映射
CAPSULE_TYPE_MAP = {
    GeneType.REPAIR: CapsuleType.REPAIR,
    GeneType.OPTIMIZE: CapsuleType.OPTIMIZE,
    GeneType.INNOVATE: CapsuleType.INNOVATE,
}


class GeneMapper:
    """
    基因图谱映射器
    
    从问题/请求中提取信号，匹配基因类型，决定胶囊类型
    """
    
    def __init__(
        self,
        min_confidence: float = 0.3,
        default_gene: GeneType = GeneType.INNOVATE
    ):
        """
        初始化基因映射器
        
        Args:
            min_confidence: 最小置信度阈值
            default_gene: 默认基因类型
        """
        self.min_confidence = min_confidence
        self.default_gene = default_gene
        
        # 权重配置
        self.gene_weights = {
            GeneType.REPAIR: 0.0,
            GeneType.OPTIMIZE: 0.0,
            GeneType.INNOVATE: 0.0,
        }
    
    # ============ 信号提取 ============
    
    def extract_signals(self, text: str) -> List[GeneSignal]:
        """从文本中提取基因信号"""
        signals = []
        text_lower = text.lower()
        
        for signal_type, patterns in SIGNAL_PATTERNS.items():
            for pattern, base_weight in patterns:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    signal = GeneSignal(
                        raw_signal=matches[0] if matches else pattern,
                        signal_type=signal_type,
                        confidence=base_weight,
                        matched_keywords=list(matches)
                    )
                    signals.append(signal)
        
        return signals
    
    def _score_signal_category(
        self, 
        signals: List[GeneSignal], 
        category: str
    ) -> float:
        """计算某个信号类别的得分"""
        category_signals = [
            s for s in signals if s.signal_type == category
        ]
        
        if not category_signals:
            return 0.0
        
        # 取最高置信度的信号
        max_confidence = max(s.confidence for s in category_signals)
        
        # 考虑信号数量（但有衰减）
        signal_count = len(category_signals)
        count_bonus = min(0.2, (signal_count - 1) * 0.05)
        
        return max_confidence + count_bonus
    
    # ============ 基因匹配 ============
    
    def match_gene(self, text: str) -> GeneMatch:
        """
        匹配基因类型
        
        Args:
            text: 输入文本
            
        Returns:
            GeneMatch匹配结果
        """
        # 提取信号
        signals = self.extract_signals(text)
        
        if not signals:
            # 无信号，使用默认基因
            return GeneMatch(
                gene_type=self.default_gene,
                confidence=0.5,
                matched_signals=[],
                reasoning="无明显信号，使用默认基因类型"
            )
        
        # 计算各类别得分
        repair_score = self._score_signal_category(signals, "problem_indicators")
        optimize_score = self._score_signal_category(signals, "optimize_indicators")
        innovate_score = self._score_signal_category(signals, "innovate_indicators")
        
        # 考虑紧急信号 - 紧急情况优先repair
        urgent_score = self._score_signal_category(signals, "urgent_indicators")
        if urgent_score > 0.5 and repair_score > 0:
            repair_score += urgent_score * 0.5
        
        # 确定最佳基因
        scores = {
            GeneType.REPAIR: repair_score,
            GeneType.OPTIMIZE: optimize_score,
            GeneType.INNOVATE: innovate_score,
        }
        
        best_gene = max(scores, key=scores.get)
        best_score = scores[best_gene]
        
        if best_score < self.min_confidence:
            best_gene = self.default_gene
            best_score = 0.5
        
        # 生成推理
        reasoning = self._generate_reasoning(best_gene, signals, scores)
        
        return GeneMatch(
            gene_type=best_gene,
            confidence=best_score,
            matched_signals=signals,
            reasoning=reasoning
        )
    
    def _generate_reasoning(
        self, 
        gene: GeneType, 
        signals: List[GeneSignal],
        scores: Dict[GeneType, float]
    ) -> str:
        """生成推理说明"""
        if gene == GeneType.REPAIR:
            problem_signals = [s for s in signals if "problem" in s.signal_type]
            if problem_signals:
                keywords = [s.raw_signal for s in problem_signals[:3]]
                return f"检测到问题信号: {', '.join(keywords)}"
            return "紧急修复需求"
        
        elif gene == GeneType.OPTIMIZE:
            optimize_signals = [s for s in signals if "optimize" in s.signal_type]
            if optimize_signals:
                keywords = [s.raw_signal for s in optimize_signals[:3]]
                return f"检测到优化信号: {', '.join(keywords)}"
            return "性能或效率优化需求"
        
        else:  # INNOVATE
            return "新功能或创新方案需求"
    
    # ============ 胶囊选择 ============
    
    def select_capsule_type(self, text: str) -> Tuple[CapsuleType, GeneMatch]:
        """
        选择胶囊类型
        
        Args:
            text: 输入文本
            
        Returns:
            (胶囊类型, 基因匹配结果)
        """
        gene_match = self.match_gene(text)
        capsule_type = CAPSULE_TYPE_MAP[gene_match.gene_type]
        
        return capsule_type, gene_match
    
    def select_capsule_type_batch(
        self, 
        texts: List[str]
    ) -> List[Tuple[CapsuleType, GeneMatch]]:
        """批量选择胶囊类型"""
        return [self.select_capsule_type(t) for t in texts]
    
    # ============ 胶囊间关联 ============
    
    def find_related_genes(
        self, 
        gene: GeneType, 
        top_k: int = 2
    ) -> List[GeneType]:
        """
        找到相关的基因类型
        
        例如: repair胶囊通常与optimize相关
        
        Returns:
            相关基因类型列表
        """
        gene_relations = {
            GeneType.REPAIR: [GeneType.OPTIMIZE, GeneType.INNOVATE],
            GeneType.OPTIMIZE: [GeneType.REPAIR, GeneType.INNOVATE],
            GeneType.INNOVATE: [GeneType.OPTIMIZE, GeneType.REPAIR],
        }
        
        return gene_relations.get(gene, [])[:top_k]


# ============ 便捷函数 ============

_default_mapper: Optional[GeneMapper] = None


def get_mapper(**kwargs) -> GeneMapper:
    """获取默认映射器"""
    global _default_mapper
    if _default_mapper is None:
        _default_mapper = GeneMapper(**kwargs)
    return _default_mapper


def match_gene(text: str) -> GeneMatch:
    """快捷基因匹配函数"""
    return get_mapper().match_gene(text)


def select_capsule_type(text: str) -> CapsuleType:
    """快捷胶囊类型选择函数"""
    capsule_type, _ = get_mapper().select_capsule_type(text)
    return capsule_type


def analyze_signals(text: str) -> List[GeneSignal]:
    """快捷信号提取函数"""
    return get_mapper().extract_signals(text)
