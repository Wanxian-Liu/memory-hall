"""
状态探针系统 - M2.1: 为每个模块添加状态探针
=============================================

非侵入式状态探针，跟踪每个模块的：
- 是否可导入 (importable)
- 是否可用 (usable)
- 最后调用时间 (last_call_time)
- 调用次数统计 (call_count)

设计参考 claw-code TaskRegistry：
- 装饰器注入方式，非侵入式
- 线程安全的探针注册表
- 状态变更回调机制
- 与 ModuleRegistry 深度集成

使用方式:
    from introspection.status_probes import ProbeRegistry, probe, get_probes

    # 获取探针注册表
    registry = get_probes()

    # 查看所有模块探针状态
    summary = registry.get_summary()

    # 查看单个模块探针
    probe = registry.get_probe("gateway.gateway")

    # 装饰器方式追踪函数调用
    @probe("my_module.my_func")
    def my_func():
        pass

    # 状态变更回调
    registry.on_state_change(lambda module_id, old, new: print(f"{module_id}: {old} -> {new}"))
"""

from __future__ import annotations

import importlib
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# 状态枚举
# ---------------------------------------------------------------------------

class ProbeState(Enum):
    """探针状态"""
    UNKNOWN = "unknown"           # 未知/未检测
    IMPORTABLE = "importable"     # 可导入
    UNAVAILABLE = "unavailable"   # 不可用（导入失败）
    HEALTHY = "healthy"           # 健康运行中
    DEGRADED = "degraded"         # 降级
    FAILED = "failed"            # 失败
    DISABLED = "disabled"        # 已禁用


# ---------------------------------------------------------------------------
# 探针数据
# ---------------------------------------------------------------------------

@dataclass
class ModuleProbe:
    """
    单个模块的探针数据。

    追踪模块的导入能力、可用性、调用统计。
    """
    module_id: str                           # 模块唯一标识 (e.g. "gateway.gateway")
    path: str                                # 模块文件路径
    state: ProbeState = ProbeState.UNKNOWN  # 当前状态
    importable: bool = False                # 是否可导入
    usable: bool = False                    # 是否可用
    last_check: Optional[str] = None         # 最后检查时间 (ISO)
    last_call: Optional[str] = None          # 最后调用时间 (ISO)
    call_count: int = 0                      # 调用次数
    error: Optional[str] = None              # 最后错误信息
    state_history: List[Dict] = field(default_factory=list)  # 状态变更历史

    def record_call(self) -> None:
        """记录一次调用"""
        self.call_count += 1
        self.last_call = datetime.now().isoformat()

    def record_check(self, importable: bool, usable: bool,
                     error: Optional[str] = None) -> ProbeState:
        """记录检查结果，返回新状态"""
        self.importable = importable
        self.usable = usable
        self.last_check = datetime.now().isoformat()
        self.error = error

        old_state = self.state

        if not importable:
            self.state = ProbeState.UNAVAILABLE
        elif not usable:
            self.state = ProbeState.DEGRADED
        elif importable and usable:
            self.state = ProbeState.HEALTHY

        # 记录状态变更
        if old_state != self.state:
            self.state_history.append({
                "timestamp": datetime.now().isoformat(),
                "from": old_state.value,
                "to": self.state.value,
            })
            # 保留最近20条历史
            if len(self.state_history) > 20:
                self.state_history = self.state_history[-20:]

        return self.state

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "module_id": self.module_id,
            "path": self.path,
            "state": self.state.value,
            "importable": self.importable,
            "usable": self.usable,
            "last_check": self.last_check,
            "last_call": self.last_call,
            "call_count": self.call_count,
            "error": self.error,
            "state_history": self.state_history[-5:],  # 最近5条
        }


# ---------------------------------------------------------------------------
# 状态变更回调
# ---------------------------------------------------------------------------

