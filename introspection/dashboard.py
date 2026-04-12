"""
轻量级仪表盘 - M2.3: Mimir-Core Dashboard
=========================================

基于StatusAggregator提供多种格式的仪表盘展示：
- 终端仪表盘（命令行输出）
- HTML简单仪表盘
- 健康分数展示
- TOP问题模块列表

参考claw-code设计：
- 简洁的信息展示
- 异常情况高亮
- 支持多种输出格式

使用方式:
    from introspection.dashboard import Dashboard, DashboardFormat

    # 终端仪表盘
    dashboard = Dashboard()
    dashboard.print_terminal()

    # HTML仪表盘
    html = dashboard.render_html()

    # 健康分数
    score = dashboard.get_health_score()

    # TOP问题模块
    top_problems = dashboard.get_top_problems(limit=5)

    # 获取完整数据
    data = dashboard.get_dashboard_data()
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# 尝试导入 rich 用于美化输出
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class HealthScore:
    """健康分数"""
    overall: float  # 0.0 - 1.0
    grade: str  # A/B/C/D/F
    color: str  # green/yellow/red
    breakdown: Dict[str, float]  # 各维度分数

    @staticmethod
    def score_to_grade(score: float) -> str:
        if score >= 0.9: return "A"
        if score >= 0.8: return "B"
        if score >= 0.6: return "C"
        if score >= 0.4: return "D"
        return "F"

    @staticmethod
    def score_to_color(score: float) -> str:
        if score >= 0.8: return "green"
        if score >= 0.6: return "yellow"
        return "red"


@dataclass
class ProblemModule:
    """问题模块"""
    module_id: str
    state: str
    severity: int  # 1=critical, 2=error, 3=warning
    message: str
    duration: Optional[str] = None  # 问题持续时间

    def __lt__(self, other):
        return self.severity < other.severity


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class Dashboard:
    """
    轻量级仪表盘

    功能：
    1. 终端仪表盘（ASCII艺术 + 高亮）
    2. HTML简单仪表盘
    3. 健康分数计算与展示
    4. TOP问题模块列表
    5. 多种输出格式支持

    设计参考claw-code：
    - 简洁的信息展示
    - 异常情况高亮
    - 状态颜色编码
    """

    # ANSI颜色码
    COLORS = {
        "reset": "\033[0m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "bold": "\033[1m",
        "dim": "\033[2m",
    }

    # 状态emoji
    STATE_EMOJI = {
        "healthy": "✅",
        "degraded": "⚠️",
        "failed": "❌",
        "unavailable": "🚫",
        "unknown": "❓",
        "disabled": "🔌",
    }

    # 状态颜色（终端）
    STATE_COLORS = {
        "healthy": "green",
        "degraded": "yellow",
        "failed": "red",
        "unavailable": "red",
        "unknown": "dim",
        "disabled": "dim",
    }

    def __init__(self, project_root: Optional[str] = None):
        from pathlib import Path
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent.resolve()

        # 延迟导入避免循环依赖
        self._aggregator = None
        self._console = None if not RICH_AVAILABLE else Console()

    @property
    def aggregator(self):
        """获取状态汇总器（延迟加载）"""
        if self._aggregator is None:
            from introspection.status_api import get_aggregator
            self._aggregator = get_aggregator()
        return self._aggregator

    # -------------------------------------------------------------------------
    # 核心数据获取
    # -------------------------------------------------------------------------

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        获取完整仪表盘数据

        Returns:
            包含所有仪表盘数据的字典
        """
        summary = self.aggregator.get_full_summary()

        # 计算健康分数
        health = self._calculate_health_score(summary)

        # 获取问题模块
        problems = self._collect_problem_modules(summary)

        return {
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "health_score": health,
            "top_problems": [p.__dict__ for p in problems],
            "stats": self._compute_stats(summary),
        }

    def _calculate_health_score(self, summary: Dict[str, Any]) -> HealthScore:
        """计算健康分数"""
        total = summary.get("total_modules", 0)
        if total == 0:
            return HealthScore(
                overall=0.0,
                grade="N/A",
                color="dim",
                breakdown={"modules": 0.0, "alerts": 0.0, "availability": 0.0}
            )

        # 各维度权重
        # 1. 模块健康度
        healthy = summary.get("healthy_modules", 0)
        by_state = summary.get("by_state", {})
        degraded = by_state.get("degraded", {}).get("count", 0)
        failed = by_state.get("failed", {}).get("count", 0)
        unknown = by_state.get("unknown", {}).get("count", 0)

        module_score = (healthy * 1.0 + degraded * 0.5 + failed * 0.0 + unknown * 0.3) / total

        # 2. 告警分数
        alerts_active = summary.get("alerts", {}).get("active", 0)
        alert_penalty = min(alerts_active * 0.05, 0.5)  # 每个活跃告警扣0.05，最多扣0.5
        alert_score = 1.0 - alert_penalty

        # 3. 可用性分数
        available = healthy + degraded
        availability_score = available / total

        # 综合分数
        overall = module_score * 0.5 + alert_score * 0.3 + availability_score * 0.2

        return HealthScore(
            overall=round(overall, 3),
            grade=HealthScore.score_to_grade(overall),
            color=HealthScore.score_to_color(overall),
            breakdown={
                "modules": round(module_score, 3),
                "alerts": round(alert_score, 3),
                "availability": round(availability_score, 3),
            }
        )

    def _collect_problem_modules(self, summary: Dict[str, Any]) -> List[ProblemModule]:
        """收集问题模块"""
        problems: List[ProblemModule] = []

        by_state = summary.get("by_state", {})

        # FAILED 模块
        failed_data = by_state.get("failed", {})
        for module_id in failed_data.get("modules", []):
            problems.append(ProblemModule(
                module_id=module_id,
                state="failed",
                severity=1,
                message="模块处于失败状态",
            ))

        # DEGRADED 模块
        degraded_data = by_state.get("degraded", {})
        for module_id in degraded_data.get("modules", []):
            problems.append(ProblemModule(
                module_id=module_id,
                state="degraded",
                severity=2,
                message="模块处于降级状态",
            ))

        # UNAVAILABLE 模块
        unavailable_data = by_state.get("unavailable", {})
        for module_id in unavailable_data.get("modules", []):
            problems.append(ProblemModule(
                module_id=module_id,
                state="unavailable",
                severity=1,
                message="模块不可用",
            ))

        # 按严重程度排序
        problems.sort()
        return problems

    def _compute_stats(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """计算统计数据"""
        by_state = summary.get("by_state", {})
        by_type = summary.get("by_module_type", {})

        # 找出最差的模块类型
        worst_type = None
        worst_score = 1.0
        for mtype, agg in by_type.items():
            if agg.get("health_score", 1.0) < worst_score:
                worst_score = agg.get("health_score", 1.0)
                worst_type = mtype

        # 24小时状态变更统计
        history = summary.get("state_history", {})
        recent_24h = history.get("recent_24h", 0)
        total_history = history.get("total_records", 0)

        return {
            "worst_module_type": worst_type,
            "worst_score": worst_score,
            "state_changes_24h": recent_24h,
            "state_changes_total": total_history,
            "uptime_percentage": summary.get("health_percentage", 0),
        }

    # -------------------------------------------------------------------------
    # 健康分数展示
    # -------------------------------------------------------------------------

    def get_health_score(self) -> HealthScore:
        """获取当前健康分数"""
        summary = self.aggregator.get_full_summary()
        return self._calculate_health_score(summary)

    def print_health_score(self, detailed: bool = False) -> None:
        """打印健康分数"""
        health = self.get_health_score()

        color = self.COLORS.get(health.color, self.COLORS["reset"])
        bold = self.COLORS["bold"]

        print(f"\n{color}{bold}🏥 健康分数: {health.overall:.1%} (Grade: {health.grade}){self.COLORS['reset']}")

        if detailed:
            print(f"\n{self.COLORS['dim']}--- 详细分解 ---{self.COLORS['reset']}")
            for dimension, score in health.breakdown.items():
                bar_len = int(score * 20)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                score_color = self.COLORS.get(HealthScore.score_to_color(score), self.COLORS["reset"])
                print(f"   {dimension:15}: [{score_color}{bar}{self.COLORS['reset']}] {score:.1%}")

    # -------------------------------------------------------------------------
    # TOP问题模块
    # -------------------------------------------------------------------------

    def get_top_problems(self, limit: int = 5) -> List[ProblemModule]:
        """获取TOP问题模块"""
        summary = self.aggregator.get_full_summary()
        problems = self._collect_problem_modules(summary)
        return problems[:limit]

    def print_top_problems(self, limit: int = 5) -> None:
        """打印TOP问题模块"""
        problems = self.get_top_problems(limit)

        if not problems:
            print(f"\n{self.COLORS['green']}✅ 没有问题模块，系统运行正常！{self.COLORS['reset']}")
            return

        print(f"\n{self.COLORS['bold']}🚨 TOP {len(problems)} 问题模块:{self.COLORS['reset']}")

        severity_labels = {1: "🔴 CRITICAL", 2: "❌ ERROR", 3: "⚠️ WARNING"}
        state_emoji = self.STATE_EMOJI

        for i, problem in enumerate(problems, 1):
            severity = severity_labels.get(problem.severity, "❓")
            emoji = state_emoji.get(problem.state, "❓")
            state_color = self.COLORS.get(self.STATE_COLORS.get(problem.state, "white"), self.COLORS["reset"])

            print(f"   {i}. {severity} {emoji} {problem.module_id}")
            print(f"      {problem.message}")
            if problem.duration:
                print(f"      持续时间: {problem.duration}")
            print()

    # -------------------------------------------------------------------------
    # 终端仪表盘 - 基础版（无需rich）
    # -------------------------------------------------------------------------

    def print_terminal(self, use_rich: bool = False) -> None:
        """
        打印终端仪表盘

        Args:
            use_rich: 是否使用rich库美化输出
        """
        if use_rich and RICH_AVAILABLE:
            self._print_terminal_rich()
        else:
            self._print_terminal_plain()

    def _print_terminal_plain(self) -> None:
        """基础终端仪表盘（ANSI彩色）"""
        data = self.get_dashboard_data()
        summary = data["summary"]
        health = data["health_score"]
        stats = data["stats"]

        # 顶部边框
        self._print_divider("═")
        print(f"{self.COLORS['bold']}{self.COLORS['cyan']}    🧵 Mimir-Core 轻量级仪表盘{self.COLORS['reset']}")
        self._print_divider("═")

        # 时间戳
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"⏰ 更新时间: {ts}")
        print()

        # 健康分数 - 居中大号展示
        color = self.COLORS.get(health.color, self.COLORS["reset"])
        bold = self.COLORS["bold"]
        print(f"{' '*20}{color}{bold}┌─────────────────────┐{self.COLORS['reset']}")
        print(f"{' '*20}{color}{bold}│  🏥 HEALTH SCORE   │{self.COLORS['reset']}")
        print(f"{' '*20}{color}{bold}│    {health.overall:>5.1%}  [{health.grade}]   │{self.COLORS['reset']}")
        print(f"{' '*20}{color}{bold}└─────────────────────┘{self.COLORS['reset']}")
        print()

        # 状态概览
        self._print_section_header("📊 系统状态概览")
        by_state = summary.get("by_state", {})

        total = summary.get("total_modules", 0)
        healthy = summary.get("healthy_modules", 0)
        print(f"   总模块数: {total}  |  健康: {healthy}  |  健康率: {summary.get('health_percentage', 0):.1f}%")
        print()

        # 状态条形图
        self._print_state_bar(by_state, total)

        # 模块类型健康度
        self._print_section_header("📦 模块类型健康度")
        by_type = summary.get("by_module_type", {})
        if by_type:
            for mtype, agg in sorted(by_type.items()):
                score = agg.get("health_score", 0)
                score_color = self.COLORS.get(HealthScore.score_to_color(score), self.COLORS["reset"])
                bar = self._make_bar(score, width=15)
                h = agg.get("healthy", 0)
                d = agg.get("degraded", 0)
                f = agg.get("failed", 0)
                print(f"   {mtype:12}: [{score_color}{bar}{self.COLORS['reset']}] {score:.2f}  (✅{h} ⚠️{d} ❌{f})")
        else:
            print(f"   {self.COLORS['dim']}无模块数据{self.COLORS['reset']}")

        # 问题模块
        print()
        self._print_section_header("🚨 问题模块")
        problems = data.get("top_problems", [])
        if problems:
            severity_labels = {1: "🔴", 2: "❌", 3: "⚠️"}
            for p in problems[:5]:
                sev = severity_labels.get(p["severity"], "❓")
                emoji = self.STATE_EMOJI.get(p["state"], "❓")
                print(f"   {sev} {emoji} {p['module_id']}: {p['message']}")
        else:
            print(f"   {self.COLORS['green']}✅ 无问题模块{self.COLORS['reset']}")

        # 告警
        print()
        self._print_section_header("🚨 活跃告警")
        alerts = summary.get("alerts", {})
        active_count = alerts.get("active", 0)
        by_level = alerts.get("by_level", {})

        if active_count == 0:
            print(f"   {self.COLORS['green']}✅ 无活跃告警{self.COLORS['reset']}")
        else:
            print(f"   总数: {active_count}")
            level_counts = []
            if by_level.get("critical"): level_counts.append(f"🔴{by_level['critical']}")
            if by_level.get("error"): level_counts.append(f"❌{by_level['error']}")
            if by_level.get("warning"): level_counts.append(f"⚠️{by_level['warning']}")
            if by_level.get("info"): level_counts.append(f"ℹ️{by_level['info']}")
            print(f"   明细: {' '.join(level_counts)}")

        # 底部边框
        print()
        self._print_divider("═")

    def _print_divider(self, char: str) -> None:
        """打印分隔线"""
        width = 60
        print(f"{self.COLORS['dim']}{char * width}{self.COLORS['reset']}")

    def _print_section_header(self, title: str) -> None:
        """打印分节标题"""
        print(f"{self.COLORS['bold']}{self.COLORS['cyan']}{title}{self.COLORS['reset']}")

    def _print_state_bar(self, by_state: Dict[str, Any], total: int) -> None:
        """打印状态条形图"""
        if total == 0:
            print(f"   {self.COLORS['dim']}[无数据]{self.COLORS['reset']}")
            return

        # 计算每种状态的宽度
        state_widths = {}
        for state, data in by_state.items():
            count = data.get("count", 0)
            state_widths[state] = int((count / total) * 30) if total > 0 else 0

        # 组合条形图
        bar_parts = []
        for state in ["healthy", "degraded", "failed", "unavailable", "unknown", "disabled"]:
            if state in state_widths and state_widths[state] > 0:
                color = self.COLORS.get(self.STATE_COLORS.get(state, "white"), self.COLORS["reset"])
                bar_parts.append(f"{color}{'█' * state_widths[state]}{self.COLORS['reset']}")

        bar_str = "".join(bar_parts) if bar_parts else f"{self.COLORS['dim']}[无数据]{self.COLORS['reset']}"
        print(f"   状态分布: [{bar_str}]")

        # 图例
        legend_parts = []
        for state in ["healthy", "degraded", "failed", "unavailable", "unknown", "disabled"]:
            if state in by_state:
                count = by_state[state].get("count", 0)
                emoji = self.STATE_EMOJI.get(state, "❓")
                legend_parts.append(f"{emoji}{count}")
        print(f"   {' '.join(legend_parts)}")
        print()

    def _make_bar(self, value: float, width: int = 15) -> str:
        """创建进度条"""
        filled = int(value * width)
        return "█" * filled + "░" * (width - filled)

    # -------------------------------------------------------------------------
    # 终端仪表盘 - Rich版（美化）
    # -------------------------------------------------------------------------

    def _print_terminal_rich(self) -> None:
        """Rich美化版终端仪表盘"""
        data = self.get_dashboard_data()
        summary = data["summary"]
        health = data["health_score"]
        stats = data["stats"]
        problems = data.get("top_problems", [])

        console = self._console

        # 标题
        console.print(Panel(
            f"[bold cyan]🧵 Mimir-Core Dashboard[/bold cyan]\n"
            f"[dim]更新于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
            box=box.DOUBLE,
            style="cyan"
        ))

        # 健康分数面板
        health_color = {
            "green": "[green]",
            "yellow": "[yellow]",
            "red": "[red]",
        }.get(health.color, "[white]")

        console.print(Panel(
            f"{health_color}[bold]HEALTH SCORE[/bold]: {health.overall:.1%} (Grade: {health.grade})[/]\n"
            f"[dim]模块: {health.breakdown['modules']:.1%} | "
            f"告警: {health.breakdown['alerts']:.1%} | "
            f"可用: {health.breakdown['availability']:.1%}[/dim]",
            title="🏥 System Health",
            box=box.ROUNDED,
            style=health.color
        ))

        # 模块类型健康度表格
        by_type = summary.get("by_module_type", {})
        if by_type:
            table = Table(title="📦 Module Type Health", box=box.SIMPLE)
            table.add_column("Type", style="cyan")
            table.add_column("Score", justify="right")
            table.add_column("Health Bar", justify="left")
            table.add_column("Details")

            for mtype, agg in sorted(by_type.items()):
                score = agg.get("health_score", 0)
                score_str = f"{score:.2f}"
                bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
                details = f"✅{agg.get('healthy', 0)} ⚠️{agg.get('degraded', 0)} ❌{agg.get('failed', 0)}"

                score_color = "green" if score >= 0.8 else "yellow" if score >= 0.6 else "red"
                table.add_row(mtype, f"[{score_color}]{score_str}[/{score_color}]", bar, details)

            console.print(table)

        # 问题模块
        if problems:
            console.print(Panel(
                "\n".join([
                    f"[red]❌ {p['module_id']}[/red]: {p['message']}"
                    for p in problems[:5]
                ]),
                title=f"🚨 Top {len(problems)} Problem Modules",
                box=box.ROUNDED,
                style="red"
            ))
        else:
            console.print(Panel(
                "[green]✅ No problem modules - System is healthy![/green]",
                title="🚨 Problem Modules",
                box=box.ROUNDED,
                style="green"
            ))

        # 告警
        alerts = summary.get("alerts", {})
        active = alerts.get("active", 0)
        if active > 0:
            alert_info = []
            by_level = alerts.get("by_level", {})
            if by_level.get("critical"): alert_info.append(f"🔴 Critical: {by_level['critical']}")
            if by_level.get("error"): alert_info.append(f"❌ Error: {by_level['error']}")
            if by_level.get("warning"): alert_info.append(f"⚠️ Warning: {by_level['warning']}")

            console.print(Panel(
                "\n".join(alert_info),
                title=f"🚨 Active Alerts ({active})",
                box=box.ROUNDED,
                style="yellow"
            ))

        console.print()  # 空行

    # -------------------------------------------------------------------------
    # HTML仪表盘
    # -------------------------------------------------------------------------

    def render_html(self, title: str = "Mimir-Core Dashboard") -> str:
        """
        渲染HTML仪表盘

        Returns:
            HTML字符串
        """
        data = self.get_dashboard_data()
        return self._build_html(data, title)

    def _build_html(self, data: Dict[str, Any], title: str) -> str:
        """构建HTML页面"""
        summary = data["summary"]
        health = data["health_score"]
        stats = data["stats"]
        problems = data.get("top_problems", [])
        by_state = summary.get("by_state", {})
        by_type = summary.get("by_module_type", {})
        alerts = summary.get("alerts", {})

        # 颜色变量
        health_color = {
            "green": "#22c55e",
            "yellow": "#eab308",
            "red": "#ef4444",
            "dim": "#6b7280",
        }.get(health.color, "#6b7280")

        # 生成状态条
        total = summary.get("total_modules", 0)
        state_bars = self._html_state_bars(by_state, total)

        # 生成模块类型表格行
        type_rows = ""
        for mtype, agg in sorted(by_type.items()):
            score = agg.get("health_score", 0)
            score_color = "#22c55e" if score >= 0.8 else "#eab308" if score >= 0.6 else "#ef4444"
            h = agg.get("healthy", 0)
            d = agg.get("degraded", 0)
            f = agg.get("failed", 0)
            bar = self._html_progress_bar(score)

            type_rows += f"""
            <tr>
                <td><span class="badge">{mtype}</span></td>
                <td><span class="score" style="color:{score_color}">{score:.2f}</span></td>
                <td>{bar}</td>
                <td><span class="stat healthy">✅{h}</span> <span class="stat degraded">⚠️{d}</span> <span class="stat failed">❌{f}</span></td>
            </tr>"""

        # 生成问题模块列表
        problem_rows = ""
        for p in problems[:10]:
            sev_class = "critical" if p["severity"] == 1 else "error" if p["severity"] == 2 else "warning"
            sev_icon = "🔴" if p["severity"] == 1 else "❌" if p["severity"] == 2 else "⚠️"
            emoji = self.STATE_EMOJI.get(p["state"], "❓")
            problem_rows += f"""
            <tr class="{sev_class}">
                <td>{sev_icon} {p['module_id']}</td>
                <td><span class="badge {p['state']}">{emoji} {p['state']}</span></td>
                <td>{p['message']}</td>
            </tr>"""

        # 生成告警列表
        alert_items = alerts.get("items", [])
        alert_rows = ""
        for alert in alert_items[:10]:
            level = alert.get("level", "info")
            level_icon = {"critical": "🔴", "error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(level, "❓")
            alert_rows += f"""
            <tr>
                <td>{level_icon} [{level.upper()}]</td>
                <td>{alert.get('module_id', 'N/A')}</td>
                <td>{alert.get('message', '')}</td>
                <td>{alert.get('timestamp', '')[:19]}</td>
            </tr>"""

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}

        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ color: #38bdf8; font-size: 2em; }}
        .header .timestamp {{ color: #64748b; margin-top: 5px; }}

        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }}
        .card h2 {{ font-size: 1em; color: #94a3b8; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 0.05em; }}

        .health-score {{ text-align: center; }}
        .health-score .big-number {{ font-size: 4em; font-weight: bold; color: {health_color}; line-height: 1; }}
        .health-score .grade {{ font-size: 1.5em; color: {health_color}; margin-top: 5px; }}
        .health-score .breakdown {{ margin-top: 15px; font-size: 0.85em; color: #94a3b8; }}

        .stat-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #334155; }}
        .stat-row:last-child {{ border-bottom: none; }}
        .stat-value {{ font-weight: bold; }}

        .state-bar {{ height: 30px; background: #334155; border-radius: 6px; overflow: hidden; display: flex; }}
        .state-segment {{ height: 100%; transition: width 0.3s; }}
        .state-healthy {{ background: #22c55e; }}
        .state-degraded {{ background: #eab308; }}
        .state-failed {{ background: #ef4444; }}
        .state-unavailable {{ background: #dc2626; }}
        .state-unknown {{ background: #6b7280; }}
        .state-disabled {{ background: #374151; }}

        .legend {{ display: flex; gap: 15px; margin-top: 10px; font-size: 0.85em; flex-wrap: wrap; }}

        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ color: #64748b; font-weight: 500; font-size: 0.85em; text-transform: uppercase; }}
        .badge {{ background: #334155; padding: 3px 8px; border-radius: 4px; font-size: 0.85em; }}
        .badge.healthy {{ background: #166534; color: #bbf7d0; }}
        .badge.degraded {{ background: #854d0e; color: #fef08a; }}
        .badge.failed {{ background: #991b1b; color: #fecaca; }}
        .badge.unavailable {{ background: #7f1d1d; color: #fecaca; }}
        .score {{ font-weight: bold; }}

        .progress-bar {{ background: #334155; height: 8px; border-radius: 4px; overflow: hidden; }}
        .progress-fill {{ height: 100%; background: #22c55e; transition: width 0.3s; }}

        tr.critical {{ background: rgba(239, 68, 68, 0.1); }}
        tr.error {{ background: rgba(239, 68, 68, 0.05); }}
        tr.warning {{ background: rgba(234, 179, 8, 0.05); }}

        .stat {{ margin-right: 8px; }}
        .stat.healthy {{ color: #22c55e; }}
        .stat.degraded {{ color: #eab308; }}
        .stat.failed {{ color: #ef4444; }}

        .footer {{ text-align: center; margin-top: 30px; color: #64748b; font-size: 0.85em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧵 Mimir-Core Dashboard</h1>
            <div class="timestamp">更新时间: {timestamp}</div>
        </div>

        <div class="grid">
            <div class="card health-score">
                <h2>🏥 健康分数</h2>
                <div class="big-number">{health.overall:.1%}</div>
                <div class="grade">Grade: {health.grade}</div>
                <div class="breakdown">
                    <div>模块: {health.breakdown['modules']:.1%}</div>
                    <div>告警: {health.breakdown['alerts']:.1%}</div>
                    <div>可用性: {health.breakdown['availability']:.1%}</div>
                </div>
            </div>

            <div class="card">
                <h2>📊 系统概览</h2>
                <div class="stat-row">
                    <span>总模块数</span>
                    <span class="stat-value">{summary.get('total_modules', 0)}</span>
                </div>
                <div class="stat-row">
                    <span>健康模块</span>
                    <span class="stat-value" style="color:#22c55e">{summary.get('healthy_modules', 0)}</span>
                </div>
                <div class="stat-row">
                    <span>健康率</span>
                    <span class="stat-value">{summary.get('health_percentage', 0):.1f}%</span>
                </div>
                <div class="stat-row">
                    <span>活跃告警</span>
                    <span class="stat-value" style="color:{'#ef4444' if alerts.get('active', 0) > 0 else '#22c55e'}">{alerts.get('active', 0)}</span>
                </div>
                <div class="stat-row">
                    <span>24h状态变更</span>
                    <span class="stat-value">{stats.get('state_changes_24h', 0)}</span>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📈 状态分布</h2>
            <div class="state-bar">{state_bars}</div>
            <div class="legend">
                {self._html_state_legend(by_state)}
            </div>
        </div>

        <div class="card">
            <h2>📦 模块类型健康度</h2>
            <table>
                <thead>
                    <tr>
                        <th>类型</th>
                        <th>分数</th>
                        <th>进度</th>
                        <th>统计</th>
                    </tr>
                </thead>
                <tbody>
                    {type_rows or '<tr><td colspan="4" style="text-align:center;color:#64748b">无数据</td></tr>'}
                </tbody>
            </table>
        </div>

        {'<div class="card"><h2>🚨 问题模块</h2><table><thead><tr><th>模块</th><th>状态</th><th>描述</th></tr></thead><tbody>' + problem_rows + '</tbody></table></div>' if problems else '<div class="card"><h2>🚨 问题模块</h2><p style="color:#22c55e;text-align:center">✅ 无问题模块</p></div>'}

        {'<div class="card"><h2>🚨 活跃告警</h2><table><thead><tr><th>级别</th><th>模块</th><th>消息</th><th>时间</th></tr></thead><tbody>' + alert_rows + '</tbody></table></div>' if alert_rows else ''}

        <div class="footer">
            Mimir-Core Dashboard | Auto-refresh recommended (interval: 30s)
        </div>
    </div>
</body>
</html>"""

    def _html_state_bars(self, by_state: Dict[str, Any], total: int) -> str:
        """生成HTML状态条"""
        if total == 0:
            return '<div class="state-segment state-unknown" style="width:100%"></div>'

        bars = []
        for state in ["healthy", "degraded", "failed", "unavailable", "unknown", "disabled"]:
            if state in by_state:
                count = by_state[state].get("count", 0)
                width = (count / total) * 100
                if width > 0:
                    bars.append(f'<div class="state-segment state-{state}" style="width:{width:.1f}%"></div>')
        return "".join(bars)

    def _html_state_legend(self, by_state: Dict[str, Any]) -> str:
        """生成HTML状态图例"""
        legend = []
        emoji_map = {"healthy": "✅", "degraded": "⚠️", "failed": "❌", "unavailable": "🚫", "unknown": "❓", "disabled": "🔌"}
        for state, data in by_state.items():
            count = data.get("count", 0)
            emoji = emoji_map.get(state, "❓")
            legend.append(f'<span>{emoji} {state}: {count}</span>')
        return "".join(legend)

    def _html_progress_bar(self, value: float) -> str:
        """生成HTML进度条"""
        pct = value * 100
        color = "#22c55e" if value >= 0.8 else "#eab308" if value >= 0.6 else "#ef4444"
        return f'<div class="progress-bar"><div class="progress-fill" style="width:{pct:.0f}%;background:{color}"></div></div>'

    def save_html(self, filepath: str, title: str = "Mimir-Core Dashboard") -> None:
        """保存HTML仪表盘到文件"""
        html = self.render_html(title)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML dashboard saved to: {filepath}")

    # -------------------------------------------------------------------------
    # 便捷输出方法
    # -------------------------------------------------------------------------

    def print_summary(self) -> None:
        """打印简洁摘要"""
        data = self.get_dashboard_data()
        summary = data["summary"]
        health = data["health_score"]

        color = self.COLORS.get(health.color, self.COLORS["reset"])
        status_icon = "✅" if health.overall >= 0.8 else "⚠️" if health.overall >= 0.6 else "❌"

        print(f"\n{color}{status_icon} Mimir-Core: {health.overall:.1%} (Grade {health.grade}){self.COLORS['reset']}")
        print(f"   模块: {summary.get('healthy_modules', 0)}/{summary.get('total_modules', 0)} 健康")
        print(f"   告警: {summary.get('alerts', {}).get('active', 0)} 活跃")
        print()

    def print_json(self) -> None:
        """打印JSON格式数据"""
        import json
        data = self.get_dashboard_data()
        print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# CLI入口
# ---------------------------------------------------------------------------

def main():
    """CLI入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Mimir-Core Dashboard")
    parser.add_argument("-f", "--format", choices=["terminal", "rich", "html", "summary", "json"], default="terminal", help="输出格式")
    parser.add_argument("-o", "--output", help="HTML输出文件路径")
    parser.add_argument("--title", default="Mimir-Core Dashboard", help="HTML页面标题")
    parser.add_argument("--problems", type=int, default=5, help="TOP问题模块数量")

    args = parser.parse_args()

    dashboard = Dashboard()

    if args.format == "terminal":
        dashboard.print_terminal(use_rich=False)
    elif args.format == "rich":
        dashboard.print_terminal(use_rich=True)
    elif args.format == "html":
        if args.output:
            dashboard.save_html(args.output, args.title)
        else:
            print(dashboard.render_html(args.title))
    elif args.format == "summary":
        dashboard.print_summary()
    elif args.format == "json":
        dashboard.print_json()


if __name__ == "__main__":
    main()
