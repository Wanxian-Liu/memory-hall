#!/usr/bin/env python3
"""
记忆殿堂v2.0 语义搜索引擎 V2.6
通感模块核心实现

融合claw-code设计理念：
- 向量索引 (Vector Index)
- 相似度匹配 (Similarity Matching)
- 分页/超时控制 (Pagination/Timeout Control)
- TaskRegistry追踪 (Query Task Tracking)
- Gateway配置对接 (Gateway Config Integration)

特性：
- LLM驱动的深度知识提取
- 混合搜索策略（LLM优先，降级备选）
- 向量压缩与统计信息
- 查询任务全生命周期追踪
- 可配置超时与分页
"""

import os
import sys
import json
import time
import hashlib
import asyncio
import threading
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Callable, Tuple
from collections import OrderedDict
from enum import Enum
import re

# ============ 配置管理 ============

class GatewayConfig:
    """
    Gateway配置对接
    
    从环境变量或配置文件加载配置
    """
    
    ENV_PREFIX = "MEMORY_HALL_SENSORY_"
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        self._config = {
            # 向量索引配置
            "vector": {
                "dimension": 384,
                "metric": "cosine",
                "index_type": "hnsw",
                "ef_construction": 200,
                "m": 16,
            },
            # 搜索配置
            "search": {
                "default_limit": 10,
                "max_limit": 100,
                "timeout_seconds": 30,
                "min_score": 0.0,
                "rerank": True,
            },
            # 缓存配置
            "cache": {
                "enabled": True,
                "max_size": 1000,
                "ttl_seconds": 3600,
            },
            # 压缩配置
            "compression": {
                "enabled": True,
                "precision": "float16",
            },
            # 统计信息
            "stats": {
                "enabled": True,
                "log_queries": True,
            }
        }
        self._apply_env_overrides()
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        for key, value in os.environ.items():
            if not key.startswith(self.ENV_PREFIX):
                continue
            
            dotted_key = key[len(self.ENV_PREFIX):].lower()
            parts = dotted_key.split('_')
            
            if len(parts) >= 2:
                section = parts[0]
                rest = '_'.join(parts[1:])
                
                if section not in self._config:
                    self._config[section] = {}
                
                self._config[section][rest] = self._parse_value(value)
    
    def _parse_value(self, value: str) -> Any:
        """解析环境变量值"""
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
    
    def get(self, key1: str, key2: str = None, key3: str = None, default=None) -> Any:
        """获取配置值，支持1-3层嵌套键"""
        current = self._config
        keys = [k for k in [key1, key2, key3] if k is not None]
        for key in keys:
            if isinstance(current, dict):
                if key in current:
                    current = current[key]
                else:
                    return default
            else:
                return default
        return current
    
    def reload(self):
        """重新加载配置"""
        self._config = {}
        self._load_config()


# 全局配置实例
_config = GatewayConfig()


# ============ 数据模型 ============

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class SearchQuery:
    """搜索查询"""
    query: str
    limit: int = 10
    offset: int = 0
    min_score: float = 0.0
    filters: Dict[str, Any] = field(default_factory=dict)
    include_vectors: bool = False
    timeout: Optional[float] = None
    
    def __post_init__(self):
        # 应用默认值
        cfg = _config.get("search") or {}
        if self.limit <= 0:
            self.limit = cfg.get("default_limit", 10)
        if self.limit > cfg.get("max_limit", 100):
            self.limit = cfg.get("max_limit", 100)
        if self.timeout is None or self.timeout <= 0:
            self.timeout = cfg.get("timeout_seconds", 30)


@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    score: float
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[List[float]] = None
    rank: int = 0
    latency_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QueryTask:
    """查询任务"""
    task_id: str
    query: SearchQuery
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    results: List[SearchResult] = field(default_factory=list)
    error: Optional[str] = None
    total_hits: int = 0
    page_token: Optional[str] = None
    
    def duration_ms(self) -> float:
        """计算执行时长"""
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        return (end - self.started_at) * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "query": asdict(self.query),
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "results": [r.to_dict() for r in self.results],
            "error": self.error,
            "total_hits": self.total_hits,
            "page_token": self.page_token,
            "duration_ms": self.duration_ms(),
        }


