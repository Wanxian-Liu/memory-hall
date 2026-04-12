"""
记忆殿堂-观自在 V3.0.0 - 六维指标收集器
"""

import os
import json
import time
from datetime import datetime
from typing import List
from .data_classes import SixDimensionData


# 路径配置
METADATA_DIR = os.path.expanduser("~/.openclaw/memory-vault/metadata")
METRICS_FILE = os.path.join(METADATA_DIR, "health_metrics.json")


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


__all__ = ["SixDimensionMetrics"]
