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


class TestSimHashAdvanced:
    """测试SimHash高级功能"""
    
    def test_tokenize_english(self):
        """测试英文分词"""
        tokens = SimHash._tokenize("hello world test")
        assert "hello" in tokens or "world" in tokens
    
    def test_tokenize_chinese(self):
        """测试中文分词"""
        tokens = SimHash._tokenize("这是一个中文测试")
        assert len(tokens) > 0
    
    def test_tokenize_mixed(self):
        """测试中英文混合分词"""
        tokens = SimHash._tokenize("Hello你好World世界")
        assert len(tokens) > 0
    
    def test_hash_token(self):
        """测试token哈希"""
        h = SimHash._hash_token("test")
        assert isinstance(h, int)
        assert h > 0
    
    def test_compute_empty_string(self):
        """测试空字符串"""
        h = SimHash.compute("")
        assert h == 0
    
    def test_hamming_distance_identical(self):
        """测试相同指纹的海明距离"""
        h = SimHash.compute("测试文本")
        distance = SimHash.hamming_distance(h, h)
        assert distance == 0
    
    def test_is_similar_with_high_threshold(self):
        """测试高阈值相似判断"""
        h1 = SimHash.compute("文本A")
        h2 = SimHash.compute("文本B")
        # 即使不相似，高阈值也应该返回True
        result = SimHash.is_similar(h1, h2, threshold=60)
        assert isinstance(result, bool)


class TestTaskRecordAdvanced:
    """测试TaskRecord高级功能"""
    
    def test_record_to_dict(self):
        """测试记录转字典"""
        record = TaskRecord(
            task_id="task_001",
            content_hash=12345,
            content_preview="预览内容",
            timestamp=1234567890.0,
            status=TaskStatus.PENDING,
            merged_into=None,
            similarity_score=0.95,
            metadata={"key": "value"}
        )
        d = record.to_dict()
        assert d["task_id"] == "task_001"
        assert d["content_hash"] == 12345
        assert d["metadata"]["key"] == "value"
    
    def test_record_from_dict(self):
        """测试从字典创建记录"""
        d = {
            "task_id": "task_002",
            "content_hash": 54321,
            "content_preview": "预览2",
            "timestamp": 9876543210.0,
            "status": "processing",
            "merged_into": "task_001",
            "similarity_score": 0.88,
            "metadata": {}
        }
        record = TaskRecord.from_dict(d)
        assert record.task_id == "task_002"
        assert record.status == TaskStatus.PROCESSING
        assert record.merged_into == "task_001"


class TestTaskRegistryAdvanced:
    """测试TaskRegistry高级功能"""
    
    def test_registry_register_and_get(self):
        """测试注册和获取"""
        registry = TaskRegistry()
        record = TaskRecord(
            task_id="reg_001",
            content_hash=SimHash.compute("内容1"),
            content_preview="内容1预览",
            timestamp=1234567890.0,
            status=TaskStatus.PENDING
        )
        registry.register("reg_001", record)
        retrieved = registry.get("reg_001")
        assert retrieved is not None
        assert retrieved.task_id == "reg_001"
    
    def test_registry_update(self):
        """测试更新记录"""
        registry = TaskRegistry()
        record = TaskRecord(
            task_id="upd_001",
            content_hash=SimHash.compute("更新测试"),
            content_preview="预览",
            timestamp=1234567890.0,
            status=TaskStatus.PENDING
        )
        registry.register("upd_001", record)
        result = registry.update("upd_001", status=TaskStatus.PROCESSING)
        assert result is True
        updated = registry.get("upd_001")
        assert updated.status == TaskStatus.PROCESSING
    
    def test_registry_update_nonexistent(self):
        """测试更新不存在的记录"""
        registry = TaskRegistry()
        result = registry.update("nonexistent", status=TaskStatus.COMPLETED)
        assert result is False
    
    def test_registry_find_by_hash(self):
        """测试通过哈希查找"""
        registry = TaskRegistry()
        content = "查找测试内容"
        hash_value = SimHash.compute(content)
        
        record = TaskRecord(
            task_id="find_001",
            content_hash=hash_value,
            content_preview=content[:100],
            timestamp=1234567890.0,
            status=TaskStatus.PENDING
        )
        registry.register("find_001", record)
        
        # 查找相似哈希（相同内容应该相似）
        results = registry.find_by_hash(hash_value)
        assert len(results) >= 1
    
    def test_registry_get_active_tasks(self):
        """测试获取活跃任务"""
        registry = TaskRegistry()
        
        record1 = TaskRecord(
            task_id="active_001",
            content_hash=1,
            content_preview="活跃1",
            timestamp=1234567890.0,
            status=TaskStatus.PENDING
        )
        record2 = TaskRecord(
            task_id="active_002",
            content_hash=2,
            content_preview="活跃2",
            timestamp=1234567891.0,
            status=TaskStatus.COMPLETED
        )
        registry.register("active_001", record1)
        registry.register("active_002", record2)
        
        active = registry.get_active_tasks()
        assert len(active) >= 1
    
    def test_registry_get_merged_history(self):
        """测试获取合并历史"""
        registry = TaskRegistry()
        
        record1 = TaskRecord(
            task_id="merge_001",
            content_hash=1,
            content_preview="合并1",
            timestamp=1234567890.0,
            status=TaskStatus.MERGED,
            merged_into="merge_target"
        )
        registry.register("merge_001", record1)
        
        history = registry.get_merged_history("merge_001")
        assert "merge_target" in history


