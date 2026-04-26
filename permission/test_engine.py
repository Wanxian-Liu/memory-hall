# -*- coding: utf-8 -*-
"""
测试 permission/engine.py - 五级权限模型 (L1认证 + L5频率限制)
"""
import os
import sys
from pathlib import Path
import pytest
import time

PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, PROJECT_ROOT)

from permission.engine import (
    # L1 认证
    AuthResult, JWTAuthenticator, authenticate,
    # L5 频率限制
    RateLimitResult, RateLimiter, check_rate_limit,
    # 核心
    PermissionEngine, PermissionContext, PermissionLevel, RuleAction,
    check_permission, get_engine, get_authenticator, get_rate_limiter
)


# ============================================================================
# L1: 身份认证测试
# ============================================================================

class TestJWTAuthenticator:
    """测试JWT认证器"""
    
    def test_authenticate_empty_token(self):
        """测试空token被拒绝"""
        auth = JWTAuthenticator(secret_key="test-secret")
        result = auth.authenticate("user1", "")
        assert not result.success
        assert "不能为空" in result.error
    
    def test_authenticate_valid_token_fallback(self):
        """测试有效token认证(无PyJWT回退模式)"""
        auth = JWTAuthenticator(secret_key="test-secret")
        token = auth.generate_token("user1")
        
        # 验证token格式
        assert "." in token
        
        # 验证认证
        result = auth.authenticate("user1", token)
        assert result.success
        assert result.user_id == "user1"
    
    def test_authenticate_invalid_user(self):
        """测试user_id不匹配"""
        auth = JWTAuthenticator(secret_key="test-secret")
        token = auth.generate_token("user1")
        
        result = auth.authenticate("user2", token)
        assert not result.success
    
    def test_token_revocation(self):
        """测试token吊销"""
        auth = JWTAuthenticator(secret_key="test-secret")
        token = auth.generate_token("user1")
        
        # 首次应该成功
        assert auth.authenticate("user1", token).success
        
        # 吊销
        auth.revoke_token(token)
        
        # 再次应该失败
        assert not auth.authenticate("user1", token).success
        assert "已被吊销" in auth.authenticate("user1", token).error
    
    def test_generate_and_verify_token(self):
        """测试token生成和验证"""
        auth = JWTAuthenticator(secret_key="my-secret-key", issuer="test-issuer")
        token = auth.generate_token("testuser", expires_in=3600)
        
        result = auth.authenticate("testuser", token)
        assert result.success


class TestAuthenticateFunction:
    """测试全局authenticate函数"""
    
    def test_authenticate_via_global(self):
        """测试全局认证函数"""
        # 设置全局认证器
        auth = get_authenticator()
        auth.secret_key = "global-secret"
        token = auth.generate_token("global_user")
        
        result = authenticate("global_user", token)
        assert result.success


# ============================================================================
# L5: 频率限制测试
# ============================================================================

