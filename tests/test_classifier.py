# -*- coding: utf-8 -*-
"""
测试 classifier 模块 - 记忆分类器
"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from classifier.classifier import (
    TaskStatus, ClassificationResult, ClassificationTask,
    TaskRegistry, TaxonomyClassifier, KnowledgeTypeClassifier,
    AutoTagger, ClassificationEngine,
    get_engine, classify, classify_dual,
    register_task, get_task, get_stats
)


class TestTaskStatus:
    """测试TaskStatus枚举"""
    def test_statuses(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"


class TestClassificationResult:
    """测试ClassificationResult类"""
    def test_result_creation(self):
        # Actual: content, taxonomy_tags, knowledge_type, task_id
        result = ClassificationResult(
            content="测试内容",
            taxonomy_tags=["技术", "学习"],
            knowledge_type={"primary_type": "concept", "type_name": "概念", "confidence": 0.95}
        )
        assert result.content_hash is not None
        assert "技术" in result.taxonomy_tags


class TestClassificationTask:
    """测试ClassificationTask类"""
    def test_task_creation(self):
        task = ClassificationTask(
            task_id="task_001",
            content="待分类内容"
        )
        assert task.task_id == "task_001"
        assert task.content == "待分类内容"
        assert task.status == TaskStatus.PENDING


class TestTaskRegistry:
    """测试TaskRegistry类"""
    def test_registry_init(self):
        registry = TaskRegistry()
        assert registry is not None

    def test_register_and_get(self):
        """测试注册和获取任务"""
        registry = TaskRegistry()
        task = ClassificationTask(
            task_id="test_task_001",
            content="测试内容"
        )
        registry.register(task)
        assert task is not None

        retrieved = registry.get("test_task_001")
        assert retrieved is not None


class TestTaxonomyClassifier:
    """测试TaxonomyClassifier类"""
    def test_classifier_init(self):
        clf = TaxonomyClassifier()
        assert clf is not None

    def test_classify(self):
        clf = TaxonomyClassifier()
        result = clf.classify("工作项目会议内容")
        assert result is not None
        assert isinstance(result, list)


class TestKnowledgeTypeClassifier:
    """测试KnowledgeTypeClassifier类"""
    def test_classifier_init(self):
        clf = KnowledgeTypeClassifier()
        assert clf is not None

    def test_classify(self):
        clf = KnowledgeTypeClassifier()
        result = clf.classify("Python编程知识")
        assert result is not None
        assert "primary_type" in result


class TestAutoTagger:
    """测试AutoTagger类"""
    def test_tagger_init(self):
        tagger = AutoTagger()
        assert tagger is not None

    def test_tag(self):
        tagger = AutoTagger()
        # classify returns ClassificationResult, not list of tags
        result = tagger.classify("技术Python开发工作")
        assert result is not None
        assert hasattr(result, 'taxonomy_tags')


class TestClassificationEngine:
    """测试ClassificationEngine主类"""
    def test_engine_init(self):
        engine = ClassificationEngine()
        assert engine is not None

    def test_classify_dual(self):
        """测试双重分类"""
        engine = get_engine()
        result = engine.classify("Python机器学习技术内容")
        assert result is not None
        assert "result" in result

    def test_classify_single(self):
        """测试单一分类"""
        engine = get_engine()
        result = engine.classify("工作内容")
        assert result is not None


class TestGlobalFunctions:
    """测试全局函数"""
    def test_get_engine(self):
        engine = get_engine()
        assert engine is not None

    def test_classify_function(self):
        result = classify("测试分类内容")
        assert result is not None

    def test_classify_dual_function(self):
        result = classify_dual("技术Python开发")
        assert result is not None

    def test_register_task_function(self):
        task_id = register_task("待分类内容")
        assert task_id is not None

    def test_get_task_function(self):
        task_id = register_task("测试内容")
        task = get_task(task_id)
        assert task is not None

    def test_get_stats_function(self):
        stats = get_stats()
        assert stats is not None
