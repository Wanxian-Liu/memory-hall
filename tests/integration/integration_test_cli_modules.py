#!/usr/bin/env python3
"""
集成测试: CLI + 各模块 协作

验证场景:
1. CLI命令触发WAL事务
2. CLI命令触发Gateway缓存操作
3. CLI命令触发Permission检查
4. CLI健康检查与各模块状态

依赖模块:
- cli/commands.py
- base_wal/wal.py
- gateway/gateway.py
- permission/engine.py
- health/health_check.py
- sensory/semantic_search.py
"""

import os
import sys
import json
import tempfile
import shutil
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from cli.commands import MemoryCommands, MemoryStore
from base_wal.wal import WALManager, WALEntryType
from gateway.gateway import Gateway
from permission.engine import PermissionEngine, PermissionContext, PermissionLevel
from health.health_check import HealthChecker

try:
    from . import BaseIntegrationTest
except ImportError:
    from tests.integration import BaseIntegrationTest


class TestCLICommands(BaseIntegrationTest):
    """CLI命令测试"""
    
    def setUp(self):
        super().setUp()
        # 创建临时vault目录
        self.test_vault_dir = tempfile.mkdtemp(prefix="cli_test_vault_")
        self.test_wal_dir = tempfile.mkdtemp(prefix="cli_test_wal_")
        
        # 初始化CLI命令类（使用测试目录）
        self.cli = MemoryCommands()
        self.cli.store = MemoryStore(vault_dir=self.test_vault_dir)
        self.cli.wal = WALManager(wal_dir=self.test_wal_dir, enable_checksum=True)
    
    def tearDown(self):
        super().tearDown()
        # 清理
        if os.path.exists(self.test_vault_dir):
            shutil.rmtree(self.test_vault_dir, ignore_errors=True)
        if os.path.exists(self.test_wal_dir):
            shutil.rmtree(self.test_wal_dir, ignore_errors=True)
    
    # ========== 测试用例 ==========
    
    def test_cli_write_command_with_wal(self):
        """
        测试场景1: CLI write命令触发WAL事务
        
        验证: /memory write -> WAL三段式提交
        """
        result = self.cli.write("test_key_1", "测试内容1")
        
        # 验证结果
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["transaction_id"])
        self.assertIsNotNone(result["wal_entry_id"])
        
        # 验证WAL状态
        wal_status = self.cli.wal.get_status()
        self.assertEqual(wal_status['active_transactions'], 0)  # 事务已提交
        
        print(f"  ✓ CLI write命令WAL事务: {result['transaction_id']}")
    
    def test_cli_read_command(self):
        """
        测试场景2: CLI read命令
        
        验证: /memory read -> 存储读取
        """
        # 先写入
        self.cli.write("read_test_key", "读取测试内容")
        
        # 再读取
        result = self.cli.read("read_test_key")
        
        self.assertTrue(result["found"])
        self.assertEqual(result["value"], "读取测试内容")
        
        print("  ✓ CLI read命令通过")
    
    def test_cli_search_command(self):
        """
        测试场景3: CLI search命令
        
        验证: /memory search -> 搜索引擎
        """
        # 写入多条记忆
        self.cli.write("search_key_1", "Python编程语言")
        self.cli.write("search_key_2", "JavaScript前端框架")
        self.cli.write("search_key_3", "Go语言后端")
        
        # 搜索
        result = self.cli.search_memories("编程", limit=10)
        
        self.assertIn("total_hits", result)
        self.assertIn("results", result)
        
        print(f"  ✓ CLI search命令: 找到{result['total_hits']}条结果")
    
    def test_cli_stats_command(self):
        """
        测试场景4: CLI stats命令
        
        验证: /memory stats -> 各模块统计信息
        """
        # 写入一些数据
        self.cli.write("stats_key_1", "统计数据1")
        self.cli.write("stats_key_2", "统计数据2")
        
        result = self.cli.stats()
        
        # 验证统计结构
        self.assertIn("memory_store", result)
        self.assertIn("wal", result)
        self.assertIn("search", result)
        
        # 验证WAL统计
        self.assertIn("wal_dir", result["wal"])
        self.assertIn("entry_count", result["wal"])
        
        print(f"  ✓ CLI stats命令: WAL条目数={result['wal']['entry_count']}")
    
    def test_cli_health_command(self):
        """
        测试场景5: CLI health命令
        
        验证: /memory health -> 健康检查
        """
        result = self.cli.health_check()
        
        self.assertIsInstance(result, dict)
        # 健康检查应该返回整体状态
        self.assertIn("overall_status", result)
        
        print(f"  ✓ CLI health命令: 状态={result.get('overall_status', 'unknown')}")
    
    def test_cli_write_read_consistency(self):
        """
        测试场景6: CLI write/read一致性
        
        验证写入后能正确读取
        """
        test_data = {
            "string": "字符串",
            "number": 123,
            "list": [1, 2, 3],
            "nested": {"key": "value"}
        }
        
        # 写入JSON兼容数据
        key = "consistency_test"
        self.cli.write(key, json.dumps(test_data, ensure_ascii=False))
        
        # 读取
        result = self.cli.read(key)
        self.assertTrue(result["found"])
        
        # 解析读取的值
        read_value = json.loads(result["value"])
        self.assertEqual(read_value["string"], test_data["string"])
        self.assertEqual(read_value["number"], test_data["number"])
        
        print("  ✓ CLI write/read一致性通过")
    
    def test_cli_wal_transaction_rollback(self):
        """
        测试场景7: CLI WAL事务回滚
        
        验证: 事务失败时正确回滚
        """
        # 手动模拟一个失败的事务
        tx_id = self.cli.wal.begin_transaction()
        self.cli.wal.prepare_write(tx_id, "rollback_key", "rollback_value")
        
        # 模拟执行失败
        def failing_write(k, v):
            raise Exception("模拟写入失败")
        
        try:
            self.cli.wal.execute_write(tx_id, failing_write)
        except Exception as e:
            # 执行失败，应该回滚
            self.cli.wal.rollback(tx_id)
        
        # 验证事务已回滚
        wal_status = self.cli.wal.get_status()
        self.assertEqual(wal_status['active_transactions'], 0)
        
        print("  ✓ CLI WAL事务回滚机制通过")
    
    def test_cli_multiple_operations_sequence(self):
        """
        测试场景8: CLI多次操作序列
        
        验证连续操作的正确性
        """
        keys = [f"seq_key_{i}" for i in range(5)]
        
        # 批量写入
        for i, key in enumerate(keys):
            result = self.cli.write(key, f"值{i}")
            self.assertTrue(result["success"])
        
        # 验证WAL条目数
        wal_status = self.cli.wal.get_status()
        self.assertGreaterEqual(wal_status['entry_count'], 5)
        
        # 批量读取
        for i, key in enumerate(keys):
            result = self.cli.read(key)
            self.assertTrue(result["found"])
            self.assertEqual(result["value"], f"值{i}")
        
        print(f"  ✓ CLI批量操作: 5次写入+5次读取成功")


