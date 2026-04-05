#!/usr/bin/env python3
"""
记忆殿堂-观自在 V3.0.0
健康检查核心模块

六维指标:
1. 任务成功率 (task_success_rate)
2. 平均步数 (steps_per_task)  
3. Token消耗 (token_per_task)
4. 工具失败率 (tool_failure_rate)
5. 验证通过率 (verification_pass_rate)
6. 延迟百分位 (latency_p50/p95/p99)

断路器状态面板:
- 萃取断路器
- 归一断路器
- 通感断路器
- 分类断路器

问题诊断:
- 自适应阈值 (IQR)
- 根因分析
- 修复建议
"""

import os
import json
import time
import threading
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum

# ============ 路径配置 ============
VAULT_DIR = os.path.expanduser("~/.openclaw/memory-vault/data")
METADATA_DIR = os.path.expanduser("~/.openclaw/memory-vault/metadata")
LOGS_DIR = os.path.expanduser("~/.openclaw/memory-vault/logs")
CIRCUIT_FILE = os.path.join(METADATA_DIR, "circuit_breaker.json")
METRICS_FILE = os.path.join(METADATA_DIR, "health_metrics.json")
DIAGNOSIS_FILE = os.path.join(METADATA_DIR, "diagnosis_history.json")


# ============ 枚举定义 ============
class HealthStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ALERT = "alert"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CircuitState(str, Enum):
    CLOSED = "closed"    # 正常
    OPEN = "open"        # 熔断
    HALF_OPEN = "half_open"  # 半开


# ============ 数据类 ============
@dataclass
class SixDimensionData:
    """六维指标数据"""
    task_success_rate: float = 1.0
    steps_per_task_p95: float = 0.0
    token_per_task_p95: float = 0.0
    tool_failure_rate: float = 0.0
    verification_pass_rate: float = 1.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    timestamp: str = ""


@dataclass
class CircuitBreakerInfo:
    """断路器信息"""
    name: str
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[float]
    failure_threshold: int
    recovery_timeout: int
    success_threshold: int


@dataclass
class DiagnosisResult:
    """诊断结果"""
    dimension: str
    status: HealthStatus
    current_value: float
    threshold_warning: float
    threshold_critical: float
    trend: str  # rising, falling, stable
    root_cause: str
    suggestions: List[str]
    timestamp: str = ""


# ============ 自适应阈值计算器 ============
class AdaptiveThresholdCalculator:
    """
    V3.0.0新增：基于IQR的自适应阈值计算
    
    使用四分位距(IQR)方法，根据历史数据动态计算阈值
    """
    
    @staticmethod
    def calculate_iqr(values: List[float]) -> tuple:
        """计算四分位数"""
        if len(values) < 4:
            return None, None, None, None
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        q1_idx = n // 4
        q3_idx = 3 * n // 4
        q1 = sorted_vals[q1_idx]
        q3 = sorted_vals[q3_idx]
        iqr = q3 - q1
        upper_fence = q3 + 1.5 * iqr
        return q1, q3, iqr, upper_fence
    
    @staticmethod
    def calculate_adaptive_thresholds(
        history: List[dict], 
        metric_key: str,
        metric_type: str = "higher_is_worse"  # or "lower_is_worse"
    ) -> Optional[Dict[str, float]]:
        """
        根据历史数据计算自适应阈值
        
        Args:
            history: 历史数据列表
            metric_key: 指标字段名
            metric_type: "higher_is_worse" | "lower_is_worse"
            
        Returns:
            {warning, critical} 或 None
        """
        values = [h.get(metric_key, 0) for h in history if metric_key in h]
        if len(values) < 7:
            return None
        
        _, _, _, upper = AdaptiveThresholdCalculator.calculate_iqr(values)
        if upper is None:
            return None
        
        if metric_type == "higher_is_worse":
            return {
                'warning': upper * 1.3,
                'critical': upper * 2.0
            }
        else:  # lower_is_worse
            return {
                'warning': max(0.85, upper * 0.9),
                'critical': max(0.75, upper * 0.8)
            }


