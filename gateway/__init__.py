"""
记忆殿堂 Gateway V2.0
独立模块 - 不依赖OpenClaw

功能：
- LRU缓存 (1000条目)
- TTL过期 (默认7天)
- 写时失效机制
- 审计日志
"""

from .gateway import (
    Gateway,
    LRUCache,
    audit_log,
    write,
    read,
    search,
    delete,
    get_audit_logs,
    get_cache_stats,
    clear_cache,
    Config,
)

__version__ = "2.0.0"
__all__ = [
    "Gateway",
    "LRUCache", 
    "audit_log",
    "write",
    "read",
    "search",
    "delete",
    "get_audit_logs",
    "get_cache_stats",
    "clear_cache",
    "Config",
]
