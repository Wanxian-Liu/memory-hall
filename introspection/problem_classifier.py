"""
问题分类引擎 - M3.2: 基于日志分析器和状态探针的问题分类
=========================================================

集成日志分析器 (log_analyzer.py) 和状态探针 (status_probes.py)，
实现多维度问题分类：

1. 问题类型分类 (ProblemType):
   - PromptDelivery: prompt传递问题
   - TrustGate: 信任门未过
   - ToolRuntime: 工具执行问题
   - Compile: 编译问题
   - Test: 测试失败
   - Infra: 基础设施问题
   - Timeout: 超时问题
   - Crash: 崩溃问题

2. 严重程度 (Severity):
   - CRITICAL: 系统级严重故障
   - ERROR: 模块级错误
   - WARNING: 警告/降级
   - INFO: 信息性

3. 影响范围 (ImpactScope):
   - SINGLE_MODULE: 单模块影响
   - MULTI_MODULE: 多模块影响
   - SYSTEM_LEVEL: 系统级影响

参考设计:
- claw-code LaneFailureClass: 问题类型映射
- LogAnalyzer: 日志解析与模式匹配
- ProbeRegistry: 模块状态探针

使用方式:
    from introspection.problem_classifier import (
        ProblemClassifier, ProblemType, Severity, ImpactScope,
        ClassifiedProblem, ClassificationReport
    )

    classifier = ProblemClassifier()
    report = classifier.classify_from_analyzer(analyzer)
    problems = classifier.classify_problem(
        message="exec failed: timeout",
        module_id="gateway.gateway"
    )
"""

from __future__ import annotations

import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# 问题类型枚举 (ProblemType)
# ---------------------------------------------------------------------------

class ProblemType(Enum):
    """
    问题类型分类（参考 claw-code LaneFailureClass）

    - PromptDelivery: prompt 传递问题
    - TrustGate: 信任门未过
    - ToolRuntime: 工具执行问题
    - Compile: 编译问题
    - Test: 测试失败
    - Infra: 基础设施问题
    - Timeout: 执行超时
    - Crash: 崩溃
    - Unknown: 未知
    """
    # Agent Core 问题
    PromptDelivery = "prompt_delivery"      # prompt 传递问题
    TrustGate = "trust_gate"                # 信任门未过
    ToolRuntime = "tool_runtime"            # 工具执行问题
    Compile = "compile"                     # 编译问题
    Test = "test"                          # 测试失败
    Infra = "infra"                         # 基础设施问题

    # 执行问题
    Timeout = "timeout"                    # 超时问题
    Crash = "crash"                        # 崩溃
    ExecutionFailure = "execution_failure"  # 执行失败

    # 资源问题
    ResourceExhausted = "resource_exhausted"  # 资源耗尽
    MemoryLeak = "memory_leak"              # 内存泄漏

    # 网络问题
    NetworkTimeout = "network_timeout"       # 网络超时
    ConnectionRefused = "connection_refused"  # 连接拒绝

    # 配置/依赖问题
    ConfigError = "config_error"             # 配置错误
    MissingDependency = "missing_dependency"  # 依赖缺失

    # 健康/稳定性
    HealthDegraded = "health_degraded"       # 健康降级
    CircuitBreaker = "circuit_breaker"        # 断路器打开

    # 未知
    Unknown = "unknown"


# ---------------------------------------------------------------------------
# 严重程度枚举 (Severity)
# ---------------------------------------------------------------------------

class Severity(Enum):
    """问题严重程度"""
    CRITICAL = "critical"  # 系统级严重故障
    ERROR = "error"        # 模块级错误
    WARNING = "warning"     # 警告/降级
    INFO = "info"          # 信息性


# ---------------------------------------------------------------------------
# 影响范围枚举 (ImpactScope)
# ---------------------------------------------------------------------------

class ImpactScope(Enum):
    """问题影响范围"""
    SINGLE_MODULE = "single_module"   # 单模块影响
    MULTI_MODULE = "multi_module"     # 多模块影响
    SYSTEM_LEVEL = "system_level"     # 系统级影响


