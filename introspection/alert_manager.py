"""
Mimir-Core 告警管理器
introspection/alert_manager.py

负责统一管理、发送和追踪系统告警。
与 ProblemClassifier 和 Threshold 模块集成。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from .problem_classifier import ProblemClassifier, ClassifiedProblem as ProblemRecord, Severity as ProblemSeverity, ImpactScope as ProblemScope

# Note: thresholds import is lazy to avoid module-load assertion bug in thresholds.py
# See: thresholds.py line 33 - HealthThreshold(warning=70, critical=50) violates invariant


class AlertSeverity(Enum):
    """告警严重程度枚举"""
    CRITICAL = "CRITICAL"  # 致命告警
    ERROR = "ERROR"        # 错误告警
    WARNING = "WARNING"   # 警告告警
    INFO = "INFO"         # 信息告警


class _AlertLevel(Enum):
    """内部告警级别（与 thresholds.AlertLevel 兼容，但本地定义以避免导入问题）"""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


# 严重程度映射：ProblemSeverity -> AlertSeverity
_SEVERITY_MAP = {
    ProblemSeverity.CRITICAL: AlertSeverity.CRITICAL,
    ProblemSeverity.ERROR: AlertSeverity.ERROR,
    ProblemSeverity.WARNING: AlertSeverity.WARNING,
    ProblemSeverity.INFO: AlertSeverity.INFO,
}


@dataclass
class Alert:
    """告警数据模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    severity: AlertSeverity = AlertSeverity.INFO
    module: str = ""
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    tags: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "module": self.module,
            "message": self.message,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "tags": self.tags,
        }

    @classmethod
    def from_problem_record(cls, record: ProblemRecord) -> "Alert":
        """从 ProblemRecord 创建 Alert"""
        return cls(
            severity=_SEVERITY_MAP.get(record.severity, AlertSeverity.INFO),
            module=record.module_name or "unknown",
            message=record.message,
            timestamp=record.timestamp,
            tags={
                "problem_type": record.problem_type.name,
                "scope": record.scope.name,
                "error_code": record.error_code,
            },
        )


class AlertChannel:
    """告警发送渠道基类"""

    def send(self, alert: Alert) -> bool:
        raise NotImplementedError


class ConsoleAlertChannel(AlertChannel):
    """控制台告警渠道"""

    def send(self, alert: Alert) -> bool:
        severity_tag = f"[{alert.severity.value}]"
        print(f"{severity_tag} [{alert.module}] {alert.message}")
        return True


class CallbackAlertChannel(AlertChannel):
    """回调告警渠道"""

    def __init__(self, callback: Callable[[Alert], bool]):
        self.callback = callback

    def send(self, alert: Alert) -> bool:
        try:
            return self.callback(alert)
        except Exception:
            return False


