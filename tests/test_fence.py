# -*- coding: utf-8 -*-
"""
测试 fence 模块 - 围栏隔离系统
"""
import os
import sys
import pytest
import time

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from fence.fence import (
    SpaceType, Permission, SpaceBoundary, ViolationEvent,
    FenceAlert, MemoryPalaceFence,
    get_fence, check_boundary, validate_access
)


class TestSpaceType:
    """测试SpaceType枚举"""
    def test_types(self):
        assert SpaceType.PRIVATE.value == "private"
        assert SpaceType.LIBRARY.value == "library"
        assert SpaceType.PUBLIC.value == "public"


class TestPermission:
    """测试Permission枚举"""
    def test_permissions(self):
        assert Permission.NONE.value == 0
        assert Permission.READ.value == 1
        assert Permission.WRITE.value == 2
        assert Permission.ADMIN.value == 3


class TestSpaceBoundary:
    """测试SpaceBoundary类"""
    def test_boundary_creation(self):
        boundary = SpaceBoundary(
            space_type=SpaceType.PRIVATE,
            path="/tmp/private",
            permission=Permission.ADMIN
        )
        assert boundary.space_type == SpaceType.PRIVATE
        assert boundary.permission == Permission.ADMIN


class TestViolationEvent:
    """测试ViolationEvent类"""
    def test_event_creation(self):
        event = ViolationEvent(
            timestamp=time.time(),
            source_space=SpaceType.PUBLIC,
            target_space=SpaceType.PRIVATE,
            action="access",
            details="public tried to access private",
            severity="high"
        )
        assert event.source_space == SpaceType.PUBLIC
        assert event.target_space == SpaceType.PRIVATE
        assert event.severity == "high"


class TestFenceAlert:
    """测试FenceAlert类"""
    def test_alert_init(self):
        alert = FenceAlert()
        assert alert is not None

    def test_register_handler(self):
        """测试注册告警处理器"""
        alert = FenceAlert()
        called = []

        def handler(event):
            called.append(event)

        alert.register_handler(handler)
        assert len(alert._handlers) == 1

        # 触发
        event = ViolationEvent(
            timestamp=time.time(),
            source_space=SpaceType.PUBLIC,
            target_space=SpaceType.PRIVATE,
            action="access",
            details="test",
            severity="low"
        )
        alert.trigger(event)
        assert len(called) == 1

    def test_get_recent_violations(self):
        """测试获取最近违规记录"""
        alert = FenceAlert()
        violations = alert.get_recent_violations(limit=10)
        assert isinstance(violations, list)


class TestMemoryPalaceFence:
    """测试MemoryPalaceFence主类"""
    def test_fence_init(self, temp_dir):
        """测试围栏初始化"""
        fence = MemoryPalaceFence(base_path=temp_dir)
        assert fence is not None
        assert len(fence._spaces) == 3  # PRIVATE, LIBRARY, PUBLIC

    def test_set_current_context(self, temp_dir):
        """测试设置当前上下文"""
        fence = MemoryPalaceFence(base_path=temp_dir)
        fence.set_current_context("test_user", SpaceType.PRIVATE)
        assert fence._current_user == "test_user"
        assert fence._current_space == SpaceType.PRIVATE

    def test_check_boundary_allowed(self, temp_dir):
        """测试允许的边界访问"""
        fence = MemoryPalaceFence(base_path=temp_dir)
        fence.set_current_context("user1", SpaceType.PRIVATE)

        allowed, violation = fence.check_boundary(
            str(temp_dir) + "/library/test.md",
            action="read"
        )
        assert allowed is True

    def test_check_boundary_denied(self, temp_dir):
        """测试被拒绝的边界访问"""
        fence = MemoryPalaceFence(base_path=temp_dir)
        fence.set_current_context("user1", SpaceType.PUBLIC)

        allowed, violation = fence.check_boundary(
            str(temp_dir) + "/private/secret.md",
            action="read"
        )
        assert allowed is False
        assert violation is not None

    def test_validate_access_read(self, temp_dir):
        """测试验证读访问"""
        fence = MemoryPalaceFence(base_path=temp_dir)
        fence.set_current_context("user1", SpaceType.PRIVATE)

        allowed = fence.validate_access(
            str(temp_dir) + "/private/test.md",
            action="read"
        )
        assert allowed is True

    def test_validate_access_denied(self, temp_dir):
        """测试访问被拒绝"""
        fence = MemoryPalaceFence(base_path=temp_dir)
        fence.set_current_context("user1", SpaceType.PUBLIC)

        allowed = fence.validate_access(
            str(temp_dir) + "/private/secret.md",
            action="write"
        )
        assert allowed is False

    def test_enforce_isolation(self, temp_dir):
        """测试强制隔离"""
        fence = MemoryPalaceFence(base_path=temp_dir)
        fence.set_current_context("test_user", SpaceType.PRIVATE)

        report = fence.enforce_isolation()
        assert report is not None
        assert "version" in report
        assert report["version"] == "1.3.0"
        assert report["isolation_status"] == "active"

    def test_get_fence_status(self, temp_dir):
        """测试获取围栏状态"""
        fence = MemoryPalaceFence(base_path=temp_dir)
        status = fence.get_fence_status()

        assert status["version"] == "1.3.0"
        assert "current_space" in status
        assert "active_spaces" in status
        assert len(status["active_spaces"]) == 3


class TestFenceGlobalFunctions:
    """测试全局函数"""
    def test_get_fence(self):
        """测试获取全局围栏"""
        fence = get_fence()
        assert fence is not None
        assert isinstance(fence, MemoryPalaceFence)

    def test_check_boundary_function(self):
        """测试全局边界检查"""
        allowed, violation = check_boundary("/tmp/test.md", "read")
        assert isinstance(allowed, bool)

    def test_validate_access_function(self):
        """测试全局访问验证"""
        allowed = validate_access("/tmp/test.md", "read")
        assert isinstance(allowed, bool)

    def test_fence_singleton(self):
        """测试围栏单例"""
        fence1 = get_fence()
        fence2 = get_fence()
        assert fence1 is fence2
