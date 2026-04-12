"""
文件系统适配器 (FileSystemAdapter)

实现IMemoryVault接口，基于文件系统存储记忆。

配置来源：
- 通过Config读取paths.vault_dir，不硬编码路径
- 兼容旧版VAULT_DIR环境变量

与旧版区别：
- 实现IMemoryVault接口，支持接口替换
- 从Config读取vault_dir，而非硬编码
- 提供异步接口（async/await）
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Any, Optional, List, Dict

from ..imemory_vault import IMemoryVault, SearchResult


class FileSystemAdapter(IMemoryVault):
    """
    文件系统存储适配器
    
    实现IMemoryVault接口，基于文件系统存储记忆。
    配置通过Config类管理，支持环境变量覆盖。
    """
    
    def __init__(self, vault_dir: str = None):
        """
        初始化文件系统适配器
        
        Args:
            vault_dir: 可选的vault目录，不指定则从Config读取
        """
        if vault_dir:
            self.vault_dir = Path(os.path.expanduser(vault_dir))
        else:
            # 从Config读取vault_dir
            from config import get_config
            vault_dir_cfg = get_config('paths', 'vault_dir', default='~/.openclaw/memory-vault/data')
            self.vault_dir = Path(os.path.expanduser(vault_dir_cfg))
        
        # 确保目录存在
        self.vault_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_file_path(self, key: str) -> Path:
        """
        根据键获取文件路径
        
        使用SHA256哈希将键转换为稳定的文件名，避免Python hash()的随机化问题。
        """
        safe_key = hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]
        return self.vault_dir / f"{safe_key}.json"
    
    async def read(self, key: str) -> Optional[Any]:
        """
        读取记忆
        
        Args:
            key: 记忆键
            
        Returns:
            记忆值或None
        """
        file_path = self._get_file_path(key)
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("value")
        except Exception:
            return None
    
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
        file_path = self._get_file_path(key)
        
        data = {
            "key": key,
            "value": value,
            "metadata": metadata or {}
        }
        
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    async def delete(self, key: str) -> bool:
        """
        删除记忆
        
        Args:
            key: 记忆键
            
        Returns:
            是否删除成功
        """
        file_path = self._get_file_path(key)
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except Exception:
                return False
        return False
    
    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        搜索记忆
        
        注意：V2.0文件系统适配器不实现搜索功能，返回空列表。
        搜索功能由外部搜索引擎（如SemanticSearchEngine）提供。
        
        Args:
            query: 搜索查询
            limit: 返回数量限制
            
        Returns:
            搜索结果列表
        """
        # 文件系统适配器不支持搜索，返回空列表
        # 搜索功能由MemoryPalaceIntegration配合搜索引擎实现
        return []
    
    async def list_keys(self) -> List[str]:
        """
        列出所有记忆键
        
        Returns:
            键列表
        """
        keys = []
        for filename in self.vault_dir.iterdir():
            if filename.suffix == '.json':
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'key' in data:
                            keys.append(data['key'])
                except Exception:
                    pass
        return keys
