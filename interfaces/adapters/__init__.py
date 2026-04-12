"""
记忆殿堂适配器模块

提供IMemoryVault接口的不同实现：
- FileSystemAdapter: 基于文件系统的实现
"""

from .file_system_adapter import FileSystemAdapter

__all__ = [
    'FileSystemAdapter',
]
