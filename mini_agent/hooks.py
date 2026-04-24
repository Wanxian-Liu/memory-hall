"""
Hook机制模块 - 精简自Claude Code hooks.rs

实现两种核心Hook：
1. before_tool_call - 工具调用前执行
2. tool_result_persist - 工具结果持久化
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any
from datetime import datetime
import json
import signal
import threading


# ============================================================================
# 安全常量
# ============================================================================

# Hook执行默认超时时间(秒)
DEFAULT_HOOK_TIMEOUT_SECONDS = 30

# 超时时的错误消息
HOOK_TIMEOUT_MESSAGE = "Hook execution timed out - operation cancelled for safety"


# ============================================================================
# 超时上下文管理器
# ============================================================================

class TimeoutError(Exception):
    """Hook执行超时异常"""
    pass


class timeout:
    """
    超时上下文管理器
    
    使用signal.SIGALRM实现超时控制(仅Unix)
    超时时抛出TimeoutError
    """
    
    def __init__(self, seconds: int):
        self.seconds = seconds
        self.old_handler = None
    
    def __enter__(self):
        if self.seconds > 0:
            self.old_handler = signal.signal(signal.SIGALRM, self._handle_timeout)
            signal.alarm(self.seconds)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.seconds > 0:
            signal.alarm(0)
            if self.old_handler is not None:
                signal.signal(signal.SIGALRM, self.old_handler)
        return False
    
    def _handle_timeout(self, signum, frame):
        raise TimeoutError()


# ============================================================================
# 数据结构
# ============================================================================

class HookEvent(Enum):
    """Hook事件类型"""
    BEFORE_TOOL_CALL = "before_tool_call"
    TOOL_RESULT_PERSIST = "tool_result_persist"
    POST_TOOL_USE = "post_tool_use"
    POST_TOOL_USE_FAILURE = "post_tool_use_failure"


@dataclass
class HookResult:
    """Hook执行结果"""
    denied: bool = False          # 是否拒绝
    failed: bool = False          # 是否失败
    cancelled: bool = False       # 是否取消
    messages: list = field(default_factory=list)  # 附加消息
    updated_input: Optional[str] = None  # 更新后的输入
    metadata: dict = field(default_factory=dict)   # 元数据


@dataclass
class ToolCall:
    """工具调用结构"""
    name: str
    arguments: dict
    call_id: Optional[str] = None


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_name: str
    result: Any
    success: bool = True
    error: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass 
class HookContext:
    """Hook执行上下文"""
    session_id: str
    agent_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    extra: dict = field(default_factory=dict)


# ============================================================================
# Hook接口
# ============================================================================

class BeforeToolCallHook:
    """工具调用前Hook接口"""
    
    def name(self) -> str:
        return "before_tool_call"
    
    def handle(
        self, 
        context: HookContext, 
        tool_call: ToolCall
    ) -> HookResult:
        """
        在工具调用前执行
        
        Args:
            context: Hook上下文
            tool_call: 待执行的工具调用
            
        Returns:
            HookResult: 允许、拒绝或修改
        """
        raise NotImplementedError


class ToolResultPersistHook:
    """工具结果持久化Hook接口"""
    
    def name(self) -> str:
        return "tool_result_persist"
    
    def handle(
        self,
        context: HookContext,
        tool_call: ToolCall,
        result: ToolResult
    ) -> HookResult:
        """
        在工具执行后持久化结果
        
        Args:
            context: Hook上下文
            tool_call: 已执行的工具调用
            result: 工具执行结果
            
        Returns:
            HookResult: 成功或失败
        """
        raise NotImplementedError


# ============================================================================
# 默认Hook实现
# ============================================================================

class DefaultBeforeToolCallHook(BeforeToolCallHook):
    """默认的before_tool_call实现"""
    
    # 允许的工具白名单
    SAFE_TOOLS = {
        "read", "write", "edit", "exec", "search", "web_fetch",
        "message", "file", "folder", "task", "memory"
    }
    
    # 危险工具黑名单
    DANGEROUS_TOOLS = {
        "rm", "delete", "format", "drop", "truncate"
    }
    
    def handle(
        self,
        context: HookContext,
        tool_call: ToolCall
    ) -> HookResult:
        tool_name = tool_call.name
        
        # 检查危险工具
        if tool_name in self.DANGEROUS_TOOLS:
            return HookResult(
                denied=True,
                failed=False,
                messages=[f"Tool '{tool_name}' is blocked for safety"],
            )
        
        # 检查未知工具
        if tool_name not in self.SAFE_TOOLS:
            return HookResult(
                denied=True,
                messages=[f"Tool '{tool_name}' is not in whitelist"],
            )
        
        # 检查exec命令安全性
        if tool_name == "exec":
            cmd = tool_call.arguments.get("command", "")
            if self._is_dangerous_command(cmd):
                return HookResult(
                    denied=True,
                    messages=[f"Command '{cmd[:50]}' may be dangerous"],
                )
        
        return HookResult(denied=False, messages=["Tool allowed"])
    
    def _is_dangerous_command(self, cmd: str) -> bool:
        """检查命令是否危险 - P0-3增强版使用shlex解析"""
        import shlex
        import os
        
        # 无论有无标志都危险的命令（命令名匹配即拦截）
        INHERENTLY_DANGEROUS = {'dd', 'shred', 'mkfs', 'fdisk', 'parted'}
        
        # 需要危险标志才危险的命令
        FLAG_DANGEROUS_COMMANDS = {'rm'}
        
        # 危险标志集合
        DANGEROUS_FLAGS = {'-rf', '-r', '-f', '--no-preserve-root'}
        
        try:
            parts = shlex.split(cmd)
        except ValueError:
            # 无法解析的命令（包含不平衡的引号等）视为危险
            return True
        
        if not parts:
            return False
        
        # 获取命令名称（去除路径）
        cmd_name = os.path.basename(parts[0].lower())
        
        # 检查是否是危险命令
        # 无条件拦截的命令（无论有无标志）
        if cmd_name in INHERENTLY_DANGEROUS:
            return True
        
        # 检查mkfs.ext4等变体（mkfs开头的命令）
        if cmd_name.startswith('mkfs'):
            return True
        
        # 需要危险标志才危险的命令
        if cmd_name in FLAG_DANGEROUS_COMMANDS:
            if any(flag in parts[1:] for flag in DANGEROUS_FLAGS):
                return True
        
        # 检查shell连接符（命令链接/管道/后台执行）
        shell_connectors = ['; ', ' && ', ' || ', '| ', '> ', '< ', '`', '$( ', ')& ', ' & ', '\n']
        if any(c in cmd for c in shell_connectors):
            if any(p in cmd for p in ['| sh', '| bash', '| zsh', '| python', '| perl']):
                return True
            if '`' in cmd and cmd.count('`') >= 2:
                return True
            if '$(' in cmd:
                return True
        
        return False

class DefaultToolResultPersistHook(ToolResultPersistHook):
    """默认的tool_result_persist实现"""
    
    def __init__(self, storage_path: str = "~/.openclaw/projects/记忆殿堂v2.0/mini_agent/results"):
        self.storage_path = storage_path
        self._results = []  # 内存缓存
    
    def handle(
        self,
        context: HookContext,
        tool_call: ToolCall,
        result: ToolResult
    ) -> HookResult:
        # 记录结果到内存
        record = {
            "timestamp": context.timestamp.isoformat(),
            "session_id": context.session_id,
            "tool_name": tool_call.name,
            "success": result.success,
            "duration_ms": result.duration_ms,
            "error": result.error,
        }
        
        # 截断大结果以节省内存
        if result.result and isinstance(result.result, str) and len(result.result) > 5000:
            record["result_preview"] = result.result[:5000] + "...[truncated]"
        else:
            record["result"] = result.result
        
        self._results.append(record)
        
        return HookResult(
            denied=False,
            messages=[f"Result persisted for {tool_call.name}"],
            metadata={"record_count": len(self._results)},
        )
    
    def get_recent_results(self, limit: int = 100) -> list:
        """获取最近的结果"""
        return self._results[-limit:]
    
    def clear(self):
        """清空缓存"""
        self._results.clear()


# ============================================================================
# Hook管理器
# ============================================================================

class HookManager:
    """Hook管理器"""
    
    def __init__(self, timeout_seconds: int = DEFAULT_HOOK_TIMEOUT_SECONDS):
        self._before_tool_hooks: list[BeforeToolCallHook] = []
        self._persist_hooks: list[ToolResultPersistHook] = []
        self._global_filters: list[Callable] = []
        self._timeout_seconds = timeout_seconds  # fix_006: 超时配置
    
    def register_before_tool_hook(self, hook: BeforeToolCallHook) -> None:
        """注册before_tool_call hook"""
        self._before_tool_hooks.append(hook)
    
    def register_persist_hook(self, hook: ToolResultPersistHook) -> None:
        """注册tool_result_persist hook"""
        self._persist_hooks.append(hook)
    
    def register_global_filter(self, filter_fn: Callable) -> None:
        """注册全局过滤器"""
        self._global_filters.append(filter_fn)
    
    def run_before_tool_call(
        self,
        context: HookContext,
        tool_call: ToolCall,
        timeout_seconds: Optional[int] = None
    ) -> HookResult:
        """运行所有before_tool_call hooks (fix_006: 添加超时保护)
        
        Args:
            context: Hook上下文
            tool_call: 工具调用
            timeout_seconds: 可选的覆盖超时时间
        """
        timeout_val = timeout_seconds if timeout_seconds is not None else self._timeout_seconds
        
        # 应用全局过滤器
        for filter_fn in self._global_filters:
            try:
                if timeout_val > 0:
                    with timeout(timeout_val):
                        filtered_tool_call = filter_fn(tool_call)
                else:
                    filtered_tool_call = filter_fn(tool_call)
                
                if filtered_tool_call is not None:
                    tool_call = filtered_tool_call
            except TimeoutError:
                return HookResult(
                    denied=True,
                    failed=True,
                    messages=[HOOK_TIMEOUT_MESSAGE],
                )
            except Exception as e:
                return HookResult(
                    denied=True,
                    failed=True,
                    messages=[f"Global filter error: {str(e)}"],
                )
        
        # 运行所有hooks
        all_messages = []
        for hook in self._before_tool_hooks:
            try:
                if timeout_val > 0:
                    with timeout(timeout_val):
                        result = hook.handle(context, tool_call)
                else:
                    result = hook.handle(context, tool_call)
                
                all_messages.extend(result.messages)
                if result.denied or result.failed:
                    return result
            except TimeoutError:
                return HookResult(
                    denied=True,
                    failed=True,
                    messages=[HOOK_TIMEOUT_MESSAGE],
                )
        
        return HookResult(denied=False, messages=all_messages)
    
    def run_tool_result_persist(
        self,
        context: HookContext,
        tool_call: ToolCall,
        result: ToolResult,
        timeout_seconds: Optional[int] = None
    ) -> HookResult:
        """运行所有tool_result_persist hooks (fix_006: 添加超时保护)
        
        Args:
            context: Hook上下文
            tool_call: 工具调用
            result: 工具执行结果
            timeout_seconds: 可选的覆盖超时时间
        """
        timeout_val = timeout_seconds if timeout_seconds is not None else self._timeout_seconds
        combined_result = HookResult()
        
        for hook in self._persist_hooks:
            try:
                if timeout_val > 0:
                    with timeout(timeout_val):
                        hook_result = hook.handle(context, tool_call, result)
                else:
                    hook_result = hook.handle(context, tool_call, result)
                
                # 合并结果
                combined_result.messages.extend(hook_result.messages)
                
                if hook_result.failed:
                    combined_result.failed = True
                
                combined_result.metadata.update(hook_result.metadata)
            except TimeoutError:
                combined_result.failed = True
                combined_result.messages.append(HOOK_TIMEOUT_MESSAGE)
        
        return combined_result
    
    def clear(self) -> None:
        """清空所有hooks"""
        self._before_tool_hooks.clear()
        self._persist_hooks.clear()
        self._global_filters.clear()


# ============================================================================
# 便捷函数
# ============================================================================

def create_default_hook_manager() -> HookManager:
    """创建带有默认hooks的管理器"""
    manager = HookManager()
    manager.register_before_tool_hook(DefaultBeforeToolCallHook())
    manager.register_persist_hook(DefaultToolResultPersistHook())
    return manager
