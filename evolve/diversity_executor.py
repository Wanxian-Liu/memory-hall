"""
Day 3: 多样性驱动执行器 (Diversity-Driven Executor)

从 Day 2 的决策日志中读取触发信号，使用熵正则化采样选择策略，
而非传统的 argmax。

核心设计：
1. 读取 decision_log.json 中的触发信号
2. 对策略选择用熵正则化采样（按分布采样，保留多样性）
3. 记录每次执行的效果分数 effectiveness_score
4. 失败时标记该路径为低分
5. 提供3种策略模板：重试、切换、降级

与 DecisionRing/ExecutionRing 的关系：
- DecisionRing 是"决策层"（分析根因 + 生成策略候选）
- DiversityExecutor 是"执行选择层"（从候选中用熵采样选择具体动作）
- ExecutionRing 是"执行层"（实际执行动作）

Author: MimirAether (self-evolved)
"""

from __future__ import annotations

import json
import math
import logging
import os
import random
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# 策略模板
# ============================================================================

class StrategyTemplate(str, Enum):
    """3种策略模板"""
    RETRY = "retry"          # 重试：同一工具再试一次
    SWITCH = "switch"        # 切换：换一个工具做同样的事
    DOWNGRADE = "downgrade"  # 降级：用更简单的方式完成


# ============================================================================
# 触发信号
# ============================================================================

@dataclass
class TriggerSignal:
    """来自 Day 2 决策日志的触发信号"""
    signal_id: str
    level: str              # token / step / episode
    trigger_type: str       # 触发类型（如 token_error_rate_exceeded）
    target: str             # 触发目标
    severity: str           # low / medium / high
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    @property
    def severity_score(self) -> float:
        """严重程度数值化"""
        mapping = {"low": 0.3, "medium": 0.6, "high": 0.9}
        return mapping.get(self.severity, 0.5)


# ============================================================================
# 策略选择器（熵正则化采样）
# ============================================================================

@dataclass
class StrategyOption:
    """一个策略选项"""
    template: StrategyTemplate
    action: str                     # 具体动作描述
    confidence: float = 0.5        # 初始置信度
    effectiveness_history: List[float] = field(default_factory=list)
    failure_count: int = 0
    success_count: int = 0

    @property
    def avg_effectiveness(self) -> float:
        if not self.effectiveness_history:
            return self.confidence
        return sum(self.effectiveness_history) / len(self.effectiveness_history)

    @property
    def is_low_score(self) -> bool:
        """是否已被标记为低分路径"""
        if len(self.effectiveness_history) < 3:
            return False
        return self.avg_effectiveness < 0.3


@dataclass
class EntropySamplingConfig:
    """熵正则化采样配置"""
    temperature: float = 1.0        # 温度参数：越高越随机
    entropy_weight: float = 0.3     # 熵正则化权重
    min_exploration_prob: float = 0.1  # 最小探索概率
    history_window: int = 10        # 效果历史窗口
    low_score_penalty: float = 0.5  # 低分路径惩罚系数


