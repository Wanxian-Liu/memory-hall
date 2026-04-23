"""
关键指标阈值系统 - 配置文件 (从 thresholds.py 拆分)
=====================================================

本模块包含：
- ThresholdLevel (枚举)
- ThresholdCheckResult (阈值检查结果)
- ThresholdChangeEvent (阈值变更事件)
- ThresholdConfig (单个阈值配置基类)

拆分自: introspection/thresholds.py (M2.4)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# 阈值级别枚举
# ---------------------------------------------------------------------------

class ThresholdLevel(Enum):
    """阈值级别（数值越小越严重）"""
    CRITICAL = 1   # 严重
    ERROR = 2      # 错误
    WARNING = 3     # 警告
    INFO = 4       # 信息
    OK = 5         # 正常


# ---------------------------------------------------------------------------
# 阈值检查结果
# ---------------------------------------------------------------------------

@dataclass
class ThresholdCheckResult:
    """阈值检查结果"""
    metric: str                    # 指标名
    value: float                   # 实际值
    threshold: float               # 触发阈值
    level: ThresholdLevel          # 触发的级别
    triggered: bool                # 是否触发
    message: str                   # 描述信息
    timestamp: str                # 检查时间
    module_id: Optional[str] = None  # 模块ID（如果是模块级别检查）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "value": round(self.value, 4),
            "threshold": round(self.threshold, 4),
            "level": self.level.name,
            "triggered": self.triggered,
            "message": self.message,
            "timestamp": self.timestamp,
            "module_id": self.module_id,
        }


@dataclass
class ThresholdChangeEvent:
    """阈值变更事件"""
    metric: str
    old_value: float
    new_value: float
    old_level: ThresholdLevel
    new_level: ThresholdLevel
    timestamp: str
    source: str = "manual"  # manual / config / system


# ---------------------------------------------------------------------------
# 阈值配置基类
# ---------------------------------------------------------------------------

@dataclass
class ThresholdConfig:
    """
    单个阈值配置。

    Attributes:
        name: 阈值名称
        default: 默认值
        value: 当前值（可动态调整）
        min_value: 最小允许值
        max_value: 最大允许值
        level: 阈值级别
        description: 描述
        enabled: 是否启用
    """
    name: str
    default: float
    value: float
    min_value: float = 0.0
    max_value: float = 1.0
    level: ThresholdLevel = ThresholdLevel.WARNING
    description: str = ""
    enabled: bool = True

    def __post_init__(self):
        # 确保 value 在有效范围内
        self.value = max(self.min_value, min(self.max_value, self.value))

    def reset(self) -> float:
        """重置为默认值"""
        old = self.value
        self.value = self.default
        return old

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "default": self.default,
            "value": self.value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "level": self.level.name,
            "description": self.description,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ThresholdConfig":
        """从字典创建"""
        return cls(
            name=data["name"],
            default=data["default"],
            value=data.get("value", data["default"]),
            min_value=data.get("min_value", 0.0),
            max_value=data.get("max_value", 1.0),
            level=ThresholdLevel[data.get("level", "WARNING").upper()],
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
        )
