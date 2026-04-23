"""
记忆殿堂-观自在 V3.0.0 - 问题诊断引擎
"""

import os
import json
from datetime import datetime
from typing import List, Optional
from .enums import HealthStatus
from .data_classes import SixDimensionData, DiagnosisResult
from .threshold import AdaptiveThresholdCalculator


# 路径配置
METADATA_DIR = os.path.expanduser("~/.openclaw/memory-vault/metadata")
DIAGNOSIS_FILE = os.path.join(METADATA_DIR, "diagnosis_history.json")


class DiagnosticEngine:
    """
    V3.0.0新增：问题诊断引擎
    
    基于六维指标和自适应阈值进行根因分析
    """
    
    def __init__(self):
        self.calculator = AdaptiveThresholdCalculator()
        self.diagnosis_file = DIAGNOSIS_FILE
    
    def diagnose(self, current: SixDimensionData, history: List[dict]) -> List[DiagnosisResult]:
        """执行全面诊断"""
        diagnoses = []
        
        # 1. 任务成功率
        diagnoses.append(self._diagnose_success_rate(current, history))
        
        # 2. 步数效率
        diagnoses.append(self._diagnose_steps(current, history))
        
        # 3. Token消耗
        diagnoses.append(self._diagnose_tokens(current, history))
        
        # 4. 工具失败率
        diagnoses.append(self._diagnose_tool_failure(current, history))
        
        # 5. 验证通过率
        diagnoses.append(self._diagnose_verification(current, history))
        
        # 6. 延迟
        diagnoses.append(self._diagnose_latency(current, history))
        
        return [d for d in diagnoses if d is not None]
    
    def _diagnose_success_rate(
        self, current: SixDimensionData, history: List[dict]
    ) -> Optional[DiagnosisResult]:
        """诊断任务成功率"""
        value = current.task_success_rate
        
        # 固定阈值（success_rate范围是0-1，IQR方法不适用）
        # >95% 为优秀，>85% 为正常，<75% 为危急
        warning = 0.85
        critical = 0.75
        
        # 特殊处理：success_rate >= 95% 视为优秀
        if value >= 0.95:
            status = HealthStatus.OK
            root_cause = "任务成功率优秀，保持良好状态"
            suggestions = ["继续保持"]
        else:
            status = self._get_status(value, warning, critical, inverted=True)
            trend = self._get_trend(history, 'success', 'higher_is_better')
            root_cause, suggestions = self._analyze_low_success(trend, value)
        
        return DiagnosisResult(
            dimension="task_success_rate",
            status=status,
            current_value=value,
            threshold_warning=warning,
            threshold_critical=critical,
            trend="stable" if value >= 0.95 else self._get_trend(history, 'success', 'higher_is_better'),
            root_cause=root_cause,
            suggestions=suggestions,
            timestamp=datetime.now().isoformat()
        )
    
    def _diagnose_steps(
        self, current: SixDimensionData, history: List[dict]
    ) -> Optional[DiagnosisResult]:
        """诊断步数效率"""
        value = current.steps_per_task_p95
        
        warning = 50
        critical = 100
        
        adaptive = self.calculator.calculate_adaptive_thresholds(
            history, 'steps', 'higher_is_worse'
        )
        if adaptive:
            warning = adaptive['warning']
            critical = adaptive['critical']
        
        status = self._get_status(value, warning, critical, inverted=False)
        trend = self._get_trend(history, 'steps', 'higher_is_worse')
        
        root_cause, suggestions = self._analyze_high_steps(trend, value)
        
        return DiagnosisResult(
            dimension="steps_per_task_p95",
            status=status,
            current_value=value,
            threshold_warning=warning,
            threshold_critical=critical,
            trend=trend,
            root_cause=root_cause,
            suggestions=suggestions,
            timestamp=datetime.now().isoformat()
        )
    
    def _diagnose_tokens(
        self, current: SixDimensionData, history: List[dict]
    ) -> Optional[DiagnosisResult]:
        """诊断Token消耗"""
        value = current.token_per_task_p95
        
        warning = 50000
        critical = 100000
        
        adaptive = self.calculator.calculate_adaptive_thresholds(
            history, 'tokens', 'higher_is_worse'
        )
        if adaptive:
            warning = adaptive['warning']
            critical = adaptive['critical']
        
        status = self._get_status(value, warning, critical, inverted=False)
        trend = self._get_trend(history, 'tokens', 'higher_is_worse')
        
        root_cause, suggestions = self._analyze_high_tokens(trend, value)
        
        return DiagnosisResult(
            dimension="token_per_task_p95",
            status=status,
            current_value=value,
            threshold_warning=warning,
            threshold_critical=critical,
            trend=trend,
            root_cause=root_cause,
            suggestions=suggestions,
            timestamp=datetime.now().isoformat()
        )
    
    def _diagnose_tool_failure(
        self, current: SixDimensionData, history: List[dict]
    ) -> Optional[DiagnosisResult]:
        """诊断工具失败率"""
        value = current.tool_failure_rate
        
        warning = 0.15
        critical = 0.25
        
        status = self._get_status(value, warning, critical, inverted=True)
        
        root_cause = "工具执行异常或目标系统不可用"
        suggestions = [
            "检查目标系统状态",
            "查看工具失败日志",
            "考虑暂时禁用故障工具"
        ]
        
        return DiagnosisResult(
            dimension="tool_failure_rate",
            status=status,
            current_value=value,
            threshold_warning=warning,
            threshold_critical=critical,
            trend="unknown",
            root_cause=root_cause,
            suggestions=suggestions,
            timestamp=datetime.now().isoformat()
        )
    
    def _diagnose_verification(
        self, current: SixDimensionData, history: List[dict]
    ) -> Optional[DiagnosisResult]:
        """诊断验证通过率"""
        value = current.verification_pass_rate
        
        warning = 0.90
        critical = 0.80
        
        status = self._get_status(value, warning, critical, inverted=True)
        trend = self._get_trend(history, 'verified', 'higher_is_better')
        
        root_cause, suggestions = self._analyze_low_verification(trend, value)
        
        return DiagnosisResult(
            dimension="verification_pass_rate",
            status=status,
            current_value=value,
            threshold_warning=warning,
            threshold_critical=critical,
            trend=trend,
            root_cause=root_cause,
            suggestions=suggestions,
            timestamp=datetime.now().isoformat()
        )
    
    def _diagnose_latency(
        self, current: SixDimensionData, history: List[dict]
    ) -> Optional[DiagnosisResult]:
        """诊断延迟"""
        value = current.latency_p95_ms
        
        warning = 5000
        critical = 10000
        
        adaptive = self.calculator.calculate_adaptive_thresholds(
            history, 'latency_ms', 'higher_is_worse'
        )
        if adaptive:
            warning = adaptive['warning']
            critical = adaptive['critical']
        
        status = self._get_status(value, warning, critical, inverted=False)
        trend = self._get_trend(history, 'latency_ms', 'higher_is_worse')
        
        root_cause = "任务执行过慢或网络延迟"
        suggestions = [
            "检查系统负载",
            "优化任务流程",
            "考虑增加并行度"
        ]
        
        return DiagnosisResult(
            dimension="latency_p95_ms",
            status=status,
            current_value=value,
            threshold_warning=warning,
            threshold_critical=critical,
            trend=trend,
            root_cause=root_cause,
            suggestions=suggestions,
            timestamp=datetime.now().isoformat()
        )
    
    def _get_status(
        self, value: float, warning: float, critical: float, inverted: bool
    ) -> HealthStatus:
        """判断健康状态"""
        # 特殊处理：0值对于"lower_is_worse"指标是完美状态
        if inverted and value == 0.0:
            return HealthStatus.OK
        
        # 特殊处理：success_rate=1.0是完美状态
        if inverted and value >= 0.99:
            return HealthStatus.OK
            
        if inverted:
            if value <= critical:
                return HealthStatus.CRITICAL
            elif value <= warning:
                return HealthStatus.WARNING
            return HealthStatus.OK
        else:
            if value >= critical:
                return HealthStatus.CRITICAL
            elif value >= warning:
                return HealthStatus.WARNING
            return HealthStatus.OK
    
    def _get_trend(
        self, history: List[dict], key: str, interpretation: str
    ) -> str:
        """判断趋势"""
        if len(history) < 3:
            return "stable"
        
        recent = history[-5:]
        values = [h.get(key, 0) for h in recent if key in h]
        
        if len(values) < 3:
            return "stable"
        
        first_half = sum(values[:len(values)//2]) / (len(values)//2)
        second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)

        if interpretation == 'higher_is_worse':
            if second_half > first_half * 1.2:
                return "rising"
            elif second_half < first_half * 0.8:
                return "falling"
        else:
            if second_half > first_half * 1.2:
                return "rising"
            elif second_half < first_half * 0.8:
                return "falling"
        
        return "stable"
    
    def _analyze_low_success(self, trend: str, value: float) -> tuple:
        """分析低成功率原因"""
        if trend == "rising":
            root = "任务成功率正在恶化，可能是输入质量下降"
            suggestions = ["检查用户输入质量", "审查最近变更"]
        elif trend == "falling":
            root = "任务成功率稳定在低水平"
            suggestions = ["全面审查任务流程", "检查依赖服务状态"]
        else:
            root = "任务成功率波动，无明显趋势"
            suggestions = ["持续监控", "记录更多上下文"]
        
        if value < 0.5:
            root = "任务成功率严重低下，需要立即处理"
            suggestions = ["暂停新任务", "启动根因分析", "检查所有依赖"]
        
        return root, suggestions
    
    def _analyze_high_steps(self, trend: str, value: float) -> tuple:
        """分析高步数原因"""
        if trend == "rising":
            root = "任务步数持续增加，可能存在循环或低效流程"
            suggestions = ["检查是否存在重复步骤", "优化任务拆分策略"]
        elif trend == "falling":
            root = "任务步数优化中"
            suggestions = ["继续保持", "记录优化经验"]
        else:
            root = "任务步数正常但偏高"
            suggestions = ["考虑进一步压缩流程"]
        
        if value > 100:
            root = "单任务步数过长，效率严重低下"
            suggestions = ["拆解大任务", "增加中间验证点"]
        
        return root, suggestions
    
    def _analyze_high_tokens(self, trend: str, value: float) -> tuple:
        """分析高Token消耗原因"""
        if trend == "rising":
            root = "Token消耗持续增长，上下文可能过于冗长"
            suggestions = ["启用上下文压缩", "清理无效历史"]
        elif trend == "falling":
            root = "Token消耗正在优化"
            suggestions = ["继续保持"]
        else:
            root = "Token消耗处于正常偏高水平"
            suggestions = ["监控增长趋势"]
        
        if value > 100000:
            root = "单任务Token消耗过高，有上下文爆炸风险"
            suggestions = ["立即启用压缩", "减少历史记录长度"]
        
        return root, suggestions
    
    def _analyze_low_verification(self, trend: str, value: float) -> tuple:
        """分析低验证通过率原因"""
        if trend == "rising":
            root = "验证通过率恶化，输出质量下降"
            suggestions = ["检查验证规则", "审查最近模型变更"]
        elif trend == "falling":
            root = "验证通过率改善中"
            suggestions = ["继续保持"]
        else:
            root = "验证通过率波动"
            suggestions = ["调整验证阈值", "增加验证样本"]
        
        return root, suggestions
    
    def save_diagnosis(self, diagnoses: List[DiagnosisResult]):
        """保存诊断历史"""
        try:
            os.makedirs(os.path.dirname(self.diagnosis_file), exist_ok=True)
            
            history = []
            if os.path.exists(self.diagnosis_file):
                with open(self.diagnosis_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            history.append({
                'timestamp': datetime.now().isoformat(),
                'diagnoses': [
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
                ]
            })
            
            # 保留最近100条
            if len(history) > 100:
                history = history[-100:]
            
            with open(self.diagnosis_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


__all__ = ["DiagnosticEngine"]