class EntropySampler:
    """
    熵正则化采样器
    
    不取 argmax，而是按 softmax 分布采样，保留策略多样性。
    """

    def __init__(self, config: Optional[EntropySamplingConfig] = None):
        self.config = config or EntropySamplingConfig()

    def sample(
        self,
        options: List[StrategyOption],
        forced_strategy: Optional[StrategyTemplate] = None
    ) -> Tuple[StrategyOption, float, float]:
        """
        从策略选项中用熵正则化采样选择一个。
        
        Args:
            options: 策略选项列表
            forced_strategy: 强制使用某模板（可选）
            
        Returns:
            (选中的选项, 选中概率, 熵值)
        """
        if not options:
            raise ValueError("No strategy options to sample from")

        if forced_strategy:
            filtered = [o for o in options if o.template == forced_strategy]
            if filtered:
                return filtered[0], 1.0, 0.0

        # 计算每个选项的得分
        scores = []
        for opt in options:
            score = self._compute_score(opt)
            scores.append(score)

        # Softmax 转概率分布
        probs = self._softmax(scores, temperature=self.config.temperature)

        # 熵正则化：在概率分布中加入探索项
        if self.config.entropy_weight > 0:
            entropy = self._compute_entropy(probs)
            exploration_bonus = self.config.entropy_weight * entropy
            # 将探索奖励均匀分配给所有选项
            for i in range(len(probs)):
                probs[i] += exploration_bonus / len(probs)
            # 重新归一化
            total = sum(probs)
            probs = [p / total for p in probs]

        # 确保最小探索概率
        for i in range(len(probs)):
            probs[i] = max(probs[i], self.config.min_exploration_prob / len(options))
        total = sum(probs)
        probs = [p / total for p in probs]

        # 按概率分布采样（不取 argmax）
        idx = random.choices(range(len(options)), weights=probs, k=1)[0]
        selected = options[idx]
        selected_prob = probs[idx]
        entropy = self._compute_entropy(probs)

        logger.debug(
            f"EntropySampler: selected={selected.template.value}/{selected.action} "
            f"prob={selected_prob:.3f} entropy={entropy:.3f} "
            f"distribution={[f'{p:.2f}' for p in probs]}"
        )

        return selected, selected_prob, entropy

    def _compute_score(self, opt: StrategyOption) -> float:
        """计算策略选项的得分"""
        base = opt.avg_effectiveness

        # 低分路径惩罚
        if opt.is_low_score:
            base *= self.config.low_score_penalty

        # 成功率加成
        total = opt.success_count + opt.failure_count
        if total > 0:
            success_rate = opt.success_count / total
            base = 0.7 * base + 0.3 * success_rate

        return max(base, 0.01)  # 保证非零

    def _softmax(self, scores: List[float], temperature: float = 1.0) -> List[float]:
        """Softmax 归一化"""
        if temperature <= 0:
            temperature = 0.1
        scaled = [s / temperature for s in scores]
        max_s = max(scaled)
        exps = [math.exp(s - max_s) for s in scaled]  # 数值稳定
        total = sum(exps)
        return [e / total for e in exps]

    def _compute_entropy(self, probs: List[float]) -> float:
        """计算概率分布的熵"""
        entropy = 0.0
        for p in probs:
            if p > 0:
                entropy -= p * math.log(p)
        return entropy / math.log(len(probs)) if len(probs) > 1 else 0.0


# ============================================================================
# 执行记录
# ============================================================================

@dataclass
class ExecutionRecord:
    """一次执行的完整记录"""
    execution_id: str
    timestamp: float
    trigger_signal: TriggerSignal
    selected_strategy: StrategyTemplate
    selected_action: str
    selection_probability: float
    entropy_at_selection: float
    effectiveness_score: float = 0.0
    success: bool = False
    error: Optional[str] = None
    feedback_data: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# 多样性驱动执行器
# ============================================================================

