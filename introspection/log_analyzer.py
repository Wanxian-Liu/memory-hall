"""
日志分析器 - M3.1: 基于状态探针系统的日志分析集成
===================================================

非侵入式日志分析，解析结构化日志，提取错误模式，统计频率，关联模块。

设计参考：
- 状态探针系统 (status_probes.py): 线程安全的注册表模式
- 问题检测器 (problem_detector.py): 基于模式的错误分类
- claw-code: 结构化日志 + 多级别支持 + 错误分类

使用方式:
    from introspection.log_analyzer import LogAnalyzer, LogLevel

    analyzer = LogAnalyzer()
    
    # 分析日志文件
    report = analyzer.analyze_logs(time_window_hours=24)
    
    # 分析内存文本
    problems = analyzer.analyze_text("some log text")
    
    # 获取错误统计
    stats = analyzer.get_error_stats()
    
    # 获取模块-错误关联
    module_errors = analyzer.get_module_error_association()
"""

from __future__ import annotations

import re
import threading
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# 日志级别枚举
# ---------------------------------------------------------------------------

class LogLevel(Enum):
    """日志级别（兼容标准 logging + 扩展）"""
    TRACE = 5      # TRACE - 最细粒度
    DEBUG = 10     # DEBUG - 调试信息
    INFO = 20      # INFO - 一般信息
    WARNING = 30   # WARNING - 警告
    ERROR = 40     # ERROR - 错误
    CRITICAL = 50  # CRITICAL - 严重错误
    # 扩展级别
    EXCEPTION = 100  # EXCEPTION - 异常（ERROR + traceback）
    FATAL = 200    # FATAL - 致命错误


# ---------------------------------------------------------------------------
# 日志解析结果
# ---------------------------------------------------------------------------

@dataclass
class LogEntry:
    """
    解析后的日志条目。

    字段设计参考claw-code结构化日志格式。
    """
    timestamp: Optional[str] = None       # ISO格式时间戳
    level: LogLevel = LogLevel.INFO      # 日志级别
    module: Optional[str] = None         # 模块名
    message: str = ""                   # 原始消息
    parsed_fields: Dict[str, Any] = field(default_factory=dict)  # 解析的额外字段
    error_category: Optional[str] = None  # 错误分类（如来自问题检测器）
    error_severity: Optional[str] = None  # 错误严重级别
    stack_trace: Optional[str] = None    # 堆栈跟踪（如果有）
    line_number: Optional[int] = None    # 原始行号
    source_file: Optional[str] = None    # 来源文件


@dataclass
class ErrorPattern:
    """
    错误模式定义。
    """
    pattern_id: str
    regex: str
    category: str
    severity: str  # "critical", "error", "warning", "info"
    description: str
    module_hint: Optional[str] = None  # 模块提示（可选）
    count: int = 0                     # 匹配次数


@dataclass
class ModuleErrorStats:
    """
    模块错误统计。
    """
    module_id: str
    total_errors: int = 0
    by_severity: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_category: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    recent_errors: List[LogEntry] = field(default_factory=list)
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


@dataclass
class LogAnalysisReport:
    """
    日志分析报告。
    """
    generated_at: str
    time_window: str
    total_entries: int
    entries_by_level: Dict[str, int]
    total_errors: int
    error_patterns: List[ErrorPattern]
    module_stats: Dict[str, ModuleErrorStats]
    top_errors: List[Tuple[str, int]]  # (error_msg_prefix, count)
    recommendations: List[str]


# ---------------------------------------------------------------------------
# 标准日志格式正则
# ---------------------------------------------------------------------------

