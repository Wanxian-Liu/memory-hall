"""
状态汇总API - M2.2: 基于ProbeRegistry的状态聚合
===============================================

整合ProbeRegistry探针系统，提供：
- 按状态类型聚合（HEALTHY/DEGRADED/FAILED等）
- 按模块类型聚合（agent/health/gateway等）
- 状态变更历史记录
- 告警列表（支持阈值配置）

参考claw-code设计：
- 结构化健康检查返回数据
- 支持时间范围过滤
- 可配置告警阈值

使用方式:
    from introspection.status_api import StatusAggregator, get_aggregator

    aggregator = get_aggregator()

    # 完整汇总
    summary = aggregator.get_full_summary()

    # 按状态聚合
    by_state = aggregator.get_aggregate_by_state()

    # 按模块类型聚合
    by_type = aggregator.get_aggregate_by_module_type()

    # 状态变更历史
    history = aggregator.get_state_history(hours=24)

    # 告警列表
    alerts = aggregator.get_alerts(threshold="warning")

    # 时间范围过滤
    filtered = aggregator.get_status_in_range(
        start_time="2026-04-01T00:00:00",
        end_time="2026-04-12T23:59:59"
    )
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# 告警级别枚举
# ---------------------------------------------------------------------------

class AlertLevel(Enum):
    """告警级别"""
    OK = "ok"           # 正常
    INFO = "info"       # 信息
    WARNING = "warning" # 警告
    ERROR = "error"     # 错误
    CRITICAL = "critical"  # 严重


class AlertSeverity(Enum):
    """告警严重程度（数值越小越严重）"""
    CRITICAL = 1
    ERROR = 2
    WARNING = 3
    INFO = 4
    OK = 5


# ---------------------------------------------------------------------------
# 告警数据
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    """告警信息"""
    alert_id: str
    module_id: str
    level: AlertLevel
    message: str
    timestamp: str
    state: str  # 触发告警的状态
    count: int = 1  # 出现次数
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "module_id": self.module_id,
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "state": self.state,
            "count": self.count,
            "acknowledged": self.acknowledged,
        }


# ---------------------------------------------------------------------------
# 状态变更记录
# ---------------------------------------------------------------------------

@dataclass
class StateChangeRecord:
    """状态变更记录"""
    module_id: str
    from_state: str
    to_state: str
    timestamp: str
    duration_seconds: Optional[float] = None  # 在前一个状态的持续时间

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
        }


# ---------------------------------------------------------------------------
# 聚合结果
# ---------------------------------------------------------------------------

@dataclass
class StateAggregate:
    """按状态聚合的结果"""
    state: str
    count: int
    modules: List[str]
    percentage: float
    avg_call_count: float
    last_change: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "count": self.count,
            "modules": self.modules,
            "percentage": round(self.percentage, 2),
            "avg_call_count": round(self.avg_call_count, 2),
            "last_change": self.last_change,
        }


@dataclass
class ModuleTypeAggregate:
    """按模块类型聚合的结果"""
    module_type: str
    total: int
    healthy: int
    degraded: int
    failed: int
    unknown: int
    health_score: float  # 0.0-1.0 健康分数

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_type": self.module_type,
            "total": self.total,
            "healthy": self.healthy,
            "degraded": self.degraded,
            "failed": self.failed,
            "unknown": self.unknown,
            "health_score": round(self.health_score, 3),
        }


# ---------------------------------------------------------------------------
# 告警阈值配置
# ---------------------------------------------------------------------------

@dataclass
class AlertThreshold:
    """告警阈值配置"""
    # 状态阈值：超过这个数量的FAILED模块触发告警
    failed_threshold: int = 1
    # 降级阈值：超过这个数量的DEGRADED模块触发告警
    degraded_threshold: int = 3
    # 健康分数阈值：低于这个分数触发告警
    health_score_threshold: float = 0.7
    # 调用超时阈值（秒）
    call_timeout_threshold: float = 30.0
    # 未知状态超时（秒）- 超过这个时间未检查的模块
    unknown_timeout_seconds: float = 3600.0  # 1小时

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failed_threshold": self.failed_threshold,
            "degraded_threshold": self.degraded_threshold,
            "health_score_threshold": self.health_score_threshold,
            "call_timeout_threshold": self.call_timeout_threshold,
            "unknown_timeout_seconds": self.unknown_timeout_seconds,
        }


# ---------------------------------------------------------------------------
# 状态汇总器
# ---------------------------------------------------------------------------

class StatusAggregator:
    """
    状态汇总API - 基于ProbeRegistry提供聚合视图。

    功能：
    1. 按状态类型聚合（HEALTHY/DEGRADED/FAILED等）
    2. 按模块类型聚合（agent/health/gateway等）
    3. 状态变更历史
    4. 告警列表（支持阈值配置）
    5. 时间范围过滤

    设计参考claw-code：
    - 线程安全的聚合操作
    - 累积输出模式
    - 可配置告警阈值
    """

    def __init__(
        self,
        project_root: Optional[str] = None,
        threshold: Optional[AlertThreshold] = None,
    ):
        if project_root is None:
            from pathlib import Path
            self.project_root = Path(__file__).parent.parent.resolve()
        else:
            from pathlib import Path
            self.project_root = Path(project_root)

        self._lock = threading.RLock()
        self._threshold = threshold or AlertThreshold()
        self._alerts: Dict[str, Alert] = {}  # alert_id -> Alert
        self._state_history: List[StateChangeRecord] = []  # 所有状态变更记录
        self._last_state: Dict[str, str] = {}  # module_id -> last known state
        self._last_state_time: Dict[str, str] = {}  # module_id -> last state change time

        # 探针注册表（延迟导入）
        self._probes = None

    # -------------------------------------------------------------------------
    # 依赖注入
    # -------------------------------------------------------------------------

    @property
    def probes(self):
        """获取探针注册表（延迟加载）"""
        if self._probes is None:
            from introspection.status_probes import get_probes
            self._probes = get_probes()
            self._probes.initialize()
            # 注册状态变更回调
            self._probes.on_state_change(self._on_probe_state_change)
        return self._probes

    def _on_probe_state_change(self, event) -> None:
        """探针状态变更回调"""
        with self._lock:
            module_id = event.module_id
            old_state = event.old_state.value if hasattr(event.old_state, 'value') else str(event.old_state)
            new_state = event.new_state.value if hasattr(event.new_state, 'value') else str(event.new_state)
            timestamp = event.timestamp

            # 计算前一个状态的持续时间
            duration = None
            if module_id in self._last_state_time:
                try:
                    last_time = datetime.fromisoformat(self._last_state_time[module_id])
                    curr_time = datetime.fromisoformat(timestamp)
                    duration = (curr_time - last_time).total_seconds()
                except Exception:
                    pass

            # 记录变更
            record = StateChangeRecord(
                module_id=module_id,
                from_state=old_state,
                to_state=new_state,
                timestamp=timestamp,
                duration_seconds=duration,
            )
            self._state_history.append(record)
            self._last_state[module_id] = old_state
            self._last_state_time[module_id] = timestamp

            # 生成告警
            self._check_and_create_alert(module_id, old_state, new_state, timestamp)

    def _check_and_create_alert(
        self,
        module_id: str,
        from_state: str,
        to_state: str,
        timestamp: str,
    ) -> None:
        """检查是否需要创建告警"""
        alert_id = f"{module_id}:{to_state}"

        # 确定告警级别
        level = AlertLevel.OK
        message = ""

        if to_state == "failed":
            level = AlertLevel.ERROR
            message = f"模块 {module_id} 状态变为 FAILED"
        elif to_state == "degraded":
            level = AlertLevel.WARNING
            message = f"模块 {module_id} 状态降级为 DEGRADED"
        elif from_state == "failed" and to_state == "healthy":
            level = AlertLevel.INFO
            message = f"模块 {module_id} 从 FAILED 恢复为 HEALTHY"
        elif to_state == "unavailable":
            level = AlertLevel.ERROR
            message = f"模块 {module_id} 不可用 (UNAVAILABLE)"
        else:
            return  # 不需要告警的状态变更

        # 更新或创建告警
        if alert_id in self._alerts:
            alert = self._alerts[alert_id]
            alert.count += 1
            alert.timestamp = timestamp
            alert.state = to_state
            if level.value < AlertLevel[alert.level.upper()].value:
                alert.level = AlertLevel[level.name]
        else:
            self._alerts[alert_id] = Alert(
                alert_id=alert_id,
                module_id=module_id,
                level=level,
                message=message,
                timestamp=timestamp,
                state=to_state,
            )

    # -------------------------------------------------------------------------
    # 阈值配置
    # -------------------------------------------------------------------------

    def set_threshold(self, threshold: AlertThreshold) -> None:
        """设置告警阈值"""
        with self._lock:
            self._threshold = threshold

    def get_threshold(self) -> AlertThreshold:
        """获取当前告警阈值"""
        return self._threshold

    # -------------------------------------------------------------------------
    # 聚合查询 - 按状态类型
    # -------------------------------------------------------------------------

    def get_aggregate_by_state(self) -> Dict[str, StateAggregate]:
        """
        按状态类型聚合所有模块。

        Returns:
            Dict[state, StateAggregate] - 以状态为键的聚合结果
        """
        with self._lock:
            all_probes = self.probes.all_probes()
            if not all_probes:
                return {}

            # 按状态分组
            by_state: Dict[str, List[str]] = defaultdict(list)
            call_counts: Dict[str, List[int]] = defaultdict(list)
            last_changes: Dict[str, Optional[str]] = {}

            for module_id, probe in all_probes.items():
                state = probe.state.value
                by_state[state].append(module_id)
                call_counts[state].append(probe.call_count)

                # 获取最近状态变更
                if probe.state_history:
                    last_changes[state] = probe.state_history[-1]["timestamp"]

            # 构建聚合结果
            total = len(all_probes)
            result = {}

            for state, modules in by_state.items():
                avg_calls = sum(call_counts[state]) / len(call_counts[state]) if call_counts[state] else 0

                result[state] = StateAggregate(
                    state=state,
                    count=len(modules),
                    modules=sorted(modules),
                    percentage=(len(modules) / total * 100) if total > 0 else 0,
                    avg_call_count=avg_calls,
                    last_change=last_changes.get(state),
                )

            return result

    # -------------------------------------------------------------------------
    # 聚合查询 - 按模块类型
    # -------------------------------------------------------------------------

    def get_aggregate_by_module_type(self) -> Dict[str, ModuleTypeAggregate]:
        """
        按模块顶层类型聚合（agent/health/gateway等）。

        Returns:
            Dict[module_type, ModuleTypeAggregate] - 以模块类型为键的聚合结果
        """
        with self._lock:
            all_probes = self.probes.all_probes()
            if not all_probes:
                return {}

            # 获取模块注册表来获取top_type
            from interfaces.modules import get_registry
            reg = get_registry()

            # 按模块类型分组
            by_type: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

            for module_id, probe in all_probes.items():
                top_type = reg.get_top_type(module_id)
                by_type[top_type][probe.state.value].append(module_id)

            # 构建聚合结果
            result = {}

            for module_type, states in by_type.items():
                total = sum(len(modules) for modules in states.values())
                healthy = len(states.get("healthy", []))
                degraded = len(states.get("degraded", []))
                failed = len(states.get("failed", []))
                unknown = len(states.get("unknown", []))

                # 计算健康分数 (weighted)
                health_score = 0.0
                if total > 0:
                    health_score = (healthy * 1.0 + degraded * 0.5 + failed * 0.0 + unknown * 0.3) / total

                result[module_type] = ModuleTypeAggregate(
                    module_type=module_type,
                    total=total,
                    healthy=healthy,
                    degraded=degraded,
                    failed=failed,
                    unknown=unknown,
                    health_score=health_score,
                )

            return result

    # -------------------------------------------------------------------------
    # 告警列表
    # -------------------------------------------------------------------------

    def get_alerts(
        self,
        min_level: Optional[AlertLevel] = None,
        module_id: Optional[str] = None,
        unacknowledged_only: bool = False,
    ) -> List[Alert]:
        """
        获取告警列表。

        Args:
            min_level: 最小告警级别（返回 >= 此级别的告警）
            module_id: 过滤特定模块
            unacknowledged_only: 仅返回未确认的告警

        Returns:
            List[Alert] - 告警列表（按严重程度排序）
        """
        with self._lock:
            alerts = list(self._alerts.values())

            # 应用过滤
            if min_level is not None:
                alerts = [a for a in alerts if AlertSeverity[a.level.name.upper()].value <= AlertSeverity[min_level.name.upper()].value]

            if module_id is not None:
                alerts = [a for a in alerts if a.module_id == module_id]

            if unacknowledged_only:
                alerts = [a for a in alerts if not a.acknowledged]

            # 按严重程度排序
            alerts.sort(key=lambda a: AlertSeverity[a.level.name.upper()].value)

            return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        with self._lock:
            if alert_id in self._alerts:
                self._alerts[alert_id].acknowledged = True
                return True
            return False

    def clear_alert(self, alert_id: str) -> bool:
        """清除告警"""
        with self._lock:
            if alert_id in self._alerts:
                del self._alerts[alert_id]
                return True
            return False

    def get_active_alert_count(self) -> Dict[str, int]:
        """获取各级别活跃告警数量"""
        with self._lock:
            counts: Dict[str, int] = defaultdict(int)
            for alert in self._alerts.values():
                if not alert.acknowledged:
                    counts[alert.level.value] += 1
            return dict(counts)

    # -------------------------------------------------------------------------
    # 状态变更历史
    # -------------------------------------------------------------------------

    def get_state_history(
        self,
        hours: Optional[float] = None,
        module_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[StateChangeRecord]:
        """
        获取状态变更历史。

        Args:
            hours: 只返回最近N小时的历史
            module_id: 过滤特定模块
            limit: 最大返回条数

        Returns:
            List[StateChangeRecord] - 状态变更记录（按时间倒序）
        """
        with self._lock:
            history = list(self._state_history)

            # 时间过滤
            if hours is not None:
                cutoff = datetime.now() - timedelta(hours=hours)
                history = [
                    r for r in history
                    if datetime.fromisoformat(r.timestamp) >= cutoff
                ]

            # 模块过滤
            if module_id is not None:
                history = [r for r in history if r.module_id == module_id]

            # 限制条数
            history = history[-limit:]

            return history

    def get_module_state_timeline(self, module_id: str) -> List[StateChangeRecord]:
        """获取特定模块的状态变更时间线"""
        with self._lock:
            return [r for r in self._state_history if r.module_id == module_id]

    # -------------------------------------------------------------------------
    # 时间范围过滤
    # -------------------------------------------------------------------------

    def get_status_in_range(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        module_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取时间范围内的状态快照。

        Args:
            start_time: ISO格式开始时间
            end_time: ISO格式结束时间
            module_id: 过滤特定模块

        Returns:
            包含时间范围内的状态变更统计
        """
        with self._lock:
            history = self._state_history

            # 时间过滤
            if start_time is not None:
                start_dt = datetime.fromisoformat(start_time)
                history = [r for r in history if datetime.fromisoformat(r.timestamp) >= start_dt]

            if end_time is not None:
                end_dt = datetime.fromisoformat(end_time)
                history = [r for r in history if datetime.fromisoformat(r.timestamp) <= end_dt]

            # 模块过滤
            if module_id is not None:
                history = [r for r in history if r.module_id == module_id]

            # 统计
            transition_counts: Dict[str, int] = defaultdict(int)
            for r in history:
                transition_counts[f"{r.from_state}->{r.to_state}"] += 1

            return {
                "start_time": start_time,
                "end_time": end_time,
                "module_id": module_id,
                "total_transitions": len(history),
                "transition_counts": dict(transition_counts),
                "records": [r.to_dict() for r in history[-50:]],  # 最多50条详情
            }

    # -------------------------------------------------------------------------
    # 完整汇总
    # -------------------------------------------------------------------------

    def get_full_summary(self) -> Dict[str, Any]:
        """
        获取完整的状态汇总（所有聚合视图）。

        Returns:
            包含所有聚合信息的完整汇总
        """
        with self._lock:
            # 刷新所有探针
            self.probes.refresh_all()

            # 获取各维度聚合
            by_state = self.get_aggregate_by_state()
            by_type = self.get_aggregate_by_module_type()
            alerts = self.get_alerts()
            active_alert_counts = self.get_active_alert_count()
            recent_history = self.get_state_history(hours=24, limit=50)

            # 计算系统整体状态
            overall = self._compute_overall_status(by_state, active_alert_counts)

            # 计算总模块数和健康模块数
            total_modules = sum(a.count for a in by_state.values())
            healthy_modules = sum(a.count for a in by_state.values() if a.state == "healthy")

            return {
                "timestamp": datetime.now().isoformat(),
                "overall_status": overall,
                "total_modules": total_modules,
                "healthy_modules": healthy_modules,
                "health_percentage": round(healthy_modules / total_modules * 100, 2) if total_modules > 0 else 0,
                "by_state": {k: v.to_dict() for k, v in by_state.items()},
                "by_module_type": {k: v.to_dict() for k, v in by_type.items()},
                "alerts": {
                    "total": len(alerts),
                    "active": len([a for a in alerts if not a.acknowledged]),
                    "by_level": active_alert_counts,
                    "items": [a.to_dict() for a in alerts[:20]],  # 最多20条
                },
                "state_history": {
                    "total_records": len(self._state_history),
                    "recent_24h": len([r for r in self._state_history
                                     if datetime.fromisoformat(r.timestamp) >= datetime.now() - timedelta(hours=24)]),
                    "recent_records": [r.to_dict() for r in recent_history],
                },
                "threshold": self._threshold.to_dict(),
            }

    def _compute_overall_status(
        self,
        by_state: Dict[str, StateAggregate],
        alert_counts: Dict[str, int],
    ) -> str:
        """计算系统整体状态"""
        total = sum(a.count for a in by_state.values())
        if total == 0:
            return "unknown"

        failed = by_state.get("failed", StateAggregate("failed", 0, [], 0, 0)).count
        degraded = by_state.get("degraded", StateAggregate("degraded", 0, [], 0, 0)).count
        healthy = by_state.get("healthy", StateAggregate("healthy", 0, [], 0, 0)).count

        # 基于告警级别提升状态
        if alert_counts.get("critical", 0) > 0:
            return "critical"
        if failed > self._threshold.failed_threshold:
            return "failed"
        if alert_counts.get("error", 0) > 0 and failed > 0:
            return "failed"
        if degraded > self._threshold.degraded_threshold:
            return "degraded"
        if alert_counts.get("warning", 0) > 0 and degraded > 0:
            return "degraded"
        if healthy == total:
            return "healthy"
        if healthy > total * 0.8:
            return "healthy"
        return "degraded"

    # -------------------------------------------------------------------------
    # 便捷方法
    # -------------------------------------------------------------------------

    def get_quick_status(self) -> Dict[str, str]:
        """获取快速状态（用于健康检查端点）"""
        summary = self.get_full_summary()
        return {
            "status": summary["overall_status"],
            "healthy": f"{summary['healthy_modules']}/{summary['total_modules']}",
            "alerts": summary["alerts"]["active"],
        }

    def check_module_health(self, module_id: str) -> Dict[str, Any]:
        """检查单个模块的健康状态"""
        with self._lock:
            probe = self.probes.get_probe(module_id)
            if not probe:
                return {
                    "module_id": module_id,
                    "found": False,
                    "status": "unknown",
                }

            # 获取该模块相关的告警
            module_alerts = self.get_alerts(module_id=module_id)

            # 获取该模块的状态历史
            timeline = self.get_module_state_timeline(module_id)

            return {
                "module_id": module_id,
                "found": True,
                "status": probe.state.value,
                "importable": probe.importable,
                "usable": probe.usable,
                "call_count": probe.call_count,
                "last_check": probe.last_check,
                "last_call": probe.last_call,
                "error": probe.error,
                "alerts": [a.to_dict() for a in module_alerts],
                "state_timeline": [r.to_dict() for r in timeline[-10:]],
                "recent_state": probe.state_history[-3:] if probe.state_history else [],
            }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_aggregator: Optional[StatusAggregator] = None
