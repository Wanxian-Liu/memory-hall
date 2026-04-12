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


class TestClassificationResultAdvanced:
    """测试ClassificationResult高级功能"""
    
    def test_result_to_dict(self):
        """测试结果转字典"""
        result = ClassificationResult(
            content="测试内容",
            taxonomy_tags=["技术", "学习"],
            knowledge_type={"primary_type": "concept", "type_name": "概念", "confidence": 0.95}
        )
        d = result.to_dict()
        assert "task_id" in d
        assert "content_hash" in d
        assert "taxonomy_tags" in d
        assert "knowledge_type" in d
        assert "timestamp" in d
    
    def test_result_repr(self):
        """测试结果字符串表示"""
        result = ClassificationResult(
            content="测试",
            taxonomy_tags=["tech"],
            knowledge_type={"primary_type": "skill", "type_name": "技能", "confidence": 0.8}
        )
        r = repr(result)
        assert "tech" in r or "skill" in r


class TestClassificationTaskAdvanced:
    """测试ClassificationTask高级功能"""
    
    def test_task_with_mode(self):
        """测试不同模式的分类任务"""
        task = ClassificationTask(
            task_id="mode_task",
            content="内容",
            mode="taxonomy_only",
            timeout=60
        )
        assert task.mode == "taxonomy_only"
        assert task.timeout == 60
    
    def test_task_to_dict(self):
        """测试任务转字典"""
        task = ClassificationTask(
            task_id="dict_task",
            content="内容",
            mode="dual"
        )
        d = task.to_dict()
        assert d["task_id"] == "dict_task"
        assert d["status"] == "pending"
        assert d["mode"] == "dual"
        assert d["result"] is None


class TestTaskRegistryAdvanced:
    """测试TaskRegistry高级功能"""
    
    def test_registry_update(self):
        """测试更新任务"""
        registry = TaskRegistry()
        task = ClassificationTask(
            task_id="update_task",
            content="测试内容"
        )
        registry.register(task)
        
        result = ClassificationResult(
            content="测试",
            taxonomy_tags=["test"],
            knowledge_type={"primary_type": "concept", "type_name": "概念", "confidence": 0.9}
        )
        registry.update("update_task", TaskStatus.COMPLETED, result)
        
        updated_task = registry.get("update_task")
        assert updated_task.status == TaskStatus.COMPLETED
    
    def test_registry_list_tasks(self):
        """测试列出任务"""
        registry = TaskRegistry()
        task1 = ClassificationTask(task_id="list_1", content="内容1")
        task2 = ClassificationTask(task_id="list_2", content="内容2")
        registry.register(task1)
        registry.register(task2)
        
        tasks = registry.list_tasks()
        assert len(tasks) >= 2
    
    def test_registry_list_tasks_by_status(self):
        """测试按状态列出任务"""
        registry = TaskRegistry()
        task = ClassificationTask(task_id="status_1", content="内容")
        registry.register(task)
        
        tasks = registry.list_tasks(status=TaskStatus.PENDING)
        assert all(t.status == TaskStatus.PENDING for t in tasks)
    
    def test_registry_record_history(self):
        """测试记录历史"""
        registry = TaskRegistry()
        result = ClassificationResult(
            content="历史测试",
            taxonomy_tags=["history", "test"],
            knowledge_type={"primary_type": "concept", "type_name": "概念", "confidence": 0.95}
        )
        registry.record_history(result)
        assert len(registry._history) >= 1
    
    def test_registry_get_popular_tags(self):
        """测试获取热门标签"""
        registry = TaskRegistry()
        result = ClassificationResult(
            content="热门标签测试",
            taxonomy_tags=["popular", "test"],
            knowledge_type={"primary_type": "concept", "type_name": "概念", "confidence": 0.9}
        )
        registry.record_history(result)
        
        popular = registry.get_popular_tags(top_n=5)
        assert isinstance(popular, list)
    
    def test_registry_get_stats(self):
        """测试获取统计"""
        registry = TaskRegistry()
        stats = registry.get_stats()
        assert "total_tasks" in stats
        assert "by_status" in stats
        assert "history_size" in stats
        assert "top_tags" in stats


