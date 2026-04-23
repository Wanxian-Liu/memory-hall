"""
关键指标阈值系统 - 健康阈值组 (从 thresholds.py 拆分)
=====================================================

本模块包含：
- HealthScoreThresholds (健康分数阈值组)
- ResponseTimeThresholds (响应时间阈值组)
- ErrorRateThresholds (错误率阈值组)
- ModuleTimeoutThresholds (模块调用超时阈值组)
- CallCountThresholds (调用计数阈值组)

拆分自: introspection/thresholds.py (M2.4)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .threshold_config import ThresholdConfig, ThresholdLevel


# ---------------------------------------------------------------------------
# 健康分数阈值
# ---------------------------------------------------------------------------

@dataclass
class HealthScoreThresholds:
    """健康分数阈值组"""
    healthy: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="health_score_healthy",
            default=0.8,
            value=0.8,
            min_value=0.0,
            max_value=1.0,
            level=ThresholdLevel.OK,
            description="健康模块的最低分数阈值"
        )
    )
    degraded: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="health_score_degraded",
            default=0.5,
            value=0.5,
            min_value=0.0,
            max_value=1.0,
            level=ThresholdLevel.WARNING,
            description="降级模块的分数阈值"
        )
    )
    failed: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="health_score_failed",
            default=0.3,
            value=0.3,
            min_value=0.0,
            max_value=1.0,
            level=ThresholdLevel.ERROR,
            description="失败模块的分数阈值"
        )
    )
    # 整体系统健康分数阈值
    system_healthy: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="system_health_score_healthy",
            default=0.7,
            value=0.7,
            min_value=0.0,
            max_value=1.0,
            level=ThresholdLevel.WARNING,
            description="系统整体健康分数阈值（低于此值触发告警）"
        )
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.healthy.to_dict(),
            "degraded": self.degraded.to_dict(),
            "failed": self.failed.to_dict(),
            "system_healthy": self.system_healthy.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthScoreThresholds":
        return cls(
            healthy=ThresholdConfig.from_dict(data["healthy"]),
            degraded=ThresholdConfig.from_dict(data["degraded"]),
            failed=ThresholdConfig.from_dict(data["failed"]),
            system_healthy=ThresholdConfig.from_dict(data.get("system_healthy", data["healthy"])),
        )


# ---------------------------------------------------------------------------
# 响应时间阈值
# ---------------------------------------------------------------------------

@dataclass
class ResponseTimeThresholds:
    """响应时间阈值组（单位：秒）"""
    fast: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="response_time_fast",
            default=0.5,
            value=0.5,
            min_value=0.0,
            max_value=60.0,
            level=ThresholdLevel.OK,
            description="快速响应阈值（秒），低于此值表示优秀"
        )
    )
    acceptable: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="response_time_acceptable",
            default=2.0,
            value=2.0,
            min_value=0.0,
            max_value=60.0,
            level=ThresholdLevel.WARNING,
            description="可接受响应阈值（秒），超过此值开始警告"
        )
    )
    slow: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="response_time_slow",
            default=5.0,
            value=5.0,
            min_value=0.0,
            max_value=60.0,
            level=ThresholdLevel.ERROR,
            description="慢响应阈值（秒），超过此值表示严重问题"
        )
    )
    timeout: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="response_time_timeout",
            default=30.0,
            value=30.0,
            min_value=1.0,
            max_value=300.0,
            level=ThresholdLevel.CRITICAL,
            description="超时阈值（秒），超过此值视为超时"
        )
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fast": self.fast.to_dict(),
            "acceptable": self.acceptable.to_dict(),
            "slow": self.slow.to_dict(),
            "timeout": self.timeout.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResponseTimeThresholds":
        return cls(
            fast=ThresholdConfig.from_dict(data["fast"]),
            acceptable=ThresholdConfig.from_dict(data["acceptable"]),
            slow=ThresholdConfig.from_dict(data["slow"]),
            timeout=ThresholdConfig.from_dict(data["timeout"]),
        )


# ---------------------------------------------------------------------------
# 错误率阈值
# ---------------------------------------------------------------------------

@dataclass
class ErrorRateThresholds:
    """错误率阈值组（0.0-1.0 表示 0%-100%）"""
    low: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="error_rate_low",
            default=0.01,
            value=0.01,
            min_value=0.0,
            max_value=1.0,
            level=ThresholdLevel.INFO,
            description="低错误率阈值（1%），超过开始记录信息"
        )
    )
    warning: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="error_rate_warning",
            default=0.05,
            value=0.05,
            min_value=0.0,
            max_value=1.0,
            level=ThresholdLevel.WARNING,
            description="警告错误率阈值（5%）"
        )
    )
    error: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="error_rate_error",
            default=0.10,
            value=0.10,
            min_value=0.0,
            max_value=1.0,
            level=ThresholdLevel.ERROR,
            description="错误率阈值（10%），超过视为模块异常"
        )
    )
    critical: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="error_rate_critical",
            default=0.25,
            value=0.25,
            min_value=0.0,
            max_value=1.0,
            level=ThresholdLevel.CRITICAL,
            description="严重错误率阈值（25%），超过视为模块失败"
        )
    )
    # 时间窗口（计算错误率的时间范围，秒）
    window_seconds: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="error_rate_window",
            default=300.0,
            value=300.0,
            min_value=60.0,
            max_value=3600.0,
            level=ThresholdLevel.INFO,
            description="错误率统计时间窗口（秒）"
        )
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "low": self.low.to_dict(),
            "warning": self.warning.to_dict(),
            "error": self.error.to_dict(),
            "critical": self.critical.to_dict(),
            "window_seconds": self.window_seconds.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorRateThresholds":
        return cls(
            low=ThresholdConfig.from_dict(data["low"]),
            warning=ThresholdConfig.from_dict(data["warning"]),
            error=ThresholdConfig.from_dict(data["error"]),
            critical=ThresholdConfig.from_dict(data["critical"]),
            window_seconds=ThresholdConfig.from_dict(data.get("window_seconds", data["low"])),
        )


# ---------------------------------------------------------------------------
# 模块调用超时阈值
# ---------------------------------------------------------------------------

@dataclass
class ModuleTimeoutThresholds:
    """模块调用超时阈值组（单位：秒）"""
    # 默认模块超时
    default: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="module_timeout_default",
            default=30.0,
            value=30.0,
            min_value=1.0,
            max_value=300.0,
            level=ThresholdLevel.ERROR,
            description="默认模块调用超时（秒）"
        )
    )
    # 快速模块超时（如工具调用）
    fast: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="module_timeout_fast",
            default=5.0,
            value=5.0,
            min_value=0.5,
            max_value=60.0,
            level=ThresholdLevel.WARNING,
            description="快速模块超时（秒），如工具调用"
        )
    )
    # 慢速模块超时（如网络请求）
    slow: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="module_timeout_slow",
            default=60.0,
            value=60.0,
            min_value=10.0,
            max_value=600.0,
            level=ThresholdLevel.ERROR,
            description="慢速模块超时（秒），如网络请求"
        )
    )
    # 连续超时次数阈值（连续超时至这个次数视为失败）
    consecutive_limit: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="module_timeout_consecutive_limit",
            default=3.0,
            value=3.0,
            min_value=1.0,
            max_value=10.0,
            level=ThresholdLevel.ERROR,
            description="连续超时次数阈值"
        )
    )
    # 特定模块超时覆盖（module_id -> timeout 秒）
    per_module_overrides: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "default": self.default.to_dict(),
            "fast": self.fast.to_dict(),
            "slow": self.slow.to_dict(),
            "consecutive_limit": self.consecutive_limit.to_dict(),
            "per_module_overrides": self.per_module_overrides,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModuleTimeoutThresholds":
        return cls(
            default=ThresholdConfig.from_dict(data["default"]),
            fast=ThresholdConfig.from_dict(data["fast"]),
            slow=ThresholdConfig.from_dict(data["slow"]),
            consecutive_limit=ThresholdConfig.from_dict(data["consecutive_limit"]),
            per_module_overrides=data.get("per_module_overrides", {}),
        )


# ---------------------------------------------------------------------------
# 调用计数阈值
# ---------------------------------------------------------------------------

@dataclass
class CallCountThresholds:
    """调用计数阈值组"""
    # 最小调用次数（太少可能表示模块未被使用）
    min_per_hour: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="call_count_min_per_hour",
            default=1.0,
            value=1.0,
            min_value=0.0,
            max_value=1000.0,
            level=ThresholdLevel.INFO,
            description="每小时最小调用次数阈值"
        )
    )
    # 最大调用次数（过高可能表示异常流量）
    max_per_minute: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="call_count_max_per_minute",
            default=100.0,
            value=100.0,
            min_value=1.0,
            max_value=10000.0,
            level=ThresholdLevel.WARNING,
            description="每分钟最大调用次数阈值"
        )
    )
    # 突发调用阈值（短时间内大量调用）
    burst_threshold: ThresholdConfig = field(
        default_factory=lambda: ThresholdConfig(
            name="call_count_burst",
            default=50.0,
            value=50.0,
            min_value=1.0,
            max_value=1000.0,
            level=ThresholdLevel.WARNING,
            description="突发调用阈值（单次检查内的最大调用数）"
        )
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_per_hour": self.min_per_hour.to_dict(),
            "max_per_minute": self.max_per_minute.to_dict(),
            "burst_threshold": self.burst_threshold.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CallCountThresholds":
        return cls(
            min_per_hour=ThresholdConfig.from_dict(data["min_per_hour"]),
            max_per_minute=ThresholdConfig.from_dict(data["max_per_minute"]),
            burst_threshold=ThresholdConfig.from_dict(data["burst_threshold"]),
        )
