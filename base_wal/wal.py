"""
记忆殿堂v2.0 - WAL (Write-Ahead Log) 协议实现

三段式提交: PREPARE → EXECUTE → COMMIT/ROLLBACK
支持 WAL 压缩 (Compaction) 和重放恢复 (Replay Recovery)
"""

import os
import json
import time
import uuid
import struct
import hashlib
import threading
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional, List, Dict, Tuple
from pathlib import Path


class WALPhase(Enum):
    """WAL 三段式提交阶段"""
    PREPARE = "PREPARE"      # 准备阶段：记录操作意图
    EXECUTE = "EXECUTE"      # 执行阶段：记录执行结果
    COMMIT = "COMMIT"        # 提交阶段：确认完成
    ROLLBACK = "ROLLBACK"    # 回滚阶段：撤销操作


class WALEntryType(Enum):
    """WAL 日志条目类型"""
    TRANSACTION_BEGIN = "TRANSACTION_BEGIN"
    TRANSACTION_END = "TRANSACTION_END"
    WRITE = "WRITE"
    DELETE = "DELETE"
    COMMIT = "COMMIT"
    ROLLBACK = "ROLLBACK"
    CHECKPOINT = "CHECKPOINT"  # 检查点，用于压缩


@dataclass
class WALEntry:
    """WAL 日志条目"""
    entry_id: str                    # 唯一标识
    entry_type: str                  # 条目类型
    transaction_id: str              # 事务ID
    phase: str                       # 当前阶段
    key: Optional[str] = None        # 操作键
    value: Optional[str] = None      # 操作值 (JSON序列化)
    timestamp: float = field(default_factory=time.time)
    prev_hash: str = ""              # 前一条目哈希
    checksum: str = ""               # 校验和
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['entry_type'] = self.entry_type
        d['phase'] = self.phase
        return d
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'WALEntry':
        return cls(
            entry_id=d['entry_id'],
            entry_type=d['entry_type'],
            transaction_id=d['transaction_id'],
            phase=d['phase'],
            key=d.get('key'),
            value=d.get('value'),
            timestamp=d.get('timestamp', time.time()),
            prev_hash=d.get('prev_hash', ''),
            checksum=d.get('checksum', '')
        )
    
    def compute_checksum(self) -> str:
        """计算校验和"""
        data = f"{self.entry_id}|{self.entry_type}|{self.transaction_id}|{self.phase}|{self.key}|{self.value}|{self.timestamp}|{self.prev_hash}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class Transaction:
    """事务状态"""
    transaction_id: str
    status: str                      # PREPARE, EXECUTE, COMMIT, ROLLBACK
    entries: List[WALEntry] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class WALManager:
    """
    WAL (Write-Ahead Log) 管理器
    
    三段式提交协议:
    1. PREPARE: 记录操作意图到 WAL
    2. EXECUTE: 执行实际操作
    3. COMMIT/ROLLBACK: 确认或回滚
    """
    
    def __init__(
        self,
        wal_dir: str = "~/.openclaw/projects/记忆殿堂v2.0/wal",
        max_file_size: int = 64 * 1024 * 1024,  # 64MB
        max_entries_before_compact: int = 10000,
        enable_checksum: bool = True
    ):
        self.wal_dir = Path(os.path.expanduser(wal_dir))
        self.wal_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_file_size = max_file_size
        self.max_entries_before_compact = max_entries_before_compact
        self.enable_checksum = enable_checksum
        
        self._lock = threading.RLock()
        self._current_file: Optional[Path] = None
        self._entry_count = 0
        self._last_hash = ""
        self._active_transactions: Dict[str, Transaction] = {}
        
        # 打开当前 WAL 文件
        self._open_current_file()
        
        # 加载元数据
        self._meta_file = self.wal_dir / "wal.meta"
        self._load_meta()
    
    def _open_current_file(self) -> None:
        """打开新的 WAL 文件"""
        timestamp = int(time.time() * 1000)
        self._current_file = self.wal_dir / f"wal_{timestamp}.log"
        self._entry_count = 0
    
    def _load_meta(self) -> None:
        """加载 WAL 元数据"""
        if self._meta_file.exists():
            try:
                with open(self._meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    self._last_hash = meta.get('last_hash', '')
                    self._entry_count = meta.get('entry_count', 0)
            except Exception:
                pass
    
    def _save_meta(self) -> None:
        """保存 WAL 元数据"""
        meta = {
            'last_hash': self._last_hash,
            'entry_count': self._entry_count,
            'timestamp': time.time()
        }
        with open(self._meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
    
    def _write_entry(self, entry: WALEntry) -> None:
        """写入 WAL 条目（优先写入）"""
        with self._lock:
            # 检查文件大小
            if self._current_file and self._current_file.exists():
                if self._current_file.stat().st_size >= self.max_file_size:
                    self._open_current_file()
            
            # 设置前一条目哈希
            entry.prev_hash = self._last_hash
            
            # 计算校验和
            if self.enable_checksum:
                entry.checksum = entry.compute_checksum()
            
            # 写入文件
            if self._current_file is None:
                self._open_current_file()
            
            line = json.dumps(entry.to_dict(), ensure_ascii=False) + "\n"
            with open(self._current_file, 'a', encoding='utf-8') as f:
                f.write(line)
            
            # 更新状态
            self._last_hash = hashlib.sha256(line.encode()).hexdigest()[:16]
            self._entry_count += 1
            
            # 保存元数据
            self._save_meta()
    
    def _read_entries(self, wal_file: Path) -> List[WALEntry]:
        """读取 WAL 文件中的所有条目"""
        entries = []
        if not wal_file.exists():
            return entries
        
        with open(wal_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    entry = WALEntry.from_dict(d)
                    
                    # 验证校验和
                    if self.enable_checksum and entry.checksum:
                        expected = entry.compute_checksum()
                        if entry.checksum != expected:
                            raise ValueError(f"Checksum mismatch for entry {entry.entry_id}")
                    
                    entries.append(entry)
                except Exception as e:
                    print(f"Warning: Failed to parse WAL entry: {e}")
        
        return entries
    
    # ==================== 三段式提交 API ====================
    
    def begin_transaction(self) -> str:
        """
        事务开始 (PREPARE 阶段)
        
        Returns:
            transaction_id: 事务ID
        """
        transaction_id = str(uuid.uuid4())
        
        with self._lock:
            self._active_transactions[transaction_id] = Transaction(
                transaction_id=transaction_id,
                status=WALPhase.PREPARE.value
            )
        
        # 写入 PREPARE 日志
        entry = WALEntry(
            entry_id=str(uuid.uuid4()),
            entry_type=WALEntryType.TRANSACTION_BEGIN.value,
            transaction_id=transaction_id,
            phase=WALPhase.PREPARE.value
        )
        self._write_entry(entry)
        
        return transaction_id
    
    def prepare_write(self, transaction_id: str, key: str, value: Any) -> None:
        """
        准备写入 (PREPARE 阶段 - 记录操作意图)
        
        Args:
            transaction_id: 事务ID
            key: 键
            value: 值
        """
        with self._lock:
            if transaction_id not in self._active_transactions:
                raise ValueError(f"Transaction {transaction_id} not found")
            
            # 更新事务状态
            self._active_transactions[transaction_id].status = WALPhase.PREPARE.value
            self._active_transactions[transaction_id].updated_at = time.time()
        
        # 序列化和记录 PREPARE
        value_json = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        
        entry = WALEntry(
            entry_id=str(uuid.uuid4()),
            entry_type=WALEntryType.WRITE.value,
            transaction_id=transaction_id,
            phase=WALPhase.PREPARE.value,
            key=key,
            value=value_json
        )
        self._write_entry(entry)
        
        # 同步添加到事务条目列表（用于execute时查找）
        with self._lock:
            if transaction_id in self._active_transactions:
                self._active_transactions[transaction_id].entries.append(entry)
    
    def execute_write(self, transaction_id: str, write_fn: Callable[[str, Any], None]) -> None:
        """
        执行写入 (EXECUTE 阶段)
        
        Args:
            transaction_id: 事务ID
            write_fn: 执行实际写入的回调函数 (key, value) -> None
        """
        with self._lock:
            if transaction_id not in self._active_transactions:
                raise ValueError(f"Transaction {transaction_id} not found")
            
            tx = self._active_transactions[transaction_id]
            
            # 查找 PREPARE 阶段的条目
            prepare_entries = [e for e in tx.entries if e.phase == WALPhase.PREPARE.value and e.entry_type == WALEntryType.WRITE.value]
            
            if not prepare_entries:
                raise ValueError(f"No PREPARE entries found for transaction {transaction_id}")
            
            # 更新事务状态
            tx.status = WALPhase.EXECUTE.value
            tx.updated_at = time.time()
        
        # 写入 EXECUTE 日志
        entry = WALEntry(
            entry_id=str(uuid.uuid4()),
            entry_type=WALEntryType.WRITE.value,
            transaction_id=transaction_id,
            phase=WALPhase.EXECUTE.value
        )
        self._write_entry(entry)
        
        # 执行实际写入
        for prepare_entry in prepare_entries:
            write_fn(prepare_entry.key, prepare_entry.value)
    
    def commit(self, transaction_id: str) -> None:
        """
        提交事务 (COMMIT 阶段)
        
        Args:
            transaction_id: 事务ID
        """
        with self._lock:
            if transaction_id not in self._active_transactions:
                raise ValueError(f"Transaction {transaction_id} not found")
            
            tx = self._active_transactions[transaction_id]
            tx.status = WALPhase.COMMIT.value
            tx.updated_at = time.time()
        
        # 写入 COMMIT 日志
        entry = WALEntry(
            entry_id=str(uuid.uuid4()),
            entry_type=WALEntryType.COMMIT.value,
            transaction_id=transaction_id,
            phase=WALPhase.COMMIT.value
        )
        self._write_entry(entry)
        
        # 清理活跃事务
        with self._lock:
            del self._active_transactions[transaction_id]
        
        # 检查是否需要压缩
        if self._entry_count >= self.max_entries_before_compact:
            self._schedule_compaction()
    
    def rollback(self, transaction_id: str) -> None:
        """
        回滚事务 (ROLLBACK 阶段)
        
        Args:
            transaction_id: 事务ID
        """
        with self._lock:
            if transaction_id not in self._active_transactions:
                raise ValueError(f"Transaction {transaction_id} not found")
            
            tx = self._active_transactions[transaction_id]
            tx.status = WALPhase.ROLLBACK.value
            tx.updated_at = time.time()
        
        # 写入 ROLLBACK 日志
        entry = WALEntry(
            entry_id=str(uuid.uuid4()),
            entry_type=WALEntryType.ROLLBACK.value,
            transaction_id=transaction_id,
            phase=WALPhase.ROLLBACK.value
        )
        self._write_entry(entry)
        
        # 清理活跃事务
        with self._lock:
            del self._active_transactions[transaction_id]
    
    def _schedule_compaction(self) -> None:
        """调度 WAL 压缩"""
        threading.Thread(target=self.compact, daemon=True).start()
    
    def add_entry(self, entry_type: WALEntryType, key: str, value: Any) -> WALEntry:
        """
        直接添加 WAL 条目（单条操作，无需事务）
        
        Args:
            entry_type: 条目类型
            key: 键
            value: 值
        
        Returns:
            WALEntry: 创建的条目
        """
        value_json = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        
        entry = WALEntry(
            entry_id=str(uuid.uuid4()),
            entry_type=entry_type.value,
            transaction_id="single",
            phase=WALPhase.COMMIT.value,
            key=key,
            value=value_json
        )
        self._write_entry(entry)
        return entry
    
    # ==================== 压缩与恢复 API ====================
    
    def compact(self) -> Tuple[int, int]:
        """
        WAL 压缩 (Compaction)
        
        合并多个 WAL 文件，移除已提交事务的冗余条目
        
        Returns:
            (removed_count, kept_count): 移除和保留的条目数
        """
        with self._lock:
            wal_files = sorted(self.wal_dir.glob("wal_*.log"))
            
            if len(wal_files) <= 1:
                return (0, 0)
            
            # 收集所有条目并分析事务状态
            all_entries: List[Tuple[Path, WALEntry]] = []
            committed_transactions = set()
            rolled_back_transactions = set()
            
            for wal_file in wal_files:
                entries = self._read_entries(wal_file)
                for entry in entries:
                    all_entries.append((wal_file, entry))
                    
                    # 记录已提交/回滚的事务
                    if entry.entry_type == WALEntryType.COMMIT.value:
                        committed_transactions.add(entry.transaction_id)
                    elif entry.entry_type == WALEntryType.ROLLBACK.value:
                        rolled_back_transactions.add(entry.transaction_id)
            
            # 筛选需要保留的条目
            kept_entries = []
            for file_path, entry in all_entries:
                # 保留: 单事务、CHECKPOINT、未完成事务的条目
                if entry.transaction_id == "single":
                    kept_entries.append(entry)
                elif entry.entry_type == WALEntryType.CHECKPOINT.value:
                    kept_entries.append(entry)
                elif entry.transaction_id in committed_transactions:
                    # 已提交事务: 只保留 COMMIT 条目
                    if entry.entry_type == WALEntryType.COMMIT.value:
                        kept_entries.append(entry)
                elif entry.transaction_id in rolled_back_transactions:
                    # 已回滚事务: 全部移除
                    pass
                else:
                    # 活跃事务: 全部保留
                    kept_entries.append(entry)
            
            kept_count = len(kept_entries)
            removed_count = len(all_entries) - kept_count
            
            if removed_count == 0:
                return (0, kept_count)
            
            # 写新的压缩文件
            compact_file = self.wal_dir / f"wal_compact_{int(time.time() * 1000)}.log"
            with open(compact_file, 'w', encoding='utf-8') as f:
                for entry in kept_entries:
                    line = json.dumps(entry.to_dict(), ensure_ascii=False) + "\n"
                    f.write(line)
            
            # 删除原文件
            for wal_file in wal_files:
                wal_file.unlink()
            
            # 重命名压缩文件
            new_wal_file = self.wal_dir / f"wal_{int(time.time() * 1000)}.log"
            compact_file.rename(new_wal_file)
            
            # 更新状态
            self._current_file = new_wal_file
            self._entry_count = kept_count
            
            # 更新元数据
            if kept_entries:
                self._last_hash = hashlib.sha256(json.dumps(kept_entries[-1].to_dict()).encode()).hexdigest()[:16]
            self._save_meta()
            
            return (removed_count, kept_count)
    
    def recover(self, apply_fn: Callable[[str, str, Any], None]) -> Dict[str, int]:
        """
        WAL 重放恢复 (Replay Recovery)
        
        从 WAL 文件中恢复数据状态
        
        Args:
            apply_fn: 应用条目的回调函数 (entry_type, key, value) -> None
        
        Returns:
            Dict: 恢复统计 {'committed': n, 'rolled_back': n, 'incomplete': n}
        """
        with self._lock:
            wal_files = sorted(self.wal_dir.glob("wal_*.log"))
            
            stats = {'committed': 0, 'rolled_back': 0, 'incomplete': 0}
            
            # 分析所有事务状态
            transaction_states: Dict[str, str] = {}
            
            for wal_file in wal_files:
                entries = self._read_entries(wal_file)
                
                for entry in entries:
                    tx_id = entry.transaction_id
                    
                    if entry.entry_type == WALEntryType.TRANSACTION_BEGIN.value:
                        if tx_id not in transaction_states:
                            transaction_states[tx_id] = WALPhase.PREPARE.value
                    
                    elif entry.entry_type == WALEntryType.WRITE.value:
                        if tx_id in transaction_states:
                            if entry.phase == WALPhase.EXECUTE.value:
                                transaction_states[tx_id] = WALPhase.EXECUTE.value
                    
                    elif entry.entry_type == WALEntryType.COMMIT.value:
                        transaction_states[tx_id] = WALPhase.COMMIT.value
                    
                    elif entry.entry_type == WALEntryType.ROLLBACK.value:
                        transaction_states[tx_id] = WALPhase.ROLLBACK.value
            
            # 重放条目
            for wal_file in wal_files:
                entries = self._read_entries(wal_file)
                
                for entry in entries:
                    tx_id = entry.transaction_id
                    
                    if tx_id == "single":
                        # 单条目直接应用
                        apply_fn(entry.entry_type, entry.key, entry.value)
                        stats['committed'] += 1
                        continue
                    
                    state = transaction_states.get(tx_id)
                    
                    if state == WALPhase.COMMIT.value:
                        # 已提交事务: 应用所有 WRITE 条目
                        if entry.entry_type == WALEntryType.WRITE.value and entry.key:
                            apply_fn(entry.entry_type, entry.key, entry.value)
                        stats['committed'] += 1
                    
                    elif state == WALPhase.ROLLBACK.value:
                        # 已回滚事务: 跳过
                        stats['rolled_back'] += 1
                    
                    else:
                        # 未完成事务: 记录但不应用
                        stats['incomplete'] += 1
            
            return stats
    
    def get_status(self) -> Dict[str, Any]:
        """获取 WAL 状态"""
        with self._lock:
            wal_files = list(self.wal_dir.glob("wal_*.log"))
            total_size = sum(f.stat().st_size for f in wal_files if f.exists())
            
            return {
                'wal_dir': str(self.wal_dir),
                'wal_file_count': len(wal_files),
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'entry_count': self._entry_count,
                'active_transactions': len(self._active_transactions),
                'last_hash': self._last_hash[:16],
                'current_file': str(self._current_file) if self._current_file else None
            }
    
    def create_checkpoint(self) -> WALEntry:
        """
        创建检查点 (CHECKPOINT)
        
        Returns:
            WALEntry: 检查点条目
        """
        entry = WALEntry(
            entry_id=str(uuid.uuid4()),
            entry_type=WALEntryType.CHECKPOINT.value,
            transaction_id="system",
            phase=WALPhase.COMMIT.value
        )
        self._write_entry(entry)
        return entry


# ==================== 便捷函数 ====================

_default_wal_manager: Optional[WALManager] = None


def get_default_wal_manager() -> WALManager:
    """获取默认 WAL 管理器实例"""
    global _default_wal_manager
    if _default_wal_manager is None:
        _default_wal_manager = WALManager()
    return _default_wal_manager


def begin() -> str:
    """开始事务"""
    return get_default_wal_manager().begin_transaction()


def prepare_write(transaction_id: str, key: str, value: Any) -> None:
    """准备写入"""
    get_default_wal_manager().prepare_write(transaction_id, key, value)


def execute_write(transaction_id: str, write_fn: Callable[[str, Any], None]) -> None:
    """执行写入"""
    get_default_wal_manager().execute_write(transaction_id, write_fn)


def commit(transaction_id: str) -> None:
    """提交事务"""
    get_default_wal_manager().commit(transaction_id)


def rollback(transaction_id: str) -> None:
    """回滚事务"""
    get_default_wal_manager().rollback(transaction_id)


def wal_write(key: str, value: Any) -> WALEntry:
    """单条 WAL 写入（无需事务）"""
    return get_default_wal_manager().add_entry(WALEntryType.WRITE, key, value)


def wal_delete(key: str, value: Any = None) -> WALEntry:
    """单条 WAL 删除（无需事务）"""
    return get_default_wal_manager().add_entry(WALEntryType.DELETE, key, value)


def compact() -> Tuple[int, int]:
    """WAL 压缩"""
    return get_default_wal_manager().compact()


def recover(apply_fn: Callable[[str, str, Any], None]) -> Dict[str, int]:
    """WAL 重放恢复"""
    return get_default_wal_manager().recover(apply_fn)


def status() -> Dict[str, Any]:
    """WAL 状态"""
    return get_default_wal_manager().get_status()
