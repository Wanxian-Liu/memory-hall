"""
MonitorCollector - 指标采集器基础框架
Phase 0 基础设施

职责:
- 收集系统指标 (内存、CPU、响应时间等)
- 支持自定义指标钩子
- 提供异步指标采集接口
"""

import time
import psutil
import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Protocol
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""
    SYSTEM = "system"           # 系统指标
    APPLICATION = "application" # 应用指标
    CUSTOM = "custom"           # 自定义指标


@dataclass
class MetricSample:
    """指标采样"""
    name: str
    value: float
    timestamp: float
    metric_type: MetricType
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


@dataclass 
class MetricsSnapshot:
    """指标快照"""
    timestamp: float
    samples: List[MetricSample]
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector(Protocol):
    """指标采集器协议"""
    async def collect(self) -> Dict[str, Any]: ...


class MonitorCollector:
    """
    指标采集器
    
    提供统一的指标采集接口，支持:
    - 系统指标 (CPU、内存、磁盘)
    - 应用指标 (响应时间、错误率)
    - 自定义指标钩子
    
    Usage:
        collector = MonitorCollector()
        await collector.register_hook("my_metric", my_hook)
        metrics = await collector.collect_all()
    """
    
    def __init__(self, collect_interval: float = 5.0):
        self.collect_interval = collect_interval
        self._last_collect_time: float = 0
        
        # 内置采集器
        self._builtin_collectors: Dict[str, Callable] = {
            "memory_usage": self._collect_memory,
            "cpu_usage": self._collect_cpu,
            "disk_usage": self._collect_disk,
            "network_io": self._collect_network,
        }
        
        # 自定义采集器
        self._custom_hooks: Dict[str, Callable] = {}
        
        # 历史采样
        self._sample_history: List[MetricsSnapshot] = []
        self._max_history = 100
        
        # 指标聚合
        self._aggregations: Dict[str, List[float]] = {}
    
    async def register_hook(
        self, 
        name: str, 
        collector: Callable,
        metric_type: MetricType = MetricType.CUSTOM
    ) -> None:
        """
        注册自定义指标采集钩子
        
        Args:
            name: 指标名称
            collector: 采集函数 (同步或异步)
            metric_type: 指标类型
        """
        self._custom_hooks[name] = collector
        logger.info(f"Registered custom hook: {name}")
    
    async def unregister_hook(self, name: str) -> bool:
        """取消注册指标采集钩子"""
        if name in self._custom_hooks:
            del self._custom_hooks[name]
            logger.info(f"Unregistered hook: {name}")
            return True
        return False
    
    async def collect_all(self) -> Dict[str, Any]:
        """
        采集所有指标
        
        Returns:
            Dict containing all collected metrics
        """
        self._last_collect_time = time.time()
        samples = []
        metrics = {}
        
        # 采集内置指标
        for name, collector in self._builtin_collectors.items():
            try:
                if asyncio.iscoroutinefunction(collector):
                    value = await collector()
                else:
                    value = collector()
                
                metrics[name] = value
                
                # 创建采样
                sample = MetricSample(
                    name=name,
                    value=value,
                    timestamp=self._last_collect_time,
                    metric_type=MetricType.SYSTEM,
                    tags={"source": "builtin"}
                )
                samples.append(sample)
                
            except Exception as e:
                logger.warning(f"Failed to collect {name}: {e}")
                metrics[name] = None
        
        # 采集自定义指标
        for name, collector in self._custom_hooks.items():
            try:
                if asyncio.iscoroutinefunction(collector):
                    value = await collector()
                else:
                    value = collector()
                
                metrics[name] = value
                
                sample = MetricSample(
                    name=name,
                    value=value,
                    timestamp=self._last_collect_time,
                    metric_type=MetricType.CUSTOM,
                    tags={"source": "custom"}
                )
                samples.append(sample)
                
            except Exception as e:
                logger.warning(f"Custom hook failed for {name}: {e}")
                metrics[name] = None
        
        # 更新聚合
        for name, value in metrics.items():
            if value is not None and isinstance(value, (int, float)):
                if name not in self._aggregations:
                    self._aggregations[name] = []
                self._aggregations[name].append(value)
                if len(self._aggregations[name]) > self._max_history:
                    self._aggregations[name].pop(0)
        
        # 创建快照
        snapshot = MetricsSnapshot(
            timestamp=self._last_collect_time,
            samples=samples,
            metadata={"collector": "MonitorCollector", "version": "1.0"}
        )
        self._sample_history.append(snapshot)
        if len(self._sample_history) > self._max_history:
            self._sample_history.pop(0)
        
        # 添加汇总统计
        metrics["_summary"] = self._compute_summary()
        metrics["timestamp"] = self._last_collect_time
        
        return metrics
    
    def _compute_summary(self) -> Dict[str, Any]:
        """计算指标汇总统计"""
        summary = {}
        for name, values in self._aggregations.items():
            if values:
                summary[name] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "count": len(values)
                }
        return summary
    
    # ========== 内置采集器实现 ==========
    
    def _collect_memory(self) -> float:
        """采集内存使用率"""
        try:
            mem = psutil.virtual_memory()
            return mem.percent / 100.0  # 归一化到 0-1
        except Exception:
            return 0.0
    
    def _collect_cpu(self) -> float:
        """采集CPU使用率"""
        try:
            return psutil.cpu_percent(interval=0.1) / 100.0
        except Exception:
            return 0.0
    
    def _collect_disk(self) -> float:
        """采集磁盘使用率"""
        try:
            disk = psutil.disk_usage('/')
            return disk.percent / 100.0
        except Exception:
            return 0.0
    
    def _collect_network(self) -> Dict[str, Any]:
        """采集网络IO"""
        try:
            net = psutil.net_io_counters()
            return {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
                "packets_sent": net.packets_sent,
                "packets_recv": net.packets_recv
            }
        except Exception:
            return {}
    
    # ========== 查询接口 ==========
    
    def get_latest(self, metric_name: str) -> Optional[float]:
        """获取最新指标值"""
        if self._sample_history:
            latest = self._sample_history[-1]
            for sample in latest.samples:
                if sample.name == metric_name:
                    return sample.value
        return None
    
    def get_history(self, metric_name: str, limit: int = 20) -> List[MetricSample]:
        """获取指标历史"""
        history = []
        for snapshot in self._sample_history[-limit:]:
            for sample in snapshot.samples:
                if sample.name == metric_name:
                    history.append(sample)
        return history
    
    def get_stats(self, metric_name: str) -> Dict[str, float]:
        """获取指标统计"""
        if metric_name in self._aggregations:
            values = self._aggregations[metric_name]
            return {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "latest": values[-1] if values else None
            }
        return {}
    
    def get_snapshot_count(self) -> int:
        """获取快照数量"""
        return len(self._sample_history)
    
    def clear_history(self) -> None:
        """清除历史数据"""
        self._sample_history.clear()
        self._aggregations.clear()
        logger.info("Metrics history cleared")


# ========== 便捷工厂函数 ==========

def create_default_collector() -> MonitorCollector:
    """创建默认配置采集器"""
    return MonitorCollector(collect_interval=5.0)


def create_lightweight_collector() -> MonitorCollector:
    """创建轻量级采集器 (仅基础指标)"""
    collector = MonitorCollector(collect_interval=10.0)
    # 移除网络采集以减少开销
    collector._builtin_collectors.pop("network_io", None)
    return collector


# ========== 模块导出 ==========

__all__ = [
    "MetricType",
    "MetricSample", 
    "MetricsSnapshot",
    "MonitorCollector",
    "MetricsCollector",
    "create_default_collector",
    "create_lightweight_collector",
]
