"""
Mimir-Core 根因分析引擎
introspection/root_cause_analyzer.py

负责从问题追溯根本原因，基于依赖关系链分析，
并与 ProblemClassifier 集成提供完整的问题诊断能力。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

try:
    from .problem_classifier import ProblemClassifier, ProblemRecord, ProblemType, Severity, Scope
except ImportError:
    from problem_classifier import ProblemClassifier, ProblemRecord, ProblemType, Severity, Scope


class RootCauseCategory(Enum):
    """根本原因分类"""
    CONFIGURATION = auto()      # 配置错误
    DEPENDENCY_FAILURE = auto() # 依赖模块失败
    RESOURCE_EXHAUSTION = auto() # 资源耗尽
    VERSION_MISMATCH = auto()   # 版本不兼容
    INITIALIZATION = auto()      # 初始化问题
    EXTERNAL_SERVICE = auto()   # 外部服务问题
    CASCADE_FAILURE = auto()   # 级联故障
    UNKNOWN = auto()


@dataclass
class CauseNode:
    """原因节点"""
    module: str
    cause_type: str
    description: str
    confidence: float  # 0.0 - 1.0
    evidence: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "cause_type": self.cause_type,
            "description": self.description,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }


@dataclass
class RootCauseResult:
    """根因分析结果"""
    root_cause: CauseNode
    cause_chain: list[CauseNode]
    affected_modules: list[str]
    category: RootCauseCategory
    fix_suggestions: list[str]
    problem_record: Optional[ProblemRecord] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_cause": self.root_cause.to_dict(),
            "cause_chain": [n.to_dict() for n in self.cause_chain],
            "affected_modules": self.affected_modules,
            "category": self.category.name,
            "fix_suggestions": self.fix_suggestions,
            "problem_record": self.problem_record.to_dict() if self.problem_record else None,
        }


class RootCauseAnalyzer:
    """
    根因分析引擎
    
    从问题出发，通过依赖关系链追溯根本原因。
    """

    # 模块类型映射
    MODULE_TYPES: dict[str, str] = {
        "config": "配置模块",
        "gateway": "网关模块",
        "agent": "代理模块",
        "memory": "记忆层",
        "pipeline": "管道模块",
        "health": "健康检查",
        "introspection": "自省模块",
    }

    # 常见根因模式
    CAUSE_PATTERNS: dict[str, dict[str, Any]] = {
        "config_missing": {
            "pattern": ["config.*missing", "required.*config", "no.*config"],
            "category": RootCauseCategory.CONFIGURATION,
            "modules": ["config", "gateway"],
        },
        "init_failure": {
            "pattern": ["init.*fail", "cannot.*init", "setup.*fail"],
            "category": RootCauseCategory.INITIALIZATION,
            "modules": ["gateway", "agent"],
        },
        "dependency_crash": {
            "pattern": ["crash", "segfault", "abort"],
            "category": RootCauseCategory.CASCADE_FAILURE,
            "modules": [],
        },
        "timeout_chain": {
            "pattern": ["timeout", "timed.*out"],
            "category": RootCauseCategory.EXTERNAL_SERVICE,
            "modules": ["gateway", "network"],
        },
        "memory_pressure": {
            "pattern": ["memory", "oom", "allocation"],
            "category": RootCauseCategory.RESOURCE_EXHAUSTION,
            "modules": ["memory", "health"],
        },
    }

    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.classifier = ProblemClassifier()
        self._dependency_cache: Optional[dict[str, list[str]]] = None

    def trace_cause(
        self,
        problem_message: str,
        raw_data: Optional[dict[str, Any]] = None
    ) -> RootCauseResult:
        """
        从问题追溯根本原因
        
        Args:
            problem_message: 问题消息文本
            raw_data: 原始数据
            
        Returns:
            RootCauseResult: 根因分析结果
        """
        raw_data = raw_data or {}

        # Step 1: 使用 ProblemClassifier 分类问题
        problem_record = self.classifier.classify(problem_message, raw_data)

        # Step 2: 构建依赖链
        module_name = problem_record.module_name or raw_data.get("source", "unknown")
        dep_chain = self.build_dependency_chain(module_name, problem_record)

        # Step 3: 分析根本原因
        root_cause = self._analyze_root_cause(problem_record, dep_chain)

        # Step 4: 获取修复建议
        fix_suggestions = self.get_fix_suggestion(root_cause, problem_record)

        # Step 5: 确定原因类别
        category = self._categorize_root_cause(root_cause, problem_record)

        return RootCauseResult(
            root_cause=root_cause,
            cause_chain=dep_chain,
            affected_modules=self._get_affected_modules(dep_chain, problem_record),
            category=category,
            fix_suggestions=fix_suggestions,
            problem_record=problem_record,
        )

    def build_dependency_chain(
        self,
        start_module: str,
        problem_record: Optional[ProblemRecord] = None
    ) -> list[CauseNode]:
        """
        基于模块依赖关系构建原因链
        
        分析从问题模块出发，沿着依赖链向上追溯可能的根本原因。
        
        Args:
            start_module: 起始模块名
            problem_record: 问题记录（可选）
            
        Returns:
            list[CauseNode]: 原因链
        """
        chain: list[CauseNode] = []
        visited: set[str] = set()

        current_module = start_module
        max_depth = 10

        for _ in range(max_depth):
            if current_module in visited:
                break
            visited.add(current_module)

            # 获取依赖关系
            deps = self._get_dependencies(current_module)

            if not deps:
                # 没有更多依赖，当前可能是源头
                chain.append(CauseNode(
                    module=current_module,
                    cause_type="leaf_module",
                    description=f"模块 {current_module} 无上游依赖，可能是根因",
                    confidence=0.7,
                    evidence=[f"在依赖链末端，无进一步上游依赖"],
                ))
                break

            # 分析依赖模块的状态
            dep_analysis = self._analyze_dependency(current_module, deps, problem_record)

            chain.append(dep_analysis)

            # 如果发现依赖模块有问题，继续追溯
            if dep_analysis.confidence < 0.5:
                # 选择第一个依赖继续追溯
                current_module = deps[0] if deps else current_module
            else:
                # 当前模块是根因
                break

        return chain

    def classify_root_cause(
        self,
        problem_message: str,
        raw_data: Optional[dict[str, Any]] = None
    ) -> RootCauseResult:
        """
        与 ProblemClassifier 集成的根因分类
        
        完整流程：问题分类 -> 依赖分析 -> 根因确定 -> 修复建议
        
        Args:
            problem_message: 问题消息
            raw_data: 原始数据
            
        Returns:
            RootCauseResult: 完整的根因分析结果
        """
        return self.trace_cause(problem_message, raw_data)

    def get_fix_suggestion(
        self,
        root_cause: CauseNode,
        problem_record: Optional[ProblemRecord] = None
    ) -> list[str]:
        """
        生成修复建议
        
        根据根本原因和问题类型生成具体的修复建议。
        
        Args:
            root_cause: 根本原因节点
            problem_record: 问题记录
            
        Returns:
            list[str]: 修复建议列表
        """
        suggestions: list[str] = []

        # 基于原因类型生成建议
        cause_type = root_cause.cause_type
        module = root_cause.module

        if "config" in cause_type.lower() or "configuration" in root_cause.description.lower():
            suggestions.extend([
                f"1. 检查 {module} 模块的配置文件是否完整",
                "2. 确认所有必需的环境变量已设置",
                "3. 验证配置文件的语法和格式",
                "4. 参照 docs/config-template.yaml 检查必需字段",
            ])

        elif "dependency" in cause_type.lower() or "cascade" in cause_type.lower():
            suggestions.extend([
                f"1. 检查 {module} 模块的上游依赖是否正常",
                "2. 查看依赖模块的日志定位具体故障点",
                "3. 确认依赖模块的版本兼容性",
                "4. 考虑实现熔断机制防止级联故障",
            ])

        elif "resource" in cause_type.lower() or "memory" in root_cause.description.lower():
            suggestions.extend([
                "1. 检查系统资源使用情况（内存、CPU、磁盘）",
                f"2. 分析 {module} 模块是否存在内存泄漏",
                "3. 考虑增加资源限制或扩容",
                "4. 查看是否有异常的资源消耗行为",
            ])

        elif "init" in cause_type.lower() or "initialization" in cause_type.lower():
            suggestions.extend([
                f"1. 检查 {module} 模块的初始化顺序",
                "2. 确认必需的前置条件已满足",
                "3. 查看启动日志中的早期错误信息",
                "4. 验证依赖服务的可用性",
            ])

        elif "external" in cause_type.lower() or "timeout" in cause_type.lower():
            suggestions.extend([
                "1. 检查外部服务的可用性和响应时间",
                "2. 验证网络连接和防火墙配置",
                "3. 考虑增加超时阈值或实现重试机制",
                "4. 检查是否有服务降级策略",
            ])

        else:
            # 通用建议
            suggestions.extend([
                f"1. 检查 {module} 模块的运行状态和日志",
                "2. 确认模块配置正确且完整",
                "3. 验证所有依赖服务的可用性",
                "4. 如有必要，重启相关服务",
            ])

        # 如果有 ProblemRecord，添加基于问题类型的建议
        if problem_record:
            if problem_record.recovery_hint:
                suggestions.insert(0, f"📌 优先检查: {problem_record.recovery_hint}")

            if problem_record.severity == Severity.CRITICAL:
                suggestions.insert(0, "🚨 严重问题: 建议立即处理")

        return suggestions

    def _load_dependency_map(self) -> dict[str, list[str]]:
        """加载依赖关系图"""
        if self._dependency_cache is not None:
            return self._dependency_cache

        # 尝试从 module_map.json 加载
        module_map_path = self.project_root / "introspection" / "module_map.json"
        if module_map_path.exists():
            try:
                with open(module_map_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 转换为 from_module -> [to_modules] 的格式
                    deps: dict[str, list[str]] = {}
                    for item in data.get("dependencies", []):
                        from_mod = item.get("from", "")
                        to_mod = item.get("to", "")
                        if from_mod and to_mod:
                            deps.setdefault(from_mod, []).append(to_mod)
                    self._dependency_cache = deps
                    return deps
            except Exception:
                pass

        # 回退：从 dependency_graph.py 构建简单映射
        return self._build_simple_dependency_map()

    def _build_simple_dependency_map(self) -> dict[str, list[str]]:
        """构建简单的依赖映射"""
        deps: dict[str, list[str]] = {
            "gateway": ["config", "agent", "memory"],
            "agent": ["memory", "pipeline"],
            "memory": ["health"],
            "health": [],
            "config": [],
            "pipeline": ["memory"],
            "introspection": ["gateway", "memory"],
        }
        return deps

    def _get_dependencies(self, module: str) -> list[str]:
        """获取模块的依赖列表"""
        dep_map = self._load_dependency_map()
        return dep_map.get(module, [])

    def _get_dependents(self, module: str) -> list[str]:
        """获取依赖该模块的模块列表"""
        dep_map = self._load_dependency_map()
        dependents: list[str] = []
        for from_mod, to_mods in dep_map.items():
            if module in to_mods:
                dependents.append(from_mod)
        return dependents

    def _analyze_dependency(
        self,
        module: str,
        dependencies: list[str],
        problem_record: Optional[ProblemRecord] = None
    ) -> CauseNode:
        """分析依赖关系"""
        if not dependencies:
            return CauseNode(
                module=module,
                cause_type="unknown",
                description=f"无法确定 {module} 的依赖关系",
                confidence=0.3,
            )

        # 检查是否有已知的问题模式
        problem_type = problem_record.problem_type if problem_record else None

        if problem_type == ProblemType.CRASH:
            # 崩溃通常从依赖模块传导
            primary_dep = dependencies[0]
            return CauseNode(
                module=module,
                cause_type="cascade_triggered",
                description=f"模块 {module} 依赖的 {primary_dep} 可能已崩溃",
                confidence=0.6,
                evidence=[f"依赖链: {module} -> {primary_dep}", "检测到崩溃信号"],
            )

        elif problem_type == ProblemType.TIMEOUT:
            return CauseNode(
                module=module,
                cause_type="upstream_timeout",
                description=f"上游依赖响应超时",
                confidence=0.7,
                evidence=[f"依赖: {', '.join(dependencies)}", "检测到超时"],
            )

        elif problem_type == ProblemType.MEMORY:
            return CauseNode(
                module=module,
                cause_type="resource_pressure",
                description=f"资源压力可能来自依赖模块",
                confidence=0.5,
                evidence=[f"依赖: {', '.join(dependencies)}", "内存问题检测"],
            )

        # 默认分析
        return CauseNode(
            module=module,
            cause_type="dependency_chain",
            description=f"模块 {module} 的上游依赖需要检查",
            confidence=0.5,
            evidence=[f"依赖链: {module} -> {', '.join(dependencies)}"],
        )

    def _analyze_root_cause(
        self,
        problem_record: ProblemRecord,
        cause_chain: list[CauseNode]
    ) -> CauseNode:
        """分析根本原因"""
        module = problem_record.module_name or "unknown"

        # 基于问题类型和严重程度确定根因
        if problem_record.severity == Severity.CRITICAL:
            if problem_record.problem_type == ProblemType.CRASH:
                # 崩溃通常有明确的根因
                if cause_chain:
                    return cause_chain[-1]
                return CauseNode(
                    module=module,
                    cause_type="critical_failure",
                    description="检测到系统崩溃，需要立即调查",
                    confidence=0.9,
                    evidence=["严重级别: CRITICAL", f"问题类型: {problem_record.problem_type.name}"],
                )

        # 从原因链中找到置信度最低的节点作为根因
        if cause_chain:
            # 根因应该是链的末端（最上游）
            root_candidate = cause_chain[-1]
            return CauseNode(
                module=root_candidate.module,
                cause_type=root_candidate.cause_type,
                description=root_candidate.description,
                confidence=min(root_candidate.confidence + 0.1, 1.0),
                evidence=root_candidate.evidence + [
                    f"问题类型: {problem_record.problem_type.name}",
                    f"严重程度: {problem_record.severity.name}",
                ],
            )

        # 没有原因链时的默认处理
        return CauseNode(
            module=module,
            cause_type="undetermined",
            description="无法自动确定根本原因，需要人工调查",
            confidence=0.2,
            evidence=[f"问题: {problem_record.message}"],
        )

    def _categorize_root_cause(
        self,
        root_cause: CauseNode,
        problem_record: ProblemRecord
    ) -> RootCauseCategory:
        """对根因进行分类"""
        cause_type = root_cause.cause_type.lower()
        description = root_cause.description.lower()
        problem_type = problem_record.problem_type

        if "config" in cause_type or "config" in description:
            return RootCauseCategory.CONFIGURATION

        if problem_type == ProblemType.CRASH and len(root_cause.evidence) > 2:
            return RootCauseCategory.CASCADE_FAILURE

        if "cascade" in cause_type:
            return RootCauseCategory.CASCADE_FAILURE

        if problem_type == ProblemType.TIMEOUT:
            return RootCauseCategory.EXTERNAL_SERVICE

        if problem_type == ProblemType.MEMORY:
            return RootCauseCategory.RESOURCE_EXHAUSTION

        if "init" in cause_type:
            return RootCauseCategory.INITIALIZATION

        if "depend" in cause_type:
            return RootCauseCategory.DEPENDENCY_FAILURE

        return RootCauseCategory.UNKNOWN

    def _get_affected_modules(
        self,
        cause_chain: list[CauseNode],
        problem_record: ProblemRecord
    ) -> list[str]:
        """获取受影响的模块列表"""
        modules: set[str] = set()

        # 从原因链中提取
        for node in cause_chain:
            modules.add(node.module)

        # 从问题记录中提取
        if problem_record.scope == Scope.MULTI_MODULE:
            modules.add(problem_record.module_name or "")

        return sorted(modules)

    def analyze_problem_record(self, record: ProblemRecord) -> RootCauseResult:
        """
        直接分析 ProblemRecord 的便捷方法
        
        Args:
            record: 问题记录
            
        Returns:
            RootCauseResult: 根因分析结果
        """
        return self.trace_cause(record.message, record.raw_data)
