"""
记忆殿堂v2.0 - WAL (Write-Ahead Log) 基座

三段式提交: PREPARE → EXECUTE → COMMIT/ROLLBACK
支持 WAL 压缩 (Compaction) 和重放恢复 (Replay Recovery)

Usage:
    from base_wal import WALManager, begin, prepare_write, execute_write, commit

    # 三段式提交示例
    tx_id = begin()
    prepare_write(tx_id, "user:1", {"name": "张三", "age": 30})
    execute_write(tx_id, lambda key, value: storage.set(key, json.loads(value)))
    commit(tx_id)
"""

from .wal import (
    # 核心类
    WALManager,
    WALPhase,
    WALEntryType,
    WALEntry,
    Transaction,
    
    # 便捷函数
    begin,
    prepare_write,
    execute_write,
    commit,
    rollback,
    wal_write,
    wal_delete,
    compact,
    recover,
    status,
    get_default_wal_manager,
)

__all__ = [
    # 核心类
    'WALManager',
    'WALPhase',
    'WALEntryType', 
    'WALEntry',
    'Transaction',
    
    # 便捷函数
    'begin',
    'prepare_write',
    'execute_write',
    'commit',
    'rollback',
    'wal_write',
    'wal_delete',
    'compact',
    'recover',
    'status',
    'get_default_wal_manager',
]

__version__ = '2.0.0'
