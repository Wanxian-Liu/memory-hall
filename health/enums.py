"""
记忆殿堂-观自在 V3.0.0 - 枚举定义
"""

from enum import Enum


class HealthStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ALERT = "alert"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CircuitState(str, Enum):
    CLOSED = "closed"    # 正常
    OPEN = "open"        # 熔断
    HALF_OPEN = "half_open"  # 半开


__all__ = ["HealthStatus", "CircuitState"]
