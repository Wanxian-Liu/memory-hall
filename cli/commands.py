#!/usr/bin/env python3
"""
记忆殿堂v2.0 - Slash命令系统 (CLI)

提供以下slash命令:
- /memory write <key> <value>  - 写入记忆
- /memory read <key>            - 读取记忆
- /memory search <query>        - 语义搜索记忆
- /memory stats                - 查看统计信息
- /memory health               - 健康检查

用法:
    python -m cli.commands write <key> <value>
    python -m cli.commands read <key>
    python -m cli.commands search <query>
    python -m cli.commands stats
    python -m cli.commands health
"""

import sys
import os
import json
import hashlib
import argparse
from typing import Optional, Dict, Any, List

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 导入核心模块
from base_wal.wal import WALManager, WALEntryType
from health.health_check import HealthChecker
from sensory.semantic_search import SemanticSearchEngine, create_engine
from interfaces.adapters import FileSystemAdapter

# ============ 配置 ============

# 使用FileSystemAdapter的配置，统一从Config读取
_adapter = FileSystemAdapter()
VAULT_DIR = str(_adapter.vault_dir)
METADATA_DIR = os.path.expanduser("~/.openclaw/memory-vault/metadata")

# 确保目录存在
os.makedirs(VAULT_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)


# ============ 记忆存储 ============

