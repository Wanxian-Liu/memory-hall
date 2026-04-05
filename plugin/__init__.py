# -*- coding: utf-8 -*-
"""
记忆殿堂v2.0 插件系统
====================

使用示例::

    from plugin import (
        PluginInterface, PluginRegistry, PluginLoader,
        PluginMetadata, PluginState, plugin_metadata
    )

    # 定义插件
    @plugin_metadata(
        id="记忆殿堂.示例",
        name="示例插件",
        version="1.0.0",
        description="演示插件系统用法"
    )
    class ExamplePlugin(PluginInterface):
        def on_load(self):
            self.log_info("插件已加载")

        def on_enable(self):
            self.log_info("插件已激活")

        def on_disable(self):
            self.log_info("插件已停用")

        def on_unload(self):
            self.log_info("插件已卸载")

    # 注册并加载
    registry = PluginRegistry()
    registry.register(ExamplePlugin)
    registry.load_plugin("记忆殿堂.示例")
    registry.enable_plugin("记忆殿堂.示例")

    # 列出所有插件
    for meta in registry.list_plugins():
        print(f"{meta.id} ({meta.version})")

    # 动态发现加载
    loader = PluginLoader([Path("~/.openclaw/projects/记忆殿堂v2.0/plugins")])
    loader.discover()
    loader.load_discovered()

"""

from __future__ import annotations

from plugin.plugin import (
    # 核心类
    PluginInterface,
    PluginMetadata,
    PluginRegistry,
    PluginLoader,
    PluginState,
    # 装饰器
    plugin_metadata,
)

__all__ = [
    "PluginInterface",
    "PluginMetadata",
    "PluginRegistry",
    "PluginLoader",
    "PluginState",
    "plugin_metadata",
]
