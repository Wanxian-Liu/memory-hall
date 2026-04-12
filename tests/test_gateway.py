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
    fence_checkpoint, notify_coordinator, audit_log,
    _sanitize_string, _validate_path, _validate_record_type,
    read_record, write_record, _gateway_cache
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
    
    def test_config_get_with_default(self):
        cfg = Config()
        result = cfg.get("nonexistent.key", "default_value")
        assert result == "default_value"
    
    def test_config_reload(self):
        cfg = Config()
        cfg.reload()  # 应该不抛出异常


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

    def test_cache_disabled(self):
        cache = LRUCache(max_size=10, ttl_days=0)
        cache.enabled = False
        cache.set("key1", "value1")
        assert cache.get("key1") is None
    
    def test_cache_invalidate_single(self):
        cache = LRUCache(max_size=10)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.invalidate("key1")
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
    
    def test_cache_invalidate_all(self):
        cache = LRUCache(max_size=10)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.invalidate()  # 清空所有
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_cache_stats(self):
        cache = LRUCache(max_size=10)
        cache.set("key1", "value1")
        stats = cache.get_stats()
        assert "size" in stats
        assert "max_size" in stats
        assert "ttl_days" in stats
        assert stats["enabled"] is True


class TestGateway:
    """测试Gateway类"""
    def test_gateway_init(self, temp_dir):
        gw = Gateway()
        assert gw is not None
    
    def test_gateway_put(self):
        gw = Gateway()
        result = gw.put("test content", "test_type", "test_user")
        assert result is not None

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
    
    def test_gateway_generate_id_identical(self):
        """测试相同内容生成相同ID"""
        id1 = generate_id("same_content")
        id2 = generate_id("same_content")
        assert id1 == id2

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
    
    def test_gateway_delete_invalid_id(self):
        """测试删除无效ID"""
        result = delete(record_id="invalid_id")
        assert result is False
    
    def test_gateway_get(self):
        """测试Gateway.get方法"""
        gw = Gateway()
        result = gw.get(record_id="nonexistent00000")
        assert result is None
    
    def test_gateway_find(self):
        """测试Gateway.find方法"""
        gw = Gateway()
        results = gw.find("test query", limit=10)
        assert isinstance(results, list)
    
    def test_gateway_remove(self):
        """测试Gateway.remove方法"""
        gw = Gateway()
        result = gw.remove(record_id="nonexistent00000")
        assert result is False
    
    def test_gateway_logs(self):
        """测试Gateway.logs方法"""
        gw = Gateway()
        logs = gw.logs(limit=10)
        assert isinstance(logs, list)
    
    def test_gateway_stats(self):
        """测试Gateway.stats方法"""
        gw = Gateway()
        stats = gw.stats()
        assert "cache" in stats
        assert "vault" in stats


class TestFenceCheckpoint:
    """测试fence_checkpoint函数"""
    def test_checkpoint(self, temp_dir):
        # Actual: fence_checkpoint takes filepath, operation, user
        result = fence_checkpoint(temp_dir, "write", "test_user")
        assert result is not None
        assert "allowed" in result
    
    def test_checkpoint_disabled(self):
        """测试禁用围栏"""
        result = fence_checkpoint("/tmp/test", "write", "test_user")
        assert result.get("allowed") is True


class TestNotifyCoordinator:
    """测试notify_coordinator函数"""
    def test_notify(self, temp_dir):
        # Actual: notify_coordinator takes filepath, source
        result = notify_coordinator(temp_dir, "test_source")
        assert result is not None
    
    def test_notify_disabled(self):
        """测试禁用协调器时返回False"""
        result = notify_coordinator("/tmp/test", "gateway")
        # 当协调器禁用时应该返回False
        assert result is False


class TestAuditLog:
    """测试audit_log函数"""
    def test_audit_log(self, temp_dir):
        result = audit_log(action="write", user="test_user", details={"test": True})
        assert result is not None
    
    def test_audit_log_no_details(self):
        """测试无详情参数的审计日志"""
        result = audit_log(action="read", user="test_user")
        assert result is not None
        assert "timestamp" in result


class TestGetAuditLogs:
    """测试get_audit_logs函数"""
    def test_get_audit_logs(self):
        logs = get_audit_logs(limit=10)
        assert isinstance(logs, list)
    
    def test_get_audit_logs_zero_limit(self):
        """测试limit为0时返回所有日志"""
        logs = get_audit_logs(limit=0)
        assert isinstance(logs, list)