class TestRateLimiter:
    """测试频率限制器"""
    
    def test_rate_limiter_allows_under_limit(self):
        """测试限制内请求允许"""
        limiter = RateLimiter()
        
        # 读操作默认100次/分
        for i in range(50):
            result = limiter.check("user1", "read")
            assert result.allowed
            assert result.current_count == i + 1
    
    def test_rate_limiter_blocks_over_limit(self):
        """测试超限请求被拒绝"""
        limiter = RateLimiter({"read": (5, 60)})
        
        # 消耗完配额
        for i in range(5):
            result = limiter.check("user1", "read")
            assert result.allowed
        
        # 第6次应该被拒绝
        result = limiter.check("user1", "read")
        assert not result.allowed
        assert result.current_count == 5
        assert result.limit == 5
        assert result.retry_after > 0
    
    def test_different_operations_have_different_limits(self):
        """测试不同操作有不同限制"""
        limiter = RateLimiter()
        
        # read: 100次/分
        for _ in range(100):
            limiter.check("user1", "read")
        
        # read应该超限
        assert not limiter.check("user1", "read").allowed
        
        # write: 20次/分 - 应该还能用
        assert limiter.check("user1", "write").allowed
        
        # distill: 5次/分 - 应该还能用
        assert limiter.check("user1", "distill").allowed
    
    def test_rate_limiter_reset(self):
        """测试重置功能"""
        limiter = RateLimiter({"read": (5, 60)})
        
        # 消耗配额
        for _ in range(5):
            limiter.check("user1", "read")
        
        assert not limiter.check("user1", "read").allowed
        
        # 重置
        limiter.reset("user1", "read")
        
        # 应该可以继续使用
        assert limiter.check("user1", "read").allowed
    
    def test_rate_limiter_window_expiry(self):
        """测试窗口过期"""
        limiter = RateLimiter({"fast": (2, 1)})  # 1秒窗口
        
        limiter.check("user1", "fast")
        limiter.check("user1", "fast")
        assert not limiter.check("user1", "fast").allowed
        
        # 等待窗口过期
        time.sleep(1.1)
        
        assert limiter.check("user1", "fast").allowed
    
    def test_rate_limiter_get_status(self):
        """测试状态查询(不消耗配额)"""
        limiter = RateLimiter({"read": (100, 60)})
        
        limiter.check("user1", "read")
        limiter.check("user1", "read")
        
        status = limiter.get_status("user1", "read")
        assert status.current_count == 2
        assert status.limit == 100
        
        # 再次查询不增加计数
        status2 = limiter.get_status("user1", "read")
        assert status2.current_count == 2
    
    def test_rate_limiter_concurrent_access(self):
        """测试并发访问"""
        import threading
        
        limiter = RateLimiter({"read": (100, 60)})
        results = []
        
        def worker():
            for _ in range(30):
                results.append(limiter.check("user1", "read").allowed)
        
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 允许的请求数不应该超过100
        allowed_count = sum(1 for r in results if r)
        assert allowed_count <= 100


class TestCheckRateLimitFunction:
    """测试全局check_rate_limit函数"""
    
    def test_global_rate_limiter(self):
        """测试全局频率限制"""
        limiter = get_rate_limiter()
        limiter.reset("testuser", "read")
        
        result = check_rate_limit("testuser", "read")
        assert result.allowed


# ============================================================================
# PermissionEngine 集成测试
# ============================================================================

class TestPermissionEngineL1Integration:
    """测试PermissionEngine的L1集成"""
    
    def test_check_requires_auth_when_credentials_provided(self):
        """测试提供凭证时需要认证"""
        engine = PermissionEngine()
        engine._authenticator = JWTAuthenticator(secret_key="secret")
        
        context = PermissionContext(operation="read", target="/memory/test")
        
        # 提供错误的token
        result = engine.check(context, PermissionLevel.READONLY, 
                              user_id="user1", auth_token="invalid-token")
        assert not result.allowed
        assert "L1认证失败" in result.message
    
    def test_check_allows_without_auth_if_no_credentials(self):
        """测试无凭证时不进行L1检查"""
        engine = PermissionEngine()
        
        context = PermissionContext(operation="read", target="/memory/test")
        
        # 不提供凭证，应该继续进行权限检查
        result = engine.check(context, PermissionLevel.READONLY)
        assert result.allowed  # 读操作默认允许


class TestPermissionEngineL5Integration:
    """测试PermissionEngine的L5集成"""
    
    def test_check_blocks_over_rate_limit(self):
        """测试超限被阻止"""
        engine = PermissionEngine()
        engine._rate_limiter = RateLimiter({"read": (3, 60)})
        
        context = PermissionContext(operation="read", target="/memory/test")
        
        # 消耗配额
        for _ in range(3):
            result = engine.check(context, PermissionLevel.READONLY, user_id="user1")
            assert result.allowed
        
        # 超限
        result = engine.check(context, PermissionLevel.READONLY, user_id="user1")
        assert not result.allowed
        assert "L5频率限制" in result.message
    
    def test_write_operation_uses_write_limit(self):
        """测试写操作使用写限制"""
        from permission.engine import Rule, RuleAction
        
        engine = PermissionEngine()
        engine._rate_limiter = RateLimiter({"write": (2, 60)})
        # 添加允许写入的规则
        engine.add_rule(Rule(
            pattern=r"^write:/memory/",
            action=RuleAction.ALLOW,
            min_level=PermissionLevel.WORKSPACE_WRITE,
            description="允许写入memory目录"
        ))
        
        context = PermissionContext(operation="write", target="/memory/test")
        
        for _ in range(2):
            result = engine.check(context, PermissionLevel.WORKSPACE_WRITE, user_id="user1")
            assert result.allowed
        
        result = engine.check(context, PermissionLevel.WORKSPACE_WRITE, user_id="user1")
        assert not result.allowed
    
    def test_distill_operation_uses_distill_limit(self):
        """测试distill操作使用专门的限制"""
        from permission.engine import Rule, RuleAction
        
        engine = PermissionEngine()
        engine._rate_limiter = RateLimiter({"distill": (2, 60)})
        # 添加允许distill的规则
        engine.add_rule(Rule(
            pattern=r"^distill:",
            action=RuleAction.ALLOW,
            min_level=PermissionLevel.READONLY,
            description="允许distill操作"
        ))
        
        context = PermissionContext(operation="distill", target="/memory/test")
        
        for _ in range(2):
            result = engine.check(context, PermissionLevel.READONLY, user_id="user1")
            assert result.allowed
        
        result = engine.check(context, PermissionLevel.READONLY, user_id="user1")
        assert not result.allowed


