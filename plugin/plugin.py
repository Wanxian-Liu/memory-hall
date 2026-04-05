# -*- coding: utf-8 -*-
"""
记忆殿堂v2.0 插件系统框架
=======================
提供插件接口定义、动态加载机制和全局注册表。

核心概念：
- PluginInterface: 所有插件必须实现的接口
- PluginLoader: 根据配置路径动态发现并加载插件
- PluginRegistry: 全局单例注册表，管理插件生命周期
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger("记忆殿堂.plugin")


# ─────────────────────────────────────────────────────────────
# 插件状态枚举
# ─────────────────────────────────────────────────────────────

class PluginState(Enum):
    """插件生命周期状态"""
    UNLOADED = auto()      # 未加载
    LOADING = auto()       # 加载中
    ACTIVE = auto()        # 已激活
    INACTIVE = auto()      # 已停用
    ERROR = auto()         # 加载/运行错误
    UNLOADING = auto()     # 卸载中


# ─────────────────────────────────────────────────────────────
# 插件元数据
# ─────────────────────────────────────────────────────────────

@dataclass
class PluginMetadata:
    """插件元信息（静态定义）"""
    id: str                           # 唯一标识符，如 "记忆殿堂.萃取"
    name: str                         # 显示名称
    version: str = "0.0.0"            # 版本号
    description: str = ""             # 插件描述
    author: str = ""                  # 作者
    tags: List[str] = field(default_factory=list)   # 标签分类
    dependencies: List[str] = field(default_factory=list)  # 依赖插件ID
    config_schema: Optional[Dict[str, Any]] = None  # 配置项schema
    entry_point: Optional[str] = None  # 自定义入口模块路径

    def __post_init__(self):
        if not self.id or not self.name:
            raise ValueError("PluginMetadata: 'id' 和 'name' 为必填项")


# ─────────────────────────────────────────────────────────────
# 插件接口
# ─────────────────────────────────────────────────────────────

class PluginInterface(ABC):
    """
    插件必须继承的抽象基类。

    实现约定：
    1. 在类级别定义 METADATA = PluginMetadata(...)
    2. on_load()  在插件首次加载时调用，用于初始化资源
    3. on_enable()  在插件激活时调用
    4. on_disable()  在插件停用时调用
    5. on_unload()  在插件卸载前调用，用于释放资源
    """

    METADATA: PluginMetadata

    def __init__(self):
        self._state: PluginState = PluginState.UNLOADED
        self._config: Dict[str, Any] = {}

    @property
    def id(self) -> str:
        return self.METADATA.id

    @property
    def state(self) -> PluginState:
        return self._state

    def set_config(self, config: Dict[str, Any]) -> None:
        """注入运行时配置"""
        self._config = config

    def get_config(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    # ── 生命周期钩子 ────────────────────────────────────────

    def on_load(self) -> None:
        """
        插件加载时调用（仅调用一次）。
        在此初始化资源、注册路由、连接数据库等。
        """
        pass

    def on_enable(self) -> None:
        """插件激活时调用。可重复调用。"""
        pass

    def on_disable(self) -> None:
        """插件停用时调用。可重复调用。"""
        pass

    def on_unload(self) -> None:
        """
        插件卸载前调用（仅调用一次）。
        在此清理资源、关闭连接等。
        """
        pass

    # ── 工具方法 ────────────────────────────────────────────

    def log_info(self, msg: str) -> None:
        logger.info(f"[{self.id}] {msg}")

    def log_warning(self, msg: str) -> None:
        logger.warning(f"[{self.id}] {msg}")

    def log_error(self, msg: str) -> None:
        logger.error(f"[{self.id}] {msg}")


# ─────────────────────────────────────────────────────────────
# 插件注册表（全局单例）
# ─────────────────────────────────────────────────────────────

class PluginRegistry:
    """
    全局插件注册中心。
    负责管理所有已发现/已加载插件的生命周期。
    """

    _instance: Optional[PluginRegistry] = None

    def __new__(cls) -> PluginRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        # plugin_id -> PluginInstance {metadata, instance, state}
        self._plugins: Dict[str, _PluginEntry] = {}
        self._enabled: Dict[str, bool] = {}  # plugin_id -> 是否启用
        # 生命周期钩子回调: event_name -> [callbacks]
        self._hooks: Dict[str, List[Callable[..., Any]]] = {
            "plugin_load": [],
            "plugin_enable": [],
            "plugin_disable": [],
            "plugin_unload": [],
        }

    # ── 注册/注销 ─────────────────────────────────────────

    def register(self, plugin_cls: Type[PluginInterface],
                  enabled: bool = True) -> None:
        """将插件类注册到注册表（不触发加载）"""
        metadata = plugin_cls.METADATA
        if metadata.id in self._plugins:
            raise ValueError(f"插件已注册: {metadata.id}")

        entry = _PluginEntry(metadata=metadata, cls=plugin_cls)
        self._plugins[metadata.id] = entry
        self._enabled[metadata.id] = enabled
        self.log_info(f"注册插件: {metadata.id} v{metadata.version}")

    def unregister(self, plugin_id: str) -> None:
        """从注册表移除插件（插件必须已卸载）"""
        entry = self._plugins.get(plugin_id)
        if entry is None:
            raise KeyError(f"插件未注册: {plugin_id}")
        if entry.state not in (PluginState.UNLOADED, PluginState.ERROR):
            raise RuntimeError(
                f"插件 {plugin_id} 当前状态为 {entry.state.name}，需先卸载"
            )
        del self._plugins[plugin_id]
        self._enabled.pop(plugin_id, None)
        self.log_info(f"注销插件: {plugin_id}")

    # ── 加载/激活/停用/卸载 ────────────────────────────────

    def load_plugin(self, plugin_id: str) -> PluginInterface:
        """加载插件（实例化 + on_load）"""
        entry = self._get_entry(plugin_id)
        if entry.state != PluginState.UNLOADED:
            raise RuntimeError(
                f"插件 {plugin_id} 状态为 {entry.state.name}，无法加载"
            )
        entry.state = PluginState.LOADING
        try:
            instance = entry.cls()
            instance.set_config(self._get_plugin_config(plugin_id))
            instance.on_load()
            entry.instance = instance
            entry.state = PluginState.ACTIVE if self._enabled[plugin_id] else PluginState.INACTIVE
            instance._state = entry.state  # Sync instance state with entry state
            self._emit("plugin_load", instance)
            self.log_info(f"加载插件: {plugin_id}")
            return instance
        except Exception as e:
            entry.state = PluginState.ERROR
            self.log_error(f"加载插件失败 [{plugin_id}]: {e}")
            raise

    def enable_plugin(self, plugin_id: str) -> None:
        """激活插件"""
        entry = self._get_entry(plugin_id)
        if entry.state == PluginState.INACTIVE:
            entry.instance.on_enable()
            entry.state = PluginState.ACTIVE
            entry.instance._state = entry.state  # Sync instance state
            self._enabled[plugin_id] = True
            self._emit("plugin_enable", entry.instance)
            self.log_info(f"激活插件: {plugin_id}")
        elif entry.state == PluginState.ACTIVE:
            pass  # 已激活，无操作
        else:
            raise RuntimeError(f"插件 {plugin_id} 状态为 {entry.state.name}，无法激活")

    def disable_plugin(self, plugin_id: str) -> None:
        """停用插件"""
        entry = self._get_entry(plugin_id)
        if entry.state == PluginState.ACTIVE:
            entry.instance.on_disable()
            entry.state = PluginState.INACTIVE
            entry.instance._state = entry.state  # Sync instance state
            self._enabled[plugin_id] = False
            self._emit("plugin_disable", entry.instance)
            self.log_info(f"停用插件: {plugin_id}")
        elif entry.state == PluginState.INACTIVE:
            pass  # 已停用，无操作
        else:
            raise RuntimeError(f"插件 {plugin_id} 状态为 {entry.state.name}，无法停用")

    def unload_plugin(self, plugin_id: str) -> None:
        """卸载插件（先停用再调用 on_unload）"""
        entry = self._get_entry(plugin_id)
        if entry.state == PluginState.ACTIVE:
            self.disable_plugin(plugin_id)
        if entry.state == PluginState.INACTIVE:
            try:
                entry.state = PluginState.UNLOADING
                if entry.instance:
                    entry.instance.on_unload()
                    entry.instance._state = PluginState.UNLOADED  # Sync instance state
                entry.state = PluginState.UNLOADED
                entry.instance = None
                self._emit("plugin_unload", plugin_id)
                self.log_info(f"卸载插件: {plugin_id}")
            except Exception as e:
                entry.state = PluginState.ERROR
                self.log_error(f"卸载插件失败 [{plugin_id}]: {e}")
                raise
        else:
            raise RuntimeError(
                f"插件 {plugin_id} 状态为 {entry.state.name}，无法卸载"
            )

    def reload_plugin(self, plugin_id: str) -> PluginInterface:
        """重载插件（卸载 + 重新加载）"""
        self.unload_plugin(plugin_id)
        return self.load_plugin(plugin_id)

    # ── 查询 ───────────────────────────────────────────────

    def get_plugin(self, plugin_id: str) -> Optional[PluginInterface]:
        """获取已加载插件实例（未加载返回 None）"""
        entry = self._plugins.get(plugin_id)
        if entry and entry.state not in (PluginState.UNLOADED, PluginState.ERROR):
            return entry.instance
        return None

    def get_metadata(self, plugin_id: str) -> PluginMetadata:
        return self._get_entry(plugin_id).metadata

    def list_plugins(self,
                     state: Optional[PluginState] = None,
                     enabled: Optional[bool] = None) -> List[PluginMetadata]:
        """列出插件，可选过滤条件"""
        result = []
        for pid, entry in self._plugins.items():
            if state is not None and entry.state != state:
                continue
            if enabled is not None and self._enabled.get(pid) != enabled:
                continue
            result.append(entry.metadata)
        return result

    def get_all_loaded(self) -> List[PluginInterface]:
        """获取所有已加载（ACTIVE 或 INACTIVE）的插件实例"""
        return [
            e.instance
            for e in self._plugins.values()
            if e.instance is not None
        ]

    # ── 生命周期钩子 ───────────────────────────────────────

    def register_hook(self, event: str, callback: Callable[..., Any]) -> None:
        """注册全局生命周期钩子"""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)

    def unregister_hook(self, event: str, callback: Callable[..., Any]) -> None:
        """注销钩子"""
        if event in self._hooks:
            self._hooks[event] = [cb for cb in self._hooks[event] if cb != callback]

    def _emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        for cb in self._hooks.get(event, []):
            try:
                cb(*args, **kwargs)
            except Exception as e:
                self.log_error(f"钩子 {event} 执行失败: {e}")

    # ── 内部 ───────────────────────────────────────────────

    def _get_entry(self, plugin_id: str) -> _PluginEntry:
        if plugin_id not in self._plugins:
            raise KeyError(f"插件未注册: {plugin_id}")
        return self._plugins[plugin_id]

    def _get_plugin_config(self, plugin_id: str) -> Dict[str, Any]:
        # TODO: 从记忆殿堂配置系统读取插件专属配置
        return {}

    def log_info(self, msg: str) -> None:
        logger.info(f"[PluginRegistry] {msg}")

    def log_error(self, msg: str) -> None:
        logger.error(f"[PluginRegistry] {msg}")

    @property
    def plugin_count(self) -> int:
        return len(self._plugins)


@dataclass
class _PluginEntry:
    """内部数据结构：插件注册条目"""
    metadata: PluginMetadata
    cls: Type[PluginInterface]
    instance: Optional[PluginInterface] = None
    state: PluginState = PluginState.UNLOADED


# ─────────────────────────────────────────────────────────────
# 插件加载器（动态发现）
# ─────────────────────────────────────────────────────────────

class PluginLoader:
    """
    从指定目录/模块路径动态发现并加载插件。
    支持两种模式：
    - dir_mode: 扫描目录，查找包含 PLUGIN_CLASS 变量的 Python 文件
    - module_mode: 直接 importlib 导入指定模块路径
    """

    DEFAULT_PLUGIN_DIR = Path("~/.openclaw/projects/记忆殿堂v2.0/plugins").expanduser()

    def __init__(self, plugin_dirs: Optional[List[Path]] = None):
        self.plugin_dirs: List[Path] = plugin_dirs or [self.DEFAULT_PLUGIN_DIR]
        self._discovered: Dict[str, Type[PluginInterface]] = {}

    def discover(self) -> Dict[str, Type[PluginInterface]]:
        """
        扫描 plugin_dirs，收集所有插件类。
        返回 plugin_id -> plugin_class 的映射。
        """
        self._discovered.clear()
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.is_dir():
                logger.warning(f"插件目录不存在: {plugin_dir}")
                continue
            self._discover_dir(plugin_dir)
        logger.info(f"发现 {len(self._discovered)} 个插件: {list(self._discovered.keys())}")
        return self._discovered

    def _discover_dir(self, plugin_dir: Path) -> None:
        """递归扫描目录中的插件文件"""
        for item in sorted(plugin_dir.rglob("*.py")):
            if item.name.startswith("_"):
                continue
            module_name = self._path_to_module(plugin_dir, item)
            try:
                spec = importlib.util.spec_from_file_location(module_name, item)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                # 查找 PLUGIN_CLASS 变量
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type)
                            and issubclass(attr, PluginInterface)
                            and attr is not PluginInterface
                            and hasattr(attr, "METADATA")):
                        metadata: PluginMetadata = attr.METADATA
                        if metadata.id in self._discovered:
                            logger.warning(
                                f"插件ID冲突 '{metadata.id}'（{item}），忽略"
                            )
                        else:
                            self._discovered[metadata.id] = attr
                            logger.debug(f"  发现插件: {metadata.id} @ {item}")
            except Exception as e:
                logger.error(f"加载插件文件失败 {item}: {e}")

    def _path_to_module(self, base: Path, file_path: Path) -> str:
        """将文件路径转换为 Python 模块名"""
        rel = file_path.relative_to(base)
        parts = list(rel.parts)
        parts[-1] = rel.stem  # 去掉 .py
        return ".".join(parts)

    def load_discovered(self,
                        registry: Optional[PluginRegistry] = None) -> None:
        """
        将已发现的插件全部注册到注册表并加载。
        需先调用 discover()。
        """
        if registry is None:
            registry = PluginRegistry()
        for plugin_id, plugin_cls in self._discovered.items():
            if plugin_id not in registry._plugins:
                registry.register(plugin_cls, enabled=True)
                registry.load_plugin(plugin_id)

    # ── 快捷导入 ───────────────────────────────────────────

    @staticmethod
    def import_plugin_module(module_path: str) -> Type[PluginInterface]:
        """
        直接从模块路径导入插件类。
        Usage: PluginLoader.import_plugin_module("记忆殿堂v2.0.plugins.my_plugin")
        """
        module = importlib.import_module(module_path)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type)
                    and issubclass(attr, PluginInterface)
                    and attr is not PluginInterface
                    and hasattr(attr, "METADATA")):
                return attr
        raise ValueError(f"模块 {module_path} 中未找到 PluginInterface 实现")


# ─────────────────────────────────────────────────────────────
# 装饰器：简化插件定义
# ─────────────────────────────────────────────────────────────

def plugin_metadata(
    plugin_id: str,
    name: str,
    version: str = "0.0.0",
    description: str = "",
    author: str = "",
    tags: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
) -> Callable[[Type[PluginInterface]], Type[PluginInterface]]:
    """
    装饰器：为插件类附加 METADATA。

    用法：
        @plugin_metadata(
            id="记忆殿堂.萃取",
            name="内容萃取",
            version="1.0.0",
            description="从记忆中萃取精华"
        )
        class MyPlugin(PluginInterface):
            pass
    """
    def decorator(cls: Type[PluginInterface]) -> Type[PluginInterface]:
        cls.METADATA = PluginMetadata(
            id=plugin_id,
            name=name,
            version=version,
            description=description,
            author=author,
            tags=tags or [],
            dependencies=dependencies or [],
        )
        return cls
    return decorator


# ─────────────────────────────────────────────────────────────
# 默认导出
# ─────────────────────────────────────────────────────────────

__all__ = [
    # 核心类
    "PluginInterface",
    "PluginMetadata",
    "PluginRegistry",
    "PluginLoader",
    "PluginState",
    # 装饰器
    "plugin_metadata",
]