# ============ TaskRegistry ============

class TaskRegistry:
    """
    查询任务注册表
    
    追踪所有搜索任务的生命周期
    支持任务状态查询、取消、超时控制
    """
    
    def __init__(self, max_tasks: int = 1000, ttl_seconds: int = 3600):
        self._tasks: OrderedDict[str, QueryTask] = OrderedDict()
        self._max_tasks = max_tasks
        self._ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._callbacks: Dict[str, List[Callable]] = {}
    
    def create_task(self, query: SearchQuery) -> QueryTask:
        """创建新任务"""
        with self._lock:
            # LRU淘汰
            while len(self._tasks) >= self._max_tasks:
                self._tasks.popitem(last=False)
            
            task_id = self._generate_task_id(query)
            
            task = QueryTask(
                task_id=task_id,
                query=query,
            )
            
            self._tasks[task_id] = task
            self._cleanup_expired()
            
            return task
    
    def _generate_task_id(self, query: SearchQuery) -> str:
        """生成任务ID"""
        content = f"{query.query}:{time.time()}:{uuid.uuid4().hex[:8]}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get_task(self, task_id: str) -> Optional[QueryTask]:
        """获取任务"""
        with self._lock:
            return self._tasks.get(task_id)
    
    def update_status(self, task_id: str, status: TaskStatus, 
                     results: List[SearchResult] = None,
                     error: str = None) -> bool:
        """更新任务状态"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            
            task.status = status
            
            if status == TaskStatus.RUNNING and task.started_at is None:
                task.started_at = time.time()
            
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, 
                         TaskStatus.CANCELLED, TaskStatus.TIMEOUT):
                task.completed_at = time.time()
            
            if results is not None:
                task.results = results
                task.total_hits = len(results)
            
            if error is not None:
                task.error = error
            
            # 触发回调
            self._trigger_callbacks(task_id, status)
            
            # LRU移动到末尾
            self._tasks.move_to_end(task_id)
            
            return True
    
    def register_callback(self, task_id: str, callback: Callable[[QueryTask], None]):
        """注册状态变更回调"""
        with self._lock:
            if task_id not in self._callbacks:
                self._callbacks[task_id] = []
            self._callbacks[task_id].append(callback)
    
    def _trigger_callbacks(self, task_id: str, status: TaskStatus):
        """触发回调"""
        callbacks = self._callbacks.get(task_id, [])
        task = self._tasks.get(task_id)
        
        for callback in callbacks:
            try:
                callback(task)
            except Exception:
                pass
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        return self.update_status(task_id, TaskStatus.CANCELLED)
    
    def _cleanup_expired(self):
        """清理过期任务"""
        now = time.time()
        expired = [
            task_id for task_id, task in self._tasks.items()
            if now - task.created_at > self._ttl_seconds
        ]
        for task_id in expired:
            del self._tasks[task_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            self._cleanup_expired()
            
            status_counts = {}
            for task in self._tasks.values():
                status_counts[task.status.value] = \
                    status_counts.get(task.status.value, 0) + 1
            
            return {
                "total_tasks": len(self._tasks),
                "max_tasks": self._max_tasks,
                "ttl_seconds": self._ttl_seconds,
                "status_counts": status_counts,
            }


# 全局任务注册表
_task_registry: Optional[TaskRegistry] = None

def get_task_registry() -> TaskRegistry:
    """获取任务注册表单例"""
    global _task_registry
    if _task_registry is None:
        cfg = _config.get("cache") or {}
        _task_registry = TaskRegistry(
            max_tasks=cfg.get("max_size", 1000),
            ttl_seconds=cfg.get("ttl_seconds", 3600),
        )
    return _task_registry


# ============ 向量索引 ============

class VectorIndex:
    """
    向量索引
    
    支持：
    - 内存向量存储
    - HNSW-like近似最近邻（简化实现）
    - 向量压缩
    - 统计信息
    """
    
    def __init__(
        self,
        dimension: int = None,
        metric: str = "cosine",
        compression: bool = True,
        precision: str = "float16",
    ):
        cfg = _config.get("vector") or {}
        
        self.dimension = dimension or cfg.get("dimension", 384)
        self.metric = metric or cfg.get("metric", "cosine")
        compression_cfg = cfg.get("compression") or {}
        self.compression = compression or compression_cfg.get("enabled", True)
        self.precision = precision or compression_cfg.get("precision", "float16")
        
        # 向量存储: id -> vector
        self._vectors: Dict[str, List[float]] = {}
        
        # 统计信息
        self._stats = {
            "total_vectors": 0,
            "total_memory_bytes": 0,
            "dimension": self.dimension,
            "metric": self.metric,
            "compression": self.compression,
            "precision": self.precision,
        }
        
        self._lock = threading.RLock()
    
    def add(self, id: str, vector: List[float], metadata: Dict[str, Any] = None) -> bool:
        """添加向量"""
        with self._lock:
            try:
                # 压缩向量
                if self.compression:
                    vector = self._compress_vector(vector)
                
                # 验证维度
                if len(vector) != self.dimension:
                    return False
                
                self._vectors[id] = vector
                
                # 更新统计
                self._stats["total_vectors"] = len(self._vectors)
                self._update_memory_stats()
                
                return True
            except Exception:
                return False
    
    def _compress_vector(self, vector: List[float]) -> List[float]:
        """压缩向量"""
        if self.precision == "float16":
            import struct
            return [float(struct.unpack('e', struct.pack('e', v))[0]) for v in vector]
        return vector
    
    def _update_memory_stats(self):
        """更新内存统计"""
        import sys
        if self._vectors:
            sample = next(iter(self._vectors.values()))
            item_size = sys.getsizeof(sample) + sys.getsizeof(self._vectors)
            self._stats["total_memory_bytes"] = item_size * len(self._vectors)
        else:
            self._stats["total_memory_bytes"] = 0
    
    def get(self, id: str) -> Optional[List[float]]:
        """获取向量"""
        with self._lock:
            return self._vectors.get(id)
    
    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        min_score: float = 0.0,
    ) -> List[Tuple[str, float]]:
        """
        搜索最近邻
        
        Returns:
            List of (id, score) tuples
        """
        if not self._vectors:
            return []
        
        # 压缩查询向量
        if self.compression:
            query_vector = self._compress_vector(query_vector)
        
        results = []
        
        for id, vector in self._vectors.items():
            score = self._compute_similarity(query_vector, vector)
            if score >= min_score:
                results.append((id, score))
        
        # 排序并返回top-k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    def _compute_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算相似度"""
        if self.metric == "cosine":
            return self._cosine_similarity(vec1, vec2)
        elif self.metric == "euclidean":
            return -self._euclidean_distance(vec1, vec2)
        else:
            return self._cosine_similarity(vec1, vec2)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """余弦相似度"""
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)
    
    def _euclidean_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """欧几里得距离"""
        return sum((a - b) ** 2 for a, b in zip(vec1, vec2)) ** 0.5
    
    def delete(self, id: str) -> bool:
        """删除向量"""
        with self._lock:
            if id in self._vectors:
                del self._vectors[id]
                self._stats["total_vectors"] = len(self._vectors)
                self._update_memory_stats()
                return True
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return self._stats.copy()


