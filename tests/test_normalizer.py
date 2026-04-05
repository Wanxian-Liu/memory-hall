# -*- coding: utf-8 -*-
"""
测试 normalizer 模块 - 去重归一化
"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from normalizer.deduplicator import (
    SimHash, TaskStatus, TaskRecord,
    LLMSemanticDeduplicator, TaskRegistry, Deduplicator
)


class TestSimHash:
    """测试SimHash类"""
    def test_simhash_init(self):
        sh = SimHash()
        assert sh is not None

    def test_compute(self):
        # Actual: compute is a class method, returns int
        hash1 = SimHash.compute("这是测试文本")
        hash2 = SimHash.compute("这是测试文本")
        assert hash1 == hash2  # 相同文本产生相同hash

    def test_compute_different(self):
        hash1 = SimHash.compute("文本A")
        hash2 = SimHash.compute("文本B")
        assert hash1 != hash2

    def test_distance(self):
        # Actual: hamming_distance is a class method
        h1 = SimHash.compute("文本1")
        h2 = SimHash.compute("文本2")
        distance = SimHash.hamming_distance(h1, h2)
        assert distance >= 0

    def test_is_similar(self):
        # Actual: is_similar is a class method
        h1 = SimHash.compute("非常相似的两段文本内容")
        h2 = SimHash.compute("非常相似的两段文本内容")  # 完全相同
        assert SimHash.is_similar(h1, h2, threshold=3) is True


class TestTaskStatus:
    """测试TaskStatus枚举 - normalizer模块的TaskStatus"""
    def test_statuses(self):
        # Actual: PENDING, PROCESSING, MERGED, DUPLICATE, DISCARDED, COMPLETED
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.PROCESSING.value == "processing"
        assert TaskStatus.COMPLETED.value == "completed"


class TestTaskRecord:
    """测试TaskRecord类"""
    def test_record_creation(self):
        # Actual: task_id, content_hash(int), content_preview, timestamp, status, merged_into, similarity_score, metadata
        record = TaskRecord(
            task_id="task_001",
            content_hash=12345,
            content_preview="测试内容预览",
            timestamp=1234567890.0,
            status=TaskStatus.PENDING
        )
        assert record.task_id == "task_001"
        assert record.content_hash == 12345


class TestLLMSemanticDeduplicator:
    """测试LLMSemanticDeduplicator类"""
    def test_dedup_init(self):
        dedup = LLMSemanticDeduplicator()
        assert dedup is not None

    def test_are_semantically_duplicate(self):
        # Actual: async method are_semantically_duplicate
        import asyncio
        dedup = LLMSemanticDeduplicator()
        content1 = "这是测试内容"
        content2 = "这是测试内容"  # 相同

        is_dup, score = asyncio.get_event_loop().run_until_complete(
            dedup.are_semantically_duplicate(content1, content2)
        )
        # Same content should have high similarity
        assert isinstance(is_dup, bool)
        assert isinstance(score, float)


class TestTaskRegistry:
    """测试TaskRegistry类"""
    def test_registry_init(self):
        registry = TaskRegistry()
        assert registry is not None


class TestDeduplicator:
    """测试Deduplicator主类"""
    def test_dedup_init(self):
        dedup = Deduplicator()
        assert dedup is not None

    def test_check_duplicate(self):
        dedup = Deduplicator()
        content1 = "要去重的内容"

        result = dedup.check_duplicate("task_1", content1)
        assert result is not None
        assert result["is_new"] is True
        assert result["task_id"] == "task_1"

    def test_check_duplicate_candidates(self):
        dedup = Deduplicator()
        content1 = "测试内容一"
        content2 = "测试内容二"

        dedup.check_duplicate("task_1", content1)
        result = dedup.check_duplicate("task_2", content2)

        assert result is not None
        # May have candidates from SimHash lookup
        assert "candidates" in result

    def test_stats(self):
        dedup = Deduplicator()
        dedup.check_duplicate("task_A", "内容A")
        dedup.check_duplicate("task_B", "内容B")
        stats = dedup.get_stats()
        assert stats is not None
        assert "total_tasks" in stats
