"""
记忆殿堂v2.0 胶囊交叉引用模块 V1.0

功能：
1. 基于语义相似度建立胶囊间关联
2. 自动添加related_capsules字段
3. 支持增量更新和批量处理

作者: agentic_identity_trust
版本: 1.0.0
"""

import hashlib
import re
import time
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum


class SimilarityMethod(Enum):
    """相似度计算方法"""
    JACCARD = "jaccard"           # Jaccard相似度（词集合）
    COSINE = "cosine"             # 余弦相似度（TF-IDF）
    BM25 = "bm25"                 # BM25排序
    SEMANTIC = "semantic"         # 语义相似度（需LLM）


@dataclass
class Capsule:
    """胶囊数据结构"""
    id: str
    content: str
    memory_type: str = "unknown"
    taxonomy_tags: List[str] = field(default_factory=list)
    knowledge_type: str = "concept"
    related_capsules: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Capsule":
        """从字典创建胶囊"""
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            memory_type=data.get("memory_type", "unknown"),
            taxonomy_tags=data.get("taxonomy_tags", []),
            knowledge_type=data.get("knowledge_type", {}).get("primary_type", "concept") if isinstance(data.get("knowledge_type"), dict) else data.get("knowledge_type", "concept"),
            related_capsules=data.get("related_capsules", []),
            metadata=data.get("metadata", {})
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "taxonomy_tags": self.taxonomy_tags,
            "knowledge_type": self.knowledge_type,
            "related_capsules": self.related_capsules,
            "metadata": self.metadata
        }


@dataclass
class CrossReferenceResult:
    """交叉引用结果"""
    source_id: str
    related: List[Dict[str, Any]]  # List of {id, similarity, reason}
    method: str
    timestamp: float = field(default_factory=time.time)