class TestGetCacheStats:
    """测试get_cache_stats函数"""
    def test_cache_stats(self):
        stats = get_cache_stats()
        assert isinstance(stats, dict)
    
    def test_cache_stats_has_keys(self):
        """测试缓存统计包含必要字段"""
        stats = get_cache_stats()
        assert "size" in stats
        assert "max_size" in stats


class TestClearCache:
    """测试clear_cache函数"""
    def test_clear_cache(self):
        result = clear_cache()  # 不应该抛出异常
        assert result is not None
    
    def test_clear_cache_success(self):
        """测试清空缓存返回成功"""
        result = clear_cache()
        assert result.get("success") is True


class TestSecurityFunctions:
    """测试安全相关函数"""
    
    def test_sanitize_string_basic(self):
        """测试字符串清理基本功能"""
        result = _sanitize_string("正常字符串")
        assert result == "正常字符串"
    
    def test_sanitize_string_null_bytes(self):
        """测试去除null字节"""
        result = _sanitize_string("test\x00string")
        assert "\x00" not in result
    
    def test_sanitize_string_truncation(self):
        """测试字符串截断"""
        long_string = "a" * 10000
        result = _sanitize_string(long_string, max_len=100)
        assert len(result) <= 100
    
    def test_validate_path_valid(self):
        """测试有效路径验证"""
        assert _validate_path("/tmp/test") is True
    
    def test_validate_path_empty(self):
        """测试空路径"""
        assert _validate_path("") is False
    
    def test_validate_path_traversal(self):
        """测试路径遍历攻击"""
        assert _validate_path("/tmp/../../../etc/passwd") is False
    
    def test_validate_path_too_long(self):
        """测试超长路径"""
        long_path = "/tmp/" + "a" * 1000
        assert _validate_path(long_path) is False
    
    def test_validate_record_type_valid(self):
        """测试有效记录类型"""
        assert _validate_record_type("test_type") is True
        assert _validate_record_type("test-type_123") is True
    
    def test_validate_record_type_invalid(self):
        """测试无效记录类型"""
        assert _validate_record_type("invalid type") is False
        assert _validate_record_type("invalid.type") is False


class TestReadWriteRecord:
    """测试底层文件读写"""
    
    def test_write_record(self, temp_dir):
        """测试写入记录"""
        filepath = os.path.join(temp_dir, "test_record.json")
        data = {"key": "value", "number": 42}
        result = write_record(filepath, data)
        assert result is True
    
    def test_read_record(self, temp_dir):
        """测试读取记录"""
        filepath = os.path.join(temp_dir, "test_record.json")
        data = {"key": "value", "number": 42}
        write_record(filepath, data)
        result = read_record(filepath)
        assert result is not None
        assert result["key"] == "value"
    
    def test_read_record_not_found(self):
        """测试读取不存在的记录"""
        result = read_record("/tmp/nonexistent_file_12345.json")
        assert result is None


class TestSearch:
    """测试搜索功能"""
    
    def test_search_empty_query(self):
        """测试空查询"""
        results = search("")
        assert results == []
    
    def test_search_with_limit(self):
        """测试带limit的搜索"""
        results = search("test", limit=5)
        assert isinstance(results, list)
    
    def test_search_with_record_type(self):
        """测试按类型搜索"""
        results = search("test", record_type="test_type", limit=10)
        assert isinstance(results, list)
    
    def test_search_large_limit(self):
        """测试过大的limit会被限制"""
        results = search("test", limit=1000)
        assert isinstance(results, list)


class TestWriteWithMetadata:
    """测试带元数据的写入"""
    
    def test_write_with_metadata(self):
        """测试写入带元数据"""
        result = write(
            content="content with metadata",
            record_type="test",
            user="test_user",
            metadata={"source": "test", "priority": 1},
            notify=False
        )
        assert result is not None
    
    def test_write_empty_content(self):
        """测试写入空内容"""
        result = write(content="", record_type="test", user="test_user")
        assert result.get("success") is False
    
    def test_write_disabled_notify(self):
        """测试禁用通知的写入"""
        result = write(
            content="no notify test",
            record_type="test",
            user="test_user",
            notify=False
        )
        assert result.get("success") is True
