"""
问题检测器 - Mimir-Core自我感知层 Phase 0
=============================================
集成日志分析，实现问题分类（借鉴claw-code的LaneFailureClass）
"""

import re
import sys
import json
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict


class ProblemSeverity(Enum):
    """问题严重级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ProblemCategory(Enum):
    """问题分类（借鉴LaneFailureClass）"""
    # 执行问题
    EXECUTION_TIMEOUT = "execution_timeout"
    EXECUTION_FAILURE = "execution_failure"
    
    # 资源问题
    RESOURCE_EXHAUSTED = "resource_exhausted"
    MEMORY_LEAK = "memory_leak"
    
    # 网络问题
    NETWORK_TIMEOUT = "network_timeout"
    CONNECTION_REFUSED = "connection_refused"
    
    # 配置问题
    CONFIG_ERROR = "config_error"
    MISSING_DEPENDENCY = "missing_dependency"
    
    # 健康问题
    HEALTH_DEGRADED = "health_degraded"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    
    # 权限问题
    PERMISSION_DENIED = "permission_denied"
    
    # 未知问题
    UNKNOWN = "unknown"


@dataclass
class Problem:
    """问题描述"""
    id: str
    category: ProblemCategory
    severity: ProblemSeverity
    message: str
    timestamp: str
    module: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    count: int = 1


@dataclass
class ProblemReport:
    """问题报告"""
    generated_at: str
    time_window: str  # 分析的时间窗口
    total_problems: int
    critical_count: int
    error_count: int
    warning_count: int
    problems: List[Problem]
    summary: Dict[str, int]  # 按类别统计


class ProblemDetector:
    """问题检测器"""
    
    # 问题模式定义
    PATTERNS = [
        # 超时问题
        (r"timeout|超时|timed out", ProblemCategory.EXECUTION_TIMEOUT, ProblemSeverity.ERROR),
        (r"Gateway timeout|gateway timeout", ProblemCategory.NETWORK_TIMEOUT, ProblemSeverity.ERROR),
        
        # 执行失败
        (r"exec failed|执行失败", ProblemCategory.EXECUTION_FAILURE, ProblemSeverity.ERROR),
        (r"preflight.*complex.*interpreter", ProblemCategory.EXECUTION_FAILURE, ProblemSeverity.WARNING),
        
        # 资源问题
        (r"out of memory|OOM|内存不足", ProblemCategory.RESOURCE_EXHAUSTED, ProblemSeverity.CRITICAL),
        (r"disk full|磁盘已满", ProblemCategory.RESOURCE_EXHAUSTED, ProblemSeverity.CRITICAL),
        (r"Connection refused|连接被拒绝", ProblemCategory.CONNECTION_REFUSED, ProblemSeverity.ERROR),
        
        # 配置问题
        (r"config.*error|配置错误", ProblemCategory.CONFIG_ERROR, ProblemSeverity.ERROR),
        (r"missing.*config|缺少配置", ProblemCategory.CONFIG_ERROR, ProblemSeverity.WARNING),
        
        # 依赖问题
        (r"ModuleNotFoundError|No module named|找不到模块", ProblemCategory.MISSING_DEPENDENCY, ProblemSeverity.ERROR),
        (r"ImportError|导入错误", ProblemCategory.MISSING_DEPENDENCY, ProblemSeverity.ERROR),
        
        # 健康问题
        (r"health.*degraded|健康状态降级", ProblemCategory.HEALTH_DEGRADED, ProblemSeverity.WARNING),
        (r"circuit.*breaker.*open|断路器打开", ProblemCategory.CIRCUIT_BREAKER_OPEN, ProblemSeverity.WARNING),
        (r"failed.*health.*check|健康检查失败", ProblemCategory.HEALTH_DEGRADED, ProblemSeverity.WARNING),
        
        # 权限问题
        (r"Permission denied|权限不足", ProblemCategory.PERMISSION_DENIED, ProblemSeverity.ERROR),
        (r"access denied|访问被拒绝", ProblemCategory.PERMISSION_DENIED, ProblemSeverity.ERROR),
        
        # WebFetch问题（来自learned patterns）
        (r"Blocked.*private.*IP|阻止.*私有.*IP", ProblemCategory.NETWORK_TIMEOUT, ProblemSeverity.WARNING),
        (r"fetch failed|抓取失败", ProblemCategory.NETWORK_TIMEOUT, ProblemSeverity.WARNING),
        (r"web_fetch.*blocked", ProblemCategory.NETWORK_TIMEOUT, ProblemSeverity.WARNING),
    ]
    
    # 日志目录
    LOG_DIRS = [
        Path.home() / ".openclaw" / "logs",
        Path.home() / ".openclaw" / "workspace" / "logs",
    ]
    
    def __init__(self, project_root: str = None):
        if project_root is None:
            self.project_root = Path(__file__).parent.parent.resolve()
        else:
            self.project_root = Path(project_root)
        
        self.problems: List[Problem] = []
        self._problem_id_counter = 0
    
    def analyze_log_file(self, log_path: Path, time_window_hours: int = 24) -> List[Problem]:
        """分析单个日志文件"""
        problems = []
        if not log_path.exists():
            return problems
        
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return problems
        
        # 时间窗口
        cutoff = datetime.now() - timedelta(hours=time_window_hours)
        
        for line_num, line in enumerate(content.splitlines(), 1):
            problem = self._detect_problem(line, log_path.name, line_num)
            if problem:
                # 检查时间戳
                problem_time = self._extract_timestamp(line)
                if problem_time and problem_time < cutoff:
                    continue
                problems.append(problem)
        
        return problems
    
    def analyze_logs(self, time_window_hours: int = 24) -> List[Problem]:
        """分析所有日志"""
        self.problems.clear()
        
        for log_dir in self.LOG_DIRS:
            if not log_dir.exists():
                continue
            
            for log_file in log_dir.rglob("*.log"):
                if "__pycache__" in str(log_file):
                    continue
                self.problems.extend(self.analyze_log_file(log_file, time_window_hours))
        
        return self.problems
    
    def analyze_text(self, text: str, source: str = "input") -> List[Problem]:
        """分析文本（内存中的日志等）"""
        problems = []
        for line_num, line in enumerate(text.splitlines(), 1):
            problem = self._detect_problem(line, source, line_num)
            if problem:
                problems.append(problem)
        return problems
    
    def _detect_problem(self, line: str, source: str, line_num: int) -> Optional[Problem]:
        """检测单行中的问题"""
        for pattern, category, severity in self.PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                self._problem_id_counter += 1
                
                # 提取模块名
                module = self._extract_module_name(line)
                
                # 提取时间戳
                timestamp = self._extract_timestamp_str(line)
                
                return Problem(
                    id=f"P{self._problem_id_counter:05d}",
                    category=category,
                    severity=severity,
                    message=line.strip()[:200],
                    timestamp=timestamp or datetime.now().isoformat(),
                    module=module,
                    details={"source": source, "line": line_num}
                )
        
        return None
    
    def _extract_module_name(self, line: str) -> Optional[str]:
        """从日志行提取模块名"""
        # 尝试匹配 [module] 格式
        match = re.search(r'\[([a-z_]+)\]', line, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # 尝试匹配 module.name 格式
        match = re.search(r'([a-z_]+)\.[a-z_]+\(', line, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        """提取时间戳"""
        timestamp_str = self._extract_timestamp_str(line)
        if timestamp_str:
            try:
                # 尝试多种格式
                for fmt in [
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                ]:
                    try:
                        return datetime.strptime(timestamp_str[:19], fmt)
                    except ValueError:
                        continue
            except Exception:
                pass
        return None
    
    def _extract_timestamp_str(self, line: str) -> Optional[str]:
        """提取时间戳字符串"""
        match = re.search(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', line)
        if match:
            return match.group(0)
        return None
    
    def generate_report(self, time_window_hours: int = 24) -> ProblemReport:
        """生成问题报告"""
        problems = self.analyze_logs(time_window_hours)
        
        # 按类别统计
        category_counts: Dict[str, int] = defaultdict(int)
        severity_counts: Dict[str, int] = defaultdict(int)
        
        for p in problems:
            category_counts[p.category.value] += 1
            severity_counts[p.severity.value] += 1
        
        # 去重并合并相似问题
        merged = self._merge_problems(problems)
        
        return ProblemReport(
            generated_at=datetime.now().isoformat(),
            time_window=f"{time_window_hours}h",
            total_problems=len(merged),
            critical_count=severity_counts["critical"],
            error_count=severity_counts["error"],
            warning_count=severity_counts["warning"],
            problems=merged[:50],  # 限制数量
            summary={
                "categories": dict(category_counts),
                "severities": dict(severity_counts),
            }
        )
    
    def _merge_problems(self, problems: List[Problem]) -> List[Problem]:
        """合并相似问题"""
        merged: Dict[str, Problem] = {}
        
        for p in problems:
            # 按类别+模块+消息前50字符分组
            key = f"{p.category.value}:{p.module or 'unknown'}:{p.message[:50]}"
            
            if key in merged:
                merged[key].count += 1
            else:
                merged[key] = p
        
        return list(merged.values())
    
    def detect_recurring(self, min_count: int = 3) -> List[Problem]:
        """检测反复出现的问题"""
        all_problems = self.analyze_logs(time_window_hours=168)  # 一周
        merged = self._merge_problems(all_problems)
        return [p for p in merged if p.count >= min_count]


def main():
    """CLI入口"""
    detector = ProblemDetector()
    
    print("🔍 分析最近24小时日志...")
    report = detector.generate_report(time_window_hours=24)
    
    print(f"\n📊 问题报告 ({report.time_window})")
    print(f"   总问题数: {report.total_problems}")
    print(f"   🔴 严重: {report.critical_count}")
    print(f"   🟠 错误: {report.error_count}")
    print(f"   🟡 警告: {report.warning_count}")
    
    if report.problems:
        print(f"\n问题分类统计:")
        for cat, count in report.summary["categories"].items():
            print(f"   {cat}: {count}")
    
    print(f"\n主要问题 (前10):")
    sorted_probs = sorted(report.problems, key=lambda x: -x.count)[:10]
    for p in sorted_probs:
        emoji = "🔴" if p.severity == ProblemSeverity.CRITICAL else "🟠" if p.severity == ProblemSeverity.ERROR else "🟡"
        print(f"   {emoji} [{p.category.value}] {p.message[:60]}... (x{p.count})")
    
    return report


if __name__ == "__main__":
    main()