# 常见日志格式
LOG_FORMAT_PATTERNS = [
    # 标准 Python logging 格式
    # 2026-04-12 15:00:00,123 ERROR [module] message
    re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)'
        r'(?:\s*(?P<ms>\d+))?'
        r'\s+(?P<level>TRACE|DEBUG|INFO|WARNING|ERROR|CRITICAL|FATAL|EXCEPTION)'
        r'\s+(?:\[(?P<module>[^\]]+)\])?'
        r'\s*(?P<message>.*)$'
    ),
    # 带线程信息的格式
    # 2026-04-12T15:00:00.123Z [Thread-1] [module] ERROR: message
    re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)'
        r'\s+\[(?P<thread>[^\]]+)\]'
        r'\s*(?:\[(?P<module>[^\]]+)\])?'
        r'\s*(?P<level>TRACE|DEBUG|INFO|WARNING|ERROR|CRITICAL|FATAL|EXCEPTION)'
        r'(?::\s*(?P<message>.*))?$'
    ),
    # JSON 结构化日志（单行）
    re.compile(
        r'^.*"timestamp":\s*"(?P<timestamp>[^"]+)".*'
        r'"level":\s*"(?P<level>\w+)".*'
        r'"message":\s*"(?P<message>[^"]+)".*$'
    ),
    # 简化格式：level: message
    re.compile(
        r'^(?P<level>TRACE|DEBUG|INFO|WARNING|ERROR|CRITICAL|FATAL|EXCEPTION)'
        r'[:\s]+(?P<message>.*)$'
    ),
]


# ---------------------------------------------------------------------------
# 错误模式库
# ---------------------------------------------------------------------------

BUILTIN_ERROR_PATTERNS = [
    # 执行超时
    ErrorPattern(
        pattern_id="exec_timeout",
        regex=r"timeout|timed out|超时",
        category="execution_timeout",
        severity="error",
        description="执行超时"
    ),
    ErrorPattern(
        pattern_id="gateway_timeout",
        regex=r"Gateway timeout|gateway timeout",
        category="network_timeout",
        severity="error",
        description="网关超时"
    ),
    # 执行失败
    ErrorPattern(
        pattern_id="exec_failed",
        regex=r"exec failed|执行失败|execution failed",
        category="execution_failure",
        severity="error",
        description="执行失败"
    ),
    ErrorPattern(
        pattern_id="preflight_complex",
        regex=r"preflight.*complex.*interpreter|exec preflight",
        category="execution_failure",
        severity="warning",
        description="Preflight检查失败"
    ),
    # 资源问题
    ErrorPattern(
        pattern_id="oom",
        regex=r"out of memory|OOM|内存不足",
        category="resource_exhausted",
        severity="critical",
        description="内存不足"
    ),
    ErrorPattern(
        pattern_id="disk_full",
        regex=r"disk full|磁盘已满|no space left",
        category="resource_exhausted",
        severity="critical",
        description="磁盘空间不足"
    ),
    # 网络问题
    ErrorPattern(
        pattern_id="connection_refused",
        regex=r"Connection refused|连接被拒绝",
        category="connection_refused",
        severity="error",
        description="连接被拒绝"
    ),
    ErrorPattern(
        pattern_id="blocked_ip",
        regex=r"Blocked.*private.*IP|阻止.*私有.*IP|internal.*IP",
        category="network_timeout",
        severity="warning",
        description="访问被阻止（私有IP）"
    ),
    ErrorPattern(
        pattern_id="fetch_failed",
        regex=r"fetch failed|抓取失败|web_fetch.*blocked",
        category="network_timeout",
        severity="warning",
        description="网络抓取失败"
    ),
    # 配置问题
    ErrorPattern(
        pattern_id="config_error",
        regex=r"config.*error|配置错误|MissingConfig",
        category="config_error",
        severity="error",
        description="配置错误"
    ),
    ErrorPattern(
        pattern_id="missing_config",
        regex=r"missing.*config|缺少配置",
        category="config_error",
        severity="warning",
        description="缺少配置"
    ),
    # 依赖问题
    ErrorPattern(
        pattern_id="module_not_found",
        regex=r"ModuleNotFoundError|No module named|找不到模块",
        category="missing_dependency",
        severity="error",
        description="模块未找到"
    ),
    ErrorPattern(
        pattern_id="import_error",
        regex=r"ImportError|导入错误",
        category="missing_dependency",
        severity="error",
        description="导入错误"
    ),
    # 健康问题
    ErrorPattern(
        pattern_id="health_degraded",
        regex=r"health.*degraded|健康状态降级",
        category="health_degraded",
        severity="warning",
        description="健康状态降级"
    ),
    ErrorPattern(
        pattern_id="circuit_breaker",
        regex=r"circuit.*breaker.*open|断路器打开",
        category="circuit_breaker_open",
        severity="warning",
        description="断路器打开"
    ),
    ErrorPattern(
        pattern_id="health_check_failed",
        regex=r"failed.*health.*check|健康检查失败",
        category="health_degraded",
        severity="warning",
        description="健康检查失败"
    ),
    # 权限问题
    ErrorPattern(
        pattern_id="permission_denied",
        regex=r"Permission denied|权限不足|access denied|访问被拒绝",
        category="permission_denied",
        severity="error",
        description="权限不足"
    ),
    # 会话/工具问题
    ErrorPattern(
        pattern_id="sessions_spawn_timeout",
        regex=r"sessions_spawn.*timeout|sessions_spawn.*failed",
        category="execution_timeout",
        severity="error",
        description="子代理启动超时"
    ),
    ErrorPattern(
        pattern_id="tool_failed",
        regex=r"tool.*failed|工具.*失败",
        category="execution_failure",
        severity="error",
        description="工具执行失败"
    ),
]