class TestTaxonomyClassifierAdvanced:
    """测试TaxonomyClassifier高级功能"""
    
    def test_classifier_custom_tags(self):
        """测试自定义标签"""
        clf = TaxonomyClassifier(custom_tags={
            "custom_tag": ["custom", "test", "special"]
        })
        assert "custom_tag" in clf.tags
    
    def test_tokenize(self):
        """测试分词"""
        clf = TaxonomyClassifier()
        tokens = clf._tokenize("Hello World 你好世界")
        assert isinstance(tokens, list)
    
    def test_score_tag(self):
        """测试标签评分"""
        clf = TaxonomyClassifier()
        score = clf._score_tag("Python编程开发", "技术", {"keywords": ["python", "编程", "开发"], "weight": 1.0})
        assert score > 0
    
    def test_classify_with_threshold(self):
        """测试带阈值的分类"""
        clf = TaxonomyClassifier()
        result = clf.classify("Python技术内容", threshold=0.3)
        assert isinstance(result, list)


class TestKnowledgeTypeClassifierAdvanced:
    """测试KnowledgeTypeClassifier高级功能"""
    
    def test_classifier_with_custom_types(self):
        """测试自定义类型"""
        clf = KnowledgeTypeClassifier()
        # 应该有默认类型
        assert clf.types is not None
    
    def test_classify_concept(self):
        """测试概念分类"""
        clf = KnowledgeTypeClassifier()
        result = clf.classify("什么是机器学习？机器学习是...")
        assert "primary_type" in result
        assert "confidence" in result
    
    def test_classify_skill(self):
        """测试技能分类"""
        clf = KnowledgeTypeClassifier()
        result = clf.classify("如何使用Python编写代码")
        assert "primary_type" in result
    
    def test_classify_experience(self):
        """测试经验分类"""
        clf = KnowledgeTypeClassifier()
        result = clf.classify("我曾经做过一个项目，在项目中我学会了...")
        assert "primary_type" in result


class TestAutoTaggerAdvanced:
    """测试AutoTagger高级功能"""
    
    def test_tagger_with_taxonomies(self):
        """测试指定分类法的标注"""
        tagger = AutoTagger()
        result = tagger.classify("技术文档内容", taxonomies=["技术"])
        assert hasattr(result, 'taxonomy_tags')
    
    def test_tagger_with_knowledge_types(self):
        """测试指定知识类型的标注"""
        tagger = AutoTagger()
        result = tagger.classify("概念解释", knowledge_types=["concept"])
        assert hasattr(result, 'knowledge_type')


class TestClassificationEngineAdvanced:
    """测试ClassificationEngine高级功能"""
    
    def test_engine_with_custom_registry(self):
        """测试自定义注册表"""
        registry = TaskRegistry(max_size=100)
        engine = ClassificationEngine(registry=registry)
        assert engine.registry is not None
    
    def test_classify_with_task_id(self):
        """测试带任务ID的分类"""
        engine = get_engine()
        result = engine.classify("测试内容", task_id="custom_task_id")
        assert result is not None
    
    def test_classify_taxonomy_only(self):
        """测试仅分类标签"""
        engine = get_engine()
        result = engine.classify("技术内容", mode="taxonomy_only")
        assert result is not None
    
    def test_classify_knowledge_type_only(self):
        """测试仅分类知识类型"""
        engine = get_engine()
        result = engine.classify("概念内容", mode="knowledge_type_only")
        assert result is not None


class TestGlobalFunctionsAdvanced:
    """测试全局函数高级功能"""
    
    def test_classify_with_custom_result_type(self):
        """测试自定义结果类型"""
        result = classify("测试", result_type="list")
        assert result is not None
    
    def test_register_task_with_callback(self):
        """测试带回调的任务注册"""
        def callback(task_id, result):
            pass
        task_id = register_task("callback test", callback=callback)
        assert task_id is not None
