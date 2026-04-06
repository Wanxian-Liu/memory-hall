"""
记忆殿堂 萃取模块 V3.2
智能摘要系统 - 4层压缩流水线

V3.3新增：
- AdaptiveCompressionController (Context Optimization Capsule)
- AdaptiveExtractionPipeline

作者: 织界中枢
版本: 3.3.0
"""

from .extractor import Extractor, MemoryType, CompressionResult
from .adaptive_compression import (
    CompressionLevel,
    AdaptiveThresholds,
    CompressionContext,
    AdaptiveCompressionController,
    AdaptiveExtractionPipeline,
)

__version__ = "3.3.0"
__all__ = [
    "Extractor",
    "MemoryType",
    "CompressionResult",
    # Adaptive Compression Capsule
    "CompressionLevel",
    "AdaptiveThresholds",
    "CompressionContext",
    "AdaptiveCompressionController",
    "AdaptiveExtractionPipeline",
]
