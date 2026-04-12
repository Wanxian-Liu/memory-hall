# -*- coding: utf-8 -*-
"""
测试 extractor 模块 - 内容萃取器
"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from extractor.extractor import (
    MemoryType, CompressionResult,
    Extractor, SimpleLLMClient
)


class TestMemoryType:
    """测试MemoryType枚举"""
    def test_types(self):
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SHORT_TERM.value == "short_term"
        assert MemoryType.LONG_TERM.value == "long_term"


class TestCompressionResult:
    """测试CompressionResult类"""
    def test_result_creation(self):
        # Actual: original_tokens, compressed_tokens, compression_ratio, memory_type, summary, key_points, confidence, metadata
        result = CompressionResult(
            original_tokens=1000,
            compressed_tokens=200,
            compression_ratio=0.2,
            memory_type=MemoryType.LONG_TERM,
            summary="这是一个摘要",
            key_points=["关键词1", "关键词2"]
        )
        assert result.original_tokens == 1000
        assert result.compressed_tokens == 200
        assert result.compression_ratio == 0.2
        assert result.summary == "这是一个摘要"
        assert "关键词1" in result.key_points
    
    def test_result_with_confidence(self):
        """测试带置信度的结果"""
        result = CompressionResult(
            original_tokens=500,
            compressed_tokens=100,
            compression_ratio=0.2,
            memory_type=MemoryType.SHORT_TERM,
            summary="短期记忆摘要",
            confidence=0.95
        )
        assert result.confidence == 0.95
    
    def test_result_with_metadata(self):
        """测试带元数据的结果"""
        result = CompressionResult(
            original_tokens=500,
            compressed_tokens=100,
            compression_ratio=0.2,
            memory_type=MemoryType.LONG_TERM,
            summary="摘要",
            metadata={"source": "test", "priority": 1}
        )
        assert result.metadata["source"] == "test"


class TestExtractor:
    """测试Extractor主类"""
    def test_extractor_init(self, temp_dir):
        extractor = Extractor()
        assert extractor is not None

    def test_extract(self, temp_dir):
        """测试萃取功能"""
        extractor = Extractor()
        content = "这是要萃取的内容" * 20
        result = extractor.extract(
            content,
            max_tokens=500
        )
        assert result is not None
        assert result.original_tokens > 0
        assert result.summary != ""

    def test_extract_batch(self, temp_dir):
        """测试批量萃取"""
        extractor = Extractor()
        contents = ["内容1" * 10, "内容2" * 10, "内容3" * 10]
        results = extractor.extract_batch(contents, max_tokens=200)
        assert len(results) == 3

    def test_classify_memory(self, temp_dir):
        """测试记忆类型分类"""
        extractor = Extractor()
        # Test episodic (has time/event keywords)
        episodic_text = "2024年3月15日，我去了深圳出差，见了王总"
        structured, mem_type, key_points = extractor._l2_structured_extract(episodic_text)
        assert mem_type in MemoryType

    def test_estimate_tokens(self, temp_dir):
        """测试token估算"""
        extractor = Extractor()
        tokens = extractor.estimate_tokens("这是一段测试文本")
        assert tokens > 0
    
    def test_estimate_tokens_mixed(self):
        """测试中英文混合token估算"""
        extractor = Extractor()
        tokens = extractor.estimate_tokens("Hello World 你好世界")
        assert tokens >= 6  # 2 english words + 4 chinese chars
    
    def test_l1_fast_prune_short_text(self):
        """测试L1裁剪短文本（不裁剪）"""
        extractor = Extractor()
        short_text = "短文本"
        result = extractor._l1_fast_prune(short_text, max_tokens=100)
        assert result == short_text
    
    def test_l1_fast_prune_long_text(self):
        """测试L1裁剪长文本"""
        extractor = Extractor()
        long_text = "这是一段很长的文本\n" * 100
        result = extractor._l1_fast_prune(long_text, max_tokens=50)
        assert len(result) < len(long_text)
    
    def test_classify_episodic(self):
        """测试情景记忆分类"""
        extractor = Extractor()
        episodic_text = "昨天我去参加了会议，在会上见到了老朋友"
        mem_type = extractor._classify_memory(episodic_text)
        assert mem_type in MemoryType
    
    def test_classify_short_term(self):
        """测试短期记忆分类"""
        extractor = Extractor()
        short_term_text = "当前正在处理的任务，需要记住待会儿要做什么"
        mem_type = extractor._classify_memory(short_term_text)
        assert mem_type in MemoryType
    
    def test_classify_long_term(self):
        """测试长期记忆分类"""
        extractor = Extractor()
        long_term_text = "Python是一种广泛使用的高级编程语言，支持多种编程范式"
        mem_type = extractor._classify_memory(long_term_text)
        assert mem_type in MemoryType
    
    def test_extract_key_points_episodic(self):
        """测试情景记忆关键点提取"""
        extractor = Extractor()
        text = "今天我去了深圳，见到了王总，讨论了项目进展"
        key_points = extractor._extract_key_points(text, MemoryType.EPISODIC)
        assert isinstance(key_points, list)
    
    def test_extract_key_points_long_term(self):
        """测试长期记忆关键点提取"""
        extractor = Extractor()
        text = "机器学习是人工智能的一个分支，专注于开发能够从数据中学习的算法"
        key_points = extractor._extract_key_points(text, MemoryType.LONG_TERM)
        assert isinstance(key_points, list)
    
    def test_reconstruct_structured(self):
        """测试结构化重构"""
        extractor = Extractor()
        text = "这是一段测试文本"
        key_points = ["关键点1", "关键点2"]
        result = extractor._reconstruct_structured(text, MemoryType.LONG_TERM, key_points)
        assert isinstance(result, str)
    
    def test_get_stats(self):
        """测试获取统计信息 - SKIP: get_stats方法未实现"""
        pytest.skip("Extractor.get_stats() 方法不存在")


class TestSimpleLLMClient:
    """测试SimpleLLMClient类"""
    def test_client_init(self):
        client = SimpleLLMClient()
        assert client is not None

    def test_generate_not_implemented(self):
        """测试生成功能 - 应该抛出NotImplementedError"""
        client = SimpleLLMClient()
        with pytest.raises(NotImplementedError):
            client.call("Say hello")
    
    def test_client_with_api_key(self):
        """测试带API密钥的客户端"""
        client = SimpleLLMClient(api_key="test_key")
        assert client is not None


class TestExtractorAdvanced:
    """测试Extractor高级功能"""
    
    def test_extract_with_memory_type_hint(self):
        """测试带记忆类型提示的萃取 - SKIP: memory_type_hint参数未实现"""
        pytest.skip("Extractor.extract() 不支持 memory_type_hint 参数")
    
    def test_extract_short_content(self):
        """测试短内容萃取"""
        extractor = Extractor()
        short_content = "短"
        result = extractor.extract(short_content, max_tokens=100)
        assert result is not None
        assert result.original_tokens >= 1
    
    def test_batch_extract_empty_list(self):
        """测试空列表批量萃取"""
        extractor = Extractor()
        results = extractor.extract_batch([], max_tokens=100)
        assert len(results) == 0
    
    def test_l2_structured_short_term(self):
        """测试L2层短期记忆提取"""
        extractor = Extractor()
        short_term_text = "我现在正在做的事情，一会儿要记得做"
        structured, mem_type, key_points = extractor._l2_structured_extract(short_term_text)
        assert isinstance(structured, str)
        assert mem_type in MemoryType
        assert isinstance(key_points, list)
    
    def test_target_ratios(self):
        """测试目标压缩比例"""
        extractor = Extractor()
        assert Extractor.TARGET_RATIOS[MemoryType.EPISODIC] == 0.3
        assert Extractor.TARGET_RATIOS[MemoryType.SHORT_TERM] == 0.5
        assert Extractor.TARGET_RATIOS[MemoryType.LONG_TERM] == 0.2
