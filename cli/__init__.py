"""
记忆殿堂v2.0 - CLI模块

提供命令行路由功能：
- 命令解析
- 参数验证
- 帮助系统

Usage:
    from cli import get_router, parse_and_run

    router = get_router()
    success, result, errors = router.run("search --query hello")
"""

from .router import (
    Router,
    Command,
    Arg,
    ArgType,
    ParsedArgs,
    get_router,
    parse_and_run,
)

__all__ = [
    "Router",
    "Command",
    "Arg",
    "ArgType",
    "ParsedArgs",
    "get_router",
    "parse_and_run",
]

__version__ = "2.0.0"
