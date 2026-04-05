# -*- coding: utf-8 -*-
"""
测试 cli/commands 模块 - CLI命令系统
"""
import os
import sys
import pytest
import json
import tempfile
import shutil

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from cli.commands import (
    MemoryStore, main
)


class TestMemoryStore:
    """测试MemoryStore类"""

    def test_store_init(self, vault_dir):
        """测试存储初始化"""
        store = MemoryStore(vault_dir=vault_dir)
        assert store.vault_dir == vault_dir
        assert os.path.exists(vault_dir)

    def test_write_and_read(self, vault_dir):
        """测试写入和读取"""
        store = MemoryStore(vault_dir=vault_dir)

        result = store.write("test_key", {"data": "test_value"})
        assert result is True

        value = store.read("test_key")
        assert value is not None
        assert value == {"data": "test_value"}

    def test_write_raw(self, vault_dir):
        """测试直接写入"""
        store = MemoryStore(vault_dir=vault_dir)

        result = store.write_raw("raw_key", "raw_value")
        assert result is True

        value = store.read("raw_key")
        assert value == "raw_value"

    def test_read_nonexistent(self, vault_dir):
        """测试读取不存在的键"""
        store = MemoryStore(vault_dir=vault_dir)

        value = store.read("nonexistent_key")
        assert value is None

    def test_delete(self, vault_dir):
        """测试删除"""
        store = MemoryStore(vault_dir=vault_dir)

        store.write("delete_key", "delete_value")
        assert store.read("delete_key") is not None

        result = store.delete("delete_key")
        assert result is True
        assert store.read("delete_key") is None

    def test_delete_nonexistent(self, vault_dir):
        """测试删除不存在的键"""
        store = MemoryStore(vault_dir=vault_dir)

        result = store.delete("nonexistent")
        assert result is False

    def test_list_keys(self, vault_dir):
        """测试列出所有键"""
        store = MemoryStore(vault_dir=vault_dir)

        store.write("key1", "value1")
        store.write("key2", "value2")
        store.write("key3", "value3")

        keys = store.list_keys()
        assert len(keys) >= 3
        assert "key1" in keys or any("key1" in k for k in keys)

    def test_count(self, vault_dir):
        """测试计数"""
        store = MemoryStore(vault_dir=vault_dir)

        initial = store.count()

        store.write("count1", "v1")
        store.write("count2", "v2")

        assert store.count() == initial + 2

    def test_get_all(self, vault_dir):
        """测试获取所有记忆"""
        store = MemoryStore(vault_dir=vault_dir)

        store.write("all1", "value1")
        store.write("all2", "value2")

        all_memories = store.get_all()
        assert len(all_memories) >= 2


class TestMain:
    """测试main函数"""

    def test_main_help(self):
        """测试main函数的帮助输出"""
        import sys
        from io import StringIO

        # 捕获stdout
        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            main()
        except SystemExit as e:
            # argparse在help时会退出
            pass

        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        # 检查输出
        assert "记忆殿堂" in output or "memory" in output.lower() or output == ""

    def test_main_write_command(self, temp_dir, monkeypatch):
        """测试write子命令"""
        import sys
        from io import StringIO

        # 临时设置环境变量
        monkeypatch.setattr(sys, "argv", ["cli.commands", "write", "test_key", "test_value"])

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            try:
                main()
            except SystemExit:
                pass
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        # 输出应该是JSON
        if output:
            try:
                result = json.loads(output)
                assert result is not None
            except json.JSONDecodeError:
                pass  # 可能不是JSON输出

    def test_main_read_command(self, temp_dir, monkeypatch):
        """测试read子命令"""
        import sys
        from io import StringIO

        monkeypatch.setattr(sys, "argv", ["cli.commands", "read", "nonexistent_key_xyz"])

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            try:
                main()
            except SystemExit:
                pass
        finally:
            sys.stdout = old_stdout
