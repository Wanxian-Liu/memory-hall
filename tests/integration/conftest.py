#!/usr/bin/env python3
"""
记忆殿堂v2.0 集成测试配置

pytest配置和fixtures
"""

import os
import sys
import tempfile
import shutil
import pytest
from pathlib import Path

# 添加项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="session")
def project_root():
    """项目根目录"""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def test_vault_dir():
    """测试用vault目录"""
    tmp_dir = tempfile.mkdtemp(prefix="记忆殿堂_test_vault_")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def test_wal_dir():
    """测试用WAL目录"""
    tmp_dir = tempfile.mkdtemp(prefix="记忆殿堂_test_wal_")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def clean_registry():
    """清理插件注册表"""
    from plugin.plugin import PluginRegistry
    
    registry = PluginRegistry()
    # 卸载所有已加载插件
    for pid in list(registry._plugins.keys()):
        try:
            registry.unload_plugin(pid)
        except:
            pass
    
    yield registry
    
    # 清理
    for pid in list(registry._plugins.keys()):
        try:
            registry.unload_plugin(pid)
        except:
            pass


def pytest_configure(config):
    """pytest配置"""
    # 注册自定义标记
    config.addinivalue_line(
        "markers", "gateway: Gateway模块测试"
    )
    config.addinivalue_line(
        "markers", "wal: WAL模块测试"
    )
    config.addinivalue_line(
        "markers", "permission: Permission模块测试"
    )
    config.addinivalue_line(
        "markers", "cli: CLI模块测试"
    )
    config.addinivalue_line(
        "markers", "plugin: Plugin模块测试"
    )


def pytest_collection_modifyitems(config, items):
    """修改测试收集"""
    for item in items:
        # 根据测试类名添加标记
        if "Gateway" in item.nodeid:
            item.add_marker(pytest.mark.gateway)
        if "WAL" in item.nodeid:
            item.add_marker(pytest.mark.wal)
        if "Permission" in item.nodeid:
            item.add_marker(pytest.mark.permission)
        if "CLI" in item.nodeid:
            item.add_marker(pytest.mark.cli)
        if "Plugin" in item.nodeid:
            item.add_marker(pytest.mark.plugin)