# ============ 断路器 ============
class CircuitBreaker:
    """
    断路器：防止级联故障
    
    状态：
    - CLOSED：正常，允许请求
    - OPEN：熔断，拒绝请求  
    - HALF_OPEN：半开，尝试恢复
    """
    
    def __init__(
        self, 
        name: str, 
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time: Optional[float] = None
        self._lock = threading.Lock()
        
        self._load_state()
    
    def _load_state(self):
        """从文件加载状态"""
        try:
            if os.path.exists(CIRCUIT_FILE):
                with open(CIRCUIT_FILE, 'r', encoding='utf-8') as f:
                    all_states = json.load(f)
                    if self.name in all_states:
                        state = all_states[self.name]
                        self.failure_count = state.get('failure_count', 0)
                        self.success_count = state.get('success_count', 0)
                        self.last_failure_time = state.get('last_failure_time')
                        self.state = CircuitState(state.get('state', 'closed'))
        except Exception:
            pass
    
    def _save_state(self):
        """保存状态到文件"""
        try:
            os.makedirs(os.path.dirname(CIRCUIT_FILE), exist_ok=True)
            all_states = {}
            if os.path.exists(CIRCUIT_FILE):
                with open(CIRCUIT_FILE, 'r', encoding='utf-8') as f:
                    all_states = json.load(f)
            
            all_states[self.name] = {
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'last_failure_time': self.last_failure_time,
                'state': self.state.value
            }
            
            with open(CIRCUIT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_states, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def call(self, func, *args, **kwargs):
        """带断路器的调用"""
        with self._lock:
            # 检查是否应该从OPEN转为HALF_OPEN
            if self.state == CircuitState.OPEN:
                if self.last_failure_time:
                    if time.time() - self.last_failure_time >= self.recovery_timeout:
                        self.state = CircuitState.HALF_OPEN
                        self.success_count = 0
                        self.failure_count = 0
            
            # 如果还是OPEN，拒绝请求
            if self.state == CircuitState.OPEN:
                return {
                    'success': False,
                    'error': f'Circuit breaker OPEN for {self.name}',
                    'state': self.state.value,
                    'bypassed': True  # 断路器熔断旁路
                }
        
        # 执行调用
        try:
            result = func(*args, **kwargs)
            self._on_success()
            result['bypassed'] = False
            return result
        except Exception as e:
            self._on_failure()
            return {
                'success': False,
                'error': str(e),
                'state': self.state.value,
                'bypassed': False
            }
    
    def _on_success(self):
        """成功处理"""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0
            self._save_state()
    
    def _on_failure(self):
        """失败处理"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            
            self._save_state()
    
    def get_info(self) -> CircuitBreakerInfo:
        """获取断路器信息"""
        return CircuitBreakerInfo(
            name=self.name,
            state=self.state,
            failure_count=self.failure_count,
            success_count=self.success_count,
            last_failure_time=self.last_failure_time,
            failure_threshold=self.failure_threshold,
            recovery_timeout=self.recovery_timeout,
            success_threshold=self.success_threshold
        )
    
    def reset(self):
        """重置断路器"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self._save_state()


# ============ 六维指标收集器 ============
class SixDimensionMetrics:
    """
    V3.0.0新增：六维健康指标收集器
    
    覆盖AI Agent特有故障模式
    """
    
    def __init__(self):
        self.metrics_file = METRICS_FILE
    
    def record_task(self, task_data: dict):
        """记录任务执行指标"""
        self._append_metric('tasks', {
            'success': task_data.get('success', False),
            'steps': task_data.get('steps', 0),
            'tokens': task_data.get('tokens', 0),
            'latency_ms': task_data.get('latency_ms', 0),
            'verified': task_data.get('verified', False),
            'timestamp': datetime.now().isoformat()
        })
    
    def record_tool_failure(self, tool_name: str, error: str = ""):
        """记录工具失败"""
        self._append_metric('tool_failures', {
            'tool': tool_name,
            'error': error,
            'timestamp': datetime.now().isoformat()
        })
    
    def get_current_metrics(self) -> SixDimensionData:
        """获取当前六维指标"""
        metrics = self._load_metrics()
        tasks = metrics.get('tasks', [])
        failures = metrics.get('tool_failures', [])
        
        return SixDimensionData(
            task_success_rate=self._calc_success_rate(tasks),
            steps_per_task_p95=self._calc_p95(tasks, 'steps'),
            token_per_task_p95=self._calc_p95(tasks, 'tokens'),
            tool_failure_rate=self._calc_tool_failure_rate(failures, tasks),
            verification_pass_rate=self._calc_verification_rate(tasks),
            latency_p50_ms=self._calc_percentile(tasks, 'latency_ms', 0.5),
            latency_p95_ms=self._calc_percentile(tasks, 'latency_ms', 0.95),
            latency_p99_ms=self._calc_percentile(tasks, 'latency_ms', 0.99),
            timestamp=datetime.now().isoformat()
        )
    
    def get_history_for_adaptive(self, days: int = 7) -> List[dict]:
        """获取历史数据用于自适应阈值计算"""
        metrics = self._load_metrics()
        tasks = metrics.get('tasks', [])
        
        cutoff = time.time() - (days * 86400)
        recent_tasks = []
        
        for task in tasks:
            try:
                ts = task.get('timestamp', '')
                if ts:
                    dt = datetime.fromisoformat(ts)
                    if dt.timestamp() >= cutoff:
                        recent_tasks.append(task)
            except Exception:
                pass
        
        return recent_tasks
    
    def _load_metrics(self) -> dict:
        """加载历史指标"""
        try:
            if os.path.exists(self.metrics_file):
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {'tasks': [], 'tool_failures': []}
    
    def _append_metric(self, metric_type: str, data: dict):
        """追加指标数据"""
        metrics = self._load_metrics()
        metrics.setdefault(metric_type, []).append(data)
        
        # 保留最近1000条
        if len(metrics[metric_type]) > 1000:
            metrics[metric_type] = metrics[metric_type][-1000:]
        
        try:
            os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def _calc_success_rate(self, tasks: list) -> float:
        """计算任务成功率"""
        if not tasks:
            return 1.0
        successes = sum(1 for t in tasks if t.get('success', False))
        return successes / len(tasks)
    
    def _calc_p95(self, tasks: list, key: str) -> float:
        """计算95百分位"""
        return self._calc_percentile(tasks, key, 0.95)
    
    def _calc_percentile(self, tasks: list, key: str, percentile: float) -> float:
        """计算任意百分位"""
        if not tasks:
            return 0.0
        values = sorted([t.get(key, 0) for t in tasks if key in t])
        if not values:
            return 0.0
        idx = int(len(values) * percentile)
        return values[min(idx, len(values) - 1)]
    
    def _calc_tool_failure_rate(self, failures: list, tasks: list) -> float:
        """计算工具失败率"""
        if not tasks:
            return 0.0
        # 按时间窗口计算最近失败
        recent_window = 100  # 最近100个任务
        recent_tasks = tasks[-recent_window:]
        task_count = len(recent_tasks)
        if task_count == 0:
            return 0.0
        
        cutoff = time.time() - 3600  # 最近1小时
        recent_failures = 0
        for f in failures:
            try:
                ts = f.get('timestamp', '')
                if ts:
                    dt = datetime.fromisoformat(ts)
                    if dt.timestamp() >= cutoff:
                        recent_failures += 1
            except Exception:
                pass
        
        return min(1.0, recent_failures / task_count)
    
    def _calc_verification_rate(self, tasks: list) -> float:
        """计算验证通过率"""
        if not tasks:
            return 1.0
        verified = sum(1 for t in tasks if t.get('verified', False))
        return verified / len(tasks)


# ============ 断路器状态面板 ============
class CircuitBreakerPanel:
    """
    V3.0.0新增：断路器状态面板
    
    统一管理和展示所有断路器状态
    """
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {
            '萃取': CircuitBreaker('萃取', failure_threshold=5, recovery_timeout=60),
            '归一': CircuitBreaker('归一', failure_threshold=5, recovery_timeout=60),
            '通感': CircuitBreaker('通感', failure_threshold=5, recovery_timeout=60),
            '分类': CircuitBreaker('分类', failure_threshold=5, recovery_timeout=60),
        }
    
    def get_panel_status(self) -> Dict[str, Any]:
        """获取面板状态"""
        breakers_info = {}
        all_ok = True
        any_open = False
        any_half_open = False
        
        for name, breaker in self.breakers.items():
            info = breaker.get_info()
            breakers_info[name] = asdict(info)
            
            if info.state == CircuitState.OPEN:
                all_ok = False
                any_open = True
            elif info.state == CircuitState.HALF_OPEN:
                all_ok = False
                any_half_open = True
        
        overall = "ok"
        if any_open:
            overall = "open"
        elif any_half_open:
            overall = "half_open"
        
        return {
            "overall": overall,
            "all_ok": all_ok,
            "breakers": breakers_info,
            "summary": {
                "total": len(self.breakers),
                "closed": sum(1 for b in breakers_info.values() if b['state'] == 'closed'),
                "open": sum(1 for b in breakers_info.values() if b['state'] == 'open'),
                "half_open": sum(1 for b in breakers_info.values() if b['state'] == 'half_open'),
            }
        }
    
    def get_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """获取特定断路器"""
        return self.breakers.get(name)
    
    def reset_breaker(self, name: str = None) -> Dict[str, Any]:
        """重置断路器"""
        if name:
            if name in self.breakers:
                self.breakers[name].reset()
                return {"success": True, "message": f"断路器 {name} 已重置"}
            return {"success": False, "message": f"断路器 {name} 不存在"}
        else:
            for breaker in self.breakers.values():
                breaker.reset()
            return {"success": True, "message": "所有断路器已重置"}
    
    def call_with_circuit(self, name: str, func, *args, **kwargs):
        """带断路器调用"""
        if name not in self.breakers:
            return {'success': False, 'error': f'Unknown circuit: {name}'}
        return self.breakers[name].call(func, *args, **kwargs)


# ============ 问题诊断引擎 ============
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
        
        # 固定阈值（自适应阈值计算结果不佳时使用）
        warning = 0.85
        critical = 0.75
        
        # 尝试使用自适应阈值
        adaptive = self.calculator.calculate_adaptive_thresholds(
            history, 'success', 'lower_is_worse'
        )
        if adaptive:
            warning = adaptive['warning']
            critical = adaptive['critical']
        
        status = self._get_status(value, warning, critical, inverted=True)
        trend = self._get_trend(history, 'success', 'higher_is_better')
        
        root_cause, suggestions = self._analyze_low_success(trend, value)
        
        return DiagnosisResult(
            dimension="task_success_rate",
            status=status,
            current_value=value,
            threshold_warning=warning,
            threshold_critical=critical,
            trend=trend,
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
                'diagnoses': [asdict(d) for d in diagnoses]
            })
            
            # 保留最近100条
            if len(history) > 100:
                history = history[-100:]
            
            with open(self.diagnosis_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


# ============ 健康检查器 ============
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
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall,
            "six_dimensions": asdict(current_metrics),
            "circuit_breakers": circuit_status,
            "diagnoses": [asdict(d) for d in diagnoses],
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


# ============ CLI入口 ============
if __name__ == "__main__":
    import sys
    
    checker = HealthChecker()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--circuit":
            result = checker.circuit_panel.get_panel_status()
        elif sys.argv[1] == "--metrics":
            result = checker.metrics.get_current_metrics()
        elif sys.argv[1] == "--diagnose":
            current = checker.metrics.get_current_metrics()
            history = checker.metrics.get_history_for_adaptive()
            diagnoses = checker.diagnostics.diagnose(current, history)
            result = {"diagnoses": [asdict(d) for d in diagnoses]}
        elif sys.argv[1] == "--reset" and len(sys.argv) > 2:
            result = checker.circuit_panel.reset_breaker(sys.argv[2])
        elif sys.argv[1] == "--reset-all":
            result = checker.circuit_panel.reset_breaker()
        else:
            result = checker.get_full_report()
    else:
        result = checker.get_full_report()
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
