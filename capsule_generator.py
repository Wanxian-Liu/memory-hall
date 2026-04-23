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

from .gdi_scorer import GDIScorer, GDIResult, CapsuleType as GDI_CapsuleType
from .evomap_validator import EvoMapValidator, EvoMapValidationResult, validate_for_evomap, EvoMapStatus

# 本地胶囊类型别名（供外部导入）
# 使用明确的前缀避免与内部Capsule类冲突
GDI_CapsuleTypeAlias = GDI_CapsuleType
# 向后兼容别名
CapsuleType = GDI_CapsuleTypeAlias


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
    
    # EvoMap兼容性字段
    evomap_validation: Optional[EvoMapValidationResult] = None
    
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
            "gene_signals": self.gene_signals,
            "evomap_validation": self.evomap_validation.to_dict() if self.evomap_validation else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Capsule":
        # 处理gdi_score字段（支持dict或GDIResult对象）
        gdi_score_data = data.get("gdi_score")
        gdi_score = None
        if gdi_score_data is not None:
            if isinstance(gdi_score_data, dict):
                gdi_score = GDIResult(
                    capsule_id=gdi_score_data.get("capsule_id", ""),
                    intrinsic=gdi_score_data.get("intrinsic", 0.0),
                    usage=gdi_score_data.get("usage", 0.0),
                    social=gdi_score_data.get("social", 0.0),
                    freshness=gdi_score_data.get("freshness", 0.0),
                    total=gdi_score_data.get("total", 0.0)
                )
            elif isinstance(gdi_score_data, GDIResult):
                gdi_score = gdi_score_data
        
        # 处理evomap_validation字段（支持dict或EvoMapValidationResult对象）
        evomap_data = data.get("evomap_validation")
        evomap_validation = None
        if evomap_data is not None:
            if isinstance(evomap_data, dict):
                # 处理overall_status可能是字符串或枚举的情况
                overall_status_raw = evomap_data.get("overall_status", EvoMapStatus.NEEDS_WORK)
                if isinstance(overall_status_raw, str):
                    # 尝试从字符串转换为EvoMapStatus枚举
                    try:
                        overall_status = EvoMapStatus[overall_status_raw.upper()]
                    except KeyError:
                        overall_status = EvoMapStatus.NEEDS_WORK
                else:
                    overall_status = overall_status_raw
                evomap_validation = EvoMapValidationResult(
                    capsule_id=evomap_data.get("capsule_id", ""),
                    is_ready_for_evomap=evomap_data.get("is_ready_for_evomap", False),
                    overall_status=overall_status
                )
            elif isinstance(evomap_data, EvoMapValidationResult):
                evomap_validation = evomap_data
        
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            capsule_type=data.get("capsule_type", "innovate"),
            memory_type=data.get("memory_type", "long_term"),
            taxonomy_tags=data.get("taxonomy_tags", []),
            knowledge_type=data.get("knowledge_type", {}),
            related_capsules=data.get("related_capsules", []),
            metadata=data.get("metadata", {}),
            gdi_score=gdi_score,
            gene_type=data.get("gene_type", "innovate"),
            gene_signals=data.get("gene_signals", []),
            evomap_validation=evomap_validation
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
        """生成修复胶囊 - 修复版"""
        import re
        
        # 从problem(input_text)中提取内容
        lines = problem.strip().split('\n')
        title = lines[0].strip() if lines else problem[:50]
        if title.startswith('#'):
            title = title.lstrip('#').strip()
        
        # 提取症状/问题
        symptoms = context.get('symptoms')
        if not symptoms:
            symptom_match = re.search(r'(?:问题|症状|挑战|难题)[：:]?(.*?)(?:\n\n|\n#|$)', problem, re.DOTALL)
            if symptom_match:
                symptoms = symptom_match.group(1).strip()[:400]
        if not symptoms:
            symptoms = problem[:300]
        
        # 提取解决方案
        solution = context.get('solution')
        if not solution:
            solution_match = re.search(r'(?:解决方案?|方法|策略|思路)[：:]?(.*?)(?:\n\n|\n#|$)', problem, re.DOTALL)
            if solution_match:
                solution = solution_match.group(1).strip()[:400]
        if not solution:
            # 提取代码块
            code = re.findall(r'```(?:python)?\s*(.*?)```', problem, re.DOTALL)
            solution = code[0][:300] if code else problem[100:400]
        
        # 提取效果/验证
        verification = context.get('verification')
        if not verification:
            effect_match = re.search(r'(?:效果|验证|指标|结果)[：:]?(.*?)(?:\n\n|\n#|$)', problem, re.DOTALL)
            if effect_match:
                verification = effect_match.group(1).strip()[:300]
        if not verification:
            metrics = [l.strip() for l in problem.split('\n') if '%' in l or '+' in l or '提升' in l or '降低' in l]
            verification = '\n'.join(metrics[:3]) if metrics else '待验证'
        
        # 提取步骤
        steps_match = re.findall(r'(?:\d+[.、]\s*)(.*?)(?:\n|$)', problem)
        steps = '\n'.join([f'{i+1}. {s.strip()}' for i, s in enumerate(steps_match[:3]) if s.strip()])
        if not steps:
            steps = '1. 分析问题\n2. 设计方案\n3. 实施修复\n4. 验证效果'
        
        return f"""## 问题诊断

{title}

## 背景症状

{symptoms or '待诊断'}

## 根本原因

{context.get('root_cause', '通过日志分析和代码审查确定根因')}

## 解决方案

{solution or '待提供'}

## 实施步骤

{steps}

## 验证方法

{verification or '待定义'}

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
        """生成创新胶囊 - 修复版
        
        从input_text中分析并提取内容填充各section
        """
        import re
        
        # 从topic(input_text)中分析提取关键信息
        # 提取标题（第一行或#开头的内容）
        lines = topic.strip().split('\n')
        title = lines[0].strip() if lines else topic[:50]
        if title.startswith('#'):
            title = title.lstrip('#').strip()
        
        # 提取背景（包含"背景"、"问题"、"挑战"等关键词的段落）
        background_patterns = [
            r'(?:背景|问题|挑战|难题|困境)[：:](.*?)(?:\n\n|\n#|$)',
            r'(?:背景|问题|挑战)[\s\n]*(.*?)(?=\n\n\w|\n#|$)',
        ]
        background = context.get('background')
        if not background:
            for pattern in background_patterns:
                match = re.search(pattern, topic, re.DOTALL)
                if match:
                    background = match.group(1).strip()[:500]
                    break
        if not background:
            # 提取前200字作为背景
            background = topic[:200].strip()
        
        # 提取解决方案（包含"方案"、"策略"、"解决"、"方法"等关键词）
        solution_patterns = [
            r'(?:解决方案?|策略|方法|思路|途径)[：:](.*?)(?:\n\n|\n#|$)',
            r'(?:解决|实现|做法)[\s\n]*(.*?)(?=\n\n\w|\n#|$)',
        ]
        solution = context.get('solution') or context.get('design')
        if not solution:
            for pattern in solution_patterns:
                match = re.search(pattern, topic, re.DOTALL)
                if match:
                    solution = match.group(1).strip()[:500]
                    break
        if not solution:
            # 提取中间部分作为方案
            mid = len(topic) // 2
            solution = topic[mid:mid+300].strip()
        
        # 提取效果/价值（包含"效果"、"价值"、"提升"、"降低"等关键词）
        value_patterns = [
            r'(?:效果|价值|提升|降低|优化|改进)[：:](.*?)(?:\n\n|\n#|$)',
            r'(?:\+|\-)(?:\d+%?|\d+x?)(?:\s|$)',  # 如 +35%, -90%
        ]
        value = context.get('value')
        if not value:
            for pattern in value_patterns:
                match = re.search(pattern, topic, re.DOTALL)
                if match:
                    value = match.group(1).strip()[:300]
                    break
        if not value:
            # 提取包含数字的行作为效果
            value_lines = [l.strip() for l in topic.split('\n') if any(c.isdigit() for c in l)]
            if value_lines:
                value = '\n'.join(value_lines[:3])
        
        # 提取代码示例（如果有）
        code_blocks = re.findall(r'```(?:python)?\s*(.*?)```', topic, re.DOTALL)
        code_example = code_blocks[0][:300] if code_blocks else None
        
        # 构建输出
        sections = [f"## 创新主题\n\n{title}"]
        sections.append(f"\n## 背景分析\n\n{background or '待分析'}")
        
        if code_example:
            sections.append(f"\n## 核心代码\n\n```python\n{code_example}\n```")
        
        sections.append(f"\n## 创新思路\n\n{solution or '待探索'}")
        sections.append(f"\n## 方案设计\n\n{context.get('design', solution or '待设计')}")
        sections.append(f"\n## 预期价值\n\n{value or '待评估'}")
        sections.append(f"\n## 实施路径\n\n{context.get('roadmap', '1. 规划设计\n2. 分步实现\n3. 验证效果')}")
        sections.append(f"\n## 风险与机会\n\n{context.get('risks_opportunities', '需根据实际情况评估')}")
        
        return '\n'.join(sections)
    
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
        
        # 5. EvoMap兼容性验证
        capsule.evomap_validation = validate_for_evomap(capsule_dict)
        
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
            "evomap_validation": capsule.evomap_validation,
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
