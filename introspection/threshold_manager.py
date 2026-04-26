"""
关键指标阈值系统 - 阈值管理器 (从 thresholds.py 拆分)
======================================================

本模块包含：
- ThresholdManager (阈值管理器类)
- get_threshold_manager() (全局单例获取函数)
- reset_threshold_manager() (重置函数)
- main() (CLI入口)

拆分自: introspection/thresholds.py (M2.4)
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .threshold_config import ThresholdConfig, ThresholdLevel, ThresholdCheckResult, ThresholdChangeEvent
from .health_thresholds import (
    HealthScoreThresholds,
    ResponseTimeThresholds,
    ErrorRateThresholds,
    ModuleTimeoutThresholds,
    CallCountThresholds,
)
from .threshold_profile import ThresholdProfile, PRESET_PROFILES


# ---------------------------------------------------------------------------
# 阈值管理器
# ---------------------------------------------------------------------------

class ThresholdManager:
    """
    阈值管理器 - 统一管理所有阈值配置。

    功能：
    1. 集中管理所有阈值
    2. 动态调整阈值（实时生效）
    3. 阈值变更回调通知
    4. 配置文件加载/保存
    5. 指标检查（判断是否触发阈值）
    6. 与 StatusAggregator 告警系统集成

    设计参考 claw-code:
    - 线程安全的读写
    - 累积配置模式
    - 变更回调机制
    - 配置持久化

    使用示例:
        tm = get_threshold_manager()

        # 检查健康分数
        result = tm.check_health_score(0.75)

        # 检查响应时间
        result = tm.check_response_time(1.5)

        # 动态调整阈值
        tm.update_threshold("health_score.healthy", 0.75)

        # 阈值变更回调
        tm.on_threshold_change(lambda event: print(f"阈值变更: {event.metric}"))

        # 保存配置
        tm.save_to_file("thresholds.json")
    """

    def __init__(
        self,
        profile: Optional[ThresholdProfile] = None,
        config_dir: Optional[str] = None,
    ):
        if config_dir is None:
            # 与 MimirAether 内嵌的 mimicore 包对齐（旧默认曾指向 ~/.openclaw/projects/Mimir-Core/config）
            self.config_dir = Path(__file__).resolve().parents[1] / "config"
        else:
            self.config_dir = Path(config_dir)

        self._lock = threading.RLock()
        self._profile = profile or ThresholdProfile()
        self._callbacks: List[Callable[[ThresholdChangeEvent], None]] = []

        # 内置指标追踪（用于比率类计算）
        self._metric_cache: Dict[str, List[float]] = {}  # metric -> [values]
        self._metric_cache_lock = threading.Lock()

        # 与 StatusAggregator 的告警系统集成
        self._alerts_enabled = True

    # -------------------------------------------------------------------------
    # 回调管理
    # -------------------------------------------------------------------------

    def on_threshold_change(
        self,
        callback: Callable[[ThresholdChangeEvent], None],
    ) -> None:
        """注册阈值变更回调"""
        with self._lock:
            self._callbacks.append(callback)

    def _notify_change(self, event: ThresholdChangeEvent) -> None:
        """通知所有回调"""
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # 配置文件
    # -------------------------------------------------------------------------

    def get_config_path(self, name: str = "thresholds") -> Path:
        """获取配置文件路径"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        return self.config_dir / f"{name}.json"

    def load_from_file(self, path: Optional[str] = None) -> bool:
        """
        从文件加载阈值配置。

        Returns:
            bool: 加载是否成功
        """
        import json
        path = Path(path) if path else self.get_config_path()
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._profile = ThresholdProfile.from_dict(data)
            return True
        except Exception:
            return False

    def save_to_file(self, path: Optional[str] = None) -> bool:
        """
        保存阈值配置到文件。

        Returns:
            bool: 保存是否成功
        """
        path = Path(path) if path else self.get_config_path()
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(self._profile.to_json(), encoding="utf-8")
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Profile 管理
    # -------------------------------------------------------------------------

    def get_profile(self) -> ThresholdProfile:
        """获取当前 Profile"""
        with self._lock:
            return self._profile

    def set_profile(self, profile: ThresholdProfile) -> None:
        """设置 Profile"""
        with self._lock:
            old = self._profile
            self._profile = profile
            # 通知所有阈值变更
            for metric, old_t, new_t in self._diff_profiles(old, profile):
                event = ThresholdChangeEvent(
                    metric=metric,
                    old_value=old_t.value,
                    new_value=new_t.value,
                    old_level=old_t.level,
                    new_level=new_t.level,
                    timestamp=datetime.now().isoformat(),
                    source="profile_switch",
                )
                self._notify_change(event)

    def switch_preset(self, preset_name: str) -> bool:
        """
        切换到预设Profile。

        Args:
            preset_name: 预设名称 (default, strict, relaxed, development)

        Returns:
            bool: 是否切换成功
        """
        if preset_name not in PRESET_PROFILES:
            return False
        self.set_profile(PRESET_PROFILES[preset_name])
        return True

    def list_presets(self) -> List[str]:
        """列出所有预设"""
        return list(PRESET_PROFILES.keys())

    def _diff_profiles(
        self,
        old: ThresholdProfile,
        new: ThresholdProfile,
    ) -> List[tuple]:
        """比较两个Profile的差异"""
        diffs = []
        old_dict = self._profile_to_flat(old)
        new_dict = self._profile_to_flat(new)

        for key in set(old_dict.keys()) | set(new_dict.keys()):
            old_t = old_dict.get(key)
            new_t = new_dict.get(key)
            if old_t != new_t:
                diffs.append((key, old_t or ThresholdConfig(key, 0, 0), new_t or ThresholdConfig(key, 0, 0)))
        return diffs

    def _profile_to_flat(self, profile: ThresholdProfile) -> Dict[str, ThresholdConfig]:
        """将Profile展平为 dict[name -> ThresholdConfig]"""
        result = {}
        for group_name, group in [
            ("health_score", profile.health_score),
            ("response_time", profile.response_time),
            ("error_rate", profile.error_rate),
            ("module_timeout", profile.module_timeout),
            ("call_count", profile.call_count),
        ]:
            for field_name in dir(group):
                if field_name.startswith("_"):
                    continue
                val = getattr(group, field_name, None)
                if isinstance(val, ThresholdConfig):
                    result[f"{group_name}.{field_name}"] = val
        return result

    # -------------------------------------------------------------------------
    # 动态阈值调整
    # -------------------------------------------------------------------------

    def update_threshold(self, metric_path: str, value: float) -> bool:
        """
        动态更新阈值。

        Args:
            metric_path: 阈值路径，如 "health_score.healthy", "response_time.timeout"
            value: 新值

        Returns:
            bool: 更新是否成功
        """
        with self._lock:
            parts = metric_path.split(".")
            if len(parts) != 2:
                return False

            group_name, field_name = parts
            group_map = {
                "health_score": self._profile.health_score,
                "response_time": self._profile.response_time,
                "error_rate": self._profile.error_rate,
                "module_timeout": self._profile.module_timeout,
                "call_count": self._profile.call_count,
            }

            group = group_map.get(group_name)
            if not group:
                return False

            if not hasattr(group, field_name):
                return False

            config = getattr(group, field_name)
            if not isinstance(config, ThresholdConfig):
                return False

            old_value = config.value
            old_level = config.level

            # 更新值（自动限制在有效范围内）
            config.value = max(config.min_value, min(config.max_value, value))

            # 重新计算级别
            config.level = self._compute_level(metric_path, config.value)

            # 触发回调
            event = ThresholdChangeEvent(
                metric=metric_path,
                old_value=old_value,
                new_value=config.value,
                old_level=old_level,
                new_level=config.level,
                timestamp=datetime.now().isoformat(),
                source="manual",
            )
            self._notify_change(event)

            return True

    def reset_threshold(self, metric_path: str) -> bool:
        """重置阈值到默认值"""
        with self._lock:
            parts = metric_path.split(".")
            if len(parts) != 2:
                return False

            group_name, field_name = parts
            group_map = {
                "health_score": self._profile.health_score,
                "response_time": self._profile.response_time,
                "error_rate": self._profile.error_rate,
                "module_timeout": self._profile.module_timeout,
                "call_count": self._profile.call_count,
            }

            group = group_map.get(group_name)
            if not group or not hasattr(group, field_name):
                return False

            config = getattr(group, field_name)
            if not isinstance(config, ThresholdConfig):
                return False

            old = config.value
            config.reset()
            if old != config.value:
                event = ThresholdChangeEvent(
                    metric=metric_path,
                    old_value=old,
                    new_value=config.value,
                    old_level=config.level,
                    new_level=config.level,
                    timestamp=datetime.now().isoformat(),
                    source="reset",
                )
                self._notify_change(event)
            return True

    def _compute_level(self, metric_path: str, value: float) -> ThresholdLevel:
        """根据指标路径和值计算级别"""
        # 简单启发式：根据路径和值范围推断
        if "healthy" in metric_path or "system_healthy" in metric_path:
            if value >= 0.8:
                return ThresholdLevel.OK
            elif value >= 0.5:
                return ThresholdLevel.WARNING
            else:
                return ThresholdLevel.ERROR
        elif "timeout" in metric_path or "slow" in metric_path:
            if value <= 2.0:
                return ThresholdLevel.OK
            elif value <= 10.0:
                return ThresholdLevel.WARNING
            else:
                return ThresholdLevel.ERROR
        elif "error_rate" in metric_path or "error" in metric_path:
            if value <= 0.01:
                return ThresholdLevel.OK
            elif value <= 0.05:
                return ThresholdLevel.WARNING
            else:
                return ThresholdLevel.ERROR
        return ThresholdLevel.WARNING

    # -------------------------------------------------------------------------
    # 指标检查
    # -------------------------------------------------------------------------

    def check_health_score(
        self,
        score: float,
        module_id: Optional[str] = None,
    ) -> ThresholdCheckResult:
        """
        检查健康分数是否触发阈值。

        Args:
            score: 健康分数 (0.0-1.0)
            module_id: 模块ID（可选）

        Returns:
            ThresholdCheckResult: 检查结果
        """
        with self._lock:
            p = self._profile.health_score

            if score >= p.healthy.value:
                return ThresholdCheckResult(
                    metric="health_score",
                    value=score,
                    threshold=p.healthy.value,
                    level=ThresholdLevel.OK,
                    triggered=False,
                    message=f"健康分数 {score:.2f} 处于健康范围 (≥{p.healthy.value:.2f})",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            elif score >= p.degraded.value:
                return ThresholdCheckResult(
                    metric="health_score",
                    value=score,
                    threshold=p.degraded.value,
                    level=ThresholdLevel.WARNING,
                    triggered=True,
                    message=f"健康分数 {score:.2f} 低于健康阈值 {p.healthy.value:.2f}，模块可能降级",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            elif score >= p.failed.value:
                return ThresholdCheckResult(
                    metric="health_score",
                    value=score,
                    threshold=p.failed.value,
                    level=ThresholdLevel.ERROR,
                    triggered=True,
                    message=f"健康分数 {score:.2f} 低于降级阈值 {p.degraded.value:.2f}，模块异常",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            else:
                return ThresholdCheckResult(
                    metric="health_score",
                    value=score,
                    threshold=p.failed.value,
                    level=ThresholdLevel.CRITICAL,
                    triggered=True,
                    message=f"健康分数 {score:.2f} 低于失败阈值 {p.failed.value:.2f}，模块已失败",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )

    def check_response_time(
        self,
        response_time: float,
        module_id: Optional[str] = None,
    ) -> ThresholdCheckResult:
        """检查响应时间是否触发阈值（单位：秒）"""
        with self._lock:
            p = self._profile.response_time

            if response_time <= p.fast.value:
                return ThresholdCheckResult(
                    metric="response_time",
                    value=response_time,
                    threshold=p.fast.value,
                    level=ThresholdLevel.OK,
                    triggered=False,
                    message=f"响应时间 {response_time:.3f}s 优秀 (≤{p.fast.value:.3f}s)",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            elif response_time <= p.acceptable.value:
                return ThresholdCheckResult(
                    metric="response_time",
                    value=response_time,
                    threshold=p.acceptable.value,
                    level=ThresholdLevel.INFO,
                    triggered=False,
                    message=f"响应时间 {response_time:.3f}s 可接受 (≤{p.acceptable.value:.3f}s)",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            elif response_time <= p.slow.value:
                return ThresholdCheckResult(
                    metric="response_time",
                    value=response_time,
                    threshold=p.slow.value,
                    level=ThresholdLevel.WARNING,
                    triggered=True,
                    message=f"响应时间 {response_time:.3f}s 偏慢 (> {p.acceptable.value:.3f}s)",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            elif response_time <= p.timeout.value:
                return ThresholdCheckResult(
                    metric="response_time",
                    value=response_time,
                    threshold=p.timeout.value,
                    level=ThresholdLevel.ERROR,
                    triggered=True,
                    message=f"响应时间 {response_time:.3f}s 超过慢阈值 {p.slow.value:.3f}s",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            else:
                return ThresholdCheckResult(
                    metric="response_time",
                    value=response_time,
                    threshold=p.timeout.value,
                    level=ThresholdLevel.CRITICAL,
                    triggered=True,
                    message=f"响应时间 {response_time:.3f}s 超时 (>{p.timeout.value:.3f}s)",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )

    def check_error_rate(
        self,
        error_rate: float,
        total_calls: int = 0,
        module_id: Optional[str] = None,
    ) -> ThresholdCheckResult:
        """检查错误率是否触发阈值 (0.0-1.0)"""
        with self._lock:
            p = self._profile.error_rate

            if error_rate <= p.low.value:
                return ThresholdCheckResult(
                    metric="error_rate",
                    value=error_rate,
                    threshold=p.low.value,
                    level=ThresholdLevel.OK,
                    triggered=False,
                    message=f"错误率 {error_rate:.2%} 优秀 (≤{p.low.value:.2%})",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            elif error_rate <= p.warning.value:
                return ThresholdCheckResult(
                    metric="error_rate",
                    value=error_rate,
                    threshold=p.warning.value,
                    level=ThresholdLevel.INFO,
                    triggered=False,
                    message=f"错误率 {error_rate:.2%} 正常 (≤{p.warning.value:.2%})",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            elif error_rate <= p.error.value:
                return ThresholdCheckResult(
                    metric="error_rate",
                    value=error_rate,
                    threshold=p.error.value,
                    level=ThresholdLevel.WARNING,
                    triggered=True,
                    message=f"错误率 {error_rate:.2%} 偏高 (> {p.warning.value:.2%})",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            elif error_rate <= p.critical.value:
                return ThresholdCheckResult(
                    metric="error_rate",
                    value=error_rate,
                    threshold=p.critical.value,
                    level=ThresholdLevel.ERROR,
                    triggered=True,
                    message=f"错误率 {error_rate:.2%} 超过错误阈值 {p.error.value:.2%}",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            else:
                return ThresholdCheckResult(
                    metric="error_rate",
                    value=error_rate,
                    threshold=p.critical.value,
                    level=ThresholdLevel.CRITICAL,
                    triggered=True,
                    message=f"错误率 {error_rate:.2%} 超过严重阈值 {p.critical.value:.2%}",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )

    def check_module_timeout(
        self,
        module_id: str,
        elapsed_time: float,
    ) -> ThresholdCheckResult:
        """检查模块调用是否超时"""
        with self._lock:
            p = self._profile.module_timeout

            # 检查是否有特定模块覆盖
            override = p.per_module_overrides.get(module_id)
            timeout_threshold = override if override is not None else p.default.value

            if elapsed_time <= p.fast.value:
                return ThresholdCheckResult(
                    metric="module_timeout",
                    value=elapsed_time,
                    threshold=timeout_threshold,
                    level=ThresholdLevel.OK,
                    triggered=False,
                    message=f"模块 {module_id} 调用快速完成 ({elapsed_time:.3f}s)",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            elif elapsed_time <= timeout_threshold:
                if elapsed_time > p.slow.value:
                    return ThresholdCheckResult(
                        metric="module_timeout",
                        value=elapsed_time,
                        threshold=timeout_threshold,
                        level=ThresholdLevel.WARNING,
                        triggered=True,
                        message=f"模块 {module_id} 调用偏慢 ({elapsed_time:.3f}s > {p.slow.value:.3f}s)",
                        timestamp=datetime.now().isoformat(),
                        module_id=module_id,
                    )
                return ThresholdCheckResult(
                    metric="module_timeout",
                    value=elapsed_time,
                    threshold=timeout_threshold,
                    level=ThresholdLevel.INFO,
                    triggered=False,
                    message=f"模块 {module_id} 调用完成但偏慢 ({elapsed_time:.3f}s)",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            else:
                return ThresholdCheckResult(
                    metric="module_timeout",
                    value=elapsed_time,
                    threshold=timeout_threshold,
                    level=ThresholdLevel.CRITICAL,
                    triggered=True,
                    message=f"模块 {module_id} 调用超时 ({elapsed_time:.3f}s > {timeout_threshold:.3f}s)",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )

    def check_call_count(
        self,
        call_count: int,
        window_seconds: float,
        module_id: Optional[str] = None,
    ) -> ThresholdCheckResult:
        """检查调用计数是否异常（过多或过少）"""
        with self._lock:
            p = self._profile.call_count

            # 归一化到每分钟
            calls_per_min = call_count / (window_seconds / 60.0) if window_seconds > 0 else 0

            if calls_per_min > p.max_per_minute.value:
                return ThresholdCheckResult(
                    metric="call_count",
                    value=calls_per_min,
                    threshold=p.max_per_minute.value,
                    level=ThresholdLevel.WARNING,
                    triggered=True,
                    message=f"模块 {module_id} 调用频率过高 ({calls_per_min:.1f}/min > {p.max_per_minute.value:.1f}/min)",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            elif call_count < p.min_per_hour.value and window_seconds >= 3600:
                return ThresholdCheckResult(
                    metric="call_count",
                    value=float(call_count),
                    threshold=p.min_per_hour.value,
                    level=ThresholdLevel.INFO,
                    triggered=True,
                    message=f"模块 {module_id} 调用过少 ({call_count} < {p.min_per_hour.value:.0f}/h)",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )
            else:
                return ThresholdCheckResult(
                    metric="call_count",
                    value=calls_per_min,
                    threshold=p.max_per_minute.value,
                    level=ThresholdLevel.OK,
                    triggered=False,
                    message=f"模块 {module_id} 调用频率正常 ({calls_per_min:.1f}/min)",
                    timestamp=datetime.now().isoformat(),
                    module_id=module_id,
                )

    def check_all(
        self,
        health_score: Optional[float] = None,
        response_time: Optional[float] = None,
        error_rate: Optional[float] = None,
        elapsed_time: Optional[float] = None,
        call_count: Optional[int] = None,
        window_seconds: float = 60.0,
        module_id: Optional[str] = None,
    ) -> List[ThresholdCheckResult]:
        """
        执行多项指标检查。

        Returns:
            List[ThresholdCheckResult]: 所有触发阈值的检查结果
        """
        results = []

        if health_score is not None:
            results.append(self.check_health_score(health_score, module_id))

        if response_time is not None:
            results.append(self.check_response_time(response_time, module_id))

        if error_rate is not None:
            results.append(self.check_error_rate(error_rate, module_id=module_id))

        if elapsed_time is not None and module_id is not None:
            results.append(self.check_module_timeout(module_id, elapsed_time))

        if call_count is not None:
            results.append(self.check_call_count(call_count, window_seconds, module_id))

        return [r for r in results if r.triggered]

    # -------------------------------------------------------------------------
    # 与 StatusAggregator 集成
    # -------------------------------------------------------------------------

    def get_active_thresholds(self) -> Dict[str, Any]:
        """获取当前所有阈值配置（用于 StatusAggregator 的告警判断）"""
        with self._lock:
            return {
                "health_score": {
                    "healthy": self._profile.health_score.healthy.value,
                    "degraded": self._profile.health_score.degraded.value,

                    "failed": self._profile.health_score.failed.value,
                    "system_healthy": self._profile.health_score.system_healthy.value,
                },
                "response_time": {
                    "fast": self._profile.response_time.fast.value,
                    "acceptable": self._profile.response_time.acceptable.value,
                    "slow": self._profile.response_time.slow.value,
                    "timeout": self._profile.response_time.timeout.value,
                },
                "error_rate": {
                    "low": self._profile.error_rate.low.value,
                    "warning": self._profile.error_rate.warning.value,
                    "error": self._profile.error_rate.error.value,
                    "critical": self._profile.error_rate.critical.value,
                },
                "module_timeout": {
                    "default": self._profile.module_timeout.default.value,
                    "fast": self._profile.module_timeout.fast.value,
                    "slow": self._profile.module_timeout.slow.value,
                    "consecutive_limit": self._profile.module_timeout.consecutive_limit.value,
                },
                "call_count": {
                    "min_per_hour": self._profile.call_count.min_per_hour.value,
                    "max_per_minute": self._profile.call_count.max_per_minute.value,
                    "burst": self._profile.call_count.burst_threshold.value,
                },
            }

    # -------------------------------------------------------------------------
    # 便捷访问
    # -------------------------------------------------------------------------

    def get_threshold(self, metric_path: str) -> Optional[float]:
        """获取阈值的当前值"""
        parts = metric_path.split(".")
        if len(parts) != 2:
            return None

        group_name, field_name = parts
        group_map = {
            "health_score": self._profile.health_score,
            "response_time": self._profile.response_time,
            "error_rate": self._profile.error_rate,
            "module_timeout": self._profile.module_timeout,
            "call_count": self._profile.call_count,
        }

        group = group_map.get(group_name)
        if not group or not hasattr(group, field_name):
            return None

        val = getattr(group, field_name)
        if isinstance(val, ThresholdConfig):
            return val.value
        elif isinstance(val, dict):
            return val.get(field_name)
        return None

    def get_all_thresholds_flat(self) -> Dict[str, float]:
        """获取所有阈值的扁平字典"""
        with self._lock:
            return {k: v.value for k, v in self._profile_to_flat(self._profile).items()}

    def describe_thresholds(self) -> str:
        """生成阈值配置说明文本"""
        with self._lock:
            lines = ["📐 当前阈值配置:", ""]
            flat = self.get_all_thresholds_flat()

            for path, value in sorted(flat.items()):
                parts = path.split(".")
                group_emoji = {
                    "health_score": "🏥",
                    "response_time": "⏱️",
                    "error_rate": "❌",
                    "module_timeout": "⏰",
                    "call_count": "📊",
                }.get(parts[0], "📏")

                lines.append(f"  {group_emoji} {path}: {value}")

            return "\n".join(lines)


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_threshold_manager: Optional[ThresholdManager] = None
_threshold_manager_lock = threading.Lock()


def get_threshold_manager() -> ThresholdManager:
    """获取全局阈值管理器（单例）"""
    global _threshold_manager
    if _threshold_manager is None:
        with _threshold_manager_lock:
            if _threshold_manager is None:
                _threshold_manager = ThresholdManager()
                # 尝试从配置文件加载
                _threshold_manager.load_from_file()
    return _threshold_manager


def reset_threshold_manager() -> None:
    """重置阈值管理器（用于测试）"""
    global _threshold_manager
    with _threshold_manager_lock:
        _threshold_manager = None


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    """CLI入口 - 展示阈值配置并演示检查"""
    import json

    tm = get_threshold_manager()

    print("=" * 60)
    print("📐 Mimir-Core 关键指标阈值系统")
    print("=" * 60)

    # 列出预设
    print(f"\n📦 可用预设: {', '.join(tm.list_presets())}")

    # 当前配置
    print(f"\n{tm.describe_thresholds()}")

    # 演示检查
    print("\n" + "-" * 40)
    print("🧪 阈值检查演示:")
    print("-" * 40)

    # 健康分数检查
    print("\n🏥 健康分数检查:")
    for score in [0.95, 0.75, 0.55, 0.25]:
        r = tm.check_health_score(score)
        emoji = "✅" if not r.triggered else "⚠️" if r.level == ThresholdLevel.WARNING else "❌" if r.level == ThresholdLevel.ERROR else "🔴"
        print(f"   {emoji} score={score:.2f} -> {r.level.name} ({r.message[:40]})")

    # 响应时间检查
    print("\n⏱️ 响应时间检查:")
    for rt in [0.3, 1.5, 4.0, 10.0, 45.0]:
        r = tm.check_response_time(rt)
        emoji = "✅" if not r.triggered else "⚠️" if r.level.value <= 3 else "❌"
        print(f"   {emoji} rt={rt:.1f}s -> {r.level.name} ({r.message[:40]})")

    # 错误率检查
    print("\n❌ 错误率检查:")
    for er in [0.005, 0.03, 0.08, 0.15, 0.35]:
        r = tm.check_error_rate(er)
        emoji = "✅" if not r.triggered else "⚠️" if r.level == ThresholdLevel.WARNING else "❌"
        print(f"   {emoji} er={er:.1%} -> {r.level.name} ({r.message[:40]})")

    # 动态调整演示
    print("\n🔧 动态调整演示:")
    print(f"   当前 health_score.healthy = {tm.get_threshold('health_score.healthy')}")
    tm.update_threshold("health_score.healthy", 0.75)
    print(f"   调整后 health_score.healthy = {tm.get_threshold('health_score.healthy')}")
    tm.reset_threshold("health_score.healthy")
    print(f"   重置后 health_score.healthy = {tm.get_threshold('health_score.healthy')}")

    # 导出配置
    print("\n💾 配置文件保存路径:")
    print(f"   {tm.get_config_path()}")

    return tm


if __name__ == "__main__":
    main()