# ---------------------------------------------------------------------------
# 分类结果
# ---------------------------------------------------------------------------

@dataclass
class ClassifiedProblem:
    """
    分类后的问题。

    包含问题的多维度分类结果。
    """
    # 问题标识
    problem_id: str
    original_message: str

    # 三维度分类
    problem_type: ProblemType
    severity: Severity
    impact_scope: ImpactScope

    # 关联信息
    module_id: Optional[str] = None
    timestamp: Optional[str] = None

    # 附加信息
    category_tag: Optional[str] = None  # 来自 log_analyzer 的错误分类
    matched_patterns: List[str] = field(default_factory=list)  # 匹配的模式 ID
    related_modules: List[str] = field(default_factory=list)  # 关联的其他模块
    stack_trace: Optional[str] = None
    count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "original_message": self.original_message,
            "problem_type": self.problem_type.value,
            "severity": self.severity.value,
            "impact_scope": self.impact_scope.value,
            "module_id": self.module_id,
            "timestamp": self.timestamp,
            "category_tag": self.category_tag,
            "matched_patterns": self.matched_patterns,
            "related_modules": self.related_modules,
            "count": self.count,
        }


@dataclass
class ClassificationReport:
    """
    分类报告。

    汇总所有问题的分类统计。
    """
    generated_at: str
    time_window: str

    # 总体统计
    total_problems: int
    unique_problems: int

    # 按维度统计
    by_type: Dict[str, int]
    by_severity: Dict[str, int]
    by_impact_scope: Dict[str, int]
    by_module: Dict[str, int]

    # 分类的问题列表
    problems: List[ClassifiedProblem]

    # 严重问题
    critical_problems: List[ClassifiedProblem]
    error_problems: List[ClassifiedProblem]
    warning_problems: List[ClassifiedProblem]

    # 影响范围统计
    system_level_problems: List[ClassifiedProblem]
    multi_module_problems: List[ClassifiedProblem]
    single_module_problems: List[ClassifiedProblem]

    # 建议
    recommendations: List[str]


# ---------------------------------------------------------------------------
# 分类规则定义
# ---------------------------------------------------------------------------

@dataclass
class ClassificationRule:
    """
    分类规则。

    定义如何将错误模式映射到问题类型、严重程度和影响范围。
    """
    rule_id: str
    patterns: List[str]  # 正则表达式列表
    problem_type: ProblemType
    severity: Severity
    impact_scope: ImpactScope
    description: str


