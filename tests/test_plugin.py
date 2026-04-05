# -*- coding: utf-8 -*-
"""
测试 plugin 模块 - 插件系统框架
"""
import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from plugin.plugin import (
    PluginInterface, PluginMetadata, PluginState,
    PluginRegistry, PluginLoader, plugin_metadata,
    _PluginEntry
)


# ---- 测试辅助：创建测试插件 ----

class TestPlugin(PluginInterface):
    """测试用插件实现"""
    METADATA = PluginMetadata(
        id="记忆殿堂.test",
        name="Test Plugin",
        version="1.0.0",
        description="A test plugin",
        author="Test Author",
        tags=["test"],
        dependencies=[]
    )

    def __init__(self):
        super().__init__()
        self.load_called = False
        self.enable_called = False
        self.disable_called = False
        self.unload_called = False

    def on_load(self):
        self.load_called = True

    def on_enable(self):
        self.enable_called = True

    def on_disable(self):
        self.disable_called = True

    def on_unload(self):
        self.unload_called = True


class AnotherTestPlugin(PluginInterface):
    """另一个测试插件"""
    METADATA = PluginMetadata(
        id="记忆殿堂.another_test",
        name="Another Test Plugin",
        version="0.5.0",
        description="Another test plugin",
        author="Test Author",
        tags=["test"],
        dependencies=[]
    )

    def on_load(self):
        pass


class FailingPlugin(PluginInterface):
    """会失败的插件"""
    METADATA = PluginMetadata(
        id="记忆殿堂.failing",
        name="Failing Plugin",
        version="0.1.0",
        description="A plugin that fails to load"
    )

    def on_load(self):
        raise RuntimeError("Intentional failure")


@pytest.fixture
def fresh_registry():
    """提供全新的PluginRegistry实例"""
    # 重置单例
    PluginRegistry._instance = None
    registry = PluginRegistry()
    yield registry
    # 测试后清理
    try:
        for pid in list(registry._plugins.keys()):
            try:
                registry.unload_plugin(pid)
            except Exception:
                pass
    except Exception:
        pass


@pytest.fixture
def plugin_a():
    """提供唯一测试插件A"""
    unique_id = f"记忆殿堂.plugin_a_{os.getpid()}_{id(object())}"
    class PluginA(PluginInterface):
        METADATA = PluginMetadata(
            id=unique_id,
            name="Plugin A",
            version="1.0.0"
        )
        def __init__(self):
            super().__init__()
            self.load_called = False
            self.enable_called = False
            self.disable_called = False
            self.unload_called = False
        def on_load(self):
            self.load_called = True
        def on_enable(self):
            self.enable_called = True
        def on_disable(self):
            self.disable_called = True
        def on_unload(self):
            self.unload_called = True
    return PluginA


@pytest.fixture
def plugin_b():
    """提供唯一测试插件B"""
    unique_id = f"记忆殿堂.plugin_b_{os.getpid()}_{id(object())}"
    class PluginB(PluginInterface):
        METADATA = PluginMetadata(
            id=unique_id,
            name="Plugin B",
            version="1.0.0"
        )
        def __init__(self):
            super().__init__()
            self.load_called = False
        def on_load(self):
            self.load_called = True
    return PluginB


class TestPluginMetadata:
    """测试PluginMetadata类"""
    def test_metadata_creation(self):
        meta = PluginMetadata(
            id="test.plugin",
            name="Test Plugin",
            version="1.0.0",
            description="A test plugin",
            author="Tester",
            tags=["test", "example"],
            dependencies=["dep.plugin"]
        )
        assert meta.id == "test.plugin"
        assert meta.name == "Test Plugin"
        assert meta.version == "1.0.0"
        assert meta.author == "Tester"
        assert "test" in meta.tags
        assert "dep.plugin" in meta.dependencies

    def test_metadata_required_fields(self):
        with pytest.raises(ValueError, match="id"):
            PluginMetadata(id="", name="Test")
        with pytest.raises(ValueError, match="name"):
            PluginMetadata(id="test", name="")


class TestPluginState:
    def test_states(self):
        # Values start at 1 with auto()
        assert PluginState.UNLOADED.value == 1
        assert PluginState.LOADING.value == 2
        assert PluginState.ACTIVE.value == 3
        assert PluginState.INACTIVE.value == 4
        assert PluginState.ERROR.value == 5
        assert PluginState.UNLOADING.value == 6


