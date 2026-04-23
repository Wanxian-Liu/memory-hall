"""
记忆殿堂归一模块 V2.5
去重引擎：SimHash指纹 + LLM语义去重 + 任务注册追踪
"""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# ======================
# SimHash 实现
# ======================

class SimHash:
    """SimHash 指纹算法 - 用于快速近似重复检测"""

    FINGERPRINT_BITS = 64

    @classmethod
    def _tokenize(cls, text: str) -> list[str]:
        """中英文混合分词"""
        # 清理标点
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        text = re.sub(r'\s+', ' ', text.strip())
        # 简单分词：按空格 + 保留中文连续段
        tokens = []
        for chunk in text.split():
            # 保留中文词/英文词
            if re.search(r'[\u4e00-\u9fff]', chunk):
                # 中文按字符分词（简化版）
                tokens.extend(list(chunk))
            else:
                tokens.append(chunk.lower())
        return tokens

    @classmethod
    def _hash_token(cls, token: str) -> int:
        """单token生成64位哈希"""
        h = hashlib.md5(token.encode('utf-8')).digest()
        return int.from_bytes(h[:8], byteorder='big', signed=False)

    @classmethod
    def compute(cls, text: str) -> int:
        """
        计算文本的SimHash指纹
        返回64位整数
        """
        tokens = cls._tokenize(text)
        if not tokens:
            return 0

        v = [0] * cls.FINGERPRINT_BITS

        for token in tokens:
            h = cls._hash_token(token)
            for i in range(cls.FINGERPRINT_BITS):
                bit = (h >> i) & 1
                v[i] += 1 if bit else -1

        fingerprint = 0
        for i in range(cls.FINGERPRINT_BITS):
            if v[i] > 0:
                fingerprint |= (1 << i)

        return fingerprint

    @classmethod
    def hamming_distance(cls, fp1: int, fp2: int) -> int:
        """计算两个指纹的海明距离"""
        xor = fp1 ^ fp2
        return bin(xor).count('1')

    @classmethod
    def is_similar(cls, fp1: int, fp2: int, threshold: int = 3) -> bool:
        """
        判断两个指纹是否相似
        threshold: 海明距离阈值，默认3表示允许3位差异
        """
        return cls.hamming_distance(fp1, fp2) <= threshold


# ======================
# 任务状态枚举
# ======================

class TaskStatus(Enum):
    PENDING = "pending"       # 待处理
    PROCESSING = "processing" # 处理中
    MERGED = "merged"         # 已合并
    DUPLICATE = "duplicate"   # 判定为重复
    DISCARDED = "discarded"   # 已丢弃
    COMPLETED = "completed"   # 完成


# ======================
# 数据结构
# ======================

@dataclass
class TaskRecord:
    """任务记录"""
    task_id: str
    content_hash: int          # SimHash指纹
    content_preview: str       # 内容预览（前100字符）
    timestamp: float
    status: TaskStatus
    merged_into: str | None = None  # 被合并到哪个任务
    similarity_score: float | None = None  # 相似度得分
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "content_hash": self.content_hash,
            "content_preview": self.content_preview,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "merged_into": self.merged_into,
            "similarity_score": self.similarity_score,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TaskRecord":
        return cls(
            task_id=d["task_id"],
            content_hash=d["content_hash"],
            content_preview=d["content_preview"],
            timestamp=d["timestamp"],
            status=TaskStatus(d["status"]),
            merged_into=d.get("merged_into"),
            similarity_score=d.get("similarity_score"),
            metadata=d.get("metadata", {})
        )


# ======================
# LLM语义去重器（接口）
# ======================

