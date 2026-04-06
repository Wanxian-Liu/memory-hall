"""
记忆殿堂v2.0 - 备份恢复与修复模块
Capsule: 01-repair-memory-palace-v2
GDI: 67.6 | 记忆殿堂 | RAG修复 | 备份恢复 | 压缩优化

包含:
- MemoryBackupManager: 记忆备份与恢复管理器
- ImportanceAwareCompressor: 重要性感知压缩器
- verify_rag_source: RAG源码验证函数
"""

import time
import asyncio
import logging
import hashlib
import json
import os
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class VerificationStatus(Enum):
    """RAG验证状态"""
    VERIFIED = "verified"           # 已验证通过
    UNVERIFIED = "unverified"       # 未验证
    HIGH_CONFIDENCE = "high"         # 高置信
    LOW_CONFIDENCE = "low"           # 低置信
    FAILED = "failed"                # 验证失败


class ImportanceLevel(Enum):
    """重要性级别"""
    CRITICAL = 1.0      # 关键决策点
    HIGH = 0.9          # 用户偏好
    MEDIUM = 0.7        # 工具结果
    LOW = 0.5           # 一般信息
    MINIMAL = 0.3       # 可丢弃


@dataclass
class BackupSnapshot:
    """备份快照"""
    snapshot_id: str
    session_id: str
    timestamp: float
    critical_keys: List[str]
    memory_state: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: Optional[str] = None
    compressed: bool = False


@dataclass
class RestorationResult:
    """恢复结果"""
    snapshot_id: str
    restored_keys: List[str]
    missing_keys: List[str]
    restored_size_bytes: int
    restoration_time_ms: float
    success: bool
    message: str = ""


@dataclass
class RAGVerificationResult:
    """RAG验证结果"""
    verified: bool
    confidence: float
    status: VerificationStatus
    source_uri: Optional[str] = None
    source_text: Optional[str] = None
    matched_content: Optional[str] = None
    similarity: float = 0.0
    verification_time_ms: float = 0.0
    claim: str = ""


@dataclass
class CompressedItem:
    """压缩后的记忆条目"""
    original_key: str
    original_value: Any
    compressed_value: Any
    importance_score: float
    preservation_reason: str


# ========== verify_rag_source ==========

async def verify_rag_source(
    retrieved_chunk: Any,
    claim: str,
    similarity_threshold: float = 0.85,
    source_fetcher: Optional[Callable] = None,
    similarity_calculator: Optional[Callable] = None
) -> RAGVerificationResult:
    """
    RAG源码验证函数
    
    验证流程:
    1. 提取检索结果的原始文档URI
    2. 获取源码内容
    3. 计算声明与源码的相似度
    4. 返回验证结果
    
    Args:
        retrieved_chunk: RAG检索返回的chunk，需包含 uri/content 字段
        claim: 待验证的声明文本
        similarity_threshold: 相似度阈值，默认0.85
        source_fetcher: 可选的源码获取函数 (uri) -> text
        similarity_calculator: 可选的相似度计算函数 (text1, text2) -> float
        
    Returns:
        RAGVerificationResult: 验证结果
    """
    start_time = time.time()
    
    # 提取chunk信息
    if isinstance(retrieved_chunk, dict):
        chunk_uri = retrieved_chunk.get("uri", retrieved_chunk.get("source", ""))
        chunk_content = retrieved_chunk.get("content", retrieved_chunk.get("text", ""))
    elif hasattr(retrieved_chunk, "uri"):
        chunk_uri = retrieved_chunk.uri
        chunk_content = getattr(retrieved_chunk, "content", "")
    else:
        chunk_uri = ""
        chunk_content = str(retrieved_chunk)
    
    if not chunk_uri and not chunk_content:
        return RAGVerificationResult(
            verified=False,
            confidence=0.0,
            status=VerificationStatus.FAILED,
            claim=claim,
            verification_time_ms=(time.time() - start_time) * 1000,
            message="Empty retrieved chunk"
        )
    
    # 尝试获取源码
    source_text = chunk_content
    
    if source_fetcher and chunk_uri:
        try:
            source_text = await source_fetcher(chunk_uri)
        except Exception as e:
            logger.warning(f"Source fetcher failed: {e}")
            # 回退到chunk内容
            source_text = chunk_content
    
    # 计算相似度
    if similarity_calculator:
        try:
            similarity = await similarity_calculator(claim, source_text)
        except Exception as e:
            logger.warning(f"Similarity calculation failed: {e}")
            similarity = _simple_similarity(claim, source_text)
    else:
        similarity = _simple_similarity(claim, source_text)
    
    # 判断验证状态
    verified = similarity >= similarity_threshold
    
    if similarity >= 0.9:
        status = VerificationStatus.HIGH_CONFIDENCE
    elif similarity >= similarity_threshold:
        status = VerificationStatus.VERIFIED
    elif similarity >= 0.5:
        status = VerificationStatus.LOW_CONFIDENCE
    else:
        status = VerificationStatus.UNVERIFIED
    
    elapsed_ms = (time.time() - start_time) * 1000
    
    return RAGVerificationResult(
        verified=verified,
        confidence=similarity,
        status=status,
        source_uri=chunk_uri,
        source_text=source_text[:500] if source_text else None,
        matched_content=chunk_content[:200] if chunk_content else None,
        similarity=similarity,
        verification_time_ms=elapsed_ms,
        claim=claim[:200]
    )