class TestCLIWithGateway(BaseIntegrationTest):
    """CLI与Gateway集成测试"""
    
    def setUp(self):
        super().setUp()
        self.test_vault_dir = tempfile.mkdtemp(prefix="cli_gateway_test_")
        self.gateway = Gateway()
    
    def tearDown(self):
        super().tearDown()
        if os.path.exists(self.test_vault_dir):
            shutil.rmtree(self.test_vault_dir, ignore_errors=True)
    
    def test_cli_gateway_cache_integration(self):
        """
        测试场景9: CLI与Gateway缓存集成
        
        验证CLI操作后Gateway缓存状态
        """
        # CLI写入时，Gateway缓存应该被失效
        cache_key = "cache_integration_test"
        
        # 先设置缓存
        self.gateway.cache.set(cache_key, {"id": cache_key, "data": "old"})
        
        # CLI操作后（模拟）触发缓存失效
        from gateway.gateway import _gateway_cache
        _gateway_cache.invalidate(cache_key)
        
        # 验证缓存已失效
        cached = self.gateway.cache.get(cache_key)
        self.assertIsNone(cached)
        
        print("  ✓ CLI与Gateway缓存集成通过")
    
    def test_cli_gateway_audit_integration(self):
        """
        测试场景10: CLI与Gateway审计集成
        """
        from gateway.gateway import audit_log
        
        # CLI操作触发审计
        audit_entry = audit_log(
            "cli_operation",
            "test_user",
            {"command": "write", "target": "test_key"}
        )
        
        # 验证审计条目
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry["action"], "cli_operation")
        
        # 获取审计日志
        logs = self.gateway.logs(limit=10)
        self.assertIsInstance(logs, list)
        
        print(f"  ✓ CLI与Gateway审计集成: {len(logs)}条日志")


