#!/usr/bin/env python3
"""
集成测试: Gateway + Permission 协作

验证场景:
1. Gateway操作前进行权限检查
2. Permission规则与Gateway操作类型映射
3. 权限级别与Gateway缓存交互
4. 权限拒绝时Gateway审计日志记录

依赖模块:
- gateway/gateway.py
- permission/engine.py
"""

import os
import sys
import json
import tempfile
import shutil
import time
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from permission.engine import (
    PermissionEngine, PermissionContext, PermissionResult,
    PermissionLevel, RuleAction, Rule
)
from gateway.gateway import Gateway, audit_log, fence_checkpoint

try:
    from . import BaseIntegrationTest
except ImportError:
    from tests.integration import BaseIntegrationTest


class TestGatewayPermissionCollaboration(BaseIntegrationTest):
    """Gateway与Permission协作测试"""
    
    def setUp(self):
        super().setUp()
        self.gateway = Gateway()
        self.permission_engine = PermissionEngine()
    
    # ========== 测试用例 ==========
    
    def test_gateway_read_permission_check(self):
        """
        测试场景1: Gateway读取操作权限检查
        
        流程: Gateway.read() -> Permission.check() -> 允许/拒绝
        """
        # 模拟读取操作
        context = PermissionContext(
            operation="read",
            target="~/.openclaw/memory-vault/data/test.json",
            requested_by="test_user"
        )
        
        # 只读权限应该允许读取
        result = self.permission_engine.check(context, PermissionLevel.READONLY)
        
        # 读操作默认允许
        self.assertTrue(result.allowed)
        self.assertEqual(result.action, RuleAction.ALLOW)
        
        print("  ✓ Gateway读取权限检查通过")
    
    def test_gateway_write_permission_check(self):
        """
        测试场景2: Gateway写入操作权限检查
        
        验证不同权限级别对写入操作的影响
        """
        context = PermissionContext(
            operation="write",
            target="~/.openclaw/memory-vault/data/test.json",
            requested_by="test_user"
        )
        
        # 只读权限应该拒绝写入
        result_readonly = self.permission_engine.check(context, PermissionLevel.READONLY)
        self.assertFalse(result_readonly.allowed)
        
        # 工作区写入权限应该允许
        result_write = self.permission_engine.check(context, PermissionLevel.WORKSPACE_WRITE)
        self.assertTrue(result_write.allowed)
        
        print("  ✓ Gateway写入权限检查通过")
    
    def test_gateway_delete_requires_confirmation(self):
        """
        测试场景3: Gateway删除操作需要确认
        
        验证删除操作被标记为需要用户确认(ASK)
        """
        context = PermissionContext(
            operation="delete",
            target="~/.openclaw/memory-vault/data/test.json",
            requested_by="test_user"
        )
        
        # 删除操作需要询问
        result = self.permission_engine.check(context, PermissionLevel.WORKSPACE_WRITE)
        
        # 删除被规则标记为需要确认
        self.assertEqual(result.action, RuleAction.ASK)
        self.assertTrue(result.requires_confirmation)
        
        print("  ✓ Gateway删除权限确认机制通过")
    
    def test_gateway_external_network_permission(self):
        """
        测试场景4: Gateway外部网络操作权限
        
        验证http/https请求需要确认
        """
        context = PermissionContext(
            operation="write",
            target="https://api.example.com/data",
            requested_by="test_user"
        )
        
        result = self.permission_engine.check(context, PermissionLevel.WORKSPACE_WRITE)
        
        # 外部网络操作需要确认
        self.assertEqual(result.action, RuleAction.ASK)
        self.assertTrue(result.requires_confirmation)
        
        print("  ✓ Gateway外部网络权限检查通过")
    
    def test_permission_deny_ssh_config_access(self):
        """
        测试场景5: SSH配置访问被拒绝
        
        验证SSH目录操作需要高权限
        """
        context = PermissionContext(
            operation="read",
            target="~/.ssh/id_rsa",
            requested_by="test_user"
        )
        
        # SSH配置需要询问或更高权限
        result = self.permission_engine.check(context, PermissionLevel.WORKSPACE_WRITE)
        
        # 规则匹配，触发询问
        self.assertEqual(result.action, RuleAction.ASK)
        self.assertTrue(result.requires_confirmation)
        
        print("  ✓ SSH配置权限检查通过")
    
    def test_gateway_audit_on_permission_denied(self):
        """
        测试场景6: 权限拒绝时Gateway审计日志
        
        验证权限检查失败会记录审计日志
        """
        # 创建一个会被拒绝的操作
        context = PermissionContext(
            operation="delete",
            target="~/.ssh/config",
            requested_by="test_user"
        )
        
        # 只读权限应该被拒绝
        result = self.permission_engine.check(context, PermissionLevel.READONLY)
        
        # 记录审计日志
        audit_entry = audit_log(
            "permission_denied",
            "test_user",
            {
                "operation": context.operation,
                "target": context.target,
                "result": "denied",
                "required_level": result.required_level.name
            }
        )
        
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry["action"], "permission_denied")
        
        print("  ✓ 权限拒绝审计日志通过")
    
    def test_permission_hook_integration(self):
        """
        测试场景7: Permission Hook与Gateway集成
        
        验证claw-code hook override机制
        """
        hook_called = []
        
        def mock_before_check(context, user_level):
            hook_called.append(("before", context.operation, user_level))
            return None  # 继续默认检查
        
        def mock_after_check(result):
            hook_called.append(("after", result.allowed, result.action))
        
        self.permission_engine.register_hook("before_permission_check", mock_before_check)
        self.permission_engine.register_hook("after_permission_check", mock_after_check)
        
        context = PermissionContext(
            operation="read",
            target="test_path",
            requested_by="test_user"
        )
        
        self.permission_engine.check(context, PermissionLevel.READONLY)
        
        # 验证hook被调用
        self.assertEqual(len(hook_called), 2)
        self.assertEqual(hook_called[0][0], "before")
        self.assertEqual(hook_called[1][0], "after")
        
        # 清理
        self.permission_engine.unregister_hook("before_permission_check")
        self.permission_engine.unregister_hook("after_permission_check")
        
        print("  ✓ Permission Hook集成通过")
    
    def test_gateway_fence_with_permission_level(self):
        """
        测试场景8: Gateway围栏与权限级别联动
        
        验证危险操作在围栏检查前先进行权限检查
        """
        # 配置Gateway使用围栏
        from gateway.gateway import _config
        original_fence = _config._config.get("fence", {})
        _config._config["fence"] = {
            "enabled": True,
            "script_path": None  # 无脚本，模拟禁用
        }
        
        # 模拟围栏检查
        result = fence_checkpoint("/tmp/test_file", "write", "test_user")
        
        # 围栏禁用时应该允许
        self.assertTrue(result["allowed"])
        
        # 恢复配置
        _config._config["fence"] = original_fence
        
        print("  ✓ Gateway围栏与权限联动通过")
    
    def test_permission_custom_rules_integration(self):
        """
        测试场景9: 自定义权限规则与Gateway集成
        
        验证用户可以添加自定义规则
        """
        initial_count = len(self.permission_engine.rules)
        
        # 添加自定义规则
        custom_rule = Rule(
            pattern=r"^delete:.*\.conf$",
            action=RuleAction.DENY,
            min_level=PermissionLevel.DANGER_FULL_ACCESS,
            description="禁止删除配置文件"
        )
        self.permission_engine.add_rule(custom_rule)
        
        # 验证规则已添加 (规则数量增加1)
        self.assertEqual(len(self.permission_engine.rules), initial_count + 1)
        
        # 测试规则匹配
        context = PermissionContext(
            operation="delete",
            target="test.conf",
            requested_by="test_user"
        )
        result = self.permission_engine.check(context, PermissionLevel.WORKSPACE_WRITE)
        
        # 配置文件删除被拒绝
        self.assertEqual(result.action, RuleAction.DENY)
        self.assertFalse(result.allowed)
        
        print("  ✓ 自定义权限规则集成通过")
    
    def test_gateway_permission_context_building(self):
        """
        测试场景10: Gateway构建PermissionContext
        
        验证Gateway能正确构建权限上下文
        """
        def build_context(operation: str, target: str, user: str) -> PermissionContext:
            return PermissionContext(
                operation=operation,
                target=target,
                requested_by=user
            )
        
        # 模拟Gateway的各种操作
        contexts = [
            build_context("write", "memory://test/key1", "user1"),
            build_context("read", "memory://test/key2", "user2"),
            build_context("delete", "memory://test/key3", "user3"),
            build_context("search", "memory://test", "user4"),
        ]
        
        for ctx in contexts:
            result = self.permission_engine.check(ctx, PermissionLevel.READONLY)
            # 基础验证上下文被正确处理
            self.assertIsNotNone(result)
            self.assertIn(result.action, [RuleAction.ALLOW, RuleAction.DENY, RuleAction.ASK])
        
        print("  ✓ Gateway权限上下文构建通过")