@dataclass
class StateChangeEvent:
    """状态变更事件"""
    module_id: str
    old_state: ProbeState
    new_state: ProbeState
    timestamp: str
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 探针注册表
# ---------------------------------------------------------------------------

class ProbeRegistry:
    """
    线程安全的探针注册表。

    管理所有模块的状态探针，提供：
    - 批量探针初始化（基于 ModuleRegistry）
    - 探针检查（导入测试、可用性测试）
    - 状态变更回调
    - 统计汇总

    设计参考:
    - RLock 保证读写并发安全
    - 按需构建索引
    - 累积输出模式
    """

    def __init__(self, project_root: Optional[str] = None):
        if project_root is None:
            self.project_root = Path(__file__).parent.parent.resolve()
        else:
            self.project_root = Path(project_root)

        self._lock = threading.RLock()
        self._probes: Dict[str, ModuleProbe] = {}           # module_id -> ModuleProbe
        self._callbacks: List[Callable[[StateChangeEvent], None]] = []  # 状态变更回调
        self._call_decorators: Dict[str, Set[str]] = {}     # module_id -> set of function names
        self._initialized: bool = False

    # -------------------------------------------------------------------------
    # 回调管理
    # -------------------------------------------------------------------------

    def on_state_change(self, callback: Callable[[StateChangeEvent], None]) -> None:
        """注册状态变更回调"""
        with self._lock:
            self._callbacks.append(callback)

    def _notify_state_change(self, event: StateChangeEvent) -> None:
        """通知所有回调"""
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                pass  # 不让回调异常影响主流程

    # -------------------------------------------------------------------------
    # 探针初始化（基于 ModuleRegistry）
    # -------------------------------------------------------------------------

    def initialize(self, skip_import_test: bool = False) -> None:
        """
        初始化所有探针（基于 ModuleRegistry 扫描结果）。

        Args:
            skip_import_test: True 则跳过实际的导入测试（快速初始化）
        """
        with self._lock:
            if self._initialized:
                return

            # 延迟导入避免循环依赖
            from introspection.modules import get_registry

            reg = get_registry()
            all_modules = reg.all_modules()

            for module_id in all_modules:
                module_data = reg.get(module_id)
                if not module_data:
                    continue

                path = str(self.project_root / module_data.get("path", ""))

                probe = ModuleProbe(
                    module_id=module_id,
                    path=path,
                    state=ProbeState.UNKNOWN,
                )

                # 立即做一次导入测试（除非跳过）
                if not skip_import_test:
                    self._check_probe(probe)

                self._probes[module_id] = probe

            self._initialized = True

    def _check_probe(self, probe: ModuleProbe) -> ProbeState:
        """
        检查单个探针的实际状态（导入测试）。

        Returns:
            ProbeState: 检查后的状态
        """
        import sys as _sys
        importable = False
        usable = False
        error = None

        try:
            # 尝试导入模块
            sys_path_backup = _sys.path.copy()
            try:
                # 确保项目根目录在 path 中
                if str(self.project_root) not in _sys.path:
                    _sys.path.insert(0, str(self.project_root))

                importlib.import_module(probe.module_id)
                importable = True
            except Exception as e:
                error = f"{type(e).__name__}: {e}"
            finally:
                _sys.path[:] = sys_path_backup

            # 如果可导入，尝试实例化主要类来测试可用性
            if importable:
                try:
                    usable = self._test_usable(probe.module_id)
                except Exception as e:
                    usable = False
                    if not error:
                        error = f"usable_test: {type(e).__name__}: {e}"

        except Exception as e:
            error = f"{type(e).__name__}: {e}"

        return probe.record_check(importable, usable, error)

    def _test_usable(self, module_id: str) -> bool:
        """
        测试模块是否真正可用（通过尝试导入其主要组件）。

        Returns:
            bool: 模块是否可用
        """
        try:
            # 获取模块的类信息
            from introspection.modules import get_registry
            reg = get_registry()
            module_data = reg.get(module_id)
            if not module_data:
                return False

            classes = module_data.get("classes", [])
            if not classes:
                # 没有类的话，检查是否有公开函数
                functions = module_data.get("functions", [])
                return len(functions) > 0

            # 尝试导入第一个类
            mod = importlib.import_module(module_id)
            first_class = getattr(mod, classes[0], None)
            if first_class is None:
                return False

            # 检查类是否可以实例化（不需要实际实例化）
            return callable(first_class)

        except Exception:
            return False

    # -------------------------------------------------------------------------
    # 探针查询
    # -------------------------------------------------------------------------

    def get_probe(self, module_id: str) -> Optional[ModuleProbe]:
        """获取单个模块探针"""
        with self._lock:
            return self._probes.get(module_id)

    def all_probes(self) -> Dict[str, ModuleProbe]:
        """返回所有探针（副本）"""
        with self._lock:
            return dict(self._probes)

    def get_by_state(self, state: ProbeState) -> List[ModuleProbe]:
        """按状态筛选探针"""
        with self._lock:
            return [p for p in self._probes.values() if p.state == state]

    def get_summary(self) -> Dict[str, Any]:
        """
        获取探针状态汇总。

        Returns:
            包含各状态数量、模块列表等统计信息
        """
        with self._lock:
            if not self._initialized:
                self.initialize(skip_import_test=True)

            state_counts: Dict[str, int] = {}
            total_calls = 0
            modules_checked = 0
            modules_healthy = 0

            for probe in self._probes.values():
                state_counts[probe.state.value] = state_counts.get(probe.state.value, 0) + 1
                total_calls += probe.call_count
                if probe.state in (ProbeState.IMPORTABLE, ProbeState.HEALTHY):
                    modules_checked += 1
                if probe.state == ProbeState.HEALTHY:
                    modules_healthy += 1

            return {
                "timestamp": datetime.now().isoformat(),
                "total_modules": len(self._probes),
                "modules_checked": modules_checked,
                "modules_healthy": modules_healthy,
                "total_calls": total_calls,
                "state_counts": state_counts,
                "probes": {
                    mid: p.to_dict()
                    for mid, p in self._probes.items()
                },
            }

    def get_status_summary(self) -> Dict[str, Any]:
        """
        精简版状态汇总（用于快速检查）。

        Returns:
            顶层状态 + 每类模块数量
        """
        summary = self.get_summary()

        # 计算顶层状态
        overall = "unknown"
        if summary["modules_healthy"] == summary["total_modules"] and summary["total_modules"] > 0:
            overall = "healthy"
        elif summary["state_counts"].get("failed", 0) > 0:
            overall = "failed"
        elif summary["state_counts"].get("degraded", 0) > 0:
            overall = "degraded"
        elif summary["modules_checked"] > 0:
            overall = "degraded"  # 部分检查过但不完全健康

        return {
            "overall": overall,
            "total_modules": summary["total_modules"],
            "modules_healthy": summary["modules_healthy"],
            "state_counts": summary["state_counts"],
            "total_calls": summary["total_calls"],
        }

    # -------------------------------------------------------------------------
    # 探针刷新
    # -------------------------------------------------------------------------

    def refresh_probe(self, module_id: str) -> Optional[ModuleProbe]:
        """
        刷新单个探针的状态。

        Returns:
            更新后的探针，或 None（模块不存在）
        """
        with self._lock:
            probe = self._probes.get(module_id)
            if not probe:
                return None

            old_state = probe.state
            new_state = self._check_probe(probe)

            # 如果状态变更，通知回调
            if old_state != new_state:
                event = StateChangeEvent(
                    module_id=module_id,
                    old_state=old_state,
                    new_state=new_state,
                    timestamp=datetime.now().isoformat(),
                )
                self._notify_state_change(event)

            return probe

    def refresh_all(self) -> Dict[str, ModuleProbe]:
        """刷新所有探针"""
        with self._lock:
            for module_id in list(self._probes.keys()):
                self.refresh_probe(module_id)
            return dict(self._probes)

    # -------------------------------------------------------------------------
    # 调用追踪
    # -------------------------------------------------------------------------

    def record_call(self, module_id: str) -> None:
        """
        记录模块被调用。

        Args:
            module_id: 模块标识符
        """
        with self._lock:
            probe = self._probes.get(module_id)
            if probe:
                probe.record_call()

    def record_module_function_call(self, module_id: str, func_name: str) -> None:
        """
        记录模块内特定函数被调用。

        Args:
            module_id: 模块标识符
            func_name: 函数名
        """
        with self._lock:
            probe = self._probes.get(module_id)
            if probe:
                probe.record_call()

            # 追踪函数级别的调用
            if module_id not in self._call_decorators:
                self._call_decorators[module_id] = set()
            self._call_decorators[module_id].add(func_name)

    # -------------------------------------------------------------------------
    # 探针装饰器
    # -------------------------------------------------------------------------

    def probe_decorator(self, module_id: str, func_name: Optional[str] = None):
        """
        返回一个装饰器，用于追踪模块函数的调用。

        Example:
            probe = get_probes().probe_decorator

            @probe("gateway.gateway", "read")
            def read(...):
                ...

            # 或自动使用函数名
            @probe("gateway.gateway")
            def my_func(...):
                ...
        """
        def decorator(func: Callable) -> Callable:
            fn = func_name or func.__name__

            def wrapper(*args, **kwargs):
                self.record_module_function_call(module_id, fn)
                return func(*args, **kwargs)

            # 复制函数元信息
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper

        return decorator


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_probes_registry: Optional[ProbeRegistry] = None
_probes_lock = threading.Lock()