class LLMSemanticDeduplicator:
    """
    LLM语义去重接口
    实际调用需要外部LLM服务
    """

    def __init__(self, llm_client=None):
        """
        llm_client: LLM客户端实例（可选）
        如不提供，使用模拟模式
        """
        self.llm_client = llm_client

    async def are_semantically_duplicate(
        self,
        text1: str,
        text2: str,
        threshold: float = 0.85
    ) -> tuple[bool, float]:
        """
        判断两段文本是否语义重复
        返回: (是否重复, 相似度得分)
        """
        if self.llm_client:
            return await self._llm_compare(text1, text2, threshold)
        else:
            # 降级：基于SimHash判断
            return self._fallback_compare(text1, text2, threshold)

    async def _llm_compare(
        self,
        text1: str,
        text2: str,
        threshold: float
    ) -> tuple[bool, float]:
        """使用LLM进行语义比较"""
        prompt = f"""判断以下两段文本是否表达相同或相似的语义（核心意图相同）。

文本1: {text1[:500]}

文本2: {text2[:500]}

请返回一个JSON格式的判断：
{{"similarity": 0.0-1.0的分数, "is_duplicate": true/false}}
"""

        try:
            response = await self.llm_client.chat_completion(prompt)
            result = json.loads(response)
            return (
                result.get("is_duplicate", False),
                result.get("similarity", 0.0)
            )
        except Exception:
            return self._fallback_compare(text1, text2, threshold)

    def _fallback_compare(
        self,
        text1: str,
        text2: str,
        threshold: float
    ) -> tuple[bool, float]:
        """降级：基于字符级相似度"""
        if not text1 or not text2:
            return False, 0.0

        # Jaccard相似度
        set1 = set(text1)
        set2 = set(text2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)

        score = intersection / union if union > 0 else 0.0
        return score >= threshold, score


# ======================
# 任务注册追踪器
# ======================