# 内置分类规则（参考 claw-code LaneFailureClass）
BUILTIN_CLASSIFICATION_RULES: List[ClassificationRule] = [
    # ===== PromptDelivery - prompt 传递问题 =====
    ClassificationRule(
        rule_id="prompt_delivery_timeout",
        patterns=[
            r"prompt.*timeout|prompt.*超时",
            r"prompt.*delivery.*fail",
            r"send.*prompt.*fail",
            r"llm.*timeout.*prompt",
        ],
        problem_type=ProblemType.PromptDelivery,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="Prompt 传递超时"
    ),
    ClassificationRule(
        rule_id="prompt_delivery_error",
        patterns=[
            r"prompt.*reject|prompt.*拒绝",
            r"prompt.*filter.*block",
            r"content.*filter.*block",
        ],
        problem_type=ProblemType.PromptDelivery,
        severity=Severity.WARNING,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="Prompt 被过滤或拒绝"
    ),

    # ===== TrustGate - 信任门未过 =====
    ClassificationRule(
        rule_id="trust_gate_denied",
        patterns=[
            r"trust.*gate.*deny|trust.*gate.*拒绝",
            r"permission.*denied|权限不足",
            r"access.*denied|访问被拒绝",
            r"not.*trusted",
            r"auth.*fail|认证失败",
            r"unauthorized",
        ],
        problem_type=ProblemType.TrustGate,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="信任门验证失败"
    ),
    ClassificationRule(
        rule_id="trust_gate_timeout",
        patterns=[
            r"trust.*gate.*timeout",
            r"auth.*timeout|认证超时",
        ],
        problem_type=ProblemType.TrustGate,
        severity=Severity.WARNING,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="信任门验证超时"
    ),

    # ===== ToolRuntime - 工具执行问题 =====
    ClassificationRule(
        rule_id="tool_runtime_failed",
        patterns=[
            r"tool.*failed|工具.*失败",
            r"tool.*error|工具.*错误",
            r"exec.*tool.*fail",
            r"run.*tool.*error",
            r"invoke.*fail|调用.*失败",
        ],
        problem_type=ProblemType.ToolRuntime,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="工具执行失败"
    ),
    ClassificationRule(
        rule_id="tool_runtime_not_found",
        patterns=[
            r"tool.*not.*found|工具.*未找到",
            r"tool.*missing|工具.*缺失",
            r"unknown.*tool",
            r"no.*tool.*named",
        ],
        problem_type=ProblemType.ToolRuntime,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="工具不存在"
    ),
    ClassificationRule(
        rule_id="sessions_spawn_failed",
        patterns=[
            r"sessions_spawn.*timeout",
            r"sessions_spawn.*fail",
            r"subagent.*fail.*spawn",
            r"agent.*spawn.*error",
        ],
        problem_type=ProblemType.ToolRuntime,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.MULTI_MODULE,
        description="子代理启动失败"
    ),

    # ===== Compile - 编译问题 =====
    ClassificationRule(
        rule_id="compile_error",
        patterns=[
            r"compile.*error|编译.*错误",
            r"syntax.*error|语法错误",
            r"parse.*error|解析错误",
            r"ast.*error",
        ],
        problem_type=ProblemType.Compile,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="编译错误"
    ),
    ClassificationRule(
        rule_id="compile_timeout",
        patterns=[
            r"compile.*timeout|编译超时",
            r"build.*timeout|构建超时",
        ],
        problem_type=ProblemType.Compile,
        severity=Severity.WARNING,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="编译超时"
    ),

    # ===== Test - 测试失败 =====
    ClassificationRule(
        rule_id="test_failed",
        patterns=[
            r"test.*fail|测试.*失败",
            r"assertion.*fail|断言失败",
            r"unittest.*fail",
            r"pytest.*fail",
            r"test.*error",
        ],
        problem_type=ProblemType.Test,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="测试失败"
    ),
    ClassificationRule(
        rule_id="test_timeout",
        patterns=[
            r"test.*timeout|测试超时",
            r"test.*hang|测试挂起",
        ],
        problem_type=ProblemType.Test,
        severity=Severity.WARNING,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="测试超时"
    ),

    # ===== Infra - 基础设施问题 =====
    ClassificationRule(
        rule_id="infra_gateway",
        patterns=[
            r"gateway.*down|gateway.*宕机",
            r"gateway.*error|gateway.*错误",
            r"gateway.*timeout",
        ],
        problem_type=ProblemType.Infra,
        severity=Severity.CRITICAL,
        impact_scope=ImpactScope.SYSTEM_LEVEL,
        description="Gateway 基础设施故障"
    ),
    ClassificationRule(
        rule_id="infra_disk",
        patterns=[
            r"disk.*full|磁盘已满",
            r"no.*space.*left",
            r"disk.*error|磁盘错误",
        ],
        problem_type=ProblemType.Infra,
        severity=Severity.CRITICAL,
        impact_scope=ImpactScope.SYSTEM_LEVEL,
        description="磁盘空间不足"
    ),
    ClassificationRule(
        rule_id="infra_memory",
        patterns=[
            r"out.*of.*memory|OOM|内存不足",
            r"memory.*error|内存错误",
        ],
        problem_type=ProblemType.Infra,
        severity=Severity.CRITICAL,
        impact_scope=ImpactScope.SYSTEM_LEVEL,
        description="内存耗尽"
    ),
    ClassificationRule(
        rule_id="infra_network",
        patterns=[
            r"network.*error|网络错误",
            r"network.*unavailable|网络不可用",
            r"dns.*fail|DNS.*失败",
        ],
        problem_type=ProblemType.Infra,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SYSTEM_LEVEL,
        description="网络基础设施故障"
    ),

    # ===== Timeout - 超时问题 =====
    ClassificationRule(
        rule_id="timeout_exec",
        patterns=[
            r"exec.*timeout|执行超时",
            r"command.*timeout|命令超时",
            r"process.*timeout|进程超时",
        ],
        problem_type=ProblemType.Timeout,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="执行超时"
    ),
    ClassificationRule(
        rule_id="timeout_gateway",
        patterns=[
            r"gateway.*timeout|gateway.*超时",
            r"http.*timeout|HTTP.*超时",
        ],
        problem_type=ProblemType.Timeout,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.MULTI_MODULE,
        description="网关超时"
    ),
    ClassificationRule(
        rule_id="timeout_web_fetch",
        patterns=[
            r"fetch.*timeout|抓取超时",
            r"web.*fetch.*timeout",
            r"blocked.*private.*IP",
        ],
        problem_type=ProblemType.Timeout,
        severity=Severity.WARNING,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="Web 抓取超时"
    ),

    # ===== Crash - 崩溃问题 =====
    ClassificationRule(
        rule_id="crash_exception",
        patterns=[
            r"uncaught.*exception|未捕获异常",
            r"fatal.*error|致命错误",
            r"segmentation.*fault",
            r"core.*dumped",
        ],
        problem_type=ProblemType.Crash,
        severity=Severity.CRITICAL,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="进程崩溃"
    ),
    ClassificationRule(
        rule_id="crash_panic",
        patterns=[
            r"panic|panic.*recover",
            r"assertion.*panic",
        ],
        problem_type=ProblemType.Crash,
        severity=Severity.CRITICAL,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="Panic 崩溃"
    ),

    # ===== ExecutionFailure - 执行失败 =====
    ClassificationRule(
        rule_id="exec_failed",
        patterns=[
            r"exec.*failed|执行失败",
            r"execution.*failed",
            r"run.*failed|运行失败",
        ],
        problem_type=ProblemType.ExecutionFailure,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="执行失败"
    ),
    ClassificationRule(
        rule_id="exec_preflight",
        patterns=[
            r"preflight.*complex.*interpreter",
            r"exec.*preflight.*deny",
        ],
        problem_type=ProblemType.ExecutionFailure,
        severity=Severity.WARNING,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="Preflight 检查拒绝"
    ),

    # ===== ResourceExhausted - 资源耗尽 =====
    ClassificationRule(
        rule_id="resource_cpu",
        patterns=[
            r"cpu.*100%|CPU.*100%",
            r"cpu.*exhausted|CPU.*耗尽",
            r"too.*many.*process",
        ],
        problem_type=ProblemType.ResourceExhausted,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SYSTEM_LEVEL,
        description="CPU 资源耗尽"
    ),

    # ===== MissingDependency - 依赖缺失 =====
    ClassificationRule(
        rule_id="missing_module",
        patterns=[
            r"ModuleNotFoundError|No.*module.*named|找不到模块",
            r"import.*error|导入错误",
            r"cannot.*import",
        ],
        problem_type=ProblemType.MissingDependency,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="模块未找到"
    ),
    ClassificationRule(
        rule_id="missing_config",
        patterns=[
            r"missing.*config|缺少配置",
            r"config.*not.*found|配置未找到",
            r"no.*config.*file",
        ],
        problem_type=ProblemType.MissingDependency,
        severity=Severity.ERROR,
        impact_scope=ImpactScope.SINGLE_MODULE,
        description="配置缺失"
    ),

    # ===== HealthDegraded - 健康降级 =====
    ClassificationRule(
        rule_id="health_check_fail",
        patterns=[
            r"health.*check.*fail|健康检查失败",
            r"health.*degraded|健康状态降级",
            r"unhealthy",
        ],
        problem_type=ProblemType.HealthDegraded,
        severity=Severity.WARNING,
        impact_scope=ImpactScope.MULTI_MODULE,
        description="健康检查失败"
    ),
    ClassificationRule(
        rule_id="circuit_breaker_open",
        patterns=[
            r"circuit.*breaker.*open|断路器打开",
            r"circuit.*breaker.*trip",
        ],
        problem_type=ProblemType.CircuitBreaker,
        severity=Severity.WARNING,
        impact_scope=ImpactScope.MULTI_MODULE,
        description="断路器打开"
    ),
]


