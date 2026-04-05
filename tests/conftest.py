# -*- coding: utf-8 -*-
"""
记忆殿堂v2.0 - pytest配置和共享fixtures
"""
import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path.home() / ".openclaw" / "projects" / "记忆殿堂v2.0"
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def temp_dir():
    """创建临时目录用于测试"""
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def wal_dir(temp_dir):
    """WAL测试目录"""
    d = os.path.join(temp_dir, "wal")
    os.makedirs(d, exist_ok=True)
    return d


@pytest.fixture
def vault_dir(temp_dir):
    """存储测试目录"""
    d = os.path.join(temp_dir, "vault")
    os.makedirs(d, exist_ok=True)
    return d


@pytest.fixture
def metadata_dir(temp_dir):
    """元数据测试目录"""
    d = os.path.join(temp_dir, "metadata")
    os.makedirs(d, exist_ok=True)
    return d


@pytest.fixture
def plugin_dir(temp_dir):
    """插件测试目录"""
    d = os.path.join(temp_dir, "plugins")
    os.makedirs(d, exist_ok=True)
    return d


@pytest.fixture
def sample_content():
    """示例记忆内容"""
    return {
        "key": "test_key",
        "value": "这是一个测试记忆内容",
        "metadata": {"type": "test", "tags": ["测试"]}
    }


@pytest.fixture
def sample_contents():
    """多个示例记忆内容"""
    return [
        {"key": f"key_{i}", "value": f"内容_{i}", "metadata": {"index": i}}
        for i in range(5)
    ]