class TestPermissionEngineFullFlow:
    """测试完整权限检查流程"""
    
    def test_full_flow_with_l1_and_l5(self):
        """测试L1认证 + 规则检查 + L5限制的完整流程"""
        engine = PermissionEngine()
        engine._authenticator = JWTAuthenticator(secret_key="secret")
        engine._rate_limiter = RateLimiter({"read": (10, 60)})
        
        token = engine._authenticator.generate_token("user1")
        context = PermissionContext(operation="read", target="/memory/test")
        
        # 正常请求应该通过
        result = engine.check(context, PermissionLevel.READONLY, 
                              user_id="user1", auth_token=token)
        assert result.allowed
    
    def test_path_traversal_still_blocked(self):
        """测试路径遍历攻击仍然被阻止"""
        engine = PermissionEngine()
        
        context = PermissionContext(operation="read", target="../../../etc/passwd")
        result = engine.check(context, PermissionLevel.ALLOW)
        
        assert not result.allowed
        assert "路径遍历" in result.message
    
    def test_protocol_validation_still_active(self):
        """测试协议验证仍然有效"""
        engine = PermissionEngine()
        
        context = PermissionContext(operation="read", target="file:///etc/passwd")
        result = engine.check(context, PermissionLevel.ALLOW)
        
        assert not result.allowed
        assert "协议验证" in result.message or "协议" in result.message


# ============================================================================
# 快捷函数测试
# ============================================================================

class TestCheckPermissionFunction:
    """测试快捷权限检查函数"""
    
    def test_check_permission_with_auth(self):
        """测试带认证的快捷检查"""
        engine = get_engine()
        engine._authenticator = JWTAuthenticator(secret_key="secret")
        engine._rate_limiter = RateLimiter({"read": (100, 60)})
        
        token = engine._authenticator.generate_token("user1")
        
        result = check_permission(
            operation="read",
            target="/memory/test",
            user_level=PermissionLevel.READONLY,
            user_id="user1",
            auth_token=token
        )
        assert result.allowed
    
    def test_check_permission_blocks_on_rate_limit(self):
        """测试快捷检查在超限时阻止"""
        engine = get_engine()
        engine._rate_limiter = RateLimiter({"read": (2, 60)})
        engine._rate_limiter.reset("rateuser")
        
        # 前两次通过
        assert check_permission("read", "/test", PermissionLevel.READONLY, 
                                user_id="rateuser").allowed
        assert check_permission("read", "/test", PermissionLevel.READONLY, 
                                user_id="rateuser").allowed
        
        # 第三次被阻止
        result = check_permission("read", "/test", PermissionLevel.READONLY, 
                                 user_id="rateuser")
        assert not result.allowed


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_none_user_id_no_l1_check(self):
        """测试user_id为None时不进行L1检查"""
        engine = PermissionEngine()
        engine._authenticator = JWTAuthenticator(secret_key="secret")
        
        context = PermissionContext(operation="read", target="/memory/test")
        
        # 只有token没有user_id
        result = engine.check(context, PermissionLevel.READONLY, 
                              user_id="", auth_token="some-token")
        # 空user_id不触发L1检查，只检查token是否为空
        # 因为user_id为空字符串被视为未提供认证信息
    
    def test_empty_operation_map_to_default_limit(self):
        """测试未知操作映射到default限制"""
        limiter = RateLimiter()
        
        result = limiter.check("user1", "unknown_operation")
        assert result.limit == 60  # default限制


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
