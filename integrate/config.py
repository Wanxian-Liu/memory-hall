"""
记忆殿堂 配置模块

提供MemoryPalaceIntegration所需的配置类
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class IntegrationConfig:
    """集成配置"""
    # 压缩配置
    base_compression_interval: float = 300.0
    min_compression_interval: float = 60.0
    max_compression_interval: float = 600.0
    compression_target_ratio: float = 0.2
    
    # 备份配置
    backup_dir: str = "~/.openclaw/workspace/memory_backups"
    max_backups_per_session: int = 5
    backup_retention_hours: int = 24
    
    # 纠错配置
    confidence_threshold: float = 0.85
    correction_window: int = 50
    
    # 意图预测配置
    n_predictions: int = 3
    preload_limit: int = 5
    
    # RAG验证配置
    rag_similarity_threshold: float = 0.85
    
    # 增量索引配置
    delta_threshold: int = 100
    delta_merge_interval: float = 300.0
    
    # 预测压缩配置
    benefit_threshold: float = 0.7
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'base_compression_interval': self.base_compression_interval,
            'min_compression_interval': self.min_compression_interval,
            'max_compression_interval': self.max_compression_interval,
            'compression_target_ratio': self.compression_target_ratio,
            'backup_dir': self.backup_dir,
            'max_backups_per_session': self.max_backups_per_session,
            'backup_retention_hours': self.backup_retention_hours,
            'confidence_threshold': self.confidence_threshold,
            'correction_window': self.correction_window,
            'n_predictions': self.n_predictions,
            'preload_limit': self.preload_limit,
            'rag_similarity_threshold': self.rag_similarity_threshold,
            'delta_threshold': self.delta_threshold,
            'delta_merge_interval': self.delta_merge_interval,
            'benefit_threshold': self.benefit_threshold,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntegrationConfig":
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