def _simple_similarity(text1: str, text2: str) -> float:
    """
    简单的词重叠相似度计算
    
    基于Jaccard相似度:
    similarity = |intersection(words)| / |union(words)|
    """
    if not text1 or not text2:
        return 0.0
    
    # 分词 (简单按空格和标点)
    import re
    words1 = set(re.findall(r'\w+', text1.lower()))
    words2 = set(re.findall(r'\w+', text2.lower()))
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    # 考虑文本长度惩罚
    len_ratio = min(len(words1), len(words2)) / max(len(words1), len(words2))
    
    return (len(intersection) / len(union)) * (0.5 + 0.5 * len_ratio)


# ========== MemoryBackupManager ==========

class MemoryBackupManager:
    """
    记忆备份与恢复管理器
    
    在压缩等不可逆操作前创建快照，
    支持版本回溯和信息恢复。
    
    核心功能:
    - backup_before_compress: 压缩前备份
    - restore: 从快照恢复
    - list_snapshots: 列出可用快照
    - cleanup: 过期快照清理
    """
    
    def __init__(
        self,
        backup_dir: str = "~/.openclaw/workspace/memory_backups",
        max_backups_per_session: int = 5,
        max_total_size_mb: int = 100,
        retention_hours: int = 24
    ):
        self.backup_dir = os.path.expanduser(backup_dir)
        self.max_backups_per_session = max_backups_per_session
        self.max_total_size_mb = max_total_size_mb
        self.retention_hours = retention_hours
        
        # 确保备份目录存在
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # 内存索引
        self._snapshot_index: Dict[str, BackupSnapshot] = {}
        self._session_snapshots: Dict[str, List[str]] = defaultdict(list)
        
        # 统计
        self._stats = {
            "backups_created": 0,
            "restores_performed": 0,
            "cleanups_performed": 0,
            "snapshots_cleaned": 0,
            "total_backup_size_bytes": 0
        }
    
    def backup_before_compress(
        self,
        session_id: str,
        memory_state: Dict[str, Any],
        critical_keys: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> BackupSnapshot:
        """
        压缩前创建备份
        
        策略:
        1. 提取关键信息 (决策点、用户偏好等)
        2. 生成快照
        3. 写入磁盘
        4. 更新索引
        
        Args:
            session_id: 会话ID
            memory_state: 当前记忆状态
            critical_keys: 关键记忆键列表 (优先保留)
            metadata: 额外元数据
            
        Returns:
            BackupSnapshot: 备份快照
        """
        # 生成快照ID
        snapshot_id = self._generate_snapshot_id(session_id)
        
        # 提取关键信息
        if critical_keys is None:
            critical_keys = self._extract_critical_keys(memory_state)
        
        # 构建快照
        snapshot = BackupSnapshot(
            snapshot_id=snapshot_id,
            session_id=session_id,
            timestamp=time.time(),
            critical_keys=critical_keys,
            memory_state=memory_state,
            metadata=metadata or {},
            checksum=self._calculate_checksum(memory_state)
        )
        
        # 写入磁盘
        self._write_snapshot_to_disk(snapshot)
        
        # 更新索引
        self._snapshot_index[snapshot_id] = snapshot
        self._session_snapshots[session_id].append(snapshot_id)
        
        # 维护会话快照数量限制
        self._enforce_session_backup_limit(session_id)
        
        # 更新统计
        self._stats["backups_created"] += 1
        self._update_total_size()
        
        logger.info(f"Backup created: {snapshot_id} for session {session_id}")
        
        return snapshot
    
    def _extract_critical_keys(self, memory_state: Dict[str, Any]) -> List[str]:
        """
        从记忆状态中提取关键记忆键
        
        关键性判断:
        - 包含特定关键词的键 (decision, preference, important)
        - 最近访问的
        - 高频访问的
        """
        critical = []
        
        importance_indicators = [
            "decision", "preference", "important", "critical",
            "用户偏好", "关键决策", "重要", "记住"
        ]
        
        for key in memory_state.keys():
            key_lower = key.lower()
            
            # 关键词匹配
            for indicator in importance_indicators:
                if indicator in key_lower:
                    critical.append(key)
                    break
            
            # 键值对重要性评分
            value = memory_state[key]
            if hasattr(value, "importance_score"):
                if value.importance_score >= 0.9:
                    critical.append(key)
    
        return critical
    
    def _generate_snapshot_id(self, session_id: str) -> str:
        """生成快照ID"""
        timestamp = int(time.time() * 1000)
        hash_input = f"{session_id}_{timestamp}_{id(self)}"
        short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"snap_{session_id}_{timestamp}_{short_hash}"
    
    def _calculate_checksum(self, memory_state: Dict[str, Any]) -> str:
        """计算记忆状态的校验和"""
        serialized = json.dumps(memory_state, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
    
    def _write_snapshot_to_disk(self, snapshot: BackupSnapshot) -> None:
        """将快照写入磁盘"""
        filepath = os.path.join(
            self.backup_dir,
            f"{snapshot.snapshot_id}.json"
        )
        
        data = {
            "snapshot_id": snapshot.snapshot_id,
            "session_id": snapshot.session_id,
            "timestamp": snapshot.timestamp,
            "critical_keys": snapshot.critical_keys,
            "memory_state": snapshot.memory_state,
            "metadata": snapshot.metadata,
            "checksum": snapshot.checksum,
            "compressed": snapshot.compressed
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    def _read_snapshot_from_disk(self, snapshot_id: str) -> Optional[BackupSnapshot]:
        """从磁盘读取快照"""
        filepath = os.path.join(self.backup_dir, f"{snapshot_id}.json")
        
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return BackupSnapshot(
                snapshot_id=data["snapshot_id"],
                session_id=data["session_id"],
                timestamp=data["timestamp"],
                critical_keys=data["critical_keys"],
                memory_state=data["memory_state"],
                metadata=data.get("metadata", {}),
                checksum=data.get("checksum"),
                compressed=data.get("compressed", False)
            )
        except Exception as e:
            logger.error(f"Failed to read snapshot {snapshot_id}: {e}")
            return None
    
    def _enforce_session_backup_limit(self, session_id: str) -> None:
        """强制执行会话备份数量限制"""
        snapshots = self._session_snapshots.get(session_id, [])
        
        while len(snapshots) > self.max_backups_per_session:
            oldest_id = snapshots.pop(0)
            
            # 从磁盘删除
            filepath = os.path.join(self.backup_dir, f"{oldest_id}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
            
            # 从索引删除
            if oldest_id in self._snapshot_index:
                del self._snapshot_index[oldest_id]
            
            self._stats["snapshots_cleaned"] += 1
    
    def restore(
        self,
        snapshot_id: str,
        target_keys: Optional[List[str]] = None
    ) -> RestorationResult:
        """
        从快照恢复记忆
        
        Args:
            snapshot_id: 快照ID
            target_keys: 可选，指定要恢复的键；None表示全部
            
        Returns:
            RestorationResult: 恢复结果
        """
        start_time = time.time()
        
        snapshot = self._read_snapshot_from_disk(snapshot_id)
        
        if not snapshot:
            return RestorationResult(
                snapshot_id=snapshot_id,
                restored_keys=[],
                missing_keys=[],
                restored_size_bytes=0,
                restoration_time_ms=0,
                success=False,
                message=f"Snapshot not found: {snapshot_id}"
            )
        
        # 确定要恢复的键
        keys_to_restore = target_keys or list(snapshot.memory_state.keys())
        
        restored_keys = []
        missing_keys = []
        restored_size = 0
        
        for key in keys_to_restore:
            if key in snapshot.memory_state:
                restored_keys.append(key)
                restored_size += len(str(snapshot.memory_state[key]))
        
        missing_keys = [k for k in keys_to_restore if k not in snapshot.memory_state]
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        self._stats["restores_performed"] += 1
        
        return RestorationResult(
            snapshot_id=snapshot_id,
            restored_keys=restored_keys,
            missing_keys=missing_keys,
            restored_size_bytes=restored_size,
            restoration_time_ms=elapsed_ms,
            success=len(missing_keys) == 0,
            message=f"Restored {len(restored_keys)} keys" + 
                    (f", missing {len(missing_keys)}" if missing_keys else "")
        )
    
    def restore_critical_only(self, snapshot_id: str) -> Dict[str, Any]:
        """
        仅恢复关键记忆
        
        Args:
            snapshot_id: 快照ID
            
        Returns:
            Dict[str, Any]: 关键记忆字典
        """
        snapshot = self._read_snapshot_from_disk(snapshot_id)
        
        if not snapshot:
            logger.warning(f"Snapshot not found for critical restore: {snapshot_id}")
            return {}
        
        critical_state = {}
        
        for key in snapshot.critical_keys:
            if key in snapshot.memory_state:
                critical_state[key] = snapshot.memory_state[key]
        
        return critical_state
    
    def list_snapshots(
        self,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[BackupSnapshot]:
        """
        列出可用快照
        
        Args:
            session_id: 可选，按会话ID筛选
            limit: 返回数量限制
            
        Returns:
            List[BackupSnapshot]: 快照列表
        """
        if session_id:
            snapshot_ids = self._session_snapshots.get(session_id, [])
            snapshots = [
                self._snapshot_index.get(sid)
                for sid in snapshot_ids
                if sid in self._snapshot_index
            ]
        else:
            # 所有快照，按时间倒序
            all_snapshots = list(self._snapshot_index.values())
            all_snapshots.sort(key=lambda x: x.timestamp, reverse=True)
            snapshots = all_snapshots
        
        return [s for s in snapshots if s][:limit]
    
    def cleanup_expired(self) -> int:
        """
        清理过期快照
        
        清理策略:
        - 超过retention_hours的
        - 总大小超过max_total_size_mb时，优先删旧的
        
        Returns:
            int: 清理的快照数量
        """
        current_time = time.time()
        cutoff_time = current_time - (self.retention_hours * 3600)
        
        cleaned = 0
        
        # 按时间清理
        for snapshot_id, snapshot in list(self._snapshot_index.items()):
            if snapshot.timestamp < cutoff_time:
                self._delete_snapshot(snapshot_id)
                cleaned += 1
        
        # 按大小清理
        while self._get_total_size_mb() > self.max_total_size_mb:
            oldest = self._find_oldest_snapshot()
            if not oldest:
                break
            self._delete_snapshot(oldest)
            cleaned += 1
        
        if cleaned > 0:
            self._stats["cleanups_performed"] += 1
            self._stats["snapshots_cleaned"] += cleaned
        
        return cleaned
    
    def _delete_snapshot(self, snapshot_id: str) -> None:
        """删除快照"""
        filepath = os.path.join(self.backup_dir, f"{snapshot_id}.json")
        
        if os.path.exists(filepath):
            os.remove(filepath)
        
        if snapshot_id in self._snapshot_index:
            snapshot = self._snapshot_index[snapshot_id]
            
            # 从会话列表移除
            session_id = snapshot.session_id
            if session_id in self._session_snapshots:
                try:
                    self._session_snapshots[session_id].remove(snapshot_id)
                except ValueError:
                    pass
            
            del self._snapshot_index[snapshot_id]
    
    def _find_oldest_snapshot(self) -> Optional[str]:
        """找到最旧的快照ID"""
        if not self._snapshot_index:
            return None
        
        oldest = min(
            self._snapshot_index.items(),
            key=lambda x: x[1].timestamp
        )
        
        return oldest[0]
    
    def _get_total_size_mb(self) -> float:
        """获取当前备份总大小(MB)"""
        total_size = 0
        
        for filename in os.listdir(self.backup_dir):
            filepath = os.path.join(self.backup_dir, filename)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
        
        return total_size / (1024 * 1024)
    
    def _update_total_size(self) -> None:
        """更新总大小统计"""
        self._stats["total_backup_size_bytes"] = self._get_total_size_mb() * 1024 * 1024
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        stats["total_size_mb"] = self._get_total_size_mb()
        stats["snapshot_count"] = len(self._snapshot_index)
        stats["session_count"] = len(self._session_snapshots)
        return stats


# ========== ImportanceAwareCompressor ==========

class ImportanceAwareCompressor:
    """
    重要性感知压缩器
    
    在压缩时根据信息重要性区分处理:
    - CRITICAL: 必须保留
    - HIGH: 优先保留
    - MEDIUM: 适度压缩
    - LOW: 可丢弃
    
    权重配置:
    - decision_point: 1.0 (关键决策)
    - user_preference: 0.9 (用户偏好)
    - tool_result: 0.7 (工具结果)
    - general: 0.5 (一般信息)
    """
    
    IMPORTANCE_WEIGHTS = {
        "decision_point": 1.0,
        "user_preference": 0.9,
        "tool_result": 0.7,
        "context_setup": 0.6,
        "general": 0.5,
        "temporary": 0.3
    }
    
    def __init__(
        self,
        target_ratio: float = 0.2,
        min_critical_preservation: float = 0.95,
        backup_manager: Optional[MemoryBackupManager] = None
    ):
        self.target_ratio = target_ratio
        self.min_critical_preservation = min_critical_preservation
        self.backup_manager = backup_manager
        
        # 统计
        self._stats = {
            "compressions_performed": 0,
            "items_preserved": 0,
            "items_dropped": 0,
            "bytes_saved": 0,
            "critical_preserved_count": 0,
            "critical_total_count": 0
        }
    
    def calculate_importance(
        self,
        item: Any,
        item_type: Optional[str] = None
    ) -> float:
        """
        计算单条记忆的重要性评分
        
        评分维度:
        - 类型权重 (decision_point > user_preference > tool_result > general)
        - 时间衰减 (越新越重要)
        - 访问频率 (高频更重要)
        - 用户显式标记
        
        Returns:
            float: 重要性评分 0.0-1.0
        """
        base_score = 0.5
        
        # 类型权重
        if item_type:
            base_score = self.IMPORTANCE_WEIGHTS.get(item_type, 0.5)
        
        # 对象属性检查
        if hasattr(item, "importance_score"):
            # 已有评分，按比例调整
            return max(0.0, min(1.0, item.importance_score * base_score * 1.5))
        
        if hasattr(item, "item_type"):
            type_weight = self.IMPORTANCE_WEIGHTS.get(item.item_type, 0.5)
            base_score = max(base_score, type_weight)
        
        # 时间衰减 (最近30分钟内为1.0，之后每小时-0.1)
        if hasattr(item, "timestamp"):
            age_hours = (time.time() - item.timestamp) / 3600
            time_factor = max(0.3, 1.0 - age_hours * 0.1)
            base_score *= (0.5 + 0.5 * time_factor)
        
        # 访问频率加成
        if hasattr(item, "access_count"):
            access_boost = min(0.2, item.access_count * 0.02)
            base_score += access_boost
        
        return max(0.0, min(1.0, base_score))
    
    def compress_with_importance(
        self,
        memory_items: List[Any],
        target_ratio: Optional[float] = None,
        item_key_extractor: Optional[Callable] = None,
        item_type_extractor: Optional[Callable] = None
    ) -> Tuple[List[Any], List[Any]]:
        """
        根据重要性压缩记忆列表
        
        Args:
            memory_items: 待压缩的记忆条目列表
            target_ratio: 目标保留比例 (默认0.2)
            item_key_extractor: 从item提取key的函数
            item_type_extractor: 从item提取类型的函数
            
        Returns:
            Tuple[List[Any], List[Any]]: (保留的条目, 丢弃的条目)
        """
        target = target_ratio or self.target_ratio
        self._stats["compressions_performed"] += 1
        
        # 计算每个条目的重要性
        scored_items = []
        
        for item in memory_items:
            # 提取类型
            item_type = None
            if item_type_extractor:
                try:
                    item_type = item_type_extractor(item)
                except Exception:
                    pass
            elif hasattr(item, "item_type"):
                item_type = item.item_type
            
            # 计算重要性
            importance = self.calculate_importance(item, item_type)
            
            # 提取key
            key = None
            if item_key_extractor:
                try:
                    key = item_key_extractor(item)
                except Exception:
                    pass
            elif hasattr(item, "key"):
                key = item.key
            elif isinstance(item, dict):
                key = item.get("key", str(id(item)))
            else:
                key = str(id(item))
            
            scored_items.append((item, importance, key))
        
        # 按重要性排序
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        # 确定保留数量
        preserve_count = max(
            1,  # 至少保留1个
            int(len(memory_items) * target)
        )
        
        # 确保CRITICAL级别的全部保留
        critical_items = [
            (item, importance, key) 
            for item, importance, key in scored_items 
            if importance >= 1.0
        ]
        
        # 调整保留数量，确保关键项
        if critical_items:
            preserve_count = max(
                preserve_count,
                len(critical_items)
            )
        
        self._stats["critical_total_count"] += len(critical_items)
        self._stats["critical_preserved_count"] += len(critical_items)
        
        # 分割
        preserved = [item for item, _, _ in scored_items[:preserve_count]]
        dropped = [item for item, _, _ in scored_items[preserve_count:]]
        
        # 更新统计
        self._stats["items_preserved"] += len(preserved)
        self._stats["items_dropped"] += len(dropped)
        
        # 计算字节节省
        preserved_size = sum(len(str(p)) for p in preserved)
        dropped_size = sum(len(str(d)) for d in dropped)
        self._stats["bytes_saved"] += dropped_size
        
        return preserved, dropped
    
    def compress_with_backup(
        self,
        session_id: str,
        memory_items: List[Any],
        memory_state: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Any], Optional[BackupSnapshot]]:
        """
        带备份的压缩
        
        在压缩前创建备份，确保可回滚。
        
        Args:
            session_id: 会话ID
            memory_items: 待压缩的记忆条目
            memory_state: 完整记忆状态 (用于备份)
            
        Returns:
            Tuple[List[Any], BackupSnapshot]: (压缩结果, 备份快照)
        """
        snapshot = None
        
        # 创建备份
        if self.backup_manager:
            state_to_backup = memory_state
            if state_to_backup is None:
                # 从items构建状态
                state_to_backup = {
                    str(id(item)): item 
                    for item in memory_items
                }
            
            # 提取关键键
            critical_keys = [
                str(id(item)) for item in memory_items
                if self.calculate_importance(item) >= 1.0
            ]
            
            snapshot = self.backup_manager.backup_before_compress(
                session_id=session_id,
                memory_state=state_to_backup,
                critical_keys=critical_keys,
                metadata={"item_count": len(memory_items)}
            )
        
        # 执行压缩
        preserved, dropped = self.compress_with_importance(memory_items)
        
        return preserved, snapshot
    
    def get_importance_distribution(
        self,
        memory_items: List[Any]
    ) -> Dict[str, int]:
        """
        获取记忆条目重要性分布
        
        Returns:
            Dict[str, int]: 各级别的数量 {CRITICAL: n, HIGH: n, ...}
        """
        distribution = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "MINIMAL": 0
        }
        
        for item in memory_items:
            importance = self.calculate_importance(item)
            
            if importance >= 1.0:
                distribution["CRITICAL"] += 1
            elif importance >= 0.9:
                distribution["HIGH"] += 1
            elif importance >= 0.7:
                distribution["MEDIUM"] += 1
            elif importance >= 0.5:
                distribution["LOW"] += 1
            else:
                distribution["MINIMAL"] += 1
        
        return distribution
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        
        total = stats["items_preserved"] + stats["items_dropped"]
        if total > 0:
            stats["preservation_rate"] = stats["items_preserved"] / total
        
        if stats["critical_total_count"] > 0:
            stats["critical_preservation_rate"] = (
                stats["critical_preserved_count"] / stats["critical_total_count"]
            )
        
        return stats


# ========== 模块导出 ==========

__all__ = [
    "verify_rag_source",
    "MemoryBackupManager",
    "ImportanceAwareCompressor",
    "BackupSnapshot",
    "RestorationResult",
    "RAGVerificationResult",
    "CompressedItem",
    "VerificationStatus",
    "ImportanceLevel",
]
