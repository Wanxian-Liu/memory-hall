"""
记忆殿堂抽象接口 (IMemoryVault)

定义记忆殿堂的标准接口契约，任何存储实现必须实现此接口。
Mimir-Core只通过此接口访问存储，不关心底层实现。

接口方法：
- read(key) -> Optional[Any]: 读取记忆
- write(key, value, metadata) -> bool: 写入记忆
- delete(key) -> bool: 删除记忆
- search(query, limit) -> List[SearchResult]: 搜索记忆
- list_keys() -> List[str]: 列出所有键
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict
from dataclasses import dataclass


@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    score: float
    content: str
    metadata: Dict = None


class IMemoryVault(ABC):
    """
    记忆殿堂抽象接口
    
    所有存储实现必须实现此接口，以保证：
    1. CLI和Gateway走同一接口
    2. 接口可替换（支持内存/文件/远程实现）
    3. 配置通过config.yaml管理，不在代码中硬编码
    """
    
    @abstractmethod
    async def read(self, key: str) -> Optional[Any]:
        """
        读取记忆
        
        Args:
            key: 记忆键
            
        Returns:
            记忆值或None
        """
        pass
    
    @abstractmethod
    async def write(self, key: str, value: Any, metadata: Dict = None) -> bool:
        """
        写入记忆
        
        Args:
            key: 记忆键
            value: 记忆值
            metadata: 可选元数据
            
        Returns:
            是否写入成功
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        删除记忆
        
        Args:
            key: 记忆键
            
        Returns:
            是否删除成功
        """
        pass
    
    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        搜索记忆
        
        Args:
            query: 搜索查询
            limit: 返回数量限制
            
        Returns:
            搜索结果列表
        """
        pass
    
    @abstractmethod
    async def list_keys(self) -> List[str]:
        """
        列出所有记忆键
        
        Returns:
            键列表
        """
        pass
