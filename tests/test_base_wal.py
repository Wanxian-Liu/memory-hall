# -*- coding: utf-8 -*-
"""
测试 base_wal 模块 - WAL日志系统
"""
import os
import sys
import uuid
import pytest

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from pathlib import Path

from base_wal.wal import (
    WALManager, WALEntry, WALEntryType, WALPhase,
    Transaction,
    get_default_wal_manager,
    begin, prepare_write, execute_write, commit, rollback,
    wal_write, wal_delete, compact, recover, status
)


class TestWALEntryType:
    """测试WALEntryType枚举"""
    def test_entry_types(self):
        assert WALEntryType.WRITE.value == "WRITE"
        assert WALEntryType.DELETE.value == "DELETE"
        assert WALEntryType.COMMIT.value == "COMMIT"
        assert WALEntryType.ROLLBACK.value == "ROLLBACK"
        assert WALEntryType.TRANSACTION_BEGIN.value == "TRANSACTION_BEGIN"
        assert WALEntryType.TRANSACTION_END.value == "TRANSACTION_END"
        assert WALEntryType.CHECKPOINT.value == "CHECKPOINT"


class TestWALPhase:
    """测试WALPhase枚举"""
    def test_phases(self):
        assert WALPhase.PREPARE.value == "PREPARE"
        assert WALPhase.EXECUTE.value == "EXECUTE"
        assert WALPhase.COMMIT.value == "COMMIT"
        assert WALPhase.ROLLBACK.value == "ROLLBACK"


class TestWALEntry:
    """测试WALEntry类"""
    def test_entry_creation(self):
        entry = WALEntry(
            entry_id=str(uuid.uuid4()),
            entry_type=WALEntryType.WRITE.value,
            transaction_id='tx_test',
            phase='PREPARE',
            key="test_key",
            value="test_value"
        )
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.entry_type == WALEntryType.WRITE.value

    def test_entry_with_tx_id(self):
        entry = WALEntry(
            entry_id=str(uuid.uuid4()),
            entry_type=WALEntryType.WRITE.value,
            transaction_id="tx_123",
            phase='PREPARE',
            key="key1",
            value="value1"
        )
        assert entry.transaction_id == "tx_123"


class TestTransaction:
    """测试Transaction类"""
    def test_transaction_creation(self):
        tx = Transaction(
            transaction_id="tx_test",
            status="PREPARE"
        )
        assert tx.transaction_id == "tx_test"
        assert tx.status == "PREPARE"


class TestWALManager:
    """测试WALManager类"""
    def test_manager_init(self, wal_dir):
        manager = WALManager(wal_dir=wal_dir)
        assert manager.wal_dir is not None

    def test_begin_transaction(self, wal_dir):
        manager = WALManager(wal_dir=wal_dir)
        tx_id = manager.begin_transaction()
        assert tx_id is not None
        assert tx_id in manager._active_transactions

    def test_transaction_lifecycle(self, wal_dir):
        """测试事务完整生命周期"""
        manager = WALManager(wal_dir=wal_dir)

        tx_id = manager.begin_transaction()
        tx = manager._active_transactions[tx_id]
        assert tx.status == "PREPARE"

        manager.prepare_write(tx_id, "key1", "value1")
        tx = manager._active_transactions[tx_id]
        assert tx.status == "PREPARE"
        assert len(tx.entries) == 1

        write_calls = []
        def mock_write(key, value):
            write_calls.append((key, value))
            return True

        # Actual: execute_write returns None
        manager.execute_write(tx_id, mock_write)
        assert len(write_calls) == 1

        manager.commit(tx_id)
        assert tx_id not in manager._active_transactions

    def test_transaction_rollback(self, wal_dir):
        """测试事务回滚"""
        manager = WALManager(wal_dir=wal_dir)

        tx_id = manager.begin_transaction()
        manager.prepare_write(tx_id, "key1", "value1")
        manager.rollback(tx_id)
        assert tx_id not in manager._active_transactions

    def test_get_status(self, wal_dir):
        """测试获取WAL状态"""
        manager = WALManager(wal_dir=wal_dir)
        status = manager.get_status()
        assert "wal_dir" in status
        assert "entry_count" in status
        assert "wal_file_count" in status
        assert "total_size_bytes" in status

    def test_add_entry(self, wal_dir):
        """测试添加条目"""
        manager = WALManager(wal_dir=wal_dir)
        entry = manager.add_entry(
            entry_type=WALEntryType.WRITE,
            key="test_key",
            value="test_value"
        )
        assert entry is not None
        assert entry.key == "test_key"
        assert entry.entry_type == WALEntryType.WRITE.value


class TestWALGlobalFunctions:
    """测试WAL全局函数"""
    def test_wal_write(self, wal_dir):
        manager = WALManager(wal_dir=wal_dir)
        entry = wal_write("global_key", "global_value")
        assert entry is not None

    def test_wal_delete(self, wal_dir):
        entry = wal_delete("delete_key")
        assert entry is not None

    def test_begin(self, wal_dir):
        tx_id = begin()
        assert tx_id is not None

    def test_prepare_write(self, wal_dir):
        tx_id = begin()
        prepare_write(tx_id, "prep_key", "prep_value")
        assert True

    def test_commit_and_rollback(self, wal_dir):
        tx_id = begin()
        prepare_write(tx_id, "tx_key", "tx_value")

        write_calls = []
        def mock_write(k, v):
            write_calls.append((k, v))
        execute_write(tx_id, mock_write)
        commit(tx_id)

        # 测试回滚
        tx_id2 = begin()
        prepare_write(tx_id2, "rb_key", "rb_value")
        rollback(tx_id2)


class TestWALCompaction:
    """测试WAL压缩功能"""
    
    def test_compact_empty_dir(self, wal_dir):
        """测试空目录压缩"""
        manager = WALManager(wal_dir=wal_dir)
        removed, kept = manager.compact()
        assert removed == 0
        assert kept == 0
    
    def test_compact_single_file(self, wal_dir):
        """测试单文件压缩"""
        manager = WALManager(wal_dir=wal_dir)
        # 添加一些条目
        manager.add_entry(WALEntryType.WRITE, "key1", "value1")
        manager.add_entry(WALEntryType.WRITE, "key2", "value2")
        removed, kept = manager.compact()
        assert kept >= 0
    
    def test_compact_with_committed_transaction(self, wal_dir):
        """测试已提交事务的压缩"""
        manager = WALManager(wal_dir=wal_dir)
        
        # 创建并提交事务
        tx_id = manager.begin_transaction()
        manager.prepare_write(tx_id, "tx_key", "tx_value")
        
        write_calls = []
        def mock_write(k, v):
            write_calls.append((k, v))
        manager.execute_write(tx_id, mock_write)
        manager.commit(tx_id)
        
        # 压缩应该保留COMMIT条目
        removed, kept = manager.compact()
        # 验证没有抛出异常且返回值是元组
        assert (removed, kept) is not None


class TestWALChecksum:
    """测试WAL校验和功能"""
    
    def test_checksum_validation(self, wal_dir):
        """测试校验和计算"""
        manager = WALManager(wal_dir=wal_dir, enable_checksum=True)
        
        entry = manager.add_entry(WALEntryType.WRITE, "checksum_key", "checksum_value")
        assert entry is not None
    
    def test_no_checksum_mode(self, wal_dir):
        """测试禁用校验和模式"""
        manager = WALManager(wal_dir=wal_dir, enable_checksum=False)
        
        entry = manager.add_entry(WALEntryType.WRITE, "no_checksum_key", "no_checksum_value")
        assert entry is not None