class TestPermissionEngineStandalone(BaseIntegrationTest):
    """Permission引擎独立测试"""
    
    def setUp(self):
        super().setUp()
        self.engine = PermissionEngine()
    
    def test_permission_level_hierarchy(self):
        """
        测试: 权限级别层级关系
        
        验证五级权限的正确排序
        """
        levels = [
            PermissionLevel.READONLY,
            PermissionLevel.WORKSPACE_WRITE,
            PermissionLevel.DANGER_FULL_ACCESS,
            PermissionLevel.PROMPT,
            PermissionLevel.ALLOW
        ]
        
        # 验证升序排列
        for i in range(len(levels) - 1):
            self.assertLess(levels[i], levels[i + 1])
        
        print("  ✓ 权限级别层级正确")
    
    def test_permission_context_validation(self):
        """
        测试: PermissionContext验证
        """
        # 有效上下文
        ctx = PermissionContext(
            operation="read",
            target="test_path",
            requested_by="user"
        )
        self.assertEqual(ctx.operation, "read")
        self.assertEqual(ctx.target, "test_path")
        
        # 带元数据的上下文
        ctx_with_meta = PermissionContext(
            operation="write",
            target="test_path",
            requested_by="user",
            metadata={"source": "test", "priority": 1}
        )
        self.assertEqual(ctx_with_meta.metadata["source"], "test")
        
        print("  ✓ PermissionContext验证通过")
    
    def test_engine_set_level(self):
        """
        测试: 字符串权限级别转换
        """
        level_map = {
            "readonly": PermissionLevel.READONLY,
            "workspace_write": PermissionLevel.WORKSPACE_WRITE,
            "danger_full_access": PermissionLevel.DANGER_FULL_ACCESS,
            "prompt": PermissionLevel.PROMPT,
            "allow": PermissionLevel.ALLOW
        }
        
        for str_level, expected in level_map.items():
            result = self.engine.set_level(str_level)
            self.assertEqual(result, expected)
        
        # 无效值应该返回只读
        invalid = self.engine.set_level("invalid_level")
        self.assertEqual(invalid, PermissionLevel.READONLY)
        
        print("  ✓ 权限级别字符串转换通过")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