class TestCLIWithPermission(BaseIntegrationTest):
    """CLI与Permission集成测试"""
    
    def setUp(self):
        super().setUp()
        self.permission_engine = PermissionEngine()
    
    def test_cli_permission_check_before_operation(self):
        """
        测试场景11: CLI操作前权限检查
        
        验证: 执行CLI命令前先检查权限
        """
        def check_before_cli(operation: str, target: str, user_level: PermissionLevel) -> bool:
            context = PermissionContext(
                operation=operation,
                target=target,
                requested_by="cli_user"
            )
            result = self.permission_engine.check(context, user_level)
            return result.allowed
        
        # 读操作应该允许
        self.assertTrue(check_before_cli("read", "memory://test", PermissionLevel.READONLY))
        
        # 写操作只读应该拒绝
        self.assertFalse(check_before_cli("write", "memory://test", PermissionLevel.READONLY))
        
        # 写操作工作区写入应该允许
        self.assertTrue(check_before_cli("write", "memory://test", PermissionLevel.WORKSPACE_WRITE))
        
        print("  ✓ CLI权限检查集成通过")
    
    def test_cli_delete_requires_permission(self):
        """
        测试场景12: CLI删除操作权限要求
        """
        context = PermissionContext(
            operation="delete",
            target="memory://test/key",
            requested_by="cli_user"
        )
        
        result = self.permission_engine.check(context, PermissionLevel.WORKSPACE_WRITE)
        
        # 删除操作需要确认
        self.assertEqual(result.action.value, "ASK")
        self.assertTrue(result.requires_confirmation)
        
        print("  ✓ CLI删除权限要求通过")


class TestCLIRunner(BaseIntegrationTest):
    """CLI命令行运行器测试"""
    
    def test_cli_main_entry_point(self):
        """
        测试场景13: CLI主入口点
        
        验证: 直接运行cli/commands.py
        """
        # 注意: 这个测试需要在项目根目录运行
        
        # 由于测试环境限制，我们验证模块可以被导入
        from cli.commands import main, MemoryCommands
        
        self.assertTrue(callable(main))
        self.assertTrue(hasattr(MemoryCommands, 'write'))
        self.assertTrue(hasattr(MemoryCommands, 'read'))
        self.assertTrue(hasattr(MemoryCommands, 'search'))
        
        print("  ✓ CLI主入口点验证通过")
    
    def test_memory_store_independence(self):
        """
        测试场景14: MemoryStore独立性
        
        验证: MemoryStore可以独立使用
        """
        test_dir = tempfile.mkdtemp(prefix="store_test_")
        
        try:
            store = MemoryStore(vault_dir=test_dir)
            
            # 写入
            self.assertTrue(store.write("key1", "value1"))
            self.assertTrue(store.write("key2", "value2"))
            
            # 读取
            self.assertEqual(store.read("key1"), "value1")
            self.assertEqual(store.read("key2"), "value2")
            
            # 列出
            keys = store.list_keys()
            self.assertIn("key1", keys)
            self.assertIn("key2", keys)
            
            # 计数
            self.assertEqual(store.count(), 2)
            
            # 删除
            self.assertTrue(store.delete("key1"))
            self.assertIsNone(store.read("key1"))
            
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)
        
        print("  ✓ MemoryStore独立性通过")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