class AlertManager:
    """
    告警管理器
    
    统一管理告警的创建、发送和追踪。
    集成 ProblemClassifier 和 Threshold 模块。
    """

    def __init__(self):
        self._active_alerts: list[Alert] = []
        self._channels: list[AlertChannel] = [ConsoleAlertChannel()]
        self._classifier: Optional[ProblemClassifier] = None

    def add_channel(self, channel: AlertChannel) -> None:
        """添加告警发送渠道"""
        self._channels.append(channel)

    def set_classifier(self, classifier: ProblemClassifier) -> None:
        """设置问题分类器"""
        self._classifier = classifier

    def send_alert(
        self,
        severity: AlertSeverity,
        module: str,
        message: str,
        tags: Optional[dict] = None,
    ) -> Alert:
        """
        发送告警
        
        Args:
            severity: 告警严重程度
            module: 触发告警的模块名称
            message: 告警消息
            tags: 额外标签
            
        Returns:
            创建的 Alert 对象
        """
        alert = Alert(
            severity=severity,
            module=module,
            message=message,
            tags=tags or {},
        )
        self._active_alerts.append(alert)

        # 通过所有渠道发送
        for channel in self._channels:
            channel.send(alert)

        return alert

    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        module: Optional[str] = None,
    ) -> list[Alert]:
        """
        获取活跃告警
        
        Args:
            severity: 按严重程度过滤（可选）
            module: 按模块过滤（可选）
            
        Returns:
            活跃告警列表
        """
        alerts = [a for a in self._active_alerts if not a.resolved]

        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]
        if module is not None:
            alerts = [a for a in alerts if a.module == module]

        return alerts

    def resolve_alert(self, alert_id: str) -> bool:
        """标记告警为已解决"""
        for alert in self._active_alerts:
            if alert.id == alert_id:
                alert.resolved = True
                return True
        return False

    def classify_and_alert(
        self,
        raw_message: str,
        module: str,
        raw_data: Optional[dict] = None,
    ) -> Optional[Alert]:
        """
        使用 ProblemClassifier 分类并发送告警
        
        Args:
            raw_message: 原始消息/日志内容
            module: 模块名称
            raw_data: 原始数据字典
            
        Returns:
            创建的 Alert，或 None（如果不需要告警）
        """
        if self._classifier is None:
            self._classifier = ProblemClassifier()

        problem = self._classifier.classify(raw_message, raw_data or {})

        # 仅对 WARNING 及以上级别告警
        if problem.severity in (ProblemSeverity.WARNING, ProblemSeverity.ERROR, ProblemSeverity.CRITICAL):
            return self.send_alert(
                severity=_SEVERITY_MAP.get(problem.severity, AlertSeverity.INFO),
                module=module,
                message=problem.message,
                tags={
                    "problem_type": problem.problem_type.name,
                    "scope": problem.scope.name,
                    "error_code": problem.error_code,
                },
            )
        return None

    def threshold_alert(
        self,
        metric_name: str,
        value: float,
        module: str,
        metric_type: str = "health",
    ) -> Optional[Alert]:
        """
        基于阈值评估发送告警
        
        Args:
            metric_name: 指标名称
            value: 指标值
            module: 模块名称
            metric_type: 指标类型 (health/response_time/error_rate/timeout)
            
        Returns:
            创建的 Alert，或 None（如果指标正常）
        """
        # 健康分数：值越低越差（语义与其他指标相反）
        if metric_type == "health":
            # thresholds.py 的 HealthThreshold 断言 warning < critical
            # 但健康分数中 lower = worse，所以 warning=70, critical=50 的语义是反的
            # 这里修正逻辑：value <= critical -> CRITICAL, value <= warning -> WARNING
            if value <= 50.0:  # critical threshold
                level = _AlertLevel.CRITICAL
            elif value <= 70.0:  # warning threshold
                level = _AlertLevel.WARNING
            else:
                level = _AlertLevel.OK
        elif metric_type == "response_time":
            from .thresholds import evaluate_response_time
            level = evaluate_response_time(value)
        elif metric_type == "error_rate":
            from .thresholds import evaluate_error_rate
            level = evaluate_error_rate(value)
        elif metric_type == "timeout":
            from .thresholds import evaluate_call_timeout
            level = evaluate_call_timeout(value)
        else:
            level = _AlertLevel.OK

        if level == _AlertLevel.CRITICAL:
            severity = AlertSeverity.CRITICAL
        elif level == _AlertLevel.WARNING:
            severity = AlertSeverity.WARNING
        else:
            return None

        return self.send_alert(
            severity=severity,
            module=module,
            message=f"{metric_name} {level.value.upper()}: {value}",
            tags={"metric_type": metric_type, "value": value},
        )


# 全局默认实例
_default_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """获取全局告警管理器实例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = AlertManager()
    return _default_manager


def send_alert(
    severity: AlertSeverity,
    module: str,
    message: str,
    tags: Optional[dict] = None,
) -> Alert:
    """快捷函数：发送告警"""
    return get_alert_manager().send_alert(severity, module, message, tags)


def get_active_alerts(
    severity: Optional[AlertSeverity] = None,
    module: Optional[str] = None,
) -> list[Alert]:
    """快捷函数：获取活跃告警"""
    return get_alert_manager().get_active_alerts(severity, module)