class MemoryStore:
    """
    记忆存储，基于IMemoryVault接口
    
    统一通过FileSystemAdapter访问文件系统，
    不再直接操作文件系统。
    """
    
    def __init__(self, vault_dir: str = VAULT_DIR):
        # 统一使用FileSystemAdapter，从Config读取路径
        self.adapter = FileSystemAdapter()
        self.vault_dir = str(self.adapter.vault_dir)
    
    def _get_file_path(self, key: str) -> str:
        """获取键对应的文件路径"""
        # 使用hashlib进行稳定哈希，避免Python hash()的随机化问题
        safe_key = hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]
        return os.path.join(self.vault_dir, f"{safe_key}.json")
    
    def write(self, key: str, value: Any) -> bool:
        """写入记忆"""
        file_path = self._get_file_path(key)
        data = {
            "key": key,
            "value": value,
            "timestamp": None  # 由WAL添加
        }
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"写入失败: {e}")
            return False

    def write_raw(self, key: str, value_any: Any) -> bool:
        """直接写入值（用于WAL回调）"""
        file_path = self._get_file_path(key)
        try:
            # value已经是处理过的原始值
            value = value_any
            data = {
                "key": key,
                "value": value,
                "timestamp": None
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"写入失败: {e}")
            return False
    
    def read(self, key: str) -> Optional[Any]:
        """读取记忆"""
        file_path = self._get_file_path(key)
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("value")
        except Exception as e:
            print(f"读取失败: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """删除记忆"""
        file_path = self._get_file_path(key)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except Exception:
                return False
        return False
    
    def list_keys(self) -> List[str]:
        """列出所有键"""
        keys = []
        for filename in os.listdir(self.vault_dir):
            if filename.endswith('.json'):
                try:
                    file_path = os.path.join(self.vault_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'key' in data:
                            keys.append(data['key'])
                except Exception:
                    pass
        return keys
    
    def count(self) -> int:
        """获取记忆数量"""
        return len([f for f in os.listdir(self.vault_dir) if f.endswith('.json')])
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有记忆"""
        result = {}
        for key in self.list_keys():
            value = self.read(key)
            if value is not None:
                result[key] = value
        return result


# ============ 命令实现 ============

class MemoryCommands:
    """记忆殿堂CLI命令类"""
    
    def __init__(self):
        self.store = MemoryStore()
        self.wal = WALManager(
            wal_dir=os.path.join(PROJECT_ROOT, "wal"),
            enable_checksum=True
        )
        self.health = HealthChecker()
        self.search = create_engine()
        
        # 初始化搜索引擎索引
        self._init_search_index()
    
    def _init_search_index(self):
        """初始化搜索引擎索引"""
        # 从存储加载所有文档到搜索引擎
        for key in self.store.list_keys():
            value = self.store.read(key)
            if value is not None:
                # 将值转为字符串以便搜索
                content = f"{key}: {json.dumps(value, ensure_ascii=False)}"
                self.search.add_document(
                    id=key,
                    content=content,
                    metadata={"key": key, "type": "memory"}
                )
    
    def write(self, key: str, value: Any) -> Dict[str, Any]:
        """
        /memory write <key> <value>
        
        写入记忆到WAL系统
        """
        result = {
            "command": "write",
            "key": key,
            "success": False,
            "transaction_id": None,
            "wal_entry_id": None
        }
        
        try:
            # 三段式提交: BEGIN -> PREPARE -> EXECUTE -> COMMIT
            tx_id = self.wal.begin_transaction()
            result["transaction_id"] = tx_id
            
            # PREPARE: 记录操作意图
            self.wal.prepare_write(tx_id, key, value)
            
            # EXECUTE: 执行实际写入（使用write_raw处理JSON序列化的值）
            self.wal.execute_write(tx_id, self.store.write_raw)
            
            # COMMIT: 提交事务
            self.wal.commit(tx_id)
            
            # 添加到搜索引擎
            content = f"{key}: {json.dumps(value, ensure_ascii=False)}"
            self.search.add_document(
                id=key,
                content=content,
                metadata={"key": key, "type": "memory"}
            )
            
            result["success"] = True
            result["wal_entry_id"] = tx_id
            
        except Exception as e:
            result["error"] = str(e)
            # 尝试回滚
            if result["transaction_id"]:
                try:
                    self.wal.rollback(result["transaction_id"])
                except Exception:
                    pass
        
        return result
    
    def read(self, key: str) -> Dict[str, Any]:
        """
        /memory read <key>
        
        从WAL系统读取记忆
        """
        result = {
            "command": "read",
            "key": key,
            "found": False,
            "value": None
        }
        
        try:
            value = self.store.read(key)
            if value is not None:
                result["found"] = True
                result["value"] = value
            else:
                result["error"] = "Key not found"
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def search_memories(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        /memory search <query>
        
        语义搜索记忆
        """
        result = {
            "command": "search",
            "query": query,
            "total_hits": 0,
            "results": [],
            "stats": {}
        }
        
        try:
            results, total_hits, next_token = self.search.search(
                query=query,
                limit=limit,
                include_vectors=False
            )
            
            result["total_hits"] = total_hits
            result["results"] = [
                {
                    "id": r.id,
                    "score": round(r.score, 4),
                    "content": r.content[:200] if len(r.content) > 200 else r.content,
                    "rank": r.rank
                }
                for r in results
            ]
            result["stats"] = self.search.get_stats()
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def stats(self) -> Dict[str, Any]:
        """
        /memory stats
        
        显示统计信息
        """
        result = {
            "command": "stats",
            "memory_store": {},
            "wal": {},
            "search": {}
        }
        
        try:
            # 记忆存储统计
            all_memories = self.store.get_all()
            result["memory_store"] = {
                "total_memories": len(all_memories),
                "vault_dir": self.store.vault_dir,
                "keys": list(all_memories.keys())[:20]  # 限制显示
            }
            
            # WAL统计
            wal_status = self.wal.get_status()
            result["wal"] = {
                "wal_dir": wal_status.get("wal_dir"),
                "entry_count": wal_status.get("entry_count"),
                "wal_file_count": wal_status.get("wal_file_count"),
                "total_size_mb": wal_status.get("total_size_mb"),
                "active_transactions": wal_status.get("active_transactions")
            }
            
            # 搜索引擎统计
            result["search"] = self.search.get_stats()
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def health_check(self) -> Dict[str, Any]:
        """
        /memory health
        
        健康检查
        """
        try:
            return self.health.get_full_report()
        except Exception as e:
            return {
                "command": "health",
                "error": str(e),
                "overall_status": "unknown"
            }


# ============ CLI入口 ============

def main():
    """CLI主入口"""
    parser = argparse.ArgumentParser(
        description="记忆殿堂v2.0 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  /memory write name "张三"
  /memory read name
  /memory search Python
  /memory stats
  /memory health
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # write命令
    write_parser = subparsers.add_parser("write", help="写入记忆")
    write_parser.add_argument("key", help="记忆键")
    write_parser.add_argument("value", help="记忆值")
    
    # read命令
    read_parser = subparsers.add_parser("read", help="读取记忆")
    read_parser.add_argument("key", help="记忆键")
    
    # search命令
    search_parser = subparsers.add_parser("search", help="搜索记忆")
    search_parser.add_argument("query", help="搜索查询")
    search_parser.add_argument("--limit", "-n", type=int, default=10, help="结果数量")
    
    # stats命令
    subparsers.add_parser("stats", help="查看统计")
    
    # health命令
    subparsers.add_parser("health", help="健康检查")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # 执行命令
    commands = MemoryCommands()
    
    if args.command == "write":
        result = commands.write(args.key, args.value)
    elif args.command == "read":
        result = commands.read(args.key)
    elif args.command == "search":
        result = commands.search_memories(args.query, args.limit)
    elif args.command == "stats":
        result = commands.stats()
    elif args.command == "health":
        result = commands.health_check()
    else:
        parser.print_help()
        return 1
    
    # 输出结果
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
