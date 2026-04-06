"""
记忆殿堂v2.0 胶囊类型生成器 V1.0

根据基因图谱决定生成的胶囊类型:
- repair: 修复胶囊
- optimize: 优化胶囊
- innovate: 创新胶囊

作者: engineering_software_architect
版本: 1.0.0
"""

import re
import time
import hashlib
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from gdi_scorer import GDIScorer, GDIResult, CapsuleType as GDI_CapsuleType

# 本地胶囊类型别名（供外部导入）
CapsuleType = GDI_CapsuleType


class GeneType(Enum):
    """基因类型"""
    REPAIR = "repair"       # 修复基因
    OPTIMIZE = "optimize"  # 优化基因
    INNOVATE = "innovate"  # 创新胶囊


@dataclass
class Capsule:
    """胶囊数据"""
    id: str = ""
    content: str = ""
    capsule_type: str = "innovate"
    memory_type: str = "long_term"
    taxonomy_tags: List[str] = field(default_factory=list)
    knowledge_type: Dict[str, Any] = field(default_factory=dict)
    related_capsules: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # GDI评分
    gdi_score: Optional[GDIResult] = None
    
    # 基因信息
    gene_type: str = "innovate"
    gene_signals: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "capsule_type": self.capsule_type,
            "memory_type": self.memory_type,
            "taxonomy_tags": self.taxonomy_tags,
            "knowledge_type": self.knowledge_type,
            "related_capsules": self.related_capsules,
            "metadata": self.metadata,
            "gdi_score": self.gdi_score.to_dict() if self.gdi_score else None,
            "gene_type": self.gene_type,
            "gene_signals": self.gene_signals
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Capsule":
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            capsule_type=data.get("capsule_type", "innovate"),
            memory_type=data.get("memory_type", "long_term"),
            taxonomy_tags=data.get("taxonomy_tags", []),
            knowledge_type=data.get("knowledge_type", {}),
            related_capsules=data.get("related_capsules", []),
            metadata=data.get("metadata", {}),
            gene_type=data.get("gene_type", "innovate"),
            gene_signals=data.get("gene_signals", [])
        )


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
    "problem_indicators": [
        (r'错误|bug|报错|失败|异常|问题', 1.0),
        (r'不能|无法|不行|失败', 0.8),
        (r'不对|不正确|有误|失效', 0.7),
        (r'崩溃|卡死|无响应|超时', 0.9),
        (r'缺失|缺少|没有|找不到', 0.7),
    ],
    "optimize_indicators": [
        (r'优化|改进|提升|增强', 1.0),
        (r'更快|更高效|更省|更低', 0.8),
        (r'性能|效率|速度|延迟', 0.7),
        (r'简化|精简|减肥|压缩', 0.6),
        (r'重构|重写|改写|升级', 0.7),
    ],
    "innovate_indicators": [
        (r'新功能|新特性|新方案', 1.0),
        (r'创新|创造|发明|设计', 0.9),
        (r'探索|尝试|实验|研究', 0.7),
        (r'集成|融合|结合|混合', 0.6),
        (r'自动化|智能化|自主', 0.7),
    ],
    "urgent_indicators": [
        (r'紧急|急需|立刻|马上', 1.0),
        (r'Critical|紧急|重要', 0.9),
        (r'立即|即时|马上', 0.8),
    ],
}


class GeneMapper:
    """基因图谱映射器"""
    
    def __init__(
        self,
        min_confidence: float = 0.3,
        default_gene: GeneType = GeneType.INNOVATE
    ):
        self.min_confidence = min_confidence
        self.default_gene = default_gene
    
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
    
    def _score_signal_category(self, signals: List[GeneSignal], category: str) -> float:
        """计算某个信号类别的得分"""
        category_signals = [s for s in signals if s.signal_type == category]
        
        if not category_signals:
            return 0.0
        
        max_confidence = max(s.confidence for s in category_signals)
        signal_count = len(category_signals)
        count_bonus = min(0.2, (signal_count - 1) * 0.05)
        
        return max_confidence + count_bonus
    
    def match_gene(self, text: str) -> GeneMatch:
        """匹配基因类型"""
        import re as _re
        
        signals = self.extract_signals(text)
        
        if not signals:
            return GeneMatch(
                gene_type=self.default_gene,
                confidence=0.5,
                matched_signals=[],
                reasoning="无明显信号，使用默认基因类型"
            )
        
        repair_score = self._score_signal_category(signals, "problem_indicators")
        optimize_score = self._score_signal_category(signals, "optimize_indicators")
        innovate_score = self._score_signal_category(signals, "innovate_indicators")
        
        urgent_score = self._score_signal_category(signals, "urgent_indicators")
        if urgent_score > 0.5 and repair_score > 0:
            repair_score += urgent_score * 0.5
        
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
        
        reasoning = self._generate_reasoning(best_gene, signals, scores)
        
        return GeneMatch(
            gene_type=best_gene,
            confidence=best_score,
            matched_signals=signals,
            reasoning=reasoning
        )
    
    def _generate_reasoning(self, gene: GeneType, signals: List[GeneSignal], scores: Dict) -> str:
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
        else:
            return "新功能或创新方案需求"
    
    def select_capsule_type(self, text: str):
        """选择胶囊类型"""
        gene_match = self.match_gene(text)
        capsule_type_map = {
            GeneType.REPAIR: CapsuleType.REPAIR,
            GeneType.OPTIMIZE: CapsuleType.OPTIMIZE,
            GeneType.INNOVATE: CapsuleType.INNOVATE,
        }
        return capsule_type_map[gene_match.gene_type], gene_match