class TestPluginInterface:
    def test_plugin_init(self):
        plugin = TestPlugin()
        assert plugin.state == PluginState.UNLOADED
        assert plugin.id == "记忆殿堂.test"

    def test_plugin_config(self):
        plugin = TestPlugin()
        plugin.set_config({"key": "value"})
        assert plugin.get_config("key") == "value"
        assert plugin.get_config("nonexistent", "default") == "default"

    def test_plugin_lifecycle_hooks(self):
        plugin = TestPlugin()
        plugin.on_load()
        assert plugin.load_called is True
        plugin.on_enable()
        assert plugin.enable_called is True
        plugin.on_disable()
        assert plugin.disable_called is True
        plugin.on_unload()
        assert plugin.unload_called is True

    def test_plugin_logging(self):
        plugin = TestPlugin()
        plugin.log_info("Info")
        plugin.log_warning("Warning")
        plugin.log_error("Error")


class TestPluginRegistry:
    """测试PluginRegistry类 - 使用fresh_registry fixture"""

    def test_registry_singleton(self, fresh_registry):
        registry2 = PluginRegistry()
        # 单例应该返回同一实例
        assert registry2 is fresh_registry

    def test_register_plugin(self, fresh_registry, plugin_a):
        fresh_registry.register(plugin_a)
        meta = fresh_registry.get_metadata(plugin_a.METADATA.id)
        assert meta is not None
        assert meta.id == plugin_a.METADATA.id

    def test_register_duplicate(self, fresh_registry, plugin_a):
        fresh_registry.register(plugin_a)
        with pytest.raises(ValueError, match="已注册"):
            fresh_registry.register(plugin_a)

    def test_unregister_plugin(self, fresh_registry, plugin_a):
        fresh_registry.register(plugin_a)
        fresh_registry.unregister(plugin_a.METADATA.id)
        with pytest.raises(KeyError):
            fresh_registry.get_metadata(plugin_a.METADATA.id)

    def test_load_plugin(self, fresh_registry, plugin_a):
        fresh_registry.register(plugin_a, enabled=True)
        instance = fresh_registry.load_plugin(plugin_a.METADATA.id)
        assert instance is not None
        assert instance.load_called is True

    def test_load_plugin_not_registered(self, fresh_registry):
        with pytest.raises(KeyError):
            fresh_registry.load_plugin("nonexistent.plugin")

    def test_load_plugin_already_loaded(self, fresh_registry, plugin_a):
        fresh_registry.register(plugin_a, enabled=True)
        fresh_registry.load_plugin(plugin_a.METADATA.id)
        with pytest.raises(RuntimeError, match="无法加载"):
            fresh_registry.load_plugin(plugin_a.METADATA.id)

    def test_enable_plugin(self, fresh_registry, plugin_a):
        fresh_registry.register(plugin_a, enabled=False)
        instance = fresh_registry.load_plugin(plugin_a.METADATA.id)
        assert instance.state == PluginState.INACTIVE
        fresh_registry.enable_plugin(plugin_a.METADATA.id)
        assert instance.state == PluginState.ACTIVE
        assert instance.enable_called is True

    def test_disable_plugin(self, fresh_registry, plugin_a):
        fresh_registry.register(plugin_a, enabled=True)
        fresh_registry.load_plugin(plugin_a.METADATA.id)
        fresh_registry.disable_plugin(plugin_a.METADATA.id)
        instance = fresh_registry.get_plugin(plugin_a.METADATA.id)
        assert instance.state == PluginState.INACTIVE

    def test_unload_plugin(self, fresh_registry, plugin_a):
        fresh_registry.register(plugin_a, enabled=True)
        instance = fresh_registry.load_plugin(plugin_a.METADATA.id)
        fresh_registry.unload_plugin(plugin_a.METADATA.id)
        # After unload, get_plugin returns None since state is UNLOADED
        assert fresh_registry.get_plugin(plugin_a.METADATA.id) is None
        # But we still have the instance reference
        assert instance.unload_called is True

    def test_reload_plugin(self, fresh_registry, plugin_a):
        fresh_registry.register(plugin_a, enabled=True)
        fresh_registry.load_plugin(plugin_a.METADATA.id)
        instance1 = fresh_registry.get_plugin(plugin_a.METADATA.id)
        instance2 = fresh_registry.reload_plugin(plugin_a.METADATA.id)
        assert instance2 is not None
        assert instance1 is not instance2

    def test_get_plugin(self, fresh_registry, plugin_a):
        fresh_registry.register(plugin_a, enabled=True)
        assert fresh_registry.get_plugin(plugin_a.METADATA.id) is None
        fresh_registry.load_plugin(plugin_a.METADATA.id)
        instance = fresh_registry.get_plugin(plugin_a.METADATA.id)
        assert instance is not None

    def test_list_plugins(self, fresh_registry, plugin_a, plugin_b):
        fresh_registry.register(plugin_a, enabled=True)
        fresh_registry.register(plugin_b, enabled=False)
        all_p = fresh_registry.list_plugins()
        ids = [p.id for p in all_p]
        assert plugin_a.METADATA.id in ids
        assert plugin_b.METADATA.id in ids

    def test_get_all_loaded(self, fresh_registry, plugin_a):
        fresh_registry.register(plugin_a, enabled=True)
        fresh_registry.load_plugin(plugin_a.METADATA.id)
        loaded = fresh_registry.get_all_loaded()
        assert len(loaded) >= 1

    def test_register_hook(self, fresh_registry):
        called = []
        def hook(*args, **kwargs):
            called.append((args, kwargs))
        fresh_registry.register_hook("plugin_load", hook)
        assert "plugin_load" in fresh_registry._hooks
        assert len(fresh_registry._hooks["plugin_load"]) == 1

    def test_unregister_hook(self, fresh_registry):
        def hook(*args, **kwargs):
            pass
        fresh_registry.register_hook("plugin_load", hook)
        fresh_registry.unregister_hook("plugin_load", hook)
        assert len(fresh_registry._hooks.get("plugin_load", [])) == 0

    def test_plugin_count(self, fresh_registry, plugin_a, plugin_b):
        initial = fresh_registry.plugin_count
        fresh_registry.register(plugin_a, enabled=True)
        assert fresh_registry.plugin_count == initial + 1


