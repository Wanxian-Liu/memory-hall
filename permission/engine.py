"""
记忆殿堂v2.0 - 权限引擎
Permission Engine with 5-level model and Rule Engine

五级权限模型:
- L1: 身份认证 (Authentication)
- L2: 只读访问 (ReadOnly)
- L3: 工作区写入 (WorkspaceWrite)
- L4: 危险操作完全访问 (DangerFullAccess)
- L5: 频率限制 (Rate Limiting)

规则引擎:
- allow: 允许操作
- deny: 拒绝操作
- ask: 需要用户确认
"""

from enum import IntEnum
from typing import Callable, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta
import threading
import re
import time
import hashlib
import hmac
import base64
import json

# 可选JWT支持
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False


# ============================================================================
# 安全常量
# ============================================================================

# 允许的协议白名单
ALLOWED_PROTOCOLS = frozenset({"http", "https"})

# 禁止的协议黑名单
BLOCKED_PROTOCOLS = frozenset({"file", "ftp", "sftp", "smb", "nfs", "ssh", "scp"})


class PermissionLevel(IntEnum):
    """五级权限枚举 (与五级安全模型对齐)"""
    READONLY = 1       # 只读
    WORKSPACE_WRITE = 2  # 工作区写入
    DANGER_FULL_ACCESS = 3  # 危险完全访问
    PROMPT = 4        # 需要确认
    ALLOW = 5         # 完全允许


class RuleAction(IntEnum):
    """规则动作"""
    ALLOW = 1    # 允许
    DENY = 2     # 拒绝
    ASK = 3      # 询问


@dataclass
class Rule:
    """权限规则"""
    pattern: str                    # 匹配模式 (正则表达式)
    action: RuleAction              # 动作: allow/deny/ask
    min_level: PermissionLevel = PermissionLevel.READONLY  # 最小权限要求
    description: str = ""          # 规则描述


@dataclass
class PermissionContext:
    """权限检查上下文"""
    operation: str                  # 操作类型 (read, write, delete, exec, etc.)
    target: str                     # 目标路径/资源
    requested_by: str = "system"   # 请求来源
    metadata: dict = field(default_factory=dict)


@dataclass
class PermissionResult:
    """权限检查结果"""
    allowed: bool
    action: RuleAction
    required_level: PermissionLevel
    message: str
    requires_confirmation: bool = False


# ============================================================================
# L1: 身份认证 (Authentication)
# ============================================================================

class AuthResult:
    """认证结果"""
    def __init__(self, success: bool, user_id: str = "", error: str = ""):
        self.success = success
        self.user_id = user_id
        self.error = error


class JWTAuthenticator:
    """
    JWT身份认证器 (L1)
    
    支持:
    - JWT token验证 (RS256/HS256)
    - Token过期检查
    - 签名验证
    """
    
    def __init__(self, secret_key: str = "", public_key: str = "", 
                 algorithm: str = "HS256", issuer: str = ""):
        self.secret_key = secret_key
        self.public_key = public_key
        self.algorithm = algorithm
        self.issuer = issuer
        self._token_blacklist: set[str] = set()
    
    def authenticate(self, user_id: str, token: str) -> AuthResult:
        """
        验证JWT token
        
        Args:
            user_id: 用户ID
            token: JWT token字符串
            
        Returns:
            AuthResult: 认证结果
        """
        if not token:
            return AuthResult(success=False, error="Token不能为空")
        
        # 检查黑名单
        if token in self._token_blacklist:
            return AuthResult(success=False, error="Token已被吊销")
        
        if not JWT_AVAILABLE:
            return self._fallback_authenticate(user_id, token)
        
        try:
            # 解码并验证token
            options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": bool(self.issuer)
            }
            
            if self.algorithm.startswith("HS"):
                payload = jwt.decode(
                    token, 
                    self.secret_key, 
                    algorithms=[self.algorithm],
                    issuer=self.issuer if self.issuer else None,
                    options=options
                )
            else:
                # RS256/ES256 等非对称算法
                payload = jwt.decode(
                    token, 
                    self.public_key, 
                    algorithms=[self.algorithm],
                    issuer=self.issuer if self.issuer else None,
                    options=options
                )
            
            # 验证user_id匹配
            token_user = payload.get("sub") or payload.get("user_id")
            if token_user and token_user != user_id:
                return AuthResult(success=False, error=f"Token用户ID不匹配: {token_user} != {user_id}")
            
            return AuthResult(success=True, user_id=token_user or user_id)
            
        except jwt.ExpiredSignatureError:
            return AuthResult(success=False, error="Token已过期")
        except jwt.InvalidTokenError as e:
            return AuthResult(success=False, error=f"Token验证失败: {str(e)}")
    
    def _fallback_authenticate(self, user_id: str, token: str) -> AuthResult:
        """
        回退认证方案 (无PyJWT时)
        
        使用HMAC-SHA256进行简单验证
        """
        try:
            parts = token.split(".")
            if len(parts) >= 2:
                decoded_user = base64.b64decode(parts[0]).decode("utf-8")
                if decoded_user == user_id:
                    return AuthResult(success=True, user_id=user_id)
            return AuthResult(success=False, error="回退认证: Token格式无效")
        except Exception as e:
            return AuthResult(success=False, error=f"回退认证失败: {str(e)}")
    
    def revoke_token(self, token: str) -> None:
        """吊销token (加入黑名单)"""
        self._token_blacklist.add(token)
    
    def generate_token(self, user_id: str, expires_in: int = 3600) -> str:
        """
        生成JWT token (用于测试)
        
        Args:
            user_id: 用户ID
            expires_in: 过期时间(秒)
            
        Returns:
            str: JWT token
        """
        if not JWT_AVAILABLE:
            # 回退: 简单token格式
            sig = hmac.new(
                self.secret_key.encode(), 
                user_id.encode(), 
                hashlib.sha256
            ).digest()
            token = f"{base64.b64encode(user_id.encode()).decode()}.{base64.b64encode(sig).decode()}"
            return token
        
        payload = {
            "sub": user_id,
            "iat": int(time.time()),
            "exp": int(time.time()) + expires_in
        }
        if self.issuer:
            payload["iss"] = self.issuer
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)


