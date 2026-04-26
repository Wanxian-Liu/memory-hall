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
from pathlib import Path

# 路径设置（最早设置，避免导入时路径冲突）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 导入核心模块
from base_wal.wal import WALManager, WALEntryType
from health.health_check import HealthChecker
from sensory.semantic_search import SemanticSearchEngine, create_engine
from interfaces.adapters import FileSystemAdapter
from task import TaskManager, TaskStatus

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
    
    def __init__(self, vault_dir: str = None):
        # 统一使用FileSystemAdapter，从Config读取路径
        self.adapter = FileSystemAdapter()
        # 如果传入了vault_dir，则使用传入的路径；否则使用adapter的路径
        self.vault_dir = vault_dir if vault_dir is not None else str(self.adapter.vault_dir)
    
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
        self.health_checker = HealthChecker()
        self.search_engine = create_engine()
        
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
                self.search_engine.add_document(
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
            self.search_engine.add_document(
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
            results, total_hits, next_token = self.search_engine.search(
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
            result["stats"] = self.search_engine.get_stats()
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        /memory search <query>
        
        Alias for search_memories for backward compatibility.
        """
        return self.search_memories(query, limit)
    
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
            result["search"] = self.search_engine.get_stats()
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def health_check(self) -> Dict[str, Any]:
        """
        /memory health
        
        健康检查
        """
        try:
            return self.health_checker.get_full_report()
        except Exception as e:
            return {
                "command": "health",
                "error": str(e),
                "overall_status": "unknown"
            }


class TaskCommands:
    """任务管理CLI命令类"""
    
    def __init__(self):
        self.manager = TaskManager()
    
    def create(self, name: str, description: str = "") -> Dict[str, Any]:
        """
        task create <name> <description>
        
        创建新任务
        """
        result = {
            "command": "task_create",
            "name": name,
            "description": description,
            "success": False,
            "task_id": None
        }
        try:
            task_id = self.manager.register_task(name=name, description=description)
            result["success"] = True
            result["task_id"] = task_id
            result["status"] = TaskStatus.PENDING.value
        except Exception as e:
            result["error"] = str(e)
        return result
    
    def list(self, status: Optional[str] = None) -> Dict[str, Any]:
        """
        task list [--status STATUS]
        
        列出任务
        """
        result = {
            "command": "task_list",
            "status_filter": status,
            "total": 0,
            "tasks": []
        }
        try:
            status_filter = None
            if status:
                status_filter = TaskStatus(status)
            
            tasks = self.manager.list_tasks(status=status_filter)
            result["total"] = len(tasks)
            result["tasks"] = [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "description": t.description,
                    "status": t.status.value,
                    "phase": t.current_phase.value,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at
                }
                for t in tasks
            ]
        except Exception as e:
            result["error"] = str(e)
        return result
    
    def get(self, task_id: str) -> Dict[str, Any]:
        """
        task get <task_id>
        
        获取任务详情
        """
        result = {
            "command": "task_get",
            "task_id": task_id,
            "found": False,
            "task": None
        }
        try:
            task = self.manager.get_task(task_id)
            if task:
                result["found"] = True
                result["task"] = {
                    "task_id": task.task_id,
                    "name": task.name,
                    "description": task.description,
                    "status": task.status.value,
                    "phase": task.current_phase.value,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                    "retry_count": task.retry_count,
                    "max_retries": task.max_retries,
                    "timeout": task.timeout,
                    "metadata": task.metadata,
                    "circuit_state": self.manager.get_circuit_state(task_id).value
                }
            else:
                result["error"] = "Task not found"
        except Exception as e:
            result["error"] = str(e)
        return result
    
    def complete(self, task_id: str) -> Dict[str, Any]:
        """
        task complete <task_id>
        
        完成任务
        """
        result = {
            "command": "task_complete",
            "task_id": task_id,
            "success": False
        }
        try:
            task = self.manager.get_task(task_id)
            if not task:
                result["error"] = "Task not found"
                return result
            if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                result["error"] = f"Cannot complete task in status: {task.status.value}"
                return result
            success = self.manager.transition_to(task_id, TaskStatus.COMPLETED)
            result["success"] = success
            if success:
                result["new_status"] = TaskStatus.COMPLETED.value
            else:
                result["error"] = "Transition failed"
        except Exception as e:
            result["error"] = str(e)
        return result
    
    def cancel(self, task_id: str) -> Dict[str, Any]:
        """
        task cancel <task_id>
        
        取消任务
        """
        result = {
            "command": "task_cancel",
            "task_id": task_id,
            "success": False
        }
        try:
            success = self.manager.cancel_task(task_id)
            result["success"] = success
            if success:
                result["new_status"] = TaskStatus.CANCELLED.value
            else:
                task = self.manager.get_task(task_id)
                if not task:
                    result["error"] = "Task not found"
                else:
                    result["error"] = f"Cannot cancel task in status: {task.status.value}"
        except Exception as e:
            result["error"] = str(e)
        return result


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
    
    # task命令
    task_parser = subparsers.add_parser("task", help="任务管理")
    task_subparsers = task_parser.add_subparsers(dest="task_command", help="任务命令")
    
    # task create
    task_create_parser = task_subparsers.add_parser("create", help="创建任务")
    task_create_parser.add_argument("name", help="任务名称")
    task_create_parser.add_argument("description", nargs="?", default="", help="任务描述")
    
    # task list
    task_list_parser = task_subparsers.add_parser("list", help="列出任务")
    task_list_parser.add_argument("--status", "-s", dest="status", 
                                  choices=["pending", "running", "completed", "failed", "cancelled", "timeout", "circuit_open"],
                                  help="按状态过滤")
    
    # task get
    task_get_parser = task_subparsers.add_parser("get", help="获取任务详情")
    task_get_parser.add_argument("task_id", help="任务ID")
    
    # task complete
    task_complete_parser = task_subparsers.add_parser("complete", help="完成任务")
    task_complete_parser.add_argument("task_id", help="任务ID")
    
    # task cancel
    task_cancel_parser = task_subparsers.add_parser("cancel", help="取消任务")
    task_cancel_parser.add_argument("task_id", help="任务ID")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # 执行命令
    if args.command == "task":
        # Task commands
        task_commands = TaskCommands()
        if args.task_command == "create":
            result = task_commands.create(args.name, args.description)
        elif args.task_command == "list":
            result = task_commands.list(args.status)
        elif args.task_command == "get":
            result = task_commands.get(args.task_id)
        elif args.task_command == "complete":
            result = task_commands.complete(args.task_id)
        elif args.task_command == "cancel":
            result = task_commands.cancel(args.task_id)
        else:
            task_parser.print_help()
            return 1
    else:
        # Memory commands
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
