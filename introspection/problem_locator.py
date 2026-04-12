"""
Mimir-Core 问题定位器
introspection/problem_locator.py

整合告警管理器、日志分析器、问题分类器、根因分析器，
基于告警/日志/探针数据定位问题，生成完整的问题报告。

设计原则：
- 事件驱动：接收告警/日志/探针数据作为输入
- 层级分析：告警 -> 问题分类 -> 日志分析 -> 根因追溯 -> 报告生成
- 模块协同：委托各模块完成专业分析，ProblemLocator 协调调度
- 可观测性：完整记录分析过程，便于复盘和优化

使用方式:
    from introspection.problem_locator import ProblemLocator, ProblemLocatorConfig

    locator = ProblemLocator()

    # 基于告警定位问题
    report = locator.locate(alerts=[alert_obj])

    # 基于日志定位问题
    report = locator.locate(log_text="error log content...")

    # 基于探针状态定位问题
    report = locator.locate(probe_states={"module_x": ProbeState.FAILED})

    # 混合模式
    report = locator.locate(alerts=[], log_text="...", probe_states={})
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

# 导入依赖模块
from .alert_manager import Alert, AlertChannel, AlertManager, AlertSeverity
from .log_analyzer import LogAnalyzer, LogEntry, LogLevel, ModuleErrorStats
from .problem_classifier import (
    ProblemClassifier,
    ProblemRecord,
    ProblemType,
    Scope,
    Severity as ProblemSeverity,
)
from .root_cause_analyzer import (
    CauseNode,
    RootCauseAnalyzer,
    RootCauseCategory,
    RootCauseResult,
)
from .status_probes import ModuleProbe, ProbeState


# ============================================================================
# 配置
# ============================================================================

class LocatorMode(Enum):
    """问题定位模式"""
    ALERT_ONLY = "alert_only"           # 仅基于告警
    LOG_HEAVY = "log_heavy"            # 日志密集型
    PROBE_AWARE = "probe_aware"        # 探针感知
    COMPREHENSIVE = "comprehensive"    # 综合分析（默认）


@dataclass
class ProblemLocatorConfig:
    """问题定位器配置"""
    mode: LocatorMode = LocatorMode.COMPREHENSIVE
    time_window_hours: int = 24        # 分析时间窗口（小时）
    log_analyzer_enabled: bool = True  # 启用日志分析
    root_cause_enabled: bool = True    # 启用根因分析
    alert_manager_enabled: bool = True # 启用告警管理
    max_cause_depth: int = 5           # 最大原因追溯深度
    confidence_threshold: float = 0.6  # 置信度阈值
    auto_resolve_threshold: float = 0.9  # 自动解决阈值
    report_format: str = "dict"        # 报告格式: dict, json, markdown


# ============================================================================
# 问题定位结果
# ============================================================================

@dataclass
class LocatedProblem:
    """定位到的问题"""
    problem_id: str
    alert: Optional[Alert] = None
    problem_record: Optional[ProblemRecord] = None
    root_cause_result: Optional[RootCauseResult] = None
    log_entries: List[LogEntry] = field(default_factory=list)
    related_probes: List[ModuleProbe] = field(default_factory=list)
    affected_modules: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    confidence: float = 0.0
    status: str = "located"  # located, analyzing, resolved, escalated

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "alert": self.alert.to_dict() if self.alert else None,
            "problem_record": self.problem_record.to_dict() if self.problem_record else None,
            "root_cause_result": self.root_cause_result.to_dict() if self.root_cause_result else None,
            "log_entries": [asdict(e) for e in self.log_entries],
            "related_probes": [asdict(p) for p in self.related_probes],
            "affected_modules": self.affected_modules,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "status": self.status,
        }


@dataclass
class ProblemReport:
    """问题定位报告"""
    report_id: str
    created_at: float = field(default_factory=time.time)
    config: Dict[str, Any] = field(default_factory=dict)
    located_problems: List[LocatedProblem] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "created_at": self.created_at,
            "created_at_iso": datetime.fromtimestamp(self.created_at).isoformat(),
            "config": self.config,
            "located_problems": [p.to_dict() for p in self.located_problems],
            "summary": self.summary,
            "recommendations": self.recommendations,
            "execution_time_ms": self.execution_time_ms,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_markdown(self) -> str:
        """生成 Markdown 格式报告"""
        lines = [
            f"# 问题定位报告",
            f"",
            f"**报告ID**: {self.report_id}",
            f"**生成时间**: {datetime.fromtimestamp(self.created_at).isoformat()}",
            f"**执行耗时**: {self.execution_time_ms:.2f}ms",
            f"",
            f"## 摘要",
            f"",
        ]

        if self.summary:
            lines.append(f"- 问题总数: {self.summary.get('total_problems', 0)}")
            lines.append(f"- 严重问题: {self.summary.get('critical_count', 0)}")
            lines.append(f"- 高置信度问题: {self.summary.get('high_confidence_count', 0)}")
            lines.append(f"- 影响模块数: {self.summary.get('affected_module_count', 0)}")
            lines.append("")

        lines.append("## 问题详情")
        lines.append("")

        for i, problem in enumerate(self.located_problems, 1):
            lines.append(f"### {i}. {problem.problem_id}")
            lines.append(f"")
            lines.append(f"- **状态**: {problem.status}")
            lines.append(f"- **置信度**: {problem.confidence:.2%}")
            lines.append(f"- **时间**: {datetime.fromtimestamp(problem.timestamp).isoformat()}")
            lines.append(f"- **影响模块**: {', '.join(problem.affected_modules) or '未知'}")

            if problem.problem_record:
                pr = problem.problem_record
                lines.append(f"- **问题类型**: {pr.problem_type.name}")
                lines.append(f"- **严重程度**: {pr.severity.name}")
                lines.append(f"- **消息**: {pr.message}")

            if problem.root_cause_result:
                rcr = problem.root_cause_result
                lines.append(f"- **根因类别**: {rcr.category.name}")
                lines.append(f"- **根因**: {rcr.root_cause.description}")
                if rcr.fix_suggestions:
                    lines.append(f"- **修复建议**:")
                    for suggestion in rcr.fix_suggestions:
                        lines.append(f"  - {suggestion}")

            lines.append("")

        if self.recommendations:
            lines.append("## 总体建议")
            lines.append("")
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)


# ============================================================================
# 问题定位器
# ============================================================================

class ProblemLocator:
    """
    问题定位器

    协调各模块，基于告警/日志/探针数据定位问题。
    """

    def __init__(
        self,
        config: Optional[ProblemLocatorConfig] = None,
        project_root: Optional[str] = None,
    ):
        self.config = config or ProblemLocatorConfig()
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent

        # 初始化子模块
        self._init_submodules()

        # 内部状态
        self._reports: Dict[str, ProblemReport] = {}
        self._problem_count = 0

    def _init_submodules(self) -> None:
        """初始化子模块"""
        # 日志分析器
        self.log_analyzer = LogAnalyzer(project_root=str(self.project_root)) if self.config.log_analyzer_enabled else None

        # 问题分类器
        self.problem_classifier = ProblemClassifier()

        # 根因分析器
        self.root_cause_analyzer = RootCauseAnalyzer(project_root=str(self.project_root)) if self.config.root_cause_enabled else None

        # 告警管理器
        self.alert_manager = AlertManager() if self.config.alert_manager_enabled else None

    def locate(
        self,
        alerts: Optional[List[Alert]] = None,
        log_text: Optional[str] = None,
        log_files: Optional[List[str]] = None,
        probe_states: Optional[Dict[str, ProbeState]] = None,
        raw_data: Optional[Dict[str, Any]] = None,
    ) -> ProblemReport:
        """
        基于输入数据定位问题

        Args:
            alerts: 告警列表
            log_text: 日志文本
            log_files: 日志文件路径列表
            probe_states: 探针状态字典
            raw_data: 原始数据

        Returns:
            ProblemReport: 问题定位报告
        """
        start_time = time.time()
        self._problem_count += 1
        report_id = f"report_{self._problem_count}_{int(start_time)}"

        # 创建报告
        report = ProblemReport(
            report_id=report_id,
            config=asdict(self.config),
        )

        # 确定输入类型
        has_alerts = bool(alerts)
        has_logs = bool(log_text or log_files)
        has_probes = bool(probe_states)

        # 根据模式决定分析策略
        if self.config.mode == LocatorMode.ALERT_ONLY:
            report.located_problems = self._locate_from_alerts(alerts or [])
        elif self.config.mode == LocatorMode.LOG_HEAVY:
            report.located_problems = self._locate_from_logs(log_text, log_files)
        elif self.config.mode == LocatorMode.PROBE_AWARE:
            report.located_problems = self._locate_from_probes(probe_states or {})
        else:  # COMPREHENSIVE
            report.located_problems = self._locate_comprehensive(
                alerts or [],
                log_text,
                log_files,
                probe_states or {},
                raw_data or {},
            )

        # 生成摘要
        report.summary = self._generate_summary(report.located_problems)

        # 生成建议
        report.recommendations = self._generate_recommendations(report.located_problems, report.summary)

        # 更新告警状态
        if self.alert_manager and alerts:
            for problem in report.located_problems:
                if problem.alert:
                    problem.alert.resolved = problem.status == "resolved"
                    self.alert_manager.update_alert(problem.alert)

        report.execution_time_ms = (time.time() - start_time) * 1000
        self._reports[report_id] = report

        return report

    def _locate_from_alerts(self, alerts: List[Alert]) -> List[LocatedProblem]:
        """仅基于告警定位问题"""
        problems: List[LocatedProblem] = []

        for alert in alerts:
            # 创建问题记录
            problem_record = self._alert_to_problem_record(alert)

            # 根因分析
            root_cause_result = None
            if self.root_cause_analyzer:
                root_cause_result = self.root_cause_analyzer.trace_cause(
                    problem_record.message,
                    asdict(problem_record),
                )

            # 构建 LocatedProblem
            problem = LocatedProblem(
                problem_id=f"problem_{alert.id}",
                alert=alert,
                problem_record=problem_record,
                root_cause_result=root_cause_result,
                affected_modules=self._get_affected_modules(root_cause_result, alert.module),
                confidence=self._calculate_confidence(alert.severity, root_cause_result),
            )
            problems.append(problem)

        return problems

    def _locate_from_logs(
        self,
        log_text: Optional[str],
        log_files: Optional[List[str]],
    ) -> List[LocatedProblem]:
        """基于日志定位问题"""
        problems: List[LocatedProblem] = []

        if not self.log_analyzer:
            return problems

        # 分析日志
        if log_text:
            log_entries = self.log_analyzer.analyze_text(log_text)
        elif log_files:
            log_entries = []
            for f in log_files:
                entries = self.log_analyzer.analyze_file(f)
                log_entries.extend(entries)
        else:
            return problems

        # 按错误类别分组
        error_groups: Dict[str, List[LogEntry]] = {}
        for entry in log_entries:
            if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL, LogLevel.EXCEPTION):
                category = entry.error_category or "unknown"
                if category not in error_groups:
                    error_groups[category] = []
                error_groups[category].append(entry)

        # 为每个错误组创建问题
        for category, entries in error_groups.items():
            # 取最具代表性的日志条目
            representative = entries[0]

            # 创建问题记录
            problem_record = self.problem_classifier.classify(
                representative.message,
                {
                    "source": representative.module or representative.source_file,
                    "error_category": category,
                    "error_severity": representative.error_severity,
                },
            )
            problem_record.stack_trace = representative.stack_trace

            # 根因分析
            root_cause_result = None
            if self.root_cause_analyzer:
                root_cause_result = self.root_cause_analyzer.trace_cause(
                    representative.message,
                    {
                        "source": representative.module,
                        "category": category,
                    },
                )

            # 创建告警
            alert = None
            if self.alert_manager:
                alert = Alert(
                    severity=self._severity_from_problem(problem_record.severity),
                    module=representative.module or "unknown",
                    message=representative.message,
                    timestamp=float(datetime.fromisoformat(representative.timestamp or datetime.now().isoformat()).timestamp()) if representative.timestamp else time.time(),
                    tags={"category": category, "count": len(entries)},
                )

            problem = LocatedProblem(
                problem_id=f"problem_log_{category}_{int(time.time())}",
                alert=alert,
                problem_record=problem_record,
                root_cause_result=root_cause_result,
                log_entries=entries,
                affected_modules=[representative.module] if representative.module else [],
                confidence=self._calculate_confidence_from_entries(entries, root_cause_result),
            )
            problems.append(problem)

        return problems

    def _locate_from_probes(
        self,
        probe_states: Dict[str, ProbeState],
    ) -> List[LocatedProblem]:
        """基于探针状态定位问题"""
        problems: List[LocatedProblem] = []

        for module_id, state in probe_states.items():
            if state in (ProbeState.FAILED, ProbeState.DEGRADED, ProbeState.UNAVAILABLE):
                # 创建问题记录
                problem_record = self.problem_classifier.classify(
                    f"Module {module_id} in {state.value} state",
                    {"source": module_id, "probe_state": state.value},
                )
                problem_record.module_name = module_id

                # 根因分析
                root_cause_result = None
                if self.root_cause_analyzer:
                    root_cause_result = self.root_cause_analyzer.trace_cause(
                        problem_record.message,
                        asdict(problem_record),
                    )

                # 创建告警
                alert = None
                if self.alert_manager:
                    alert = Alert(
                        severity=self._severity_from_problem(problem_record.severity),
                        module=module_id,
                        message=problem_record.message,
                        tags={"probe_state": state.value},
                    )

                problem = LocatedProblem(
                    problem_id=f"problem_probe_{module_id}",
                    alert=alert,
                    problem_record=problem_record,
                    root_cause_result=root_cause_result,
                    related_probes=self._get_probes_for_module(module_id),
                    affected_modules=[module_id],
                    confidence=0.8 if state == ProbeState.FAILED else 0.6,
                )
                problems.append(problem)

        return problems

    def _locate_comprehensive(
        self,
        alerts: List[Alert],
        log_text: Optional[str],
        log_files: Optional[List[str]],
        probe_states: Dict[str, ProbeState],
        raw_data: Dict[str, Any],
    ) -> List[LocatedProblem]:
        """综合分析定位问题"""
        # 1. 从告警定位基础问题
        alert_problems = self._locate_from_alerts(alerts)

        # 2. 从日志增强问题
        log_problems = self._locate_from_logs(log_text, log_files)

        # 3. 从探针状态补充问题
        probe_problems = self._locate_from_probes(probe_states)

        # 4. 合并去重
        all_problems = alert_problems + log_problems + probe_problems
        merged_problems = self._merge_problems(all_problems)

        # 5. 用日志分析增强告警问题
        if self.log_analyzer and log_text:
            merged_problems = self._enhance_with_logs(merged_problems, log_text)

        return merged_problems

    def _merge_problems(self, problems: List[LocatedProblem]) -> List[LocatedProblem]:
        """合并相似问题"""
        if not problems:
            return []

        # 按模块分组
        module_groups: Dict[str, List[LocatedProblem]] = {}
        for problem in problems:
            modules = problem.affected_modules or [problem.alert.module if problem.alert else "unknown"]
            for mod in modules:
                if mod not in module_groups:
                    module_groups[mod] = []
                module_groups[mod].append(problem)

        # 每个组保留最严重的一个
        merged: List[LocatedProblem] = []
        for mod, group in module_groups.items():
            # 按置信度排序
            group.sort(key=lambda p: p.confidence, reverse=True)
            best = group[0]
            # 合并日志条目
            for p in group[1:]:
                best.log_entries.extend(p.log_entries)
                best.related_probes.extend(p.related_probes)
            merged.append(best)

        return merged

    def _enhance_with_logs(
        self,
        problems: List[LocatedProblem],
        log_text: str,
    ) -> List[LocatedProblem]:
        """用日志分析增强问题"""
        if not self.log_analyzer:
            return problems

        log_entries = self.log_analyzer.analyze_text(log_text)

        for problem in problems:
            # 找出相关的日志条目
            problem_modules = set(problem.affected_modules)
            if problem.alert:
                problem_modules.add(problem.alert.module)

            related_entries = [
                e for e in log_entries
                if e.module in problem_modules
                or (e.source_file and any(m in e.source_file for m in problem_modules))
            ]

            if related_entries:
                problem.log_entries.extend(related_entries)

                # 更新置信度
                if len(related_entries) >= 3:
                    problem.confidence = min(1.0, problem.confidence + 0.1)

        return problems

    def _generate_summary(self, problems: List[LocatedProblem]) -> Dict[str, Any]:
        """生成报告摘要"""
        if not problems:
            return {
                "total_problems": 0,
                "critical_count": 0,
                "error_count": 0,
                "warning_count": 0,
                "high_confidence_count": 0,
                "affected_module_count": 0,
                "resolved_count": 0,
            }

        critical = sum(
            1 for p in problems
            if p.problem_record and p.problem_record.severity == ProblemSeverity.CRITICAL
        )
        error = sum(
            1 for p in problems
            if p.problem_record and p.problem_record.severity == ProblemSeverity.ERROR
        )
        warning = sum(
            1 for p in problems
            if p.problem_record and p.problem_record.severity == ProblemSeverity.WARNING
        )
        high_conf = sum(1 for p in problems if p.confidence >= self.config.confidence_threshold)
        resolved = sum(1 for p in problems if p.status == "resolved")

        all_modules: Set[str] = set()
        for p in problems:
            all_modules.update(p.affected_modules)

        return {
            "total_problems": len(problems),
            "critical_count": critical,
            "error_count": error,
            "warning_count": warning,
            "high_confidence_count": high_conf,
            "affected_module_count": len(all_modules),
            "resolved_count": resolved,
            "affected_modules": list(all_modules),
        }

    def _generate_recommendations(
        self,
        problems: List[LocatedProblem],
        summary: Dict[str, Any],
    ) -> List[str]:
        """生成建议"""
        recommendations: List[str] = []

        if summary.get("critical_count", 0) > 0:
            recommendations.append("存在严重问题，建议立即处理")

        if summary.get("error_count", 0) > 2:
            recommendations.append("错误数量较多，建议批量排查")

        # 基于根因类别的建议
        categories: Dict[RootCauseCategory, int] = {}
        for problem in problems:
            if problem.root_cause_result:
                cat = problem.root_cause_result.category
                categories[cat] = categories.get(cat, 0) + 1

        if RootCauseCategory.CONFIGURATION in categories:
            recommendations.append("发现配置问题，建议检查配置文件")
        if RootCauseCategory.DEPENDENCY_FAILURE in categories:
            recommendations.append("发现依赖模块故障，建议检查模块间依赖")
        if RootCauseCategory.RESOURCE_EXHAUSTION in categories:
            recommendations.append("发现资源耗尽问题，建议检查内存和连接池")
        if RootCauseCategory.EXTERNAL_SERVICE in categories:
            recommendations.append("发现外部服务问题，建议检查网络连通性")

        if not recommendations:
            recommendations.append("系统运行正常，未发现明显问题")

        return recommendations

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _alert_to_problem_record(self, alert: Alert) -> ProblemRecord:
        """将告警转换为问题记录"""
        problem_type_map = {
            AlertSeverity.CRITICAL: ProblemType.CRASH,
            AlertSeverity.ERROR: ProblemType.ERROR,
            AlertSeverity.WARNING: ProblemType.TIMEOUT,
            AlertSeverity.INFO: ProblemType.UNKNOWN,
        }

        severity_map = {
            AlertSeverity.CRITICAL: ProblemSeverity.CRITICAL,
            AlertSeverity.ERROR: ProblemSeverity.ERROR,
            AlertSeverity.WARNING: ProblemSeverity.WARNING,
            AlertSeverity.INFO: ProblemSeverity.INFO,
        }

        # 从标签提取问题类型
        tags = alert.tags or {}
        problem_type = ProblemType(str(tags.get("problem_type", "UNKNOWN")).upper())
        if not isinstance(problem_type, ProblemType):
            problem_type = problem_type_map.get(alert.severity, ProblemType.UNKNOWN)

        return ProblemRecord(
            problem_type=problem_type,
            severity=severity_map.get(alert.severity, ProblemSeverity.INFO),
            scope=Scope.SINGLE_MODULE,
            message=alert.message,
            timestamp=alert.timestamp,
            module_name=alert.module,
            error_code=tags.get("error_code"),
            raw_data=tags,
        )

    def _severity_from_problem(self, severity: ProblemSeverity) -> AlertSeverity:
        """将问题严重程度转换为告警严重程度"""
        mapping = {
            ProblemSeverity.CRITICAL: AlertSeverity.CRITICAL,
            ProblemSeverity.ERROR: AlertSeverity.ERROR,
            ProblemSeverity.WARNING: AlertSeverity.WARNING,
            ProblemSeverity.INFO: AlertSeverity.INFO,
        }
        return mapping.get(severity, AlertSeverity.INFO)

    def _calculate_confidence(
        self,
        alert_severity: AlertSeverity,
        root_cause_result: Optional[RootCauseResult],
    ) -> float:
        """计算置信度"""
        base = 0.5

        # 基于告警严重程度
        severity_boost = {
            AlertSeverity.CRITICAL: 0.3,
            AlertSeverity.ERROR: 0.2,
            AlertSeverity.WARNING: 0.1,
            AlertSeverity.INFO: 0.0,
        }
        base += severity_boost.get(alert_severity, 0.0)

        # 基于根因分析置信度
        if root_cause_result:
            base += root_cause_result.root_cause.confidence * 0.3

        return min(1.0, base)

    def _calculate_confidence_from_entries(
        self,
        entries: List[LogEntry],
        root_cause_result: Optional[RootCauseResult],
    ) -> float:
        """基于日志条目计算置信度"""
        base = 0.4

        # 基于条目数量
        count = len(entries)
        if count >= 10:
            base += 0.3
        elif count >= 5:
            base += 0.2
        elif count >= 3:
            base += 0.1

        # 基于根因分析
        if root_cause_result:
            base += root_cause_result.root_cause.confidence * 0.3

        return min(1.0, base)

    def _get_affected_modules(
        self,
        root_cause_result: Optional[RootCauseResult],
        default_module: str,
    ) -> List[str]:
        """获取受影响的模块"""
        if root_cause_result:
            return root_cause_result.affected_modules
        return [default_module] if default_module else []

    def _get_probes_for_module(self, module_id: str) -> List[ModuleProbe]:
        """获取模块的探针列表"""
        # 简化实现，实际应从 ProbeRegistry 获取
        return []

    # ========================================================================
    # 报告管理
    # ========================================================================

    def get_report(self, report_id: str) -> Optional[ProblemReport]:
        """获取报告"""
        return self._reports.get(report_id)

    def list_reports(self) -> List[str]:
        """列出所有报告ID"""
        return list(self._reports.keys())

    def get_latest_report(self) -> Optional[ProblemReport]:
        """获取最新报告"""
        if not self._reports:
            return None
        return self._reports[max(self._reports.keys())]


# ============================================================================
# 便捷函数
# ============================================================================

def locate_problems(
    alerts: Optional[List[Alert]] = None,
    log_text: Optional[str] = None,
    probe_states: Optional[Dict[str, ProbeState]] = None,
    mode: LocatorMode = LocatorMode.COMPREHENSIVE,
) -> ProblemReport:
    """
    便捷函数：定位问题

    Args:
        alerts: 告警列表
        log_text: 日志文本
        probe_states: 探针状态字典
        mode: 定位模式

    Returns:
        ProblemReport: 问题定位报告
    """
    config = ProblemLocatorConfig(mode=mode)
    locator = ProblemLocator(config=config)
    return locator.locate(
        alerts=alerts,
        log_text=log_text,
        probe_states=probe_states,
    )