# ---------------------------------------------------------------------------
# 日志分析器
# ---------------------------------------------------------------------------

class LogAnalyzer:
    """
    线程安全的日志分析器。

    功能：
    - 解析多种格式的日志
    - 提取错误模式和分类
    - 统计错误频率
    - 关联模块与错误
    - 与状态探针系统集成

    设计参考：
    - ProbeRegistry 的线程安全模式
    - 累积输出模式
    - 回调机制
    """

    # 默认日志目录
    DEFAULT_LOG_DIRS = [
        Path.home() / ".openclaw" / "logs",
        Path.home() / ".openclaw" / "workspace" / "logs",
        Path.home() / ".openclaw" / "logs" / "gateway",
    ]

    def __init__(
        self,
        project_root: Optional[str] = None,
        log_dirs: Optional[List[Path]] = None,
    ):
        if project_root is None:
            self.project_root = Path(__file__).parent.parent.resolve()
        else:
            self.project_root = Path(project_root)

        self._lock = threading.RLock()

        # 日志目录
        self.log_dirs = log_dirs or self.DEFAULT_LOG_DIRS

        # 解析的日志条目
        self._entries: List[LogEntry] = []
        self._entries_by_level: Dict[str, List[LogEntry]] = defaultdict(list)

        # 错误模式
        self._error_patterns: Dict[str, ErrorPattern] = {
            p.pattern_id: p for p in BUILTIN_ERROR_PATTERNS
        }

        # 模块统计
        self._module_stats: Dict[str, ModuleErrorStats] = {}

        # 错误消息频率（用于top errors）
        self._error_freq: Dict[str, int] = defaultdict(int)

        # 回调
        self._callbacks: List[Callable[[LogEntry], None]] = []

        # 统计计数
        self._total_entries = 0
        self._total_errors = 0

    # -------------------------------------------------------------------------
    # 回调管理
    # -------------------------------------------------------------------------

    def on_error(self, callback: Callable[[LogEntry], None]) -> None:
        """注册错误发现回调"""
        with self._lock:
            self._callbacks.append(callback)

    def _notify_error(self, entry: LogEntry) -> None:
        """通知所有回调"""
        for cb in self._callbacks:
            try:
                cb(entry)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # 错误模式管理
    # -------------------------------------------------------------------------

    def add_pattern(self, pattern: ErrorPattern) -> None:
        """添加自定义错误模式"""
        with self._lock:
            self._error_patterns[pattern.pattern_id] = pattern

    def remove_pattern(self, pattern_id: str) -> None:
        """移除错误模式"""
        with self._lock:
            self._error_patterns.pop(pattern_id, None)

    def get_patterns(self) -> Dict[str, ErrorPattern]:
        """获取所有错误模式"""
        with self._lock:
            return dict(self._error_patterns)

    # -------------------------------------------------------------------------
    # 日志解析
    # -------------------------------------------------------------------------

    def parse_line(self, line: str, source_file: Optional[str] = None) -> Optional[LogEntry]:
        """
        解析单行日志。

        尝试多种格式，返回解析后的 LogEntry 或 None。
        """
        if not line or not line.strip():
            return None

        # 尝试每种格式
        for pattern in LOG_FORMAT_PATTERNS:
            match = pattern.match(line.strip())
            if match:
                return self._build_entry(match.groupdict(), line, source_file)

        # 无法解析，当作纯文本 INFO 处理
        return LogEntry(
            timestamp=datetime.now().isoformat(),
            level=LogLevel.INFO,
            module=None,
            message=line.strip(),
            source_file=source_file,
        )

    def _build_entry(
        self,
        groups: Dict[str, str],
        raw_line: str,
        source_file: Optional[str],
    ) -> LogEntry:
        """从正则匹配组构建 LogEntry"""
        # 解析时间戳
        timestamp = groups.get("timestamp")
        if timestamp:
            # 清理时间戳格式
            timestamp = timestamp.replace(',', '.').replace('Z', '')

        # 解析级别
        level_str = groups.get("level", "INFO").upper()
        try:
            level = LogLevel[level_str]
        except KeyError:
            level = LogLevel.INFO

        # 解析模块
        module = groups.get("module")

        # 解析消息
        message = groups.get("message", "")

        # 检测错误模式
        error_category = None
        error_severity = None
        matched_pattern_id = None

        with self._lock:
            patterns = list(self._error_patterns.values())

        for pattern in patterns:
            if re.search(pattern.regex, message, re.IGNORECASE):
                error_category = pattern.category
                error_severity = pattern.severity
                matched_pattern_id = pattern.pattern_id
                # 更新计数
                with self._lock:
                    if matched_pattern_id in self._error_patterns:
                        self._error_patterns[matched_pattern_id].count += 1
                break

        return LogEntry(
            timestamp=timestamp,
            level=level,
            module=module,
            message=message,
            parsed_fields=groups,
            error_category=error_category,
            error_severity=error_severity,
            source_file=source_file,
        )

    # -------------------------------------------------------------------------
    # 日志分析
    # -------------------------------------------------------------------------

    def analyze_file(
        self,
        log_path: Path,
        time_window_hours: Optional[int] = None,
    ) -> List[LogEntry]:
        """
        分析单个日志文件。

        Args:
            log_path: 日志文件路径
            time_window_hours: 只分析最近N小时的条目（None表示全部）

        Returns:
            解析的日志条目列表
        """
        entries = []

        if not log_path.exists():
            return entries

        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return entries

        # 时间窗口
        cutoff = None
        if time_window_hours:
            cutoff = datetime.now() - timedelta(hours=time_window_hours)

        for line_num, line in enumerate(content.splitlines(), 1):
            entry = self.parse_line(line, str(log_path))
            if entry:
                entry.line_number = line_num

                # 时间过滤
                if cutoff and entry.timestamp:
                    try:
                        entry_time = datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
                        if entry_time < cutoff:
                            continue
                    except Exception:
                        pass

                entries.append(entry)
                self._record_entry(entry)

        return entries

    def analyze_logs(
        self,
        time_window_hours: Optional[int] = 24,
    ) -> List[LogEntry]:
        """
        分析所有日志目录。

        Args:
            time_window_hours: 只分析最近N小时的条目

        Returns:
            所有解析的日志条目
        """
        with self._lock:
            self._entries.clear()
            self._entries_by_level.clear()
            self._module_stats.clear()
            self._error_freq.clear()
            self._total_entries = 0
            self._total_errors = 0

        for log_dir in self.log_dirs:
            if not log_dir.exists():
                continue

            # 递归查找所有 .log 文件
            for log_file in log_dir.rglob("*.log"):
                if "__pycache__" in str(log_file):
                    continue
                self.analyze_file(log_file, time_window_hours)

        return list(self._entries)

    def analyze_text(
        self,
        text: str,
        source: str = "input",
        time_window_hours: Optional[int] = None,
    ) -> List[LogEntry]:
        """
        分析内存中的文本。

        Args:
            text: 日志文本
            source: 来源标识
            time_window_hours: 可选的时间过滤

        Returns:
            解析的日志条目
        """
        entries = []

        cutoff = None
        if time_window_hours:
            cutoff = datetime.now() - timedelta(hours=time_window_hours)

        for line_num, line in enumerate(text.splitlines(), 1):
            entry = self.parse_line(line, source)
            if entry:
                entry.line_number = line_num

                if cutoff and entry.timestamp:
                    try:
                        entry_time = datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
                        if entry_time < cutoff:
                            continue
                    except Exception:
                        pass

                entries.append(entry)
                self._record_entry(entry)

        return entries

    def _record_entry(self, entry: LogEntry) -> None:
        """记录条目到内部状态"""
        with self._lock:
            self._entries.append(entry)
            self._entries_by_level[entry.level.name].append(entry)
            self._total_entries += 1

            # 错误统计
            if entry.error_category:
                self._total_errors += 1

                # 更新模块统计
                module_id = entry.module or "unknown"
                if module_id not in self._module_stats:
                    self._module_stats[module_id] = ModuleErrorStats(module_id=module_id)

                stats = self._module_stats[module_id]
                stats.total_errors += 1
                stats.by_severity[entry.error_severity or "unknown"] += 1
                stats.by_category[entry.error_category] += 1

                # 限制 recent_errors 大小
                if len(stats.recent_errors) < 100:
                    stats.recent_errors.append(entry)

                # 更新时间范围
                if not stats.first_seen or (entry.timestamp and entry.timestamp < stats.first_seen):
                    stats.first_seen = entry.timestamp
                if not stats.last_seen or (entry.timestamp and entry.timestamp > stats.last_seen):
                    stats.last_seen = entry.timestamp

                # 错误频率统计（按消息前60字符分组）
                msg_key = entry.message[:60]
                self._error_freq[msg_key] += 1

                # 触发回调
                self._notify_error(entry)

    # -------------------------------------------------------------------------
    # 统计查询
    # -------------------------------------------------------------------------

    def get_entries(
        self,
        level: Optional[LogLevel] = None,
        module: Optional[str] = None,
        error_only: bool = False,
        limit: int = 1000,
    ) -> List[LogEntry]:
        """获取日志条目（支持过滤）"""
        with self._lock:
            entries = list(self._entries)

        if level:
            entries = [e for e in entries if e.level == level]

        if module:
            entries = [e for e in entries if e.module == module]

        if error_only:
            entries = [e for e in entries if e.error_category is not None]

        return entries[-limit:]

    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        with self._lock:
            return {
                "total_entries": self._total_entries,
                "total_errors": self._total_errors,
                "error_rate": self._total_errors / max(self._total_entries, 1),
                "by_level": {
                    level: len(items)
                    for level, items in self._entries_by_level.items()
                },
                "by_category": self._get_error_category_counts(),
                "by_severity": self._get_error_severity_counts(),
                "pattern_counts": {
                    pid: p.count
                    for pid, p in self._error_patterns.items()
                    if p.count > 0
                },
            }

    def _get_error_category_counts(self) -> Dict[str, int]:
        """统计各类别的错误数"""
        counts: Dict[str, int] = defaultdict(int)
        for entry in self._entries:
            if entry.error_category:
                counts[entry.error_category] += 1
        return dict(counts)

    def _get_error_severity_counts(self) -> Dict[str, int]:
        """统计各严重级别的错误数"""
        counts: Dict[str, int] = defaultdict(int)
        for entry in self._entries:
            if entry.error_severity:
                counts[entry.error_severity] += 1
        return dict(counts)

    def get_module_error_association(self) -> Dict[str, ModuleErrorStats]:
        """获取模块-错误关联"""
        with self._lock:
            return dict(self._module_stats)

    def get_top_errors(self, limit: int = 10) -> List[Tuple[str, int]]:
        """获取最频繁的错误"""
        with self._lock:
            sorted_freq = sorted(
                self._error_freq.items(),
                key=lambda x: -x[1]
            )
            return sorted_freq[:limit]

    # -------------------------------------------------------------------------
    # 报告生成
    # -------------------------------------------------------------------------

    def generate_report(
        self,
        time_window_hours: int = 24,
    ) -> LogAnalysisReport:
        """
        生成完整的日志分析报告。

        与状态探针系统集成，关联模块状态与日志错误。
        """
        # 确保已分析
        if not self._entries:
            self.analyze_logs(time_window_hours)

        # 收集模式统计
        patterns_with_hits = [
            p for p in self._error_patterns.values()
            if p.count > 0
        ]

        # 获取 top errors
        top_errors = self.get_top_errors(limit=20)

        # 生成建议
        recommendations = self._generate_recommendations()

        # 级别统计
        entries_by_level = {
            level: len(items)
            for level, items in self._entries_by_level.items()
        }

        return LogAnalysisReport(
            generated_at=datetime.now().isoformat(),
            time_window=f"{time_window_hours}h",
            total_entries=self._total_entries,
            entries_by_level=entries_by_level,
            total_errors=self._total_errors,
            error_patterns=sorted(patterns_with_hits, key=lambda p: -p.count),
            module_stats=dict(self._module_stats),
            top_errors=top_errors,
            recommendations=recommendations,
        )

    def _generate_recommendations(self) -> List[str]:
        """基于分析结果生成建议"""
        recommendations = []

        # 高频错误建议
        top = self.get_top_errors(limit=3)
        if top:
            for msg, count in top:
                if count >= 10:
                    recommendations.append(
                        f"高频错误 ({count}x): {msg[:50]}... - 建议深入调查根本原因"
                    )

        # 严重错误建议
        critical_count = self._get_error_severity_counts().get("critical", 0)
        if critical_count > 0:
            recommendations.append(
                f"发现 {critical_count} 个严重错误 - 需要立即处理"
            )

        # 模块级建议
        if self._module_stats:
            problematic_modules = [
                m for m, s in self._module_stats.items()
                if s.total_errors >= 5
            ]
            if problematic_modules:
                recommendations.append(
                    f"错误高发模块: {', '.join(problematic_modules[:5])}"
                )

        if not recommendations:
            recommendations.append("系统运行正常，未发现明显问题")

        return recommendations

    # -------------------------------------------------------------------------
    # 与状态探针集成
    # -------------------------------------------------------------------------

    def integrate_with_probes(self) -> None:
        """
        与状态探针系统集成。

        将日志分析结果反馈到探针状态。
        """
        try:
            from introspection.status_probes import get_probes, ProbeState

            probes = get_probes()

            # 更新有错误记录的模块探针
            for module_id, stats in self.get_module_error_association().items():
                if stats.total_errors > 0:
                    probe = probes.get_probe(module_id)
                    if probe:
                        # 如果有严重错误，更新探针状态
                        if stats.by_severity.get("critical", 0) > 0:
                            probe.record_check(
                                importable=probe.importable,
                                usable=False,
                                error=f"LogAnalyzer: {stats.total_errors} errors detected"
                            )
                        elif stats.by_severity.get("error", 0) > 0:
                            probe.record_check(
                                importable=probe.importable,
                                usable=True,
                                error=f"LogAnalyzer: {stats.total_errors} errors"
                            )

        except ImportError:
            pass  # 探针系统未加载


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_log_analyzer: Optional[LogAnalyzer] = None
_analyzer_lock = threading.Lock()