class CrossReferenceEngine:
    """
    胶囊交叉引用引擎
    
    基于多种相似度方法建立胶囊间关联
    """

    def __init__(
        self,
        similarity_method: SimilarityMethod = SimilarityMethod.JACCARD,
        min_similarity: float = 0.01,  # 降低默认阈值以适应中文n-gram tokenization
        max_related: int = 5,
        cache_dir: Optional[str] = None
    ):
        self.similarity_method = similarity_method
        self.min_similarity = min_similarity
        self.max_related = max_related
        self.cache_dir = cache_dir
        
        # 索引缓存
        self._token_index: Dict[str, Set[str]] = {}  # token -> capsule_ids
        self._capsule_tokens: Dict[str, Set[str]] = {}  # capsule_id -> tokens
        
    def _tokenize(self, text: str) -> Set[str]:
        """分词 - 支持中英文混合"""
        text_lower = text.lower()
        tokens = set()
        
        # 提取英文单词
        english_words = re.findall(r'[a-z0-9]{2,}', text_lower)
        tokens.update(english_words)
        
        # 提取中文词（按字符，保留2-gram和3-gram）
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text_lower)
        # 单字
        tokens.update(chinese_chars)
        # 2-gram
        for i in range(len(chinese_chars) - 1):
            tokens.add(chinese_chars[i] + chinese_chars[i+1])
        # 3-gram（如果长度足够）
        for i in range(len(chinese_chars) - 2):
            tokens.add(chinese_chars[i] + chinese_chars[i+1] + chinese_chars[i+2])
        
        return tokens
    
    def _build_index(self, capsules: List[Capsule]):
        """构建倒排索引"""
        self._token_index.clear()
        self._capsule_tokens.clear()
        
        for capsule in capsules:
            tokens = self._tokenize(capsule.content)
            self._capsule_tokens[capsule.id] = tokens
            
            for token in tokens:
                if token not in self._token_index:
                    self._token_index[token] = set()
                self._token_index[token].add(capsule.id)
    
    def _jaccard_similarity(self, tokens1: Set[str], tokens2: Set[str]) -> float:
        """Jaccard相似度"""
        if not tokens1 or not tokens2:
            return 0.0
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        return intersection / union if union > 0 else 0.0
    
    def _compute_similarity(self, source: Capsule, target: Capsule) -> float:
        """计算两个胶囊的相似度"""
        if source.id == target.id:
            return 0.0
            
        if self.similarity_method == SimilarityMethod.JACCARD:
            tokens1 = self._capsule_tokens.get(source.id, self._tokenize(source.content))
            tokens2 = self._capsule_tokens.get(target.id, self._tokenize(target.content))
            return self._jaccard_similarity(tokens1, tokens2)
        
        # 默认使用Jaccard
        return self._jaccard_similarity(
            self._tokenize(source.content),
            self._tokenize(target.content)
        )
    
    def _find_similar_capsules(
        self, 
        source: Capsule, 
        all_capsules: List[Capsule],
        top_k: int = None
    ) -> List[Tuple[Capsule, float]]:
        """查找相似的胶囊"""
        if top_k is None:
            top_k = self.max_related
            
        similarities = []
        for target in all_capsules:
            if target.id == source.id:
                continue
            sim = self._compute_similarity(source, target)
            if sim >= self.min_similarity:
                similarities.append((target, sim))
        
        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def _generate_reason(self, source: Capsule, target: Capsule, similarity: float) -> str:
        """生成关联原因"""
        # 检查标签重叠
        common_tags = set(source.taxonomy_tags) & set(target.taxonomy_tags)
        if common_tags:
            return f"共享标签: {', '.join(list(common_tags)[:3])}"
        
        # 检查知识类型
        if source.knowledge_type == target.knowledge_type:
            return f"同类型知识: {source.knowledge_type}"
        
        # 检查记忆类型
        if source.memory_type == target.memory_type:
            return f"同类型记忆: {source.memory_type}"
        
        return f"内容相似度: {similarity:.2f}"
    
    def compute_cross_references(
        self, 
        capsules: List[Capsule],
        update_existing: bool = True
    ) -> List[Capsule]:
        """
        计算所有胶囊的交叉引用
        
        Args:
            capsules: 胶囊列表
            update_existing: 是否更新已有的related_capsules
            
        Returns:
            更新后的胶囊列表
        """
        if not capsules:
            return []
        
        # 构建索引
        self._build_index(capsules)
        
        results = []
        for capsule in capsules:
            # 查找相似胶囊
            similar = self._find_similar_capsules(capsule, capsules)
            
            # 构建关联列表
            related = []
            for target, sim in similar:
                related.append({
                    "id": target.id,
                    "similarity": round(sim, 3),
                    "reason": self._generate_reason(capsule, target, sim),
                    "memory_type": target.memory_type,
                    "knowledge_type": target.knowledge_type
                })
            
            # 更新胶囊
            if update_existing or not capsule.related_capsules:
                capsule.related_capsules = related
            
            results.append(capsule)
        
        return results
    
    def add_cross_reference(
        self,
        source: Capsule,
        target: Capsule,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        为单个胶囊添加交叉引用
        
        Args:
            source: 源胶囊
            target: 目标胶囊
            reason: 关联原因
            
        Returns:
            交叉引用条目
        """
        similarity = self._compute_similarity(source, target)
        if similarity < self.min_similarity:
            return None
            
        return {
            "id": target.id,
            "similarity": round(similarity, 3),
            "reason": reason or self._generate_reason(source, target, similarity),
            "memory_type": target.memory_type,
            "knowledge_type": target.knowledge_type
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "similarity_method": self.similarity_method.value,
            "min_similarity": self.min_similarity,
            "max_related": self.max_related,
            "indexed_tokens": len(self._token_index),
            "indexed_capsules": len(self._capsule_tokens)
        }


# ============ 便捷函数 ============

_default_engine: Optional[CrossReferenceEngine] = None


def get_engine(
    similarity_method: SimilarityMethod = SimilarityMethod.JACCARD,
    min_similarity: float = 0.15,
    max_related: int = 5
) -> CrossReferenceEngine:
    """获取默认引擎"""
    global _default_engine
    if _default_engine is None:
        _default_engine = CrossReferenceEngine(
            similarity_method=similarity_method,
            min_similarity=min_similarity,
            max_related=max_related
        )
    return _default_engine


def compute_cross_references(
    capsules: List[Dict],
    similarity_method: str = "jaccard",
    min_similarity: float = 0.01,  # 与类默认一致
    max_related: int = 5
) -> List[Dict]:
    """
    快捷交叉引用计算函数
    
    Args:
        capsules: 胶囊字典列表
        similarity_method: 相似度方法 (jaccard/cosine/bm25)
        min_similarity: 最小相似度阈值
        max_related: 最大关联数量
        
    Returns:
        更新后的胶囊列表
    """
    method = SimilarityMethod(similarity_method)
    engine = CrossReferenceEngine(
        similarity_method=method,
        min_similarity=min_similarity,
        max_related=max_related
    )
    
    # 转换为Capsule对象
    capsule_objects = [Capsule.from_dict(c) for c in capsules]
    
    # 计算交叉引用
    results = engine.compute_cross_references(capsule_objects)
    
    # 转换回字典
    return [r.to_dict() for r in results]


# ============ CLI测试 ============

if __name__ == "__main__":
    # 测试代码
    test_capsules = [
        {
            "id": "capsule_001",
            "content": "Python是一种高级编程语言，支持面向对象、函数式编程。它有丰富的库，如NumPy、Pandas等。",
            "memory_type": "long_term",
            "taxonomy_tags": ["技术", "编程"],
            "knowledge_type": "concept"
        },
        {
            "id": "capsule_002",
            "content": "今天学习了Python的装饰器用法。装饰器可以在不修改原函数的情况下增强功能。",
            "memory_type": "episodic",
            "taxonomy_tags": ["技术", "学习"],
            "knowledge_type": "skill"
        },
        {
            "id": "capsule_003",
            "content": "JavaScript是一种脚本语言，主要用于Web前端开发。它支持闭包、原型链等特性。",
            "memory_type": "long_term",
            "taxonomy_tags": ["技术", "前端"],
            "knowledge_type": "concept"
        },
        {
            "id": "capsule_004",
            "content": "天工框架的迭代流程包括：需求分析、组件设计、编码实现、测试验证、部署上线。",
            "memory_type": "long_term",
            "taxonomy_tags": ["天工", "流程"],
            "knowledge_type": "workflow"
        },
        {
            "id": "capsule_005",
            "content": "记忆殿堂的萃取模块使用4层压缩流水线：L1裁剪、L2提取、L3摘要、L4格式化。",
            "memory_type": "long_term",
            "taxonomy_tags": ["记忆殿堂", "技术"],
            "knowledge_type": "concept"
        }
    ]
    
    print("=" * 60)
    print("胶囊交叉引用测试")
    print("=" * 60)
    
    # 计算交叉引用
    results = compute_cross_references(test_capsules, min_similarity=0.1, max_related=3)
    
    for capsule in results:
        print(f"\n[{capsule['id']}] {capsule['memory_type']}")
        print(f"  标签: {capsule['taxonomy_tags']}")
        if capsule['related_capsules']:
            print(f"  关联胶囊 ({len(capsule['related_capsules'])}个):")
            for rel in capsule['related_capsules']:
                print(f"    - {rel['id']} (相似度: {rel['similarity']}, 原因: {rel['reason']})")
        else:
            print(f"  关联胶囊: 无")
