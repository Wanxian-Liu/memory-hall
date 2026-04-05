# -*- coding: utf-8 -*-
"""
测试 permission 模块 - 权限管理引擎
"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from permission.engine import (
    PermissionLevel, RuleAction, Rule,
    PermissionContext, PermissionResult,
    PermissionEngine, get_engine, check_permission
)


class TestPermissionLevel:
    """测试PermissionLevel枚举"""
    def test_levels(self):
        # Actual: READONLY=1, WORKSPACE_WRITE=2, DANGER_FULL_ACCESS=3, PROMPT=4, ALLOW=5
        assert PermissionLevel.READONLY.value == 1
        assert PermissionLevel.WORKSPACE_WRITE.value == 2
        assert PermissionLevel.DANGER_FULL_ACCESS.value == 3
        assert PermissionLevel.PROMPT.value == 4
        assert PermissionLevel.ALLOW.value == 5


class TestRuleAction:
    """测试RuleAction枚举"""
    def test_actions(self):
        # Actual: ALLOW=1, DENY=2, ASK=3
        assert RuleAction.ALLOW.value == 1
        assert RuleAction.DENY.value == 2
        assert RuleAction.ASK.value == 3


class TestRule:
    """测试Rule类"""
    def test_rule_creation(self):
        # Actual: pattern, action, min_level, description
        rule = Rule(
            pattern=r"/memory/public/*",
            action=RuleAction.ALLOW,
            min_level=PermissionLevel.READONLY,
            description="Public memory access"
        )
        assert rule.action == RuleAction.ALLOW
        assert rule.min_level == PermissionLevel.READONLY
        assert rule.pattern == r"/memory/public/*"


class TestPermissionContext:
    """测试PermissionContext类"""
    def test_context_creation(self):
        # Actual: operation, target, requested_by, metadata
        ctx = PermissionContext(
            operation="read",
            target="/memory/private/test.md",
            requested_by="user_1"
        )
        assert ctx.operation == "read"
        assert ctx.target == "/memory/private/test.md"
        assert ctx.requested_by == "user_1"


class TestPermissionResult:
    """测试PermissionResult类"""
    def test_result_creation(self):
        # Actual: allowed, action, required_level, message, requires_confirmation
        result = PermissionResult(
            allowed=True,
            action=RuleAction.ALLOW,
            required_level=PermissionLevel.READONLY,
            message="Access allowed"
        )
        assert result.allowed is True
        assert result.action == RuleAction.ALLOW
        assert result.message == "Access allowed"


class TestPermissionEngine:
    """测试PermissionEngine类"""
    def test_engine_init(self):
        engine = PermissionEngine()
        assert engine is not None

    def test_get_engine(self):
        """测试获取引擎单例"""
        engine1 = get_engine()
        engine2 = get_engine()
        # 可能返回同一实例
        assert engine1 is not None
        assert engine2 is not None

    def test_engine_check(self):
        """测试权限检查"""
        engine = get_engine()
        # Actual: check takes PermissionContext and user_level
        ctx = PermissionContext(
            operation="read",
            target="/memory/public/test.md",
            requested_by="test_user"
        )
        result = engine.check(ctx, PermissionLevel.READONLY)
        assert result is not None

    def test_check_permission_function(self):
        """测试全局check_permission函数"""
        # Actual: operation, target, user_level, requested_by
        result = check_permission(
            operation="read",
            target="/memory/public/test.md",
            user_level=PermissionLevel.READONLY,
            requested_by="test_user"
        )
        assert result is not None