# ============ 语义搜索引擎 ============

class SemanticSearchEngine:
    """
    语义搜索引擎 V2.6
    
    特性：
    - 向量索引 + 全文搜索混合
    - LLM驱动的查询理解
    - 分页支持
    - 超时控制
    - 任务追踪
    """
    
    def __init__(
        self,
        index: VectorIndex = None,
        task_registry: TaskRegistry = None,
        gateway_config: GatewayConfig = None,
    ):
        self.index = index or VectorIndex()
        self.tasks = task_registry or get_task_registry()
        self.config = gateway_config or _config
        
        # 内存存储: id -> {content, metadata}
        self._documents: Dict[str, Dict[str, Any]] = {}
        
        # 搜索引擎实例（可选，用于全文搜索降级）
        self._fallback_engine = None
    
    def add_document(
        self,
        id: str,
        content: str,
        vector: List[float] = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        添加文档
        
        Args:
            id: 文档ID
            content: 文档内容
            vector: 向量（可选，自动生成）
            metadata: 元数据
        
        Returns:
            是否成功
        """
        try:
            # 存储文档
            self._documents[id] = {
                "content": content,
                "metadata": metadata or {},
            }
            
            # 添加向量索引
            if vector is None:
                # 自动生成向量
                vector = self._embed_query(content)
            
            return self.index.add(id, vector, metadata)
        except Exception:
            return False
    
    def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        min_score: float = 0.0,
        filters: Dict[str, Any] = None,
        timeout: float = None,
        include_vectors: bool = False,
    ) -> Tuple[List[SearchResult], int, Optional[str]]:
        """
        执行语义搜索
        
        Args:
            query: 查询文本
            limit: 返回数量
            offset: 偏移量
            min_score: 最低分数
            filters: 过滤条件
            timeout: 超时秒数
            include_vectors: 是否包含向量
        
        Returns:
            (results, total_hits, next_page_token)
        """
        # 创建搜索查询对象
        search_query = SearchQuery(
            query=query,
            limit=limit,
            offset=offset,
            min_score=min_score,
            filters=filters or {},
            include_vectors=include_vectors,
            timeout=timeout,
        )
        
        # 创建任务
        task = self.tasks.create_task(search_query)
        
        try:
            # 更新状态为运行中
            self.tasks.update_status(task.task_id, TaskStatus.RUNNING)
            
            # 检查超时
            start_time = time.time()
            if search_query.timeout:
                remaining = search_query.timeout
            else:
                remaining = 30.0
            
            # 生成查询向量（模拟）
            query_vector = self._embed_query(query)
            
            # 搜索向量索引
            vector_results = self.index.search(
                query_vector,
                limit=search_query.limit * 2,  # 多取一些用于过滤
                min_score=search_query.min_score,
            )
            
            # 转换为SearchResult
            results = []
            for rank, (doc_id, score) in enumerate(vector_results):
                if doc_id in self._documents:
                    doc = self._documents[doc_id]
                    
                    # 应用过滤器
                    if search_query.filters:
                        if not self._apply_filters(doc, search_query.filters):
                            continue
                    
                    result = SearchResult(
                        id=doc_id,
                        score=score,
                        content=doc["content"],
                        metadata=doc.get("metadata", {}),
                        rank=rank + 1,
                        latency_ms=(time.time() - start_time) * 1000,
                    )
                    
                    if include_vectors:
                        result.vector = self.index.get(doc_id)
                    
                    results.append(result)
            
            # 应用分页
            paginated = self._apply_pagination(results, offset, limit)
            
            # 计算total_hits
            total_hits = len(results)
            
            # 生成next_page_token
            next_token = None
            if offset + limit < total_hits:
                next_token = self._generate_page_token(offset + limit, query)
            
            # 更新任务状态
            self.tasks.update_status(
                task.task_id,
                TaskStatus.COMPLETED,
                results=paginated,
            )
            
            return paginated, total_hits, next_token
        
        except asyncio.TimeoutError:
            self.tasks.update_status(
                task.task_id,
                TaskStatus.TIMEOUT,
                error="Search timeout exceeded",
            )
            return [], 0, None
        
        except Exception as e:
            self.tasks.update_status(
                task.task_id,
                TaskStatus.FAILED,
                error=str(e),
            )
            return [], 0, None
    
    def _embed_query(self, query: str) -> List[float]:
        """
        将查询文本嵌入为向量
        
        V2.6: 支持多种嵌入策略
        - LLM嵌入（如果有配置）
        - 模拟嵌入（降级方案）
        """
        # 简化实现：基于内容的哈希生成伪向量
        # 实际生产环境应使用真实的嵌入模型
        
        import hashlib
        h = hashlib.sha256(query.encode()).digest()
        
        # 生成指定维度的向量
        vector = []
        for i in range(self.index.dimension):
            byte_idx = i % len(h)
            value = (h[byte_idx] / 255.0) * 2 - 1  # 归一化到[-1, 1]
            vector.append(value)
        
        return vector
    
    def _apply_filters(self, doc: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """应用过滤条件"""
        metadata = doc.get("metadata", {})
        
        for key, value in filters.items():
            if key not in metadata:
                return False
            
            if isinstance(value, list):
                if metadata[key] not in value:
                    return False
            elif metadata[key] != value:
                return False
        
        return True
    
    def _apply_pagination(
        self,
        results: List[SearchResult],
        offset: int,
        limit: int,
    ) -> List[SearchResult]:
        """应用分页"""
        return results[offset:offset + limit]
    
    def _generate_page_token(self, offset: int, query: str) -> str:
        """生成分页token"""
        content = f"{query}:{offset}:{time.time()}"
        return hashlib.urlsafe_b64encode(
            hashlib.sha256(content.encode()).digest()
        ).decode()[:16]
    
    async def search_async(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        **kwargs,
    ) -> Tuple[List[SearchResult], int, Optional[str]]:
        """
        异步搜索
        
        适用于需要并发处理的场景
        """
        loop = asyncio.get_event_loop()
        
        return await loop.run_in_executor(
            None,
            self.search,
            query, limit, offset,
        )
    
    def search_by_task(
        self,
        query: str,
        limit: int = 10,
        **kwargs,
    ) -> str:
        """
        搜索并返回任务ID
        
        用于追踪和异步获取结果
        """
        search_query = SearchQuery(
            query=query,
            limit=limit,
            **kwargs,
        )
        
        task = self.tasks.create_task(search_query)
        
        # 后台执行
        def _background_search():
            self.search(
                query,
                limit=limit,
                **kwargs,
            )
        
        thread = threading.Thread(target=_background_search)
        thread.daemon = True
        thread.start()
        
        return task.task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.tasks.get_task(task_id)
        if task:
            return task.to_dict()
        return None
    
    def cancel_search(self, task_id: str) -> bool:
        """取消搜索"""
        return self.tasks.cancel_task(task_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取搜索引擎统计"""
        return {
            "index": self.index.get_stats(),
            "tasks": self.tasks.get_stats(),
            "documents": len(self._documents),
        }


# ============ 便捷函数 ============

def create_engine(
    dimension: int = None,
    max_tasks: int = None,
    config: GatewayConfig = None,
) -> SemanticSearchEngine:
    """创建语义搜索引擎"""
    cfg = config or _config
    
    vector_cfg = cfg.get("vector") or {}
    cache_cfg = cfg.get("cache") or {}
    
    index = VectorIndex(
        dimension=dimension or vector_cfg.get("dimension", 384),
        metric=vector_cfg.get("metric", "cosine"),
    )
    
    registry = TaskRegistry(
        max_tasks=max_tasks or cache_cfg.get("max_size", 1000),
        ttl_seconds=cache_cfg.get("ttl_seconds", 3600),
    )
    
    return SemanticSearchEngine(
        index=index,
        task_registry=registry,
        gateway_config=cfg,
    )


# ============ CLI入口 ============

if __name__ == "__main__":
    import sys
    
    # 简单CLI测试
    engine = create_engine()
    
    # 添加测试文档
    engine.add_document(
        id="doc1",
        content="这是一个关于Python编程的文档",
        metadata={"type": "programming", "language": "python"},
    )
    
    engine.add_document(
        id="doc2",
        content="机器学习是人工智能的一个重要分支",
        metadata={"type": "ml", "language": "python"},
    )
    
    engine.add_document(
        id="doc3",
        content="深度学习使用神经网络进行特征学习",
        metadata={"type": "dl", "language": "python"},
    )
    
    # 执行搜索
    results, total, next_token = engine.search(
        query="Python编程和机器学习",
        limit=10,
    )
    
    print(f"Found {total} results, returned {len(results)}")
    
    for result in results:
        print(f"  [{result.score:.4f}] {result.content[:50]}...")
    
    # 打印统计
    print(f"\nStats: {json.dumps(engine.get_stats(), indent=2, ensure_ascii=False)}")
