"""
记忆殿堂-观自在 V3.0.0 - 健康检查器
"""

from typing import Any, Dict, List
from .enums import HealthStatus
from .data_classes import DiagnosisResult
from .metrics import SixDimensionMetrics
from .panel import CircuitBreakerPanel
from .diagnostic import DiagnosticEngine


class HealthChecker:
    """
    V3.0.0主健康检查器
    
    整合六维指标、断路器面板和问题诊断
    """
    
    def __init__(self):
        self.metrics = SixDimensionMetrics()
        self.circuit_panel = CircuitBreakerPanel()
        self.diagnostics = DiagnosticEngine()
    
    def get_full_report(self) -> Dict[str, Any]:
        """获取完整健康报告"""
        # 收集六维指标
        current_metrics = self.metrics.get_current_metrics()
        history = self.metrics.get_history_for_adaptive()
        
        # 执行诊断
        diagnoses = self.diagnostics.diagnose(current_metrics, history)
        self.diagnostics.save_diagnosis(diagnoses)
        
        # 获取断路器面板状态
        circuit_status = self.circuit_panel.get_panel_status()
        
        # 综合判断
        overall = self._compute_overall_status(diagnoses, circuit_status)
        
        return {
            "version": "3.0.0",
            "timestamp": current_metrics.timestamp,
            "overall_status": overall,
            "six_dimensions": {
                'task_success_rate': current_metrics.task_success_rate,
                'steps_per_task_p95': current_metrics.steps_per_task_p95,
                'token_per_task_p95': current_metrics.token_per_task_p95,
                'tool_failure_rate': current_metrics.tool_failure_rate,
                'verification_pass_rate': current_metrics.verification_pass_rate,
                'latency_p50_ms': current_metrics.latency_p50_ms,
                'latency_p95_ms': current_metrics.latency_p95_ms,
                'latency_p99_ms': current_metrics.latency_p99_ms,
                'timestamp': current_metrics.timestamp,
            },
            "circuit_breakers": circuit_status,
            "diagnoses": [
                {
                    'dimension': d.dimension,
                    'status': d.status.value,
                    'current_value': d.current_value,
                    'threshold_warning': d.threshold_warning,
                    'threshold_critical': d.threshold_critical,
                    'trend': d.trend,
                    'root_cause': d.root_cause,
                    'suggestions': d.suggestions,
                    'timestamp': d.timestamp,
                }
                for d in diagnoses
            ],
            "recommendations": self._generate_recommendations(diagnoses, circuit_status)
        }
    
    def get_quick_status(self) -> Dict[str, Any]:
        """快速状态检查"""
        circuit_status = self.circuit_panel.get_panel_status()
        current_metrics = self.metrics.get_current_metrics()
        
        return {
            "overall": circuit_status["overall"],
            "task_success_rate": current_metrics.task_success_rate,
            "tool_failure_rate": current_metrics.tool_failure_rate,
            "circuits_open": circuit_status["summary"]["open"]
        }
    
    def record_task_completion(
        self,
        success: bool,
        steps: int,
        tokens: int,
        latency_ms: float,
        verified: bool = False
    ):
        """记录任务完成"""
        self.metrics.record_task({
            'success': success,
            'steps': steps,
            'tokens': tokens,
            'latency_ms': latency_ms,
            'verified': verified
        })
    
    def record_failure(self, tool_name: str, error: str = ""):
        """记录工具失败"""
        self.metrics.record_tool_failure(tool_name, error)
    
    def _compute_overall_status(
        self, 
        diagnoses: List[DiagnosisResult],
        circuit_status: Dict[str, Any]
    ) -> str:
        """计算综合状态"""
        # 断路器OPEN
        if circuit_status["summary"]["open"] > 0:
            return "degraded"
        
        # 检查诊断结果
        statuses = [d.status for d in diagnoses]
        
        if HealthStatus.CRITICAL in statuses:
            return "critical"
        elif HealthStatus.ALERT in statuses:
            return "alert"
        elif HealthStatus.WARNING in statuses:
            return "warning"
        
        return "ok"
    
    def _generate_recommendations(
        self,
        diagnoses: List[DiagnosisResult],
        circuit_status: Dict[str, Any]
    ) -> List[str]:
        """生成建议"""
        recommendations = []
        
        # 从诊断结果提取
        for d in diagnoses:
            if d.status != HealthStatus.OK:
                for suggestion in d.suggestions[:2]:
                    if suggestion not in recommendations:
                        recommendations.append(suggestion)
        
        # 断路器建议
        if circuit_status["summary"]["open"] > 0:
            recommendations.append("有断路器熔断，考虑重置或等待自动恢复")
        
        return recommendations[:5]  # 最多5条


__all__ = ["HealthChecker"]