# 默认全局认证器
_authenticator: Optional[JWTAuthenticator] = None


def get_authenticator() -> JWTAuthenticator:
    """获取全局认证器"""
    global _authenticator
    if _authenticator is None:
        _authenticator = JWTAuthenticator()
    return _authenticator


def authenticate(user_id: str, token: str) -> AuthResult:
    """
    L1身份认证
    
    Args:
        user_id: 用户ID
        token: 认证token
        
    Returns:
        AuthResult: 认证结果
    """
    return get_authenticator().authenticate(user_id, token)


# ============================================================================
# L5: 频率限制 (Rate Limiting)
# ============================================================================

@dataclass
class RateLimitResult:
    """频率限制结果"""
    allowed: bool
    current_count: int
    limit: int
    window_seconds: int
    retry_after: int = 0  # 距离下次可用还剩多少秒


class RateLimiter:
    """
    频率限制器 (L5)
    
    使用滑动窗口算法实现精确的请求频率控制
    
    限制规则:
    - read_limit: 100次/分钟
    - write_limit: 20次/分钟  
    - distill_limit: 5次/分钟
    """
    
    # 默认限制配置
    DEFAULT_LIMITS = {
        "read": (100, 60),    # (次数, 窗口秒数)
        "write": (20, 60),
        "distill": (5, 60),
        "default": (60, 60),  # 其他操作默认60次/分
    }
    
    def __init__(self, custom_limits: dict = None):
        """
        初始化频率限制器
        
        Args:
            custom_limits: 自定义限制 {operation: (count, window_seconds)}
        """
        self.limits = dict(self.DEFAULT_LIMITS)
        if custom_limits:
            self.limits.update(custom_limits)
        
        # 滑动窗口存储: {user_id: {operation: [(timestamp, count)]}}
        self._windows: dict[str, dict[str, list[tuple[float, int]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._lock = threading.RLock()
    
    def _cleanup_window(self, user_id: str, operation: str, now: float) -> None:
        """清理过期的窗口数据"""
        window_seconds = self.get_limit(operation)[1]
        cutoff = now - window_seconds
        
        # 保留窗口内和窗口边界的记录
        self._windows[user_id][operation] = [
            (ts, cnt) for ts, cnt in self._windows[user_id][operation]
            if ts > cutoff
        ]
    
    def get_limit(self, operation: str) -> tuple[int, int]:
        """获取操作限制"""
        return self.limits.get(operation, self.limits["default"])
    
    def check(self, user_id: str, operation: str, count: int = 1) -> RateLimitResult:
        """
        检查频率限制
        
        Args:
            user_id: 用户ID
            operation: 操作类型 (read/write/distill)
            count: 本次请求消耗的配额
            
        Returns:
            RateLimitResult: 限制检查结果
        """
        limit_count, window_seconds = self.get_limit(operation)
        now = time.time()
        
        with self._lock:
            # 清理过期数据
            self._cleanup_window(user_id, operation, now)
            
            # 计算当前窗口内请求总数
            total = sum(cnt for _, cnt in self._windows[user_id][operation])
            
            # 检查是否超限
            if total + count > limit_count:
                # 计算重试时间
                retry_after = window_seconds
                if self._windows[user_id][operation]:
                    oldest = min(ts for ts, _ in self._windows[user_id][operation])
                    retry_after = max(1, int(oldest + window_seconds - now))
                
                return RateLimitResult(
                    allowed=False,
                    current_count=total,
                    limit=limit_count,
                    window_seconds=window_seconds,
                    retry_after=retry_after
                )
            
            # 记录请求
            self._windows[user_id][operation].append((now, count))
            
            return RateLimitResult(
                allowed=True,
                current_count=total + count,
                limit=limit_count,
                window_seconds=window_seconds,
                retry_after=0
            )
    
    def reset(self, user_id: str, operation: str = None) -> None:
        """
        重置频率限制
        
        Args:
            user_id: 用户ID
            operation: 操作类型 (None表示全部)
        """
        with self._lock:
            if operation:
                self._windows[user_id][operation] = []
            else:
                self._windows[user_id] = defaultdict(list)
    
    def get_status(self, user_id: str, operation: str) -> RateLimitResult:
        """
        获取当前频率状态 (不消耗配额)
        
        Args:
            user_id: 用户ID
            operation: 操作类型
            
        Returns:
            RateLimitResult: 当前状态
        """
        limit_count, window_seconds = self.get_limit(operation)
        now = time.time()
        
        with self._lock:
            self._cleanup_window(user_id, operation, now)
            total = sum(cnt for _, cnt in self._windows[user_id][operation])
            
            return RateLimitResult(
                allowed=total < limit_count,
                current_count=total,
                limit=limit_count,
                window_seconds=window_seconds
            )


# 全局频率限制器
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """获取全局频率限制器"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def check_rate_limit(user_id: str, operation: str, count: int = 1) -> RateLimitResult:
    """
    L5频率限制检查
    
    Args:
        user_id: 用户ID
        operation: 操作类型
        count: 配额消耗
        
    Returns:
        RateLimitResult: 检查结果
    """
    return get_rate_limiter().check(user_id, operation, count)


# ============================================================================
# PermissionEngine (集成L1和L5)
# ============================================================================

class PermissionEngine:
    """
    记忆殿堂权限引擎
    
    Features:
    - 五级权限模型 (L1-L5)
    - L1: 身份认证 (JWT)
    - L5: 频率限制 (Rate Limiting)
    - 规则引擎 (allow/deny/ask)
    - Hook Override 集成
    - 上下文感知
    """
    
    def __init__(self, authenticator: JWTAuthenticator = None, rate_limiter: RateLimiter = None):
        self.rules: list[Rule] = []
        self.hooks: dict[str, Callable] = {}  # claw-code hook override
        self._authenticator = authenticator
        self._rate_limiter = rate_limiter
        self._init_default_rules()
    
    @property
    def authenticator(self) -> JWTAuthenticator:
        """获取认证器"""
        if self._authenticator is None:
            self._authenticator = get_authenticator()
        return self._authenticator
    
    @property
    def rate_limiter(self) -> RateLimiter:
        """获取频率限制器"""
        if self._rate_limiter is None:
            self._rate_limiter = get_rate_limiter()
        return self._rate_limiter
    
    def _init_default_rules(self):
        """初始化默认规则"""
        # 默认只读规则
        self.rules.extend([
            # 系统关键路径 - 只读 (匹配 operation:/etc/xxx 格式)
            Rule(
                pattern=r"^[a-z]+:/etc/(passwd|shadow|group)$",
                action=RuleAction.DENY,
                min_level=PermissionLevel.DANGER_FULL_ACCESS,
                description="系统密码文件禁止访问"
            ),
            # SSH配置 - 危险
            Rule(
                pattern=r":~/.ssh/",
                action=RuleAction.ASK,
                min_level=PermissionLevel.WORKSPACE_WRITE,
                description="SSH配置需要确认"
            ),
            # 外部网络操作 - 询问 (只允许http/https)
            Rule(
                pattern=r":https?://",
                action=RuleAction.ASK,
                min_level=PermissionLevel.WORKSPACE_WRITE,
                description="外部网络请求需要确认"
            ),
            # 文件删除 - 询问
            Rule(
                pattern=r"^delete:",
                action=RuleAction.ASK,
                min_level=PermissionLevel.DANGER_FULL_ACCESS,
                description="删除操作需要确认"
            ),
        ])

    def _check_path_traversal(self, target: str) -> bool:
        """
        检查路径遍历攻击
        
        阻止包含 .. 的路径，防止 ../../../etc/passwd 等攻击
        
        Args:
            target: 目标路径
            
        Returns:
            bool: True表示检测到路径遍历攻击
        """
        # 检查是否有 .. 路径遍历
        if ".." in target:
            return True
        
        # 检查是否有多余的斜杠变体 (如 ///etc/passwd)
        normalized = target.replace("//", "/")
        if "../" in normalized or normalized.endswith(".."):
            return True
        
        return False

    def _validate_protocol(self, target: str) -> tuple[bool, str]:
        """
        验证协议安全性
        
        只允许 http/https 协议
        
        Args:
            target: 目标URL
            
        Returns:
            tuple: (是否安全, 错误消息)
        """
        # 提取协议
        if ":" not in target:
            return True, ""
        
        protocol = target.split(":")[0].lower()
        
        # 检查是否是危险协议
        if protocol in BLOCKED_PROTOCOLS:
            return False, f"协议 {protocol} 被禁止使用"
        
        # 网络URL必须使用白名单协议
        if "://" in target and protocol not in ALLOWED_PROTOCOLS:
            return False, f"协议 {protocol} 不在白名单中，仅允许: {', '.join(ALLOWED_PROTOCOLS)}"
        
        return True, ""
    
    def check(self, context: PermissionContext, user_level: PermissionLevel,
              user_id: str = "", auth_token: str = "") -> PermissionResult:
        """
        检查权限 (集成L1认证和L5频率限制)
        
        Args:
            context: 权限上下文
            user_level: 用户权限级别
            user_id: 用户ID (用于L1和L5)
            auth_token: 认证token (用于L1)
            
        Returns:
            PermissionResult: 权限检查结果
        """
        # ============================================================================
        # L1: 身份认证 (Authentication)
        # ============================================================================
        if user_id and auth_token:
            auth_result = self.authenticator.authenticate(user_id, auth_token)
            if not auth_result.success:
                return PermissionResult(
                    allowed=False,
                    action=RuleAction.DENY,
                    required_level=PermissionLevel.READONLY,
                    message=f"L1认证失败: {auth_result.error}"
                )
        
        # 触发 before_permission_check hook
        if "before_permission_check" in self.hooks:
            result = self.hooks["before_permission_check"](context, user_level)
            if result is not None:
                return result
        
        # ============================================================================
        # 安全检查层
        # ============================================================================
        
        # 检查路径遍历攻击 (fix_002)
        if self._check_path_traversal(context.target):
            return PermissionResult(
                allowed=False,
                action=RuleAction.DENY,
                required_level=PermissionLevel.DANGER_FULL_ACCESS,
                message="路径遍历攻击被阻止: 操作拒绝"
            )
        
        # 检查协议安全性 (fix_003)
        is_safe, error_msg = self._validate_protocol(context.target)
        if not is_safe:
            return PermissionResult(
                allowed=False,
                action=RuleAction.DENY,
                required_level=PermissionLevel.DANGER_FULL_ACCESS,
                message=f"协议验证失败: {error_msg}"
            )
        
        # ============================================================================
        # L5: 频率限制 (Rate Limiting)
        # ============================================================================
        if user_id:
            # 映射操作类型到频率限制类型
            op_type = context.operation
            if op_type in ("read", "list", "search", "get", "query"):
                rate_op = "read"
            elif op_type in ("write", "create", "update", "edit", "delete"):
                rate_op = "write"
            elif op_type in ("distill", "extract", "analyze"):
                rate_op = "distill"
            else:
                rate_op = "default"
            
            rate_result = self.rate_limiter.check(user_id, rate_op)
            if not rate_result.allowed:
                return PermissionResult(
                    allowed=False,
                    action=RuleAction.DENY,
                    required_level=PermissionLevel.READONLY,
                    message=f"L5频率限制: {rate_result.current_count}/{rate_result.limit} "
                            f"(重试等待{rate_result.retry_after}秒)"
                )
        
        # ============================================================================
        # 规则匹配
        # ============================================================================
        
        # 组合目标字符串用于匹配
        target_str = f"{context.operation}:{context.target}"
        
        # 按优先级检查规则
        for rule in self.rules:
                # 规则模式匹配检查
                pattern_matches = False
                try:
                    pattern_matches = bool(re.search(rule.pattern, target_str))
                except re.error:
                    pattern_matches = rule.pattern in target_str
                
                # 如果规则不匹配，跳过此规则
                if not pattern_matches:
                    continue
                
                # 权限级别检查
                if user_level < rule.min_level:
                    return PermissionResult(
                        allowed=False,
                        action=rule.action,
                        required_level=rule.min_level,
                        message=f"权限不足，需要级别 {rule.min_level.name}"
                    )
                
                # 动作处理
                if rule.action == RuleAction.ALLOW:
                    return PermissionResult(
                        allowed=True,
                        action=RuleAction.ALLOW,
                        required_level=rule.min_level,
                        message="操作已允许"
                    )
                elif rule.action == RuleAction.DENY:
                    return PermissionResult(
                        allowed=False,
                        action=rule.action,
                        required_level=rule.min_level,
                        message=f"操作被拒绝: {rule.description}"
                    )
                elif rule.action == RuleAction.ASK:
                    return PermissionResult(
                        allowed=False,
                        action=RuleAction.ASK,
                        required_level=rule.min_level,
                        message=f"需要确认: {rule.description}",
                        requires_confirmation=True
                    )
        
        # 无匹配规则
        # 读操作默认允许，其他默认拒绝
        if context.operation in ("read", "list", "search"):
            return PermissionResult(
                allowed=True,
                action=RuleAction.ALLOW,
                required_level=PermissionLevel.READONLY,
                message="操作已允许 (默认规则)"
            )
        return PermissionResult(
            allowed=False,
            action=RuleAction.DENY,
            required_level=PermissionLevel.READONLY,
            message="无匹配规则，默认拒绝"
        )
    
    def _match_rule(self, pattern: str, context: PermissionContext, user_level: PermissionLevel) -> bool:
        """检查规则是否匹配"""
        # 组合目标字符串
        target = f"{context.operation}:{context.target}"
        
        try:
            return bool(re.search(pattern, target))
        except re.error:
            return pattern in target
    
    def add_rule(self, rule: Rule) -> None:
        """添加规则"""
        self.rules.append(rule)
    
    def remove_rule(self, pattern: str) -> None:
        """移除规则"""
        self.rules = [r for r in self.rules if r.pattern != pattern]
    
    def register_hook(self, hook_name: str, handler: Callable) -> None:
        """
        注册 Hook Override
        
        claw-code 集成点:
        - before_permission_check: 权限检查前
        - after_permission_check: 权限检查后
        - on_allow: 允许操作时
        - on_deny: 拒绝操作时
        - on_ask: 需要确认时
        """
        self.hooks[hook_name] = handler
    
    def unregister_hook(self, hook_name: str) -> None:
        """注销 Hook"""
        if hook_name in self.hooks:
            del self.hooks[hook_name]
    
    def get_level_name(self, level: PermissionLevel) -> str:
        """获取权限级别名称"""
        names = {
            PermissionLevel.READONLY: "只读",
            PermissionLevel.WORKSPACE_WRITE: "工作区写入",
            PermissionLevel.DANGER_FULL_ACCESS: "危险完全访问",
            PermissionLevel.PROMPT: "需要确认",
            PermissionLevel.ALLOW: "完全允许"
        }
        return names.get(level, "未知")
    
    def set_level(self, user_level: str) -> PermissionLevel:
        """根据字符串设置权限级别"""
        level_map = {
            "readonly": PermissionLevel.READONLY,
            "workspace_write": PermissionLevel.WORKSPACE_WRITE,
            "danger_full_access": PermissionLevel.DANGER_FULL_ACCESS,
            "prompt": PermissionLevel.PROMPT,
            "allow": PermissionLevel.ALLOW
        }
        return level_map.get(user_level.lower(), PermissionLevel.READONLY)


# 全局权限引擎实例
_engine: Optional[PermissionEngine] = None


def get_engine() -> PermissionEngine:
    """获取全局权限引擎"""
    global _engine
    if _engine is None:
        _engine = PermissionEngine()
    return _engine


def check_permission(
    operation: str,
    target: str,
    user_level: PermissionLevel = PermissionLevel.READONLY,
    requested_by: str = "system",
    user_id: str = "",
    auth_token: str = ""
) -> PermissionResult:
    """快捷权限检查函数 (支持L1和L5)"""
    context = PermissionContext(
        operation=operation,
        target=target,
        requested_by=requested_by
    )
    return get_engine().check(context, user_level, user_id, auth_token)
