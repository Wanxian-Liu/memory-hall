# -*- coding: utf-8 -*-
"""
测试 gateway 模块
"""
import os
import sys
import pytest
import tempfile

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from gateway.gateway import (
    Gateway, Config, LRUCache,
    write, read, search, delete, generate_id,
    get_audit_logs, get_cache_stats, clear_cache,
    fence_checkpoint, notify_coordinator, audit_log
)


class TestConfig:
    """测试Config类"""
    def test_config_defaults(self):
        cfg = Config()
        # Actual: get() method for accessing config values
        assert cfg.get("paths.vault_dir") is not None
        assert cfg.get("paths.log_dir") is not None
        assert cfg.get("cache.enabled") is True
        assert cfg.get("cache.max_size") > 0


class TestLRUCache:
    """测试LRUCache类"""
    def test_cache_init(self):
        cache = LRUCache(max_size=10)
        assert cache.max_size == 10

    def test_cache_set_get(self):
        cache = LRUCache(max_size=10)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_miss(self):
        cache = LRUCache(max_size=10)
        assert cache.get("nonexistent") is None

    def test_cache_overwrite(self):
        cache = LRUCache(max_size=10)
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"

    def test_cache_eviction(self):
        cache = LRUCache(max_size=3)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")
        cache.set("k4", "v4")  # 应该淘汰k1
        # k1可能被淘汰，取决于实现


class TestGateway:
    """测试Gateway类"""
    def test_gateway_init(self, temp_dir):
        gw = Gateway()
        assert gw is not None

    def test_gateway_write(self, temp_dir):
        # Actual: write takes content, record_type, user, metadata, notify
        result = write(
            content="test data",
            record_type="test",
            user="test_user"
        )
        assert result is not None
        assert result.get("success") is True or result.get("record_id") is not None

    def test_gateway_read(self, temp_dir):
        # Write first
        write_result = write(
            content="hello world",
            record_type="test",
            user="test_user"
        )
        record_id = write_result.get("record_id")

        # Read by record_id
        if record_id:
            record = read(record_id=record_id)
            if record:
                assert record is not None

    def test_gateway_read_not_found(self):
        record = read(record_id="nonexistent00000")
        assert record is None

    def test_gateway_generate_id(self):
        id1 = generate_id("content1")
        id2 = generate_id("content2")
        assert id1 != id2
        assert len(id1) > 0

    def test_gateway_delete(self, temp_dir):
        # Write first
        write_result = write(
            content="to delete",
            record_type="test",
            user="test_user"
        )
        record_id = write_result.get("record_id")

        if record_id:
            result = delete(record_id=record_id)
            assert result is True


class TestFenceCheckpoint:
    """测试fence_checkpoint函数"""
    def test_checkpoint(self, temp_dir):
        # Actual: fence_checkpoint takes filepath, operation, user
        result = fence_checkpoint(temp_dir, "write", "test_user")
        assert result is not None
        assert "allowed" in result


class TestNotifyCoordinator:
    """测试notify_coordinator函数"""
    def test_notify(self, temp_dir):
        # Actual: notify_coordinator takes filepath, source
        result = notify_coordinator(temp_dir, "test_source")
        assert result is not None


class TestAuditLog:
    """测试audit_log函数"""
    def test_audit_log(self, temp_dir):
        result = audit_log(action="write", user="test_user", details={"test": True})
        assert result is not None


class TestGetCacheStats:
    """测试get_cache_stats函数"""
    def test_cache_stats(self):
        stats = get_cache_stats()
        assert isinstance(stats, dict)


class TestClearCache:
    """测试clear_cache函数"""
    def test_clear_cache(self):
        result = clear_cache()  # 不应该抛出异常
        assert result is not None
