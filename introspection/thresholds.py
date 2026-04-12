"""
Mimir-Core 关键指标阈值配置
定义各指标的 warning/critical 阈值及告警级别
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class AlertLevel(Enum):
    """告警级别枚举"""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ThresholdConfig:
    """阈值配置基类"""
    warning: float
    critical: float

    def evaluate(self, value: float) -> AlertLevel:
        """评估指标值是否超过阈值"""
        if value >= self.critical:
            return AlertLevel.CRITICAL
        elif value >= self.warning:
            return AlertLevel.WARNING
        return AlertLevel.OK

    def __post_init__(self):
        assert self.warning < self.critical, "warning threshold must be less than critical"


@dataclass
class HealthThreshold:
    """
    健康分数阈值
    - warning: 健康分数低于此值时触发警告
    - critical: 健康分数低于此值时触发严重告警
    """
    warning: float = 70.0      # 健康分数 < 70 触发 warning
    critical: float = 50.0     # 健康分数 < 50 触发 critical
    
    def evaluate(self, value: float) -> AlertLevel:
        """评估健康分数（低于阈值触发告警）"""
        if value < self.critical:
            return AlertLevel.CRITICAL
        elif value < self.warning:
            return AlertLevel.WARNING
        return AlertLevel.OK


@dataclass
class ResponseTimeThreshold(ThresholdConfig):
    """
    响应时间阈值（毫秒）
    - warning: 响应时间超过此值时触发警告
    - critical: 响应时间超过此值时触发严重告警
    """
    warning: float = 500.0     # 响应时间 > 500ms 触发 warning
    critical: float = 1000.0   # 响应时间 > 1000ms 触发 critical


@dataclass
class ErrorRateThreshold(ThresholdConfig):
    """
    错误率阈值（百分比）
    - warning: 错误率超过此值时触发警告
    - critical: 错误率超过此值时触发严重告警
    """
    warning: float = 5.0       # 错误率 > 5% 触发 warning
    critical: float = 10.0    # 错误率 > 10% 触发 critical


@dataclass
class CallTimeoutThreshold(ThresholdConfig):
    """
    调用超时阈值（秒）
    - warning: 单次调用耗时超过此值时触发警告
    - critical: 单次调用耗时超过此值时触发严重告警
    """
    warning: float = 30.0      # 超时 > 30s 触发 warning
    critical: float = 60.0     # 超时 > 60s 触发 critical


# 全局默认阈值实例
DEFAULT_HEALTH_THRESHOLD = HealthThreshold()
DEFAULT_RESPONSE_TIME_THRESHOLD = ResponseTimeThreshold()
DEFAULT_ERROR_RATE_THRESHOLD = ErrorRateThreshold()
DEFAULT_CALL_TIMEOUT_THRESHOLD = CallTimeoutThreshold()


def evaluate_health(score: float) -> AlertLevel:
    """评估健康分数"""
    return DEFAULT_HEALTH_THRESHOLD.evaluate(score)


def evaluate_response_time(ms: float) -> AlertLevel:
    """评估响应时间（毫秒）"""
    return DEFAULT_RESPONSE_TIME_THRESHOLD.evaluate(ms)


def evaluate_error_rate(rate: float) -> AlertLevel:
    """评估错误率（百分比）"""
    return DEFAULT_ERROR_RATE_THRESHOLD.evaluate(rate)


def evaluate_call_timeout(seconds: float) -> AlertLevel:
    """评估调用超时（秒）"""
    return DEFAULT_CALL_TIMEOUT_THRESHOLD.evaluate(seconds)
