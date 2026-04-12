"""
记忆殿堂-观自在 V3.0.0 - 数据类定义
"""

from dataclasses import dataclass
from typing import Optional, List
from .enums import HealthStatus, CircuitState


@dataclass
class SixDimensionData:
    """六维指标数据"""
    task_success_rate: float = 1.0
    steps_per_task_p95: float = 0.0
    token_per_task_p95: float = 0.0
    tool_failure_rate: float = 0.0
    verification_pass_rate: float = 1.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    timestamp: str = ""


@dataclass
class CircuitBreakerInfo:
    """断路器信息"""
    name: str
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[float]
    failure_threshold: int
    recovery_timeout: int
    success_threshold: int


@dataclass
class DiagnosisResult:
    """诊断结果"""
    dimension: str
    status: HealthStatus
    current_value: float
    threshold_warning: float
    threshold_critical: float
    trend: str  # rising, falling, stable
    root_cause: str
    suggestions: List[str]
    timestamp: str = ""


__all__ = ["SixDimensionData", "CircuitBreakerInfo", "DiagnosisResult"]
