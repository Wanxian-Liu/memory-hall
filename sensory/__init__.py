"""
记忆殿堂v2.0 通感模块 (Sensory)
语义搜索系统 V2.6

融合claw-code设计：
- 向量索引
- 相似度匹配
- 分页/超时控制
- TaskRegistry追踪
- Gateway配置对接
- HybridCacheInvalidator (Cache Invalidation Capsule)

作者: 织界中枢
版本: 2.7.0
"""

from .semantic_search import (
    SemanticSearchEngine,
    VectorIndex,
    TaskRegistry,
    SearchResult,
    SearchQuery,
    GatewayConfig,
)

from .cache_invalidation import (
    HybridCacheInvalidator,
    MemorySensoryIndex,
    CacheEntry,
)

__version__ = "2.7.0"
__all__ = [
    "SemanticSearchEngine",
    "VectorIndex",
    "TaskRegistry",
    "SearchResult",
    "SearchQuery",
    "GatewayConfig",
    # Cache Invalidation Capsule
    "HybridCacheInvalidator",
    "MemorySensoryIndex",
    "CacheEntry",
]