# ---------------------------------------------------------------------------
# 问题分类引擎
# ---------------------------------------------------------------------------

class ProblemClassifier:
    """
    线程安全的问题分类引擎。

    功能：
    - 基于规则的问题分类
    - 集成日志分析器的模式匹配结果
    - 集成状态探针的模块状态
    - 生成多维度分类报告

    使用方式:
        # 方式1: 直接分类单条消息
        classifier = ProblemClassifier()
        problem = classifier.classify_problem(
            message="exec failed: timeout",
            module_id="gateway.gateway"
        )

        # 方式2: 从日志分析器生成报告
        from introspection.log_analyzer import get_analyzer
        analyzer = get_analyzer()
        report = classifier.classify_from_analyzer(analyzer)

        # 方式3: 从状态探针获取问题
        from introspection.status_probes import get_probes
        probes = get_probes()
        report = classifier.classify_from_probes(probes)
    """

    def __init__(
        self,
        rules: Optional[List[ClassificationRule]] = None,
    ):
        """
        初始化分类器。

        Args:
            rules: 自定义分类规则（None 则使用内置规则）
        """
        self._lock = threading.RLock()

        # 分类规则
        self._rules: Dict[str, ClassificationRule] = {}
        for rule in (rules or BUILTIN_CLASSIFICATION_RULES):
            self._rules[rule.rule_id] = rule

        # 编译正则表达式以提高性能
        self._compiled_patterns: List[Tuple[str, re.Pattern]] = []
        self._rebuild_pattern_cache()

        # 统计
        self._classification_counts: Dict[str, int] = defaultdict(int)

    def _rebuild_pattern_cache(self) -> None:
        """重新编译所有正则表达式模式"""
        with self._lock:
            self._compiled_patterns.clear()
            for rule_id, rule in self._rules.items():
                for pattern in rule.patterns:
                    try:
                        compiled = re.compile(pattern, re.IGNORECASE)
                        self._compiled_patterns.append((rule_id, compiled))
                    except re.error:
                        pass  # 忽略无效的正则

    # -------------------------------------------------------------------------
    # 规则管理
    # -------------------------------------------------------------------------

    def add_rule(self, rule: ClassificationRule) -> None:
        """添加分类规则"""
        with self._lock:
            self._rules[rule.rule_id] = rule
            self._rebuild_pattern_cache()

    def remove_rule(self, rule_id: str) -> None:
        """移除分类规则"""
        with self._lock:
            self._rules.pop(rule_id, None)
            self._rebuild_pattern_cache()

    def get_rules(self) -> Dict[str, ClassificationRule]:
        """获取所有分类规则"""
        with self._lock:
            return dict(self._rules)

    # -------------------------------------------------------------------------
    # 核心分类逻辑
    # -------------------------------------------------------------------------

    def classify_problem(
        self,
        message: str,
        module_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        category_tag: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> ClassifiedProblem:
        """
        分类单个问题。

        Args:
            message: 问题消息/错误文本
            module_id: 关联的模块 ID
            timestamp: 问题发生时间
            category_tag: 来自 log_analyzer 的错误分类标签
            stack_trace: 堆栈跟踪（如果有）

        Returns:
            ClassifiedProblem: 分类结果
        """
        if not message:
            return self._create_unknown_problem(
                message="<empty>",
                module_id=module_id,
                timestamp=timestamp,
            )

        # 匹配规则
        matched_rules: List[Tuple[ClassificationRule, str]] = []
        with self._lock:
            patterns = list(self._compiled_patterns)

        for rule_id, compiled_pattern in patterns:
            if compiled_pattern.search(message):
                rule = self._rules[rule_id]
                matched_rules.append((rule, rule_id))
                # 更新统计
                with self._lock:
                    self._classification_counts[rule_id] += 1

        # 选择最匹配的规则（优先顺序：CRITICAL > ERROR > WARNING > INFO）
        if matched_rules:
            # 按严重程度排序
            severity_order = {
                Severity.CRITICAL: 0,
                Severity.ERROR: 1,
                Severity.WARNING: 2,
                Severity.INFO: 3,
            }
            matched_rules.sort(key=lambda x: severity_order.get(x[0].severity, 99))

            best_rule = matched_rules[0][0]
            matched_rule_ids = [r[1] for r in matched_rules]

            # 根据 category_tag 调整影响范围
            impact_scope = self._determine_impact_scope(
                best_rule.impact_scope,
                module_id,
                category_tag,
            )

            return ClassifiedProblem(
                problem_id=self._generate_problem_id(message, module_id),
                original_message=message,
                problem_type=best_rule.problem_type,
                severity=best_rule.severity,
                impact_scope=impact_scope,
                module_id=module_id,
                timestamp=timestamp or datetime.now().isoformat(),
                category_tag=category_tag,
                matched_patterns=matched_rule_ids,
                stack_trace=stack_trace,
            )

        # 无法分类，标记为 Unknown
        return self._create_unknown_problem(
            message=message,
            module_id=module_id,
            timestamp=timestamp,
        )

    def _create_unknown_problem(
        self,
        message: str,
        module_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> ClassifiedProblem:
        """创建 Unknown 类型的分类结果"""
        return ClassifiedProblem(
            problem_id=self._generate_problem_id(message, module_id),
            original_message=message,
            problem_type=ProblemType.Unknown,
            severity=Severity.INFO,
            impact_scope=ImpactScope.SINGLE_MODULE,
            module_id=module_id,
            timestamp=timestamp or datetime.now().isoformat(),
        )

    def _determine_impact_scope(
        self,
        base_scope: ImpactScope,
        module_id: Optional[str],
        category_tag: Optional[str],
    ) -> ImpactScope:
        """
        根据上下文信息调整影响范围。

        Args:
            base_scope: 规则定义的基础影响范围
            module_id: 关联的模块 ID
            category_tag: 错误分类标签

        Returns:
            ImpactScope: 调整后的影响范围
        """
        # 如果是核心基础设施模块，影响范围扩大
        if module_id:
            infra_modules = {
                "gateway.gateway",
                "introspection.status_probes",
                "introspection.log_analyzer",
                "health.health_check",
            }
            if module_id in infra_modules:
                return ImpactScope.SYSTEM_LEVEL

        # 如果是跨模块错误标记
        if category_tag:
            cross_module_tags = {
                "network_timeout",
                "circuit_breaker_open",
                "health_degraded",
            }
            if category_tag in cross_module_tags:
                return ImpactScope.MULTI_MODULE

        return base_scope

    def _generate_problem_id(
        self,
        message: str,
        module_id: Optional[str],
    ) -> str:
        """生成唯一的问题 ID"""
        # 使用消息的前50字符的哈希
        msg_hash = hash(message[:50]) % 100000
        timestamp = datetime.now().strftime("%m%d%H%M%S")
        module_part = module_id.split(".")[-1] if module_id else "unknown"
        return f"prob_{module_part}_{timestamp}_{msg_hash}"

    # -------------------------------------------------------------------------
    # 批量分类
    # -------------------------------------------------------------------------

    def classify_batch(
        self,
        entries: List[Dict[str, Any]],
    ) -> List[ClassifiedProblem]:
        """
        批量分类问题。

        Args:
            entries: 问题条目列表，每项包含:
                - message: 问题消息
                - module_id (可选): 模块 ID
                - timestamp (可选): 时间戳
                - category_tag (可选): 错误分类标签

        Returns:
            List[ClassifiedProblem]: 分类结果列表
        """
        results = []
        for entry in entries:
            problem = self.classify_problem(
                message=entry.get("message", ""),
                module_id=entry.get("module_id"),
                timestamp=entry.get("timestamp"),
                category_tag=entry.get("category_tag"),
                stack_trace=entry.get("stack_trace"),
            )
            results.append(problem)
        return results

    # -------------------------------------------------------------------------
    # 与日志分析器集成
    # -------------------------------------------------------------------------

    def classify_from_analyzer(
        self,
        analyzer,  # LogAnalyzer
        time_window_hours: int = 24,
    ) -> ClassificationReport:
        """
        从日志分析器生成分类报告。

        Args:
            analyzer: LogAnalyzer 实例
            time_window_hours: 分析的时间窗口

        Returns:
            ClassificationReport: 分类报告
        """
        # 获取错误条目
        error_entries = analyzer.get_entries(error_only=True, limit=1000)

        # 批量分类
        entries = []
        for entry in error_entries:
            entries.append({
                "message": entry.message,
                "module_id": entry.module,
                "timestamp": entry.timestamp,
                "category_tag": entry.error_category,
                "stack_trace": entry.stack_trace,
            })

        classified = self.classify_batch(entries)

        # 生成报告
        return self._generate_report(
            problems=classified,
            time_window=f"{time_window_hours}h",
        )

    # -------------------------------------------------------------------------
    # 与状态探针集成
    # -------------------------------------------------------------------------

    def classify_from_probes(
        self,
        probes,  # ProbeRegistry
    ) -> ClassificationReport:
        """
        从状态探针生成分类报告。

        Args:
            probes: ProbeRegistry 实例

        Returns:
            ClassificationReport: 分类报告
        """
        all_probes = probes.all_probes()
        classified = []

        for module_id, probe in all_probes.items():
            # 只处理有问题的探针
            if probe.state.value in ("failed", "degraded", "unavailable"):
                problem = self.classify_problem(
                    message=probe.error or f"Module {module_id} in {probe.state.value} state",
                    module_id=module_id,
                    timestamp=probe.last_check,
                )
                classified.append(problem)

        return self._generate_report(
            problems=classified,
            time_window="current",
        )

    # -------------------------------------------------------------------------
    # 报告生成
    # -------------------------------------------------------------------------

    def _generate_report(
        self,
        problems: List[ClassifiedProblem],
        time_window: str,
    ) -> ClassificationReport:
        """生成分类报告"""
        # 按维度统计
        by_type: Dict[str, int] = defaultdict(int)
        by_severity: Dict[str, int] = defaultdict(int)
        by_impact_scope: Dict[str, int] = defaultdict(int)
        by_module: Dict[str, int] = defaultdict(int)

        for p in problems:
            by_type[p.problem_type.value] += 1
            by_severity[p.severity.value] += 1
            by_impact_scope[p.impact_scope.value] += 1
            if p.module_id:
                by_module[p.module_id] += 1

        # 按严重程度分组
        critical_problems = [p for p in problems if p.severity == Severity.CRITICAL]
        error_problems = [p for p in problems if p.severity == Severity.ERROR]
        warning_problems = [p for p in problems if p.severity == Severity.WARNING]

        # 按影响范围分组
        system_level_problems = [p for p in problems if p.impact_scope == ImpactScope.SYSTEM_LEVEL]
        multi_module_problems = [p for p in problems if p.impact_scope == ImpactScope.MULTI_MODULE]
        single_module_problems = [p for p in problems if p.impact_scope == ImpactScope.SINGLE_MODULE]

        # 生成建议
        recommendations = self._generate_recommendations(
            problems,
            by_severity,
            by_impact_scope,
        )

        return ClassificationReport(
            generated_at=datetime.now().isoformat(),
            time_window=time_window,
            total_problems=len(problems),
            unique_problems=len(set(p.problem_id for p in problems)),
            by_type=dict(by_type),
            by_severity=dict(by_severity),
            by_impact_scope=dict(by_impact_scope),
            by_module=dict(by_module),
            problems=problems,
            critical_problems=critical_problems,
            error_problems=error_problems,
            warning_problems=warning_problems,
            system_level_problems=system_level_problems,
            multi_module_problems=multi_module_problems,
            single_module_problems=single_module_problems,
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        problems: List[ClassifiedProblem],
        by_severity: Dict[str, int],
        by_impact_scope: Dict[str, int],
    ) -> List[str]:
        """基于分类结果生成建议"""
        recommendations = []

        # 系统级问题建议
        if by_impact_scope.get("system_level", 0) > 0:
            recommendations.append(
                "发现系统级基础设施问题 - 需要立即处理"
            )

        # 严重问题建议
        critical_count = by_severity.get("critical", 0)
        if critical_count > 0:
            recommendations.append(
                f"发现 {critical_count} 个严重问题 - 优先处理崩溃/资源耗尽"
            )

        # 特定问题类型建议
        infra_problems = [p for p in problems if p.problem_type == ProblemType.Infra]
        if infra_problems:
            infra_modules = set(p.module_id for p in infra_problems if p.module_id)
            recommendations.append(
                f"基础设施问题 ({len(infra_problems)}个): {', '.join(infra_modules)}"
            )

        tool_problems = [p for p in problems if p.problem_type == ProblemType.ToolRuntime]
        if tool_problems:
            recommendations.append(
                f"工具执行问题 ({len(tool_problems)}个) - 检查工具注册和调用"
            )

        timeout_problems = [p for p in problems if p.problem_type == ProblemType.Timeout]
        if timeout_problems:
            recommendations.append(
                f"超时问题 ({len(timeout_problems)}个) - 考虑增加超时阈值或优化性能"
            )

        # 无问题
        if not recommendations:
            recommendations.append("系统运行正常，未发现明显问题")

        return recommendations

    # -------------------------------------------------------------------------
    # 统计查询
    # -------------------------------------------------------------------------

    def get_classification_stats(self) -> Dict[str, Any]:
        """获取分类统计"""
        with self._lock:
            return {
                "total_rules": len(self._rules),
                "compiled_patterns": len(self._compiled_patterns),
                "classification_counts": dict(self._classification_counts),
            }

    # -------------------------------------------------------------------------
    # CLI 支持
    # -------------------------------------------------------------------------

    def classify_text(self, text: str) -> ClassificationReport:
        """
        分类文本中的问题（每行作为一个问题）。

        Args:
            text: 多行文本

        Returns:
            ClassificationReport: 分类报告
        """
        entries = []
        for line in text.splitlines():
            if line.strip():
                entries.append({"message": line.strip()})

        classified = self.classify_batch(entries)
        return self._generate_report(problems=classified, time_window="input")


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_classifier: Optional[ProblemClassifier] = None
_classifier_lock = threading.Lock()


def get_classifier() -> ProblemClassifier:
    """获取全局问题分类器（单例）"""
    global _classifier
    if _classifier is None:
        with _classifier_lock:
            if _classifier is None:
                _classifier = ProblemClassifier()
    return _classifier


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    """CLI 入口 - 演示问题分类"""
    classifier = get_classifier()

    # 测试用例
    test_cases = [
        ("exec failed: timeout", "gateway.gateway", "执行超时"),
        ("sessions_spawn timeout after 30000ms", "gateway.gateway", "子代理启动超时"),
        ("out of memory: OOM", "system", "内存不足"),
        ("health check failed: degraded", "introspection.status_probes", "健康检查失败"),
        ("Permission denied: trust gate", "auth.trust_gate", "信任门拒绝"),
        ("ModuleNotFoundError: No module named 'foo'", "plugins.foo", "模块未找到"),
    ]

    print("Problem Classification Results")
    print("=" * 70)
    for msg, mod, desc in test_cases:
        p = classifier.classify_problem(message=msg, module_id=mod)
        print(f"{p.problem_type.value:25} | {p.severity.value:10} | {p.impact_scope.value:15} | {desc}")
    print("=" * 70)


if __name__ == "__main__":
    main()