def get_probes() -> ProbeRegistry:
    """获取全局探针注册表（单例）"""
    global _probes_registry
    if _probes_registry is None:
        with _probes_lock:
            if _probes_registry is None:
                _probes_registry = ProbeRegistry()
    return _probes_registry


def initialize_probes() -> ProbeRegistry:
    """初始化并返回全局探针注册表"""
    registry = get_probes()
    registry.initialize()
    return registry


# ---------------------------------------------------------------------------
# 便捷装饰器
# ---------------------------------------------------------------------------

def probe(module_id: str, func_name: Optional[str] = None) -> Callable:
    """
    便捷装饰器：记录模块函数调用。

    Example:
        @probe("gateway.gateway", "read")
        def read_record(...):
            ...

        # 自动使用函数名
        @probe("gateway.gateway")
        def some_function(...):
            ...
    """
    return get_probes().probe_decorator(module_id, func_name)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    """CLI入口 - 展示所有探针状态"""
    import json

    registry = get_probes()
    registry.initialize()

    print("🔍 初始化探针完成，开始检查模块状态...")

    # 刷新所有探针
    registry.refresh_all()

    # 打印汇总
    summary = registry.get_summary()

    print(f"\n📊 探针汇总:")
    print(f"   总模块数: {summary['total_modules']}")
    print(f"   健康模块: {summary['modules_healthy']}")
    print(f"   总调用次数: {summary['total_calls']}")
    print(f"\n状态分布:")
    for state, count in summary["state_counts"].items():
        print(f"   {state}: {count}")

    print(f"\n详细探针 (前10个):")
    for i, (mid, pdata) in enumerate(summary["probes"].items()):
        if i >= 10:
            print(f"   ... 还有 {len(summary['probes']) - 10} 个模块")
            break
        emoji = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unavailable": "❌",
            "unknown": "❓",
        }.get(pdata["state"], "❓")
        print(f"   {emoji} {mid}: {pdata['state']} (calls={pdata['call_count']})")
        if pdata["error"]:
            print(f"      错误: {pdata['error'][:60]}...")

    # 打印精简状态
    print(f"\n🏥 系统健康状态: {registry.get_status_summary()['overall']}")

    return summary


if __name__ == "__main__":
    main()
