"""
记忆殿堂v2.0 - 权限引擎
Permission Engine with 5-level model and Rule Engine

五级权限模型:
- ReadOnly: 只读访问
- WorkspaceWrite: 工作区写入
- DangerFullAccess: 危险操作完全访问
- Prompt: 需要确认提示
- Allow: 完全允许

规则引擎:
- allow: 允许操作
- deny: 拒绝操作
- ask: 需要用户确认
"""

from enum import IntEnum
from typing import Callable, Optional
from dataclasses import dataclass, field
import re
from urllib.parse import urlparse


# ============================================================================
# 安全常量
# ============================================================================

# 允许的协议白名单
ALLOWED_PROTOCOLS = frozenset({"http", "https"})

# 禁止的协议黑名单
BLOCKED_PROTOCOLS = frozenset({"file", "ftp", "sftp", "smb", "nfs", "ssh", "scp"})


class PermissionLevel(IntEnum):
    """五级权限枚举"""
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


class PermissionEngine:
    """
    记忆殿堂权限引擎
    
    Features:
    - 五级权限模型
    - 规则引擎 (allow/deny/ask)
    - Hook Override 集成
    - 上下文感知
    """
    
    def __init__(self):
        self.rules: list[Rule] = []
        self.hooks: dict[str, Callable] = {}  # claw-code hook override
        self._init_default_rules()
    
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
    
    def check(self, context: PermissionContext, user_level: PermissionLevel) -> PermissionResult:
        """
        检查权限
        
        Args:
            context: 权限上下文
            user_level: 用户权限级别
            
        Returns:
            PermissionResult: 权限检查结果
        """
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
        # 规则匹配
        # ============================================================================
        
        # 按优先级检查规则
        for rule in self.rules:
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
                        action=RuleAction.DENY,
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
    requested_by: str = "system"
) -> PermissionResult:
    """快捷权限检查函数"""
    context = PermissionContext(
        operation=operation,
        target=target,
        requested_by=requested_by
    )
    return get_engine().check(context, user_level)
