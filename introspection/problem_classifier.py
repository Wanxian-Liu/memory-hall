"""
Mimir-Core 问题分类引擎
introspection/problem_classifier.py

负责对系统问题进行分类、严重程度评估和影响范围判断。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class ProblemType(Enum):
    """问题类型枚举"""
    TIMEOUT = auto()      # 超时问题
    ERROR = auto()        # 一般错误
    CRASH = auto()        # 崩溃问题
    MEMORY = auto()       # 内存问题
    NETWORK = auto()      # 网络问题
    PERMISSION = auto()  # 权限问题
    CONFIG = auto()       # 配置问题
    UNKNOWN = auto()      # 未知类型


class Severity(Enum):
    """严重程度枚举"""
    CRITICAL = auto()  # 致命，影响整个系统
    ERROR = auto()     # 错误，影响主要功能
    WARNING = auto()   # 警告，影响次要功能
    INFO = auto()      # 信息，不影响功能


class Scope(Enum):
    """影响范围枚举"""
    SINGLE_MODULE = auto()   # 单模块
    MULTI_MODULE = auto()    # 多模块
    SYSTEM_WIDE = auto()      # 全系统


@dataclass
class ProblemRecord:
    """问题记录"""
    problem_type: ProblemType
    severity: Severity
    scope: Scope
    message: str
    timestamp: float = field(default_factory=time.time)
    raw_data: dict[str, Any] = field(default_factory=dict)
    module_name: Optional[str] = None
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    recovery_hint: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_type": self.problem_type.name,
            "severity": self.severity.name,
            "scope": self.scope.name,
            "message": self.message,
            "timestamp": self.timestamp,
            "module_name": self.module_name,
            "error_code": self.error_code,
            "stack_trace": self.stack_trace,
            "recovery_hint": self.recovery_hint,
            "raw_data": self.raw_data,
        }


class ProblemClassifier:
    """
    问题分类引擎
    
    根据日志内容、错误信息等对问题进行分类。
    """

    # 超时模式
    TIMEOUT_PATTERNS = [
        re.compile(r"timeout|timed?[\s-]?out", re.I),
        re.compile(r"took too long|exceeded|deadline", re.I),
        re.compile(r"connection[\s-]?timeout", re.I),
        re.compile(r"request[\s-]?timeout", re.I),
    ]

    # 崩溃模式
    CRASH_PATTERNS = [
        re.compile(r"crash|segfault|segmentation fault", re.I),
        re.compile(r"abort|panic|fatal", re.I),
        re.compile(r"core[\s-]?dumped", re.I),
        re.compile(r"sig(abrt|segv|term)", re.I),
    ]

    # 内存模式
    MEMORY_PATTERNS = [
        re.compile(r"memory|oom|out[\s-]?of[\s-]?memory", re.I),
        re.compile(r"heap|calloc|realloc|malloc", re.I),
        re.compile(r"allocation failed|cannot allocate", re.I),
        re.compile(r"stack overflow", re.I),
    ]

    # 网络模式
    NETWORK_PATTERNS = [
        re.compile(r"network|dns|connection refused|connection reset", re.I),
        re.compile(r"socket|econnrefused|econnreset|enotconn", re.I),
        re.compile(r"http.*error|status code [45]\d\d", re.I),
        re.compile(r"no route|unreachable|enoent", re.I),
    ]

    # 权限模式
    PERMISSION_PATTERNS = [
        re.compile(r"permission denied|access denied|eacces|eperm", re.I),
        re.compile(r"not allowed|unauthorized|forbidden", re.I),
        re.compile(r"chmod|chown|read[\s-]?only", re.I),
    ]

    # 配置模式
    CONFIG_PATTERNS = [
        re.compile(r"config|configuration|invalid.*option", re.I),
        re.compile(r"missing.*required|required.*missing", re.I),
        re.compile(r"schema|validation|malformed", re.I),
        re.compile(r"env(ironment)?|env var", re.I),
    ]

    # 错误代码模式
    ERROR_CODE_PATTERNS = [
        (r"ERR_(\w+)", "error_code"),
        (r"E(\w+)\s+(\d+)", "error_code"),
        (r"0x[0-9a-fA-F]+", "hex_code"),
    ]

    def __init__(self):
        self._type_patterns: list[tuple[re.Pattern, ProblemType]] = [
            (self.TIMEOUT_PATTERNS[0], ProblemType.TIMEOUT),
            (self.ERROR_CODE_PATTERNS[0], ProblemType.ERROR),
        ]

    def classify(self, message: str, raw_data: Optional[dict[str, Any]] = None) -> ProblemRecord:
        """
        对问题消息进行分类
        
        Args:
            message: 问题消息文本
            raw_data: 原始数据字典
            
        Returns:
            ProblemRecord: 分类后的问题记录
        """
        raw_data = raw_data or {}
        msg_lower = message.lower()

        # 检测问题类型
        problem_type = self._detect_type(msg_lower, message)

        # 检测严重程度
        severity = self._detect_severity(msg_lower, problem_type)

        # 检测影响范围
        scope = self._detect_scope(raw_data)

        # 提取错误代码
        error_code = self._extract_error_code(message)

        # 提取模块名
        module_name = self._extract_module(raw_data)

        # 生成恢复提示
        recovery_hint = self._generate_recovery_hint(problem_type, severity)

        return ProblemRecord(
            problem_type=problem_type,
            severity=severity,
            scope=scope,
            message=message,
            raw_data=raw_data,
            module_name=module_name,
            error_code=error_code,
            recovery_hint=recovery_hint,
        )

    def _detect_type(self, msg_lower: str, original_msg: str) -> ProblemType:
        """检测问题类型"""
        # 按优先级检测
        if any(p.search(original_msg) for p in self.CRASH_PATTERNS):
            return ProblemType.CRASH
        if any(p.search(original_msg) for p in self.TIMEOUT_PATTERNS):
            return ProblemType.TIMEOUT
        if any(p.search(original_msg) for p in self.MEMORY_PATTERNS):
            return ProblemType.MEMORY
        if any(p.search(original_msg) for p in self.NETWORK_PATTERNS):
            return ProblemType.NETWORK
        if any(p.search(original_msg) for p in self.PERMISSION_PATTERNS):
            return ProblemType.PERMISSION
        if any(p.search(original_msg) for p in self.CONFIG_PATTERNS):
            return ProblemType.CONFIG

        # 检查堆栈跟踪
        if "traceback" in msg_lower or "stack" in msg_lower:
            if "error" in msg_lower or "exception" in msg_lower:
                return ProblemType.ERROR

        return ProblemType.ERROR

    def _detect_severity(self, msg_lower: str, problem_type: ProblemType) -> Severity:
        """检测严重程度"""
        critical_keywords = ["crash", "panic", "fatal", "abort", "killed", "deadlock"]
        error_keywords = ["error", "failed", "failure", "exception", "invalid"]
        warning_keywords = ["warning", "warn", "deprecate", "retry"]

        # 崩溃直接CRITICAL
        if problem_type == ProblemType.CRASH:
            return Severity.CRITICAL

        # 检查关键词
        if any(k in msg_lower for k in critical_keywords):
            return Severity.CRITICAL
        if any(k in msg_lower for k in error_keywords):
            return Severity.ERROR
        if any(k in msg_lower for k in warning_keywords):
            return Severity.WARNING

        return Severity.INFO

    def _detect_scope(self, raw_data: dict[str, Any]) -> Scope:
        """检测影响范围"""
        # 从raw_data中推断
        if "scope" in raw_data:
            scope_val = str(raw_data["scope"]).upper()
            if scope_val == "SINGLE_MODULE":
                return Scope.SINGLE_MODULE
            elif scope_val == "MULTI_MODULE":
                return Scope.MULTI_MODULE
            elif scope_val == "SYSTEM_WIDE":
                return Scope.SYSTEM_WIDE

        # 从affected_modules推断
        affected = raw_data.get("affected_modules", raw_data.get("modules", []))
        if isinstance(affected, list):
            if len(affected) == 1:
                return Scope.SINGLE_MODULE
            elif len(affected) <= 3:
                return Scope.MULTI_MODULE
            else:
                return Scope.SYSTEM_WIDE

        return Scope.SINGLE_MODULE

    def _extract_error_code(self, message: str) -> Optional[str]:
        """提取错误代码"""
        for pattern_str, _ in self.ERROR_CODE_PATTERNS:
            pattern = re.compile(pattern_str, re.I)
            match = pattern.search(message)
            if match:
                return match.group(0)
        return None

    def _extract_module(self, raw_data: dict[str, Any]) -> Optional[str]:
        """提取模块名"""
        return (
            raw_data.get("module")
            or raw_data.get("module_name")
            or raw_data.get("source")
            or raw_data.get("component")
        )

    def _generate_recovery_hint(self, problem_type: ProblemType, severity: Severity) -> str:
        """生成恢复提示"""
        hints = {
            ProblemType.TIMEOUT: "检查网络连接或增加超时阈值，考虑实现重试机制",
            ProblemType.CRASH: "收集堆栈跟踪，检查系统资源，可能需要重启服务",
            ProblemType.MEMORY: "检查内存泄漏，考虑增加内存限制或优化内存使用",
            ProblemType.NETWORK: "检查网络配置和防火墙规则，确认服务可达性",
            ProblemType.PERMISSION: "检查文件/资源权限配置，确认运行用户权限",
            ProblemType.CONFIG: "检查配置文件和环境变量，确保必需配置已设置",
            ProblemType.ERROR: "查看详细日志定位具体错误原因",
            ProblemType.UNKNOWN: "需要进一步调查以确定根本原因",
        }

        hint = hints.get(problem_type, hints[ProblemType.UNKNOWN])

        if severity == Severity.CRITICAL:
            hint = f"[紧急] {hint}"
        elif severity == Severity.WARNING:
            hint = f"[注意] {hint}"

        return hint

    def analyze(self, log_entries: list[dict[str, Any]]) -> list[ProblemRecord]:
        """
        分析日志条目列表并返回问题记录列表
        
        与 log_analyzer 集成：
        - 接收 log_analyzer 输出的结构化日志
        - 对每条日志进行分类
        - 返回 ProblemRecord 列表
        
        Args:
            log_entries: log_analyzer 输出的日志条目列表
                        每条条目应包含至少 'message' 字段
                        
        Returns:
            list[ProblemRecord]: 分类后的问题记录列表
        """
        records = []
        for entry in log_entries:
            message = entry.get("message", "")
            if not message:
                continue
            record = self.classify(message, entry)
            records.append(record)
        return records

    def get_summary(self, records: list[ProblemRecord]) -> dict[str, Any]:
        """
        获取问题汇总统计
        
        Args:
            records: 问题记录列表
            
        Returns:
            dict: 汇总统计信息
        """
        if not records:
            return {
                "total": 0,
                "by_type": {},
                "by_severity": {},
                "by_scope": {},
                "critical_count": 0,
            }

        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        critical_count = 0

        for r in records:
            by_type[r.problem_type.name] = by_type.get(r.problem_type.name, 0) + 1
            by_severity[r.severity.name] = by_severity.get(r.severity.name, 0) + 1
            by_scope[r.scope.name] = by_scope.get(r.scope.name, 0) + 1
            if r.severity == Severity.CRITICAL:
                critical_count += 1

        return {
            "total": len(records),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_scope": by_scope,
            "critical_count": critical_count,
        }
