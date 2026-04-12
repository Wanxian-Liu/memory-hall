"""
记忆殿堂v2.0 Pipeline模块

功能：
- 胶囊交叉引用（cross_reference）
- 基于语义相似度建立胶囊间关联

作者: agentic_identity_trust
版本: 1.0.0
"""

from .cross_reference import (
    Capsule,
    SimilarityMethod,
    CrossReferenceEngine,
)

__all__ = [
    "Capsule",
    "SimilarityMethod", 
    "CrossReferenceEngine",
]
