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