def get_analyzer() -> LogAnalyzer:
    """获取全局日志分析器（单例）"""
    global _log_analyzer
    if _log_analyzer is None:
        with _analyzer_lock:
            if _log_analyzer is None:
                _log_analyzer = LogAnalyzer()
    return _log_analyzer


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    """CLI入口 - 展示日志分析结果"""
    import json

    analyzer = get_analyzer()

    print("📋 分析最近24小时日志...")
    report = analyzer.generate_report(time_window_hours=24)

    print(f"\n📊 日志分析报告 ({report.time_window})")
    print(f"   总条目数: {report.total_entries}")
    print(f"   总错误数: {report.total_errors}")

    if report.entries_by_level:
        print(f"\n📈 日志级别分布:")
        for level, count in sorted(report.entries_by_level.items()):
            emoji = {
                "TRACE": "🔲",
                "DEBUG": "🔍",
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "ERROR": "🟠",
                "CRITICAL": "🔴",
                "EXCEPTION": "💥",
                "FATAL": "💀",
            }.get(level, "❓")
            print(f"   {emoji} {level}: {count}")

    if report.error_patterns:
        print(f"\n🐛 错误模式统计 (前10):")
        for pattern in report.error_patterns[:10]:
            print(f"   [{pattern.category}] {pattern.description}: {pattern.count}x")

    if report.top_errors:
        print(f"\n🚨 高频错误 (前5):")
        for msg, count in report.top_errors[:5]:
            print(f"   {count}x: {msg[:50]}...")

    if report.module_stats:
        print(f"\n📁 模块错误关联 (前5):")
        sorted_modules = sorted(
            report.module_stats.items(),
            key=lambda x: -x[1].total_errors
        )[:5]
        for module_id, stats in sorted_modules:
            print(f"   {module_id}: {stats.total_errors} errors")
            for cat, count in list(stats.by_category.items())[:3]:
                print(f"      - {cat}: {count}")

    if report.recommendations:
        print(f"\n💡 建议:")
        for rec in report.recommendations:
            print(f"   • {rec}")

    # 与探针集成
    print(f"\n🔗 与状态探针系统集成...")
    analyzer.integrate_with_probes()
    print(f"   完成")

    return report


if __name__ == "__main__":
    main()
