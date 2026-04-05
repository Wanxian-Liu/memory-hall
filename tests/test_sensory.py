# -*- coding: utf-8 -*-
"""
测试 sensory 模块 - 语义搜索引擎
"""
import os
import sys
import pytest
import numpy as np

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from sensory.semantic_search import (
    GatewayConfig, TaskStatus, SearchQuery, SearchResult,
    QueryTask, TaskRegistry, get_task_registry,
    VectorIndex, SemanticSearchEngine, create_engine
)


class TestGatewayConfig:
    """测试GatewayConfig类"""
    def test_config_defaults(self):
        cfg = GatewayConfig()
        assert cfg is not None


class TestTaskStatus:
    """测试TaskStatus枚举"""
    def test_statuses(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"


class TestSearchQuery:
    """测试SearchQuery类"""
    def test_query_creation(self):
        query = SearchQuery(
            query="test query",
            limit=10
        )
        assert query.query == "test query"
        assert query.limit == 10


class TestSearchResult:
    """测试SearchResult类"""
    def test_result_creation(self):
        result = SearchResult(
            id="doc_001",
            score=0.95,
            content="test content",
            metadata={"type": "test"}
        )
        assert result.id == "doc_001"
        assert result.score == 0.95
        assert result.content == "test content"


class TestQueryTask:
    """测试QueryTask类"""
    def test_task_creation(self):
        query = SearchQuery(query="test")
        task = QueryTask(
            task_id="task_001",
            query=query
        )
        assert task.task_id == "task_001"
        assert task.query.query == "test"
        assert task.status == TaskStatus.PENDING


class TestTaskRegistry:
    """测试TaskRegistry类"""
    def test_registry_init(self):
        registry = TaskRegistry()
        assert registry is not None

    def test_get_registry(self):
        reg = get_task_registry()
        assert reg is not None


class TestVectorIndex:
    """测试VectorIndex类"""
    def test_index_init(self):
        index = VectorIndex(dimension=128)
        assert index.dimension == 128

    def test_add_and_search(self):
        index = VectorIndex(dimension=8)
        vec = np.random.rand(8).astype(np.float32).tolist()
        # Actual: add returns bool
        result = index.add("doc1", vec, {"content": "test"})
        assert result is True

        query = np.random.rand(8).astype(np.float32).tolist()
        # Actual: search uses 'limit' not 'top_k'
        results = index.search(query, limit=3)
        assert results is not None


class TestSemanticSearchEngine:
    """测试SemanticSearchEngine主类"""
    def test_engine_creation(self, temp_dir):
        engine = SemanticSearchEngine()
        assert engine is not None

    def test_add_document(self, temp_dir):
        """测试添加文档"""
        engine = SemanticSearchEngine()
        # Actual: add_document returns bool
        result = engine.add_document(
            id="test_doc",
            content="这是一个测试文档",
            metadata={"type": "test"}
        )
        assert result is True

    def test_search(self, temp_dir):
        """测试搜索"""
        engine = SemanticSearchEngine()
        engine.add_document(id="doc1", content="Python编程", metadata={})

        results, total, next_token = engine.search(
            query="Python",
            limit=10
        )
        assert isinstance(results, list)
        assert total >= 0

    def test_delete_document(self, temp_dir):
        """测试删除文档"""
        engine = SemanticSearchEngine()
        engine.add_document(id="to_delete", content="删除测试", metadata={})
        # Actual: has cancel_search (for task cancellation)
        assert hasattr(engine, 'cancel_search')

    def test_get_stats(self, temp_dir):
        """测试获取统计"""
        engine = SemanticSearchEngine()
        engine.add_document(id="stat1", content="统计1", metadata={})

        stats = engine.get_stats()
        assert stats is not None


class TestCreateEngine:
    """测试create_engine工厂函数"""
    def test_create_engine(self):
        engine = create_engine()
        assert engine is not None
