"""
记忆殿堂v2.0 分类模块 V2.0
智能分类系统 - 双维度分类（Taxonomy + Knowledge Type）

主要功能：
- 自动标签生成（Taxonomy + 知识类型双维度）
- 分类任务注册（TaskRegistry）
- 多标签支持
- Gateway配置对接

作者: 织界中枢
版本: 2.0.0
"""

from .classifier import (
    # 版本信息
    __version__,
    
    # 数据模型
    ClassificationResult,
    ClassificationTask,
    TaskStatus,
    
    # 分类器
    TaxonomyClassifier,
    KnowledgeTypeClassifier,
    AutoTagger,
    ClassificationEngine,
    TaskRegistry,
    
    # 快捷函数
    classify,
    classify_dual,
    register_task,
    get_task,
    get_stats,
    get_engine,
)

__version__ = "2.0.0"
__all__ = [
    # 版本
    "__version__",
    
    # 数据模型
    "ClassificationResult",
    "ClassificationTask",
    "TaskStatus",
    
    # 分类器
    "TaxonomyClassifier",
    "KnowledgeTypeClassifier",
    "AutoTagger",
    "ClassificationEngine",
    "TaskRegistry",
    
    # 快捷函数
    "classify",
    "classify_dual",
    "register_task",
    "get_task",
    "get_stats",
    "get_engine",
]