class CapsuleGenerator:
    """
    胶囊类型生成器
    
    根据问题信号生成对应类型的胶囊
    """
    
    def __init__(
        self,
        gene_mapper: Optional[GeneMapper] = None,
        gdi_scorer: Optional[GDIScorer] = None
    ):
        self.gene_mapper = gene_mapper or GeneMapper()
        self.gdi_scorer = gdi_scorer or GDIScorer()
    
    def _generate_repair_capsule(
        self,
        problem: str,
        context: Dict[str, Any]
    ) -> str:
        """生成修复胶囊"""
        return f"""## 问题诊断

{context.get('symptoms', '待诊断')}

## 根本原因

{context.get('root_cause', '待分析')}

## 解决方案

{context.get('solution', '待提供')}

## 实施步骤

1. {context.get('step1', '步骤1')}
2. {context.get('step2', '步骤2')}
3. {context.get('step3', '步骤3')}

## 验证方法

{context.get('verification', '待定义')}

## 注意事项

{context.get('notes', '无')}
"""
    
    def _generate_optimize_capsule(
        self,
        goal: str,
        context: Dict[str, Any]
    ) -> str:
        """生成优化胶囊"""
        return f"""## 当前状态

{context.get('current_state', '待描述')}

## 优化目标

{goal}

## 优化点

{context.get('optimization_points', '待分析')}

## 优化方案

{context.get('optimization_plan', '待设计')}

## 预期效果

{context.get('expected_effect', '待评估')}

## 实施风险

{context.get('risks', '无明显风险')}
"""
    
    def _generate_innovate_capsule(
        self,
        topic: str,
        context: Dict[str, Any]
    ) -> str:
        """生成创新胶囊"""
        return f"""## 创新主题

{topic}

## 背景分析

{context.get('background', '待分析')}

## 创新思路

{context.get('innovation_ideas', '待探索')}

## 方案设计

{context.get('design', '待设计')}

## 预期价值

{context.get('value', '待评估')}

## 实施路径

{context.get('roadmap', '待规划')}

## 风险与机会

{context.get('risks_opportunities', '待分析')}
"""
    
    def generate(
        self,
        input_text: str,
        capsule_type: CapsuleType = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Capsule:
        """
        生成胶囊
        
        Args:
            input_text: 输入文本
            capsule_type: 指定胶囊类型，None则自动判断
            metadata: 额外元数据
            
        Returns:
            Capsule对象
        """
        import re as _re
        
        # 1. 基因匹配
        if capsule_type is None:
            capsule_type, gene_match = self.gene_mapper.select_capsule_type(input_text)
        else:
            gene_match = self.gene_mapper.match_gene(input_text)
        
        # 2. 根据类型生成内容
        context = metadata or {}
        
        if capsule_type == CapsuleType.REPAIR:
            content = self._generate_repair_capsule(input_text, context)
        elif capsule_type == CapsuleType.OPTIMIZE:
            content = self._generate_optimize_capsule(input_text, context)
        else:
            content = self._generate_innovate_capsule(input_text, context)
        
        # 3. 创建胶囊
        capsule = Capsule(
            id=hashlib.md5(f"{input_text}{time.time()}".encode()).hexdigest()[:12],
            content=content,
            capsule_type=capsule_type.value,
            gene_type=gene_match.gene_type.value,
            gene_signals=[s.raw_signal for s in gene_match.matched_signals],
            metadata={
                "created_at": time.time(),
                "input_text": input_text,
                "gene_reasoning": gene_match.reasoning
            }
        )
        
        # 4. GDI评分
        capsule_dict = capsule.to_dict()
        capsule.gdi_score = self.gdi_scorer.score(capsule_dict)
        
        return capsule
    
    def generate_and_evaluate(
        self,
        input_text: str,
        auto_publish: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成并评估胶囊
        
        Args:
            input_text: 输入文本
            auto_publish: 是否自动发布
            metadata: 额外元数据
            
        Returns:
            {
                "capsule": Capsule对象,
                "gdi_score": GDIResult,
                "should_publish": bool,
                "reason": str
            }
        """
        capsule = self.generate(input_text, metadata=metadata)
        gdi_score = capsule.gdi_score
        
        should_publish = gdi_score.should_publish() if gdi_score else False
        
        if auto_publish and not should_publish:
            reason = f"GDI分数 {gdi_score.total:.3f} 低于阈值 {gdi_score.PUBLISH_THRESHOLD}"
        elif auto_publish:
            reason = "GDI分数达标，自动发布"
        else:
            reason = "手动模式，等待确认"
        
        return {
            "capsule": capsule,
            "gdi_score": gdi_score,
            "should_publish": should_publish,
            "reason": reason
        }


# ============ 便捷函数 ============

_default_generator: Optional[CapsuleGenerator] = None


def get_generator(**kwargs) -> CapsuleGenerator:
    """获取默认生成器"""
    global _default_generator
    if _default_generator is None:
        _default_generator = CapsuleGenerator(**kwargs)
    return _default_generator


def generate_capsule(
    input_text: str,
    capsule_type: CapsuleType = None,
    auto_publish: bool = True
) -> Dict[str, Any]:
    """快捷胶囊生成函数"""
    return get_generator().generate_and_evaluate(
        input_text, 
        auto_publish=auto_publish
    )