_aggregator_lock = threading.Lock()


def get_aggregator(threshold: Optional[AlertThreshold] = None) -> StatusAggregator:
    """获取全局状态汇总器（单例）"""
    global _aggregator
    if _aggregator is None:
        with _aggregator_lock:
            if _aggregator is None:
                _aggregator = StatusAggregator(threshold=threshold)
    return _aggregator


def reset_aggregator() -> None:
    """重置全局汇总器（用于测试）"""
    global _aggregator
    with _aggregator_lock:
        _aggregator = None


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    """CLI入口 - 展示完整状态汇总"""
    import json

    aggregator = get_aggregator()
    summary = aggregator.get_full_summary()

    print(f"\n📊 Mimir-Core 状态汇总")
    print(f"=" * 50)
    print(f"⏰ 时间: {summary['timestamp']}")
    print(f"🏥 整体状态: {summary['overall_status']}")
    print(f"📈 健康率: {summary['health_percentage']}%")
    print(f"   ({summary['healthy_modules']}/{summary['total_modules']} 模块)")

    print(f"\n📋 按状态聚合:")
    for state, agg in summary["by_state"].items():
        emoji = {
            "healthy": "✅",
            "degraded": "⚠️",
            "failed": "❌",
            "unavailable": "🚫",
            "unknown": "❓",
            "disabled": "🔌",
        }.get(state, "❓")
        print(f"   {emoji} {state}: {agg['count']} 模块 ({agg['percentage']}%)")

    print(f"\n📦 按模块类型聚合:")
    for mtype, agg in summary["by_module_type"].items():
        score_bar = "█" * int(agg['health_score'] * 10) + "░" * (10 - int(agg['health_score'] * 10))
        print(f"   {mtype}: [{score_bar}] {agg['health_score']:.2f} " +
              f"(H:{agg['healthy']} D:{agg['degraded']} F:{agg['failed']})")

    print(f"\n🚨 告警 ({summary['alerts']['active']} 活跃):")
    if summary['alerts']['items']:
        for alert in summary['alerts']['items'][:5]:
            level_emoji = {
                "critical": "🔴",
                "error": "❌",
                "warning": "⚠️",
                "info": "ℹ️",
            }.get(alert['level'], "❓")
            print(f"   {level_emoji} [{alert['level']}] {alert['message']}")
    else:
        print("   无活跃告警 ✅")

    print(f"\n📜 最近状态变更 ({summary['state_history']['recent_24h']} 条/24h):")
    for record in summary['state_history']['recent_records'][-5:]:
        print(f"   {record['timestamp'][:19]} | {record['module_id']}: {record['from_state']} -> {record['to_state']}")

    print(f"\n🔧 告警阈值:")
    for k, v in summary['threshold'].items():
        print(f"   {k}: {v}")

    return summary


if __name__ == "__main__":
    main()
