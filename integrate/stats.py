"""
记忆殿堂 统计模块

提供MemoryPalaceIntegration所需的统计类
"""

from dataclasses import dataclass


@dataclass
class MemoryStats:
    """统一统计信息"""
    sessions_tracked: int = 0
    total_memories: int = 0
    total_compressions: int = 0
    total_corrections: int = 0
    total_backups: int = 0
    total_restores: int = 0
    compression_ratio_avg: float = 0.0
    correction_success_rate: float = 0.0
    
    def to_dict(self):
        """转换为字典"""
        return {
            'sessions_tracked': self.sessions_tracked,
            'total_memories': self.total_memories,
            'total_compressions': self.total_compressions,
            'total_corrections': self.total_corrections,
            'total_backups': self.total_backups,
            'total_restores': self.total_restores,
            'compression_ratio_avg': self.compression_ratio_avg,
            'correction_success_rate': self.correction_success_rate,
        }