class TestPluginLoader:
    def test_loader_init(self, plugin_dir):
        from pathlib import Path
        loader = PluginLoader(plugin_dirs=[Path(plugin_dir)])
        assert len(loader.plugin_dirs) == 1
        assert len(loader._discovered) == 0

    def test_discover_empty_dir(self, plugin_dir):
        from pathlib import Path
        loader = PluginLoader(plugin_dirs=[Path(plugin_dir)])
        discovered = loader.discover()
        assert len(discovered) == 0

    def test_discover_with_plugins(self, plugin_dir):
        from pathlib import Path
        pdir = Path(plugin_dir)
        plugin_file = pdir / "discovery_plugin.py"
        plugin_file.write_text('''
from plugin.plugin import PluginInterface, PluginMetadata, plugin_metadata

@plugin_metadata(
    plugin_id="记忆殿堂.discovery_test",
    name="Discovery Test Plugin",
    version="1.0.0",
    description="Plugin for testing discovery"
)
class DiscoveredPlugin(PluginInterface):
    METADATA = PluginMetadata(
        id="记忆殿堂.discovery_test",
        name="Discovery Test Plugin",
        version="1.0.0"
    )
''')
        loader = PluginLoader(plugin_dirs=[pdir])
        discovered = loader.discover()
        assert "记忆殿堂.discovery_test" in discovered


class TestPluginMetadataDecorator:
    def test_decorator(self):
        @plugin_metadata(
            plugin_id="记忆殿堂.decorated",
            name="Decorated Plugin",
            version="2.0.0",
            description="Decorated test plugin"
        )
        class DecoratedPlugin(PluginInterface):
            pass

        assert hasattr(DecoratedPlugin, "METADATA")
        assert DecoratedPlugin.METADATA.id == "记忆殿堂.decorated"
        assert DecoratedPlugin.METADATA.name == "Decorated Plugin"


class Test_PluginEntry:
    def test_entry_creation(self):
        meta = PluginMetadata(id="test.entry", name="Test Entry")
        entry = _PluginEntry(metadata=meta, cls=TestPlugin)
        assert entry.metadata == meta
        assert entry.cls == TestPlugin
        assert entry.instance is None
        assert entry.state == PluginState.UNLOADED
