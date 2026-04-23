"""
关键指标阈值系统 - 阈值配置Profile (从 thresholds.py 拆分)
=========================================================

本模块包含：
- ThresholdProfile (完整阈值配置)
- PRESET_PROFILES (预设Profile字典)
- _build_presets() (预设构建函数)

拆分自: introspection/thresholds.py (M2.4)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict

from .threshold_config import ThresholdConfig, ThresholdLevel
from .health_thresholds import (
    HealthScoreThresholds,
    ResponseTimeThresholds,
    ErrorRateThresholds,
    ModuleTimeoutThresholds,
    CallCountThresholds,
)


# ---------------------------------------------------------------------------
# 聚合阈值配置（所有阈值打包）
# ---------------------------------------------------------------------------

@dataclass
class ThresholdProfile:
    """
    完整阈值配置Profile。

    将所有阈值分组打包，支持：
    - 整体加载/保存
    - 切换预设Profile
    - 与配置文件序列化
    """
    name: str = "default"
    description: str = "默认阈值配置"
    version: str = "1.0"
    health_score: HealthScoreThresholds = field(default_factory=HealthScoreThresholds)
    response_time: ResponseTimeThresholds = field(default_factory=ResponseTimeThresholds)
    error_rate: ErrorRateThresholds = field(default_factory=ErrorRateThresholds)
    module_timeout: ModuleTimeoutThresholds = field(default_factory=ModuleTimeoutThresholds)
    call_count: CallCountThresholds = field(default_factory=CallCountThresholds)

    # 全局开关
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "enabled": self.enabled,
            "health_score": self.health_score.to_dict(),
            "response_time": self.response_time.to_dict(),
            "error_rate": self.error_rate.to_dict(),
            "module_timeout": self.module_timeout.to_dict(),
            "call_count": self.call_count.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ThresholdProfile":
        return cls(
            name=data.get("name", "default"),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            enabled=data.get("enabled", True),
            health_score=HealthScoreThresholds.from_dict(data["health_score"]),
            response_time=ResponseTimeThresholds.from_dict(data["response_time"]),
            error_rate=ErrorRateThresholds.from_dict(data["error_rate"]),
            module_timeout=ModuleTimeoutThresholds.from_dict(data["module_timeout"]),
            call_count=CallCountThresholds.from_dict(data["call_count"]),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ThresholdProfile":
        return cls.from_dict(json.loads(json_str))


# ---------------------------------------------------------------------------
# 预设Profile
# ---------------------------------------------------------------------------

PRESET_PROFILES: Dict[str, ThresholdProfile] = {}


def _build_presets() -> Dict[str, ThresholdProfile]:
    """构建预设Profile"""
    return {
        "default": ThresholdProfile(
            name="default",
            description="默认阈值配置，适合生产环境",
        ),
        "strict": ThresholdProfile(
            name="strict",
            description="严格阈值配置，更敏感地检测问题",
            health_score=HealthScoreThresholds(
                healthy=ThresholdConfig("health_score_healthy", 0.9, 0.9, 0.0, 1.0, ThresholdLevel.OK, "严格：健康阈值"),
                degraded=ThresholdConfig("health_score_degraded", 0.6, 0.6, 0.0, 1.0, ThresholdLevel.WARNING, "严格：降级阈值"),
                failed=ThresholdConfig("health_score_failed", 0.4, 0.4, 0.0, 1.0, ThresholdLevel.ERROR, "严格：失败阈值"),
                system_healthy=ThresholdConfig("system_health_score_healthy", 0.8, 0.8, 0.0, 1.0, ThresholdLevel.WARNING, "严格：系统健康阈值"),
            ),
            response_time=ResponseTimeThresholds(
                fast=ThresholdConfig("response_time_fast", 0.3, 0.3, 0.0, 60.0, ThresholdLevel.OK, "严格：快速阈值"),
                acceptable=ThresholdConfig("response_time_acceptable", 1.0, 1.0, 0.0, 60.0, ThresholdLevel.WARNING, "严格：可接受阈值"),
                slow=ThresholdConfig("response_time_slow", 3.0, 3.0, 0.0, 60.0, ThresholdLevel.ERROR, "严格：慢响应阈值"),
                timeout=ThresholdConfig("response_time_timeout", 15.0, 15.0, 1.0, 300.0, ThresholdLevel.CRITICAL, "严格：超时阈值"),
            ),
        ),
        "relaxed": ThresholdProfile(
            name="relaxed",
            description="宽松阈值配置，适合开发环境",
            health_score=HealthScoreThresholds(
                healthy=ThresholdConfig("health_score_healthy", 0.6, 0.6, 0.0, 1.0, ThresholdLevel.OK, "宽松：健康阈值"),
                degraded=ThresholdConfig("health_score_degraded", 0.3, 0.3, 0.0, 1.0, ThresholdLevel.WARNING, "宽松：降级阈值"),
                failed=ThresholdConfig("health_score_failed", 0.1, 0.1, 0.0, 1.0, ThresholdLevel.ERROR, "宽松：失败阈值"),
                system_healthy=ThresholdConfig("system_health_score_healthy", 0.5, 0.5, 0.0, 1.0, ThresholdLevel.WARNING, "宽松：系统健康阈值"),
            ),
            response_time=ResponseTimeThresholds(
                fast=ThresholdConfig("response_time_fast", 1.0, 1.0, 0.0, 60.0, ThresholdLevel.OK, "宽松：快速阈值"),
                acceptable=ThresholdConfig("response_time_acceptable", 5.0, 5.0, 0.0, 60.0, ThresholdLevel.WARNING, "宽松：可接受阈值"),
                slow=ThresholdConfig("response_time_slow", 15.0, 15.0, 0.0, 60.0, ThresholdLevel.ERROR, "宽松：慢响应阈值"),
                timeout=ThresholdConfig("response_time_timeout", 60.0, 60.0, 1.0, 300.0, ThresholdLevel.CRITICAL, "宽松：超时阈值"),
            ),
        ),
        "development": ThresholdProfile(
            name="development",
            description="开发环境配置，最宽松",
            health_score=HealthScoreThresholds(
                healthy=ThresholdConfig("health_score_healthy", 0.5, 0.5, 0.0, 1.0, ThresholdLevel.OK, "开发：健康阈值"),
                degraded=ThresholdConfig("health_score_degraded", 0.2, 0.2, 0.0, 1.0, ThresholdLevel.WARNING, "开发：降级阈值"),
                failed=ThresholdConfig("health_score_failed", 0.05, 0.05, 0.0, 1.0, ThresholdLevel.ERROR, "开发：失败阈值"),
                system_healthy=ThresholdConfig("system_health_score_healthy", 0.4, 0.4, 0.0, 1.0, ThresholdLevel.WARNING, "开发：系统健康阈值"),
            ),
            response_time=ResponseTimeThresholds(
                fast=ThresholdConfig("response_time_fast", 2.0, 2.0, 0.0, 60.0, ThresholdLevel.OK, "开发：快速阈值"),
                acceptable=ThresholdConfig("response_time_acceptable", 10.0, 10.0, 0.0, 60.0, ThresholdLevel.WARNING, "开发：可接受阈值"),
                slow=ThresholdConfig("response_time_slow", 30.0, 30.0, 0.0, 60.0, ThresholdLevel.ERROR, "开发：慢响应阈值"),
                timeout=ThresholdConfig("response_time_timeout", 120.0, 120.0, 1.0, 300.0, ThresholdLevel.CRITICAL, "开发：超时阈值"),
            ),
        ),
    }


PRESET_PROFILES = _build_presets()
