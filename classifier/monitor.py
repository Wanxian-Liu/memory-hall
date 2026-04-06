# 分类监控模块

from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime
import threading

@dataclass
class ClassificationStats:
    total: int = 0
    success: int = 0
    failed: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    confidence_distribution: Dict[str, int] = field(default_factory=dict)  # <0.5, 0.5-0.7, 0.7-0.9, >=0.9

@dataclass  
class LatencyStats:
    count: int = 0
    total_ms: float = 0
    p95_ms: float = 0
    p99_ms: float = 0

class ClassificationMonitor:
    def __init__(self):
        self._stats = ClassificationStats()
        self._latency = LatencyStats()
        self._lock = threading.Lock()
        
    def record_classification(self, success: bool, classification_type: str = None, 
                            confidence: float = None, latency_ms: float = None):
        with self._lock:
            self._stats.total += 1
            if success:
                self._stats.success += 1
            else:
                self._stats.failed += 1
                
            if classification_type:
                self._stats.by_type[classification_type] = self._stats.by_type.get(classification_type, 0) + 1
                
            if confidence is not None:
                if confidence < 0.5:
                    bucket = "<0.5"
                elif confidence < 0.7:
                    bucket = "0.5-0.7"
                elif confidence < 0.9:
                    bucket = "0.7-0.9"
                else:
                    bucket = ">=0.9"
                self._stats.confidence_distribution[bucket] = self._stats.confidence_distribution.get(bucket, 0) + 1
                
            if latency_ms is not None:
                self._latency.count += 1
                self._latency.total_ms += latency_ms
                
    def get_error_rate(self) -> float:
        if self._stats.total == 0:
            return 0.0
        return self._stats.failed / self._stats.total
    
    def get_average_confidence(self) -> float:
        dist = self._stats.confidence_distribution
        total = sum(dist.values())
        if total == 0:
            return 1.0
        weighted = dist.get(">=0.9", 0) * 0.95 + dist.get("0.7-0.9", 0) * 0.8 + dist.get("0.5-0.7", 0) * 0.6 + dist.get("<0.5", 0) * 0.3
        return weighted / total
    
    def get_alerts(self) -> List[str]:
        alerts = []
        error_rate = self.get_error_rate()
        if error_rate > 0.25:
            alerts.append("CRITICAL: Error rate >25%")
        elif error_rate > 0.10:
            alerts.append("WARNING: Error rate >10%")
            
        avg_conf = self.get_average_confidence()
        if avg_conf < 0.50:
            alerts.append("CRITICAL: Avg confidence <0.50")
        elif avg_conf < 0.70:
            alerts.append("WARNING: Avg confidence <0.70")
            
        return alerts

# 全局单例
_monitor = None
def get_monitor() -> ClassificationMonitor:
    global _monitor
    if _monitor is None:
        _monitor = ClassificationMonitor()
    return _monitor