class DiversityExecutor:
    """
    多样性驱动执行器 (Day 3)
    
    核心流程：
    1. 从 decision_log.json 读取触发信号
    2. 根据信号类型构建策略候选列表
    3. 用熵正则化采样选择策略
    4. 执行并记录 effectiveness_score
    5. 失败时标记低分路径
    
    3种策略模板：
    - RETRY: 同一工具再试一次（带退避）
    - SWITCH: 换一个工具做同样的事
    - DOWNGRADE: 用更简单的方式完成
    """

    def __init__(
        self,
        decision_log_path: Optional[str] = None,
        sampler: Optional[EntropySampler] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.decision_log_path = decision_log_path or self._default_log_path()
        self.sampler = sampler or EntropySampler()
        self.config = config or {}

        # 策略选项注册表
        self._strategies: Dict[str, List[StrategyOption]] = {}
        self._init_default_strategies()

        # 执行历史
        self._execution_history: List[ExecutionRecord] = []
        self._max_history = 100

        # 触发信号缓存
        self._last_signals: List[TriggerSignal] = []

    def _default_log_path(self) -> str:
        """默认决策日志路径"""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(
            base, "feedback", "decisions", "decision_log.json"
        )

    def _init_default_strategies(self):
        """初始化默认策略选项"""
        # 每种触发类型对应一组策略选项
        default_strategies = {
            "token_error_rate_exceeded": [
                StrategyOption(
                    template=StrategyTemplate.RETRY,
                    action="retry_with_backoff",
                    confidence=0.6,
                ),
                StrategyOption(
                    template=StrategyTemplate.SWITCH,
                    action="switch_to_alternative_tool",
                    confidence=0.5,
                ),
                StrategyOption(
                    template=StrategyTemplate.DOWNGRADE,
                    action="use_simpler_query",
                    confidence=0.4,
                ),
            ],
            "elevated_up_trend_ratio": [
                StrategyOption(
                    template=StrategyTemplate.RETRY,
                    action="monitor_and_retry",
                    confidence=0.5,
                ),
                StrategyOption(
                    template=StrategyTemplate.SWITCH,
                    action="switch_monitoring_strategy",
                    confidence=0.6,
                ),
                StrategyOption(
                    template=StrategyTemplate.DOWNGRADE,
                    action="reduce_monitoring_frequency",
                    confidence=0.7,
                ),
            ],
            "tool_distribution_shift": [
                StrategyOption(
                    template=StrategyTemplate.RETRY,
                    action="rebalance_tool_usage",
                    confidence=0.4,
                ),
                StrategyOption(
                    template=StrategyTemplate.SWITCH,
                    action="switch_tool_set",
                    confidence=0.6,
                ),
                StrategyOption(
                    template=StrategyTemplate.DOWNGRADE,
                    action="use_fallback_tools_only",
                    confidence=0.5,
                ),
            ],
            "default": [
                StrategyOption(
                    template=StrategyTemplate.RETRY,
                    action="generic_retry",
                    confidence=0.5,
                ),
                StrategyOption(
                    template=StrategyTemplate.SWITCH,
                    action="generic_switch",
                    confidence=0.5,
                ),
                StrategyOption(
                    template=StrategyTemplate.DOWNGRADE,
                    action="generic_downgrade",
                    confidence=0.5,
                ),
            ],
        }

        for trigger_type, options in default_strategies.items():
            self.register_strategies(trigger_type, options)

    # ========== 策略注册 ==========

    def register_strategies(
        self,
        trigger_type: str,
        options: List[StrategyOption],
    ):
        """为某触发类型注册策略选项"""
        if trigger_type not in self._strategies:
            self._strategies[trigger_type] = []
        self._strategies[trigger_type].extend(options)

    def register_strategy(
        self,
        trigger_type: str,
        option: StrategyOption,
    ):
        """为某触发类型注册单个策略选项"""
        if trigger_type not in self._strategies:
            self._strategies[trigger_type] = []
        self._strategies[trigger_type].append(option)

    # ========== 触发信号读取 ==========

    def load_trigger_signals(self) -> List[TriggerSignal]:
        """
        从 decision_log.json 读取触发信号
        
        Returns:
            List[TriggerSignal]: 解析后的触发信号列表
        """
        log_path = Path(self.decision_log_path)
        if not log_path.exists():
            logger.warning(f"Decision log not found: {log_path}")
            return []

        try:
            with open(log_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read decision log: {e}")
            return []

        signals = []

        # 处理单条记录或列表
        records = data if isinstance(data, list) else [data]

        for record in records:
            decisions = record.get("decisions", {})
            timestamp_str = record.get("timestamp", "")

            try:
                from datetime import datetime
                ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")).timestamp()
            except (ValueError, AttributeError):
                ts = time.time()

            for level in ["token_level", "step_level", "episode_level"]:
                level_decisions = decisions.get(level, [])
                for dec in level_decisions:
                    signal = TriggerSignal(
                        signal_id=dec.get("decision_id", f"sig_{int(ts)}"),
                        level=level.replace("_level", ""),
                        trigger_type=dec.get("trigger", "unknown"),
                        target=dec.get("target", ""),
                        severity=dec.get("severity", "medium"),
                        metrics=dec.get("metrics", {}),
                        timestamp=ts,
                    )
                    signals.append(signal)

        self._last_signals = signals
        logger.info(f"Loaded {len(signals)} trigger signals from decision log")
        return signals

    # ========== 核心执行流程 ==========

    def decide_and_execute(
        self,
        signal: Optional[TriggerSignal] = None,
        dry_run: bool = False,
    ) -> ExecutionRecord:
        """
        核心方法：基于触发信号做策略选择并"执行"。
        
        流程：
        1. 如果没有提供信号，从日志加载最新信号
        2. 根据触发类型获取策略候选
        3. 用熵正则化采样选择策略
        4. 模拟执行并记录 effectiveness_score
        5. 失败时标记低分路径
        
        Args:
            signal: 触发信号（可选，不提供则自动加载）
            dry_run: 仅采样不执行
            
        Returns:
            ExecutionRecord: 执行记录
        """
        # 1. 获取触发信号
        if signal is None:
            signals = self.load_trigger_signals()
            if not signals:
                # 无信号时生成模拟信号用于测试
                signal = TriggerSignal(
                    signal_id="sig_simulated",
                    level="token",
                    trigger_type="default",
                    target="simulated",
                    severity="low",
                    metrics={"error_rate": 0.1},
                    timestamp=time.time(),
                )
            else:
                # 取最严重的信号
                signal = max(signals, key=lambda s: s.severity_score)

        # 2. 获取策略候选
        options = self._get_strategies_for_signal(signal)
        if not options:
            logger.warning(f"No strategies for trigger: {signal.trigger_type}")
            options = self._strategies.get("default", [])

        # 3. 熵正则化采样
        selected, prob, entropy = self.sampler.sample(options)

        # 4. 模拟执行
        record = ExecutionRecord(
            execution_id=f"exec_{signal.signal_id}_{int(time.time() * 1000000) % 1000000}",
            timestamp=time.time(),
            trigger_signal=signal,
            selected_strategy=selected.template,
            selected_action=selected.action,
            selection_probability=prob,
            entropy_at_selection=entropy,
        )

        if not dry_run:
            self._simulate_execution(record, selected)

        # 5. 记录历史
        self._execution_history.append(record)
        if len(self._execution_history) > self._max_history:
            self._execution_history.pop(0)

        # 6. 更新策略选项的效果历史
        self._update_strategy_history(selected, record.effectiveness_score, record.success)

        logger.info(
            f"decide_and_execute: signal={signal.trigger_type} "
            f"strategy={selected.template.value}/{selected.action} "
            f"effectiveness={record.effectiveness_score:.3f} "
            f"success={record.success}"
        )

        return record

    def _get_strategies_for_signal(
        self,
        signal: TriggerSignal,
    ) -> List[StrategyOption]:
        """根据触发信号获取对应的策略候选列表"""
        # 先精确匹配
        if signal.trigger_type in self._strategies:
            return list(self._strategies[signal.trigger_type])

        # 模糊匹配：按关键词
        for key, options in self._strategies.items():
            if key != "default" and (
                key in signal.trigger_type or signal.trigger_type in key
            ):
                return list(options)

        # 回退到默认策略
        return list(self._strategies.get("default", []))

    def _simulate_execution(
        self,
        record: ExecutionRecord,
        selected: StrategyOption,
    ) -> None:
        """模拟执行并评分"""
        # 基于策略类型和历史的模拟评分
        base_score = selected.avg_effectiveness

        # RETRY 策略：成功率中等，但可能重复失败
        if selected.template == StrategyTemplate.RETRY:
            success_prob = 0.4 + 0.3 * selected.avg_effectiveness
            record.success = random.random() < success_prob

        # SWITCH 策略：成功率较高，但成本也高
        elif selected.template == StrategyTemplate.SWITCH:
            success_prob = 0.5 + 0.3 * selected.avg_effectiveness
            record.success = random.random() < success_prob

        # DOWNGRADE 策略：成功率最高，但效果打折
        elif selected.template == StrategyTemplate.DOWNGRADE:
            success_prob = 0.7 + 0.2 * selected.avg_effectiveness
            record.success = random.random() < success_prob

        # 计算 effectiveness_score
        if record.success:
            # 成功时，效果与策略置信度正相关
            record.effectiveness_score = 0.5 + 0.5 * selected.avg_effectiveness
        else:
            # 失败时，效果打折扣
            record.effectiveness_score = max(0.1, base_score * 0.3)
            record.error = "Simulated execution failed"

    def _update_strategy_history(
        self,
        option: StrategyOption,
        effectiveness_score: float,
        success: bool,
    ) -> None:
        """更新策略选项的效果历史"""
        option.effectiveness_history.append(effectiveness_score)

        # 限制历史窗口
        window = self.sampler.config.history_window
        if len(option.effectiveness_history) > window:
            option.effectiveness_history = option.effectiveness_history[-window:]

        # 更新成功/失败计数
        if success:
            option.success_count += 1
        else:
            option.failure_count += 1

    # ========== 查询接口 ==========

    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计信息"""
        if not self._execution_history:
            return {"total_executions": 0}

        total = len(self._execution_history)
        successes = sum(1 for r in self._execution_history if r.success)
        avg_effectiveness = sum(
            r.effectiveness_score for r in self._execution_history
        ) / total

        # 策略分布
        strategy_dist = {}
        for r in self._execution_history:
            key = r.selected_strategy.value
            strategy_dist[key] = strategy_dist.get(key, 0) + 1

        return {
            "total_executions": total,
            "success_count": successes,
            "success_rate": successes / total if total > 0 else 0,
            "avg_effectiveness": avg_effectiveness,
            "strategy_distribution": strategy_dist,
        }

    def get_recent_executions(self, n: int = 10) -> List[ExecutionRecord]:
        """获取最近 n 次执行记录"""
        return list(self._execution_history[-n:])

    def get_low_score_paths(self) -> List[StrategyOption]:
        """获取所有被标记为低分的路径"""
        low_score = []
        for options in self._strategies.values():
            for opt in options:
                if opt.is_low_score:
                    low_score.append(opt)
        return low_score

    def reset_history(self):
        """重置执行历史（保留策略注册）"""
        self._execution_history.clear()
        for options in self._strategies.values():
            for opt in options:
                opt.effectiveness_history.clear()
                opt.failure_count = 0
                opt.success_count = 0
        logger.info("DiversityExecutor history reset")


# ============================================================================
# 便捷入口
# ============================================================================

def create_executor(
    decision_log_path: Optional[str] = None,
    temperature: float = 1.0,
) -> DiversityExecutor:
    """创建 DiversityExecutor 的便捷工厂函数"""
    config = EntropySamplingConfig(temperature=temperature)
    sampler = EntropySampler(config)
    return DiversityExecutor(
        decision_log_path=decision_log_path,
        sampler=sampler,
    )


def demo():
    """简单的演示：创建执行器并执行几次"""
    executor = create_executor(temperature=1.2)

    print("=" * 60)
    print("Diversity-Driven Executor Demo")
    print("=" * 60)

    for i in range(5):
        record = executor.decide_and_execute(dry_run=False)
        status = "✓" if record.success else "✗"
        print(
            f"  [{i+1}] {record.selected_strategy.value:10s} | "
            f"{record.selected_action:30s} | "
            f"effect={record.effectiveness_score:.2f} {status}"
        )

    stats = executor.get_execution_stats()
    print(f"\nStats: {stats['total_executions']} executions, "
          f"{stats['success_rate']:.0%} success rate, "
          f"avg effectiveness={stats['avg_effectiveness']:.2f}")
    print(f"Strategy distribution: {stats['strategy_distribution']}")

    return executor


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo()
