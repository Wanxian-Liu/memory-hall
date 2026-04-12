"""
记忆殿堂接口模块

导出：
- IMemoryVault: 抽象接口
- SearchResult: 搜索结果数据结构
- FileSystemAdapter: 文件系统实现
"""

from .imemory_vault import IMemoryVault, SearchResult

# 导入所有适配器
from .adapters import FileSystemAdapter

__all__ = [
    'IMemoryVault',
    'SearchResult',
    'FileSystemAdapter',
]
