"""
Day 2 — 反馈闭环编排器 (Feedback Loop Orchestrator)

输入: Day 1 三层聚合器输出 (token/step/episode)
决策: 基于规则 (无LLM)，三层独立决策
输出: 决策日志

决策规则:
  token级: 单条 error_rate > 30% → 标记异常
  step级: 窗口 error_rate 连续3窗上升 → 触发策略微调建议
  episode级: 会话间工具分布剧变 → 触发演化建议
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


# ── 路径 ──────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "aggregator_outputs"
OUTPUT_DIR = BASE_DIR / "decisions"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DECISION_LOG = OUTPUT_DIR / "decision_log.json"


# ── 数据加载 ──────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def load_all_levels() -> Tuple[dict, dict, dict]:
    return (
        load_json(INPUT_DIR / "token_level.json"),
        load_json(INPUT_DIR / "step_level.json"),
        load_json(INPUT_DIR / "episode_level.json"),
    )


# ── Token 级决策 ──────────────────────────────────────────

def decide_token_level(data: dict) -> List[dict]:
    """
    规则: 单条 token error_rate > 30% → 标记异常
    按 step_id 聚合后再判断
    """
    decisions = []
    tokens = data.get("tokens", [])

    # 按 step_id 分组
    step_groups: Dict[str, list] = {}
    for t in tokens:
        sid = t["step_id"]
        step_groups.setdefault(sid, []).append(t)

    for sid, group in step_groups.items():
        total = len(group)
        errors = sum(1 for t in group if t.get("error"))
        error_rate = errors / total if total > 0 else 0.0
        avg_conf = sum(t.get("confidence", 0.0) for t in group) / total

        if error_rate > 0.30:
            decisions.append({
                "level": "token",
                "decision_id": f"tok_anomaly_{sid}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": "token_error_rate_exceeded",
                "target": sid,
                "metrics": {
                    "error_rate": round(error_rate, 3),
                    "total_tokens": total,
                    "error_tokens": errors,
                    "avg_confidence": round(avg_conf, 3),
                },
                "action": "mark_anomaly",
                "severity": "high" if error_rate > 0.60 else "medium",
            })

    return decisions


# ── Step 级决策 ──────────────────────────────────────────

def decide_step_level(data: dict) -> List[dict]:
    """
    规则: 窗口 error_rate 连续3窗上升 → 触发策略微调建议
    """
    decisions = []
    windows = data.get("rolling_windows", [])

    # 检查连续上升趋势
    rising_count = 0
    for i, w in enumerate(windows):
        if w.get("trend") == "up":
            rising_count += 1
        else:
            rising_count = 0

        if rising_count >= 3:
            decisions.append({
                "level": "step",
                "decision_id": f"stp_tuning_{w['window_start']}_{w['window_end']}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": "consecutive_rising_error_window",
                "target": f"window_{w['window_start']}-{w['window_end']}",
                "metrics": {
                    "consecutive_rising_windows": rising_count,
                    "current_window_error_rate": w.get("avg_error_rate", 0),
                    "window_steps": w.get("steps", []),
                },
                "action": "suggest_strategy_tuning",
                "severity": "high",
            })
            # 重置，避免同一段连续上升重复触发
            rising_count = 0

    # 如果整段趋势是持续上升但没达到连续3窗，也做低优先级标记
    if not decisions:
        trends = [w.get("trend") for w in windows if w.get("trend") is not None]
        up_count = sum(1 for t in trends if t == "up")
        if up_count >= 2 and len(windows) >= 3:
            decisions.append({
                "level": "step",
                "decision_id": f"stp_attention_{int(time.time())}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": "elevated_up_trend_ratio",
                "target": "overall_window_sequence",
                "metrics": {
                    "up_windows": up_count,
                    "total_windows": len(windows),
                    "up_ratio": round(up_count / len(windows), 3),
                },
                "action": "note_strategy_concern",
                "severity": "low",
            })

    return decisions


# ── Episode 级决策 ────────────────────────────────────────

def _tool_distribution_distance(a: Dict[str, int], b: Dict[str, int]) -> float:
    """计算两个工具分布之间的差异度 (Jaccard-like)"""
    all_tools = set(a.keys()) | set(b.keys())
    if not all_tools:
        return 0.0

    diff_sum = 0.0
    for tool in all_tools:
        va = a.get(tool, 0)
        vb = b.get(tool, 0)
        diff_sum += abs(va - vb) / (va + vb + 1)  # 归一化差异

    return diff_sum / len(all_tools)


def decide_episode_level(data: dict) -> List[dict]:
    """
    规则: 会话间工具分布剧变 → 触发演化建议
    使用连续 episode 对之间的工具分布距离，超过阈值则触发
    """
    decisions = []
    episodes = data.get("episodes", [])

    if len(episodes) < 2:
        return decisions

    DISTANCE_THRESHOLD = 0.40  # 分布差异阈值

    for i in range(1, len(episodes)):
        prev = episodes[i - 1]
        curr = episodes[i]

        dist = _tool_distribution_distance(
            prev.get("tool_distribution", {}),
            curr.get("tool_distribution", {}),
        )

        if dist > DISTANCE_THRESHOLD:
            decisions.append({
                "level": "episode",
                "decision_id": f"ep_shift_{prev['episode_id']}_to_{curr['episode_id']}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": "tool_distribution_shift",
                "target": f"{prev['episode_id']} → {curr['episode_id']}",
                "metrics": {
                    "distribution_distance": round(dist, 3),
                    "threshold": DISTANCE_THRESHOLD,
                    "prev_tools": prev.get("tool_distribution"),
                    "curr_tools": curr.get("tool_distribution"),
                    "prev_error_rate": prev.get("error_rate"),
                    "curr_error_rate": curr.get("error_rate"),
                },
                "action": "suggest_evolution",
                "severity": "high" if dist > 0.60 else "medium",
            })

    return decisions


# ── 编排器主逻辑 ──────────────────────────────────────────

def run_orchestrator() -> dict:
    """运行完整反馈闭环编排，返回所有决策"""
    token_data, step_data, episode_data = load_all_levels()

    result = {
        "orchestrator_run_id": f"orchestrator_{int(time.time())}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_sources": {
            "token_level": str(INPUT_DIR / "token_level.json"),
            "step_level": str(INPUT_DIR / "step_level.json"),
            "episode_level": str(INPUT_DIR / "episode_level.json"),
        },
        "decisions": {
            "token_level": decide_token_level(token_data),
            "step_level": decide_step_level(step_data),
            "episode_level": decide_episode_level(episode_data),
        },
        "summary": {
            "total_decisions": 0,
            "total_anomalies": 0,
            "total_tuning_suggestions": 0,
            "total_evolution_suggestions": 0,
        },
    }

    # 汇总
    tok = result["decisions"]["token_level"]
    stp = result["decisions"]["step_level"]
    epi = result["decisions"]["episode_level"]

    result["summary"]["total_decisions"] = len(tok) + len(stp) + len(epi)
    result["summary"]["total_anomalies"] = len(tok)
    result["summary"]["total_tuning_suggestions"] = len(stp)
    result["summary"]["total_evolution_suggestions"] = len(epi)

    return result


def save_decision_log(result: dict) -> Path:
    """保存决策日志到文件"""
    # 追加模式：读取已有日志，追加新结果
    existing = []
    if DECISION_LOG.exists():
        try:
            with open(DECISION_LOG, "r") as f:
                existing = json.load(f)
                if not isinstance(existing, list):
                    existing = [existing]
        except (json.JSONDecodeError, Exception):
            existing = []

    existing.append(result)

    with open(DECISION_LOG, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    return DECISION_LOG


def print_decision_report(result: dict) -> None:
    """打印人类可读的决策报告"""
    s = result["summary"]
    print("=" * 60)
    print(f"  反馈闭环编排器 — 运行报告")
    print(f"  运行ID: {result['orchestrator_run_id']}")
    print(f"  时间:   {result['timestamp']}")
    print("=" * 60)

    print(f"\n📊 摘要: 共 {s['total_decisions']} 条决策")
    print(f"   ├─ Token级异常标记:    {s['total_anomalies']}")
    print(f"   ├─ Step级策略微调建议: {s['total_tuning_suggestions']}")
    print(f"   └─ Episode级演化建议:  {s['total_evolution_suggestions']}")

    # Token 级详情
    tok = result["decisions"]["token_level"]
    if tok:
        print(f"\n── Token 级异常 ──")
        for d in tok:
            sev_icon = "🔴" if d["severity"] == "high" else "🟡"
            print(f"  {sev_icon} [{d['target']}] error_rate={d['metrics']['error_rate']:.1%} → {d['action']}")

    # Step 级详情
    stp = result["decisions"]["step_level"]
    if stp:
        print(f"\n── Step 级策略建议 ──")
        for d in stp:
            sev_icon = "🔴" if d["severity"] == "high" else ("🟡" if d["severity"] == "medium" else "⚪")
            print(f"  {sev_icon} [{d['target']}] → {d['action']}")

    # Episode 级详情
    epi = result["decisions"]["episode_level"]
    if epi:
        print(f"\n── Episode 级演化建议 ──")
        for d in epi:
            sev_icon = "🔴" if d["severity"] == "high" else "🟡"
            print(f"  {sev_icon} [{d['target']}] dist={d['metrics']['distribution_distance']:.2f} → {d['action']}")

    print("\n" + "=" * 60)


# ── 入口 ──────────────────────────────────────────────────

if __name__ == "__main__":
    result = run_orchestrator()
    save_decision_log(result)
    print_decision_report(result)
