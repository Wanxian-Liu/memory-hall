"""
记忆殿堂-观自在 V3.0.0 - 健康检查模块

六维指标:
1. 任务成功率 (task_success_rate)
2. 平均步数 (steps_per_task)  
3. Token消耗 (token_per_task)
4. 工具失败率 (tool_failure_rate)
5. 验证通过率 (verification_pass_rate)
6. 延迟百分位 (latency_p50/p95/p99)

断路器状态面板:
- 萃取断路器
- 归一断路器
- 通感断路器
- 分类断路器

问题诊断:
- 自适应阈值 (IQR)
- 根因分析
- 修复建议
"""

from .enums import HealthStatus, CircuitState
from .data_classes import SixDimensionData, CircuitBreakerInfo, DiagnosisResult
from .threshold import AdaptiveThresholdCalculator
from .circuit_breaker import CircuitBreaker
from .metrics import SixDimensionMetrics
from .panel import CircuitBreakerPanel
from .diagnostic import DiagnosticEngine
from .checker import HealthChecker

__all__ = [
    # 枚举
    "HealthStatus",
    "CircuitState",
    # 数据类
    "SixDimensionData",
    "CircuitBreakerInfo",
    "DiagnosisResult",
    # 类
    "AdaptiveThresholdCalculator",
    "CircuitBreaker",
    "SixDimensionMetrics",
    "CircuitBreakerPanel",
    "DiagnosticEngine",
    "HealthChecker",
]

__version__ = "3.0.0"