class TaskRegistry:
    """
    任务注册追踪器
    记录所有任务的状态和合并历史
    """

    def __init__(self, storage_path: str | None = None):
        """
        storage_path: 持久化存储路径
        """
        self.storage_path = storage_path
        self.records: dict[str, TaskRecord] = {}
        self._load()

    def _load(self):
        """从磁盘加载"""
        if self.storage_path and os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.records = {
                        k: TaskRecord.from_dict(v)
                        for k, v in data.items()
                    }
            except Exception:
                self.records = {}

    def _save(self):
        """保存到磁盘"""
        if self.storage_path:
            Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(
                    {k: v.to_dict() for k, v in self.records.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )

    def register(self, task_id: str, record: TaskRecord) -> None:
        """注册新任务"""
        self.records[task_id] = record
        self._save()

    def get(self, task_id: str) -> TaskRecord | None:
        """获取任务记录"""
        return self.records.get(task_id)

    def update(self, task_id: str, **kwargs) -> bool:
        """更新任务字段"""
        if task_id not in self.records:
            return False
        record = self.records[task_id]
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        self._save()
        return True

    def find_by_hash(self, content_hash: int) -> list[TaskRecord]:
        """通过SimHash查找相似任务"""
        return [
            r for r in self.records.values()
            if SimHash.is_similar(r.content_hash, content_hash)
        ]

    def get_active_tasks(self) -> list[TaskRecord]:
        """获取活跃任务（未完成/未丢弃）"""
        return [
            r for r in self.records.values()
            if r.status in (TaskStatus.PENDING, TaskStatus.PROCESSING)
        ]

    def get_merged_history(self, task_id: str) -> list[str]:
        """获取合并历史"""
        history = []
        current = task_id
        visited = set()

        while current and current not in visited:
            visited.add(current)
            record = self.records.get(current)
            if not record:
                break
            if record.merged_into:
                history.append(record.merged_into)
                current = record.merged_into
            else:
                break

        return history


# ======================
# 归一化去重主引擎
# ======================

class Deduplicator:
    """
    记忆殿堂归一化去重引擎 V2.5
    三层去重：SimHash快速筛选 → LLM语义确认 → 任务注册追踪
    """

    def __init__(
        self,
        storage_dir: str | None = None,
        simhash_threshold: int = 3,
        semantic_threshold: float = 0.85,
        llm_client=None
    ):
        """
        storage_dir: 存储目录
        simhash_threshold: SimHash海明距离阈值（越小越严格）
        semantic_threshold: 语义相似度阈值
        llm_client: LLM客户端（可选）
        """
        self.storage_dir = storage_dir
        self.simhash_threshold = simhash_threshold
        self.semantic_threshold = semantic_threshold

        # 初始化组件
        registry_path = None
        if storage_dir:
            registry_path = os.path.join(storage_dir, "task_registry.json")
        self.registry = TaskRegistry(registry_path)
        self.llm_dedup = LLMSemanticDeduplicator(llm_client)

    def compute_hash(self, content: str) -> int:
        """计算内容的SimHash指纹"""
        return SimHash.compute(content)

    def check_duplicate(self, task_id: str, content: str) -> dict:
        """
        检查内容是否重复
        返回检查结果字典
        """
        content_hash = self.compute_hash(content)
        preview = content[:100]

        # 记录任务
        record = TaskRecord(
            task_id=task_id,
            content_hash=content_hash,
            content_preview=preview,
            timestamp=time.time(),
            status=TaskStatus.PENDING
        )

        # 查找相似任务
        candidates = self.registry.find_by_hash(content_hash)

        if not candidates:
            # 无相似任务，注册并标记为新任务
            self.registry.register(task_id, record)
            return {
                "is_duplicate": False,
                "is_new": True,
                "task_id": task_id,
                "merged_into": None,
                "similarity_score": None,
                "candidates": []
            }

        # 记录结果
        self.registry.register(task_id, record)

        return {
            "is_duplicate": False,
            "is_new": False,
            "task_id": task_id,
            "merged_into": None,
            "similarity_score": None,
            "candidates": [
                {"task_id": c.task_id, "preview": c.content_preview}
                for c in candidates
            ]
        }

    async def check_duplicate_with_llm(
        self,
        task_id: str,
        content: str
    ) -> dict:
        """
        使用LLM进行深度语义去重
        先用SimHash快速筛选，再用LLM确认
        """
        content_hash = self.compute_hash(content)
        preview = content[:100]

        # SimHash快速筛选
        candidates = self.registry.find_by_hash(content_hash)

        if not candidates:
            record = TaskRecord(
                task_id=task_id,
                content_hash=content_hash,
                content_preview=preview,
                timestamp=time.time(),
                status=TaskStatus.PENDING
            )
            self.registry.register(task_id, record)
            return {
                "is_duplicate": False,
                "is_new": True,
                "task_id": task_id,
                "merged_into": None,
                "similarity_score": 1.0,
                "candidates": []
            }

        # LLM语义确认
        best_match = None
        best_score = 0.0

        for candidate in candidates:
            is_dup, score = await self.llm_dedup.are_semantically_duplicate(
                content,
                candidate.content_preview,
                self.semantic_threshold
            )
            if is_dup and score > best_score:
                best_match = candidate
                best_score = score

        record = TaskRecord(
            task_id=task_id,
            content_hash=content_hash,
            content_preview=preview,
            timestamp=time.time(),
            status=TaskStatus.PENDING,
            similarity_score=best_score if best_match else None
        )

        if best_match:
            record.status = TaskStatus.DUPLICATE
            record.merged_into = best_match.task_id
            self.registry.update(task_id, status=TaskStatus.DUPLICATE,
                               merged_into=best_match.task_id,
                               similarity_score=best_score)
            return {
                "is_duplicate": True,
                "is_new": False,
                "task_id": task_id,
                "merged_into": best_match.task_id,
                "similarity_score": best_score,
                "candidates": []
            }
        else:
            self.registry.register(task_id, record)
            return {
                "is_duplicate": False,
                "is_new": True,
                "task_id": task_id,
                "merged_into": None,
                "similarity_score": None,
                "candidates": [
                    {"task_id": c.task_id, "preview": c.content_preview}
                    for c in candidates
                ]
            }

    def merge_tasks(self, source_id: str, target_id: str) -> bool:
        """
        将source任务合并到target
        """
        if source_id not in self.registry.records:
            return False
        if target_id not in self.registry.records:
            return False

        self.registry.update(
            source_id,
            status=TaskStatus.MERGED,
            merged_into=target_id
        )
        return True

    def discard_task(self, task_id: str) -> bool:
        """标记任务为丢弃"""
        return self.registry.update(task_id, status=TaskStatus.DISCARDED)

    def get_task_status(self, task_id: str) -> TaskStatus | None:
        """获取任务状态"""
        record = self.registry.get(task_id)
        return record.status if record else None

    def get_stats(self) -> dict:
        """获取统计信息"""
        records = list(self.registry.records.values())
        return {
            "total_tasks": len(records),
            "by_status": {
                s.value: sum(1 for r in records if r.status == s)
                for s in TaskStatus
            },
            "active_tasks": len(self.registry.get_active_tasks())
        }