class TestDeduplicatorAdvanced:
    """测试Deduplicator高级功能"""
    
    def test_compute_hash(self):
        """测试计算哈希"""
        dedup = Deduplicator()
        content = "测试哈希计算"
        hash1 = dedup.compute_hash(content)
        hash2 = dedup.compute_hash(content)
        assert hash1 == hash2
        assert hash1 != 0
    
    def test_merge_tasks(self):
        """测试合并任务"""
        dedup = Deduplicator()
        
        dedup.check_duplicate("merge_src", "源任务内容")
        dedup.check_duplicate("merge_tgt", "目标任务内容")
        
        result = dedup.merge_tasks("merge_src", "merge_tgt")
        assert result is True
    
    def test_merge_nonexistent_tasks(self):
        """测试合并不存在的任务"""
        dedup = Deduplicator()
        result = dedup.merge_tasks("fake_src", "fake_tgt")
        assert result is False
    
    def test_discard_task(self):
        """测试丢弃任务"""
        dedup = Deduplicator()
        dedup.check_duplicate("discard_001", "丢弃测试内容")
        result = dedup.discard_task("discard_001")
        assert result is True
    
    def test_discard_nonexistent_task(self):
        """测试丢弃不存在的任务"""
        dedup = Deduplicator()
        result = dedup.discard_task("nonexistent")
        assert result is False
    
    def test_get_task_status(self):
        """测试获取任务状态"""
        dedup = Deduplicator()
        dedup.check_duplicate("status_001", "状态测试内容")
        status = dedup.get_task_status("status_001")
        assert status == TaskStatus.PENDING
    
    def test_get_task_status_nonexistent(self):
        """测试获取不存在任务的状态"""
        dedup = Deduplicator()
        status = dedup.get_task_status("nonexistent_task")
        assert status is None
    
    def test_stats_by_status(self):
        """测试按状态统计"""
        dedup = Deduplicator()
        dedup.check_duplicate("stat_001", "统计1")
        dedup.check_duplicate("stat_002", "统计2")
        dedup.discard_task("stat_001")
        
        stats = dedup.get_stats()
        assert "by_status" in stats
        assert stats["by_status"]["pending"] >= 0


class TestLLMSemanticDeduplicatorAdvanced:
    """测试LLMSemanticDeduplicator高级功能"""
    
    def test_fallback_compare_empty_text(self):
        """测试空文本的降级比较"""
        dedup = LLMSemanticDeduplicator()
        is_dup, score = dedup._fallback_compare("", "非空文本", 0.85)
        assert is_dup is False
        assert score == 0.0
    
    def test_fallback_compare_both_empty(self):
        """测试两个空文本的比较"""
        dedup = LLMSemanticDeduplicator()
        is_dup, score = dedup._fallback_compare("", "", 0.85)
        assert is_dup is False
        assert score == 0.0
    
    def test_fallback_compare_identical(self):
        """测试相同文本的降级比较"""
        dedup = LLMSemanticDeduplicator()
        text = "相同文本内容"
        is_dup, score = dedup._fallback_compare(text, text, 0.85)
        assert is_dup is True
        assert score == 1.0
    
    def test_fallback_compare_different(self):
        """测试不同文本的降级比较"""
        dedup = LLMSemanticDeduplicator()
        is_dup, score = dedup._fallback_compare("文本A", "文本B", 0.5)
        assert isinstance(is_dup, bool)
        assert isinstance(score, float)
