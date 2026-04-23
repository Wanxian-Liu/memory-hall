"""
关键指标阈值系统 - M2.4: Mimir-Core指标阈值定义与动态配置
=============================================================

定义关键指标的阈值体系：
1. 健康分数阈值（多少算健康）
2. 响应时间阈值
3. 错误率阈值
4. 模块调用超时阈值

设计特点：
- 阈值可配置、可持久化
- 动态调整生效（无需重启）
- 阈值变更事件回调
- 与 StatusAggregator 的 Alert 系统深度集成
- 支持阈值配置文件 (YAML/JSON)

使用方式:
    from introspection.thresholds import (
        ThresholdConfig, ThresholdManager, HealthThreshold,
        get_threshold_manager
    )

    # 获取阈值管理器
    tm = get_threshold_manager()

    # 检查指标是否触发阈值
    result = tm.check_health_score(module_id, 0.65)
    if result.triggered:
        print(f"告警: {result.message}")

    # 动态调整阈值
    tm.update_threshold("health_score", 0.6)

    # 加载配置文件
    tm.load_from_file("thresholds.yaml")

    # 导出当前配置
    tm.save_to_file("thresholds.yaml")

集成于:
- M2.1 status_probes.py  (ProbeRegistry 调用计数、超时追踪)
- M2.2 status_api.py      (AlertAggregator 使用本模块的阈值生成告警)
- M2.3 problem_detector.py (问题检测时参考阈值)

拆分说明 (2026-04-24):
    本文件已拆分为多个模块以提高可维护性：
    - threshold_config.py   : ThresholdConfig, ThresholdLevel, ThresholdCheckResult, ThresholdChangeEvent
    - health_thresholds.py : HealthScoreThresholds, ResponseTimeThresholds, ErrorRateThresholds, ModuleTimeoutThresholds, CallCountThresholds
    - threshold_profile.py  : ThresholdProfile, PRESET_PROFILES
    - threshold_manager.py   : ThresholdManager, get_threshold_manager(), reset_threshold_manager(), main()

    为保持向后兼容，所有导出仍然通过本模块提供。
"""

#向后兼容：重新导出所有公共API
from .threshold_config import (
    ThresholdLevel,
    ThresholdCheckResult,
    ThresholdChangeEvent,
    ThresholdConfig,
)

from .health_thresholds import (
    HealthScoreThresholds,
    ResponseTimeThresholds,
    ErrorRateThresholds,
    ModuleTimeoutThresholds,
    CallCountThresholds,
)

from .threshold_profile import (
    ThresholdProfile,
    PRESET_PROFILES,
)

from .threshold_manager import (
    ThresholdManager,
    get_threshold_manager,
    reset_threshold_manager,
    main,
)

__all__ = [
    # threshold_config
    "ThresholdLevel",
    "ThresholdCheckResult",
    "ThresholdChangeEvent",
    "ThresholdConfig",
    # health_thresholds
    "HealthScoreThresholds",
    "ResponseTimeThresholds",
    "ErrorRateThresholds",
    "ModuleTimeoutThresholds",
    "CallCountThresholds",
    # threshold_profile
    "ThresholdProfile",
    "PRESET_PROFILES",
    # threshold_manager
    "ThresholdManager",
    "get_threshold_manager",
    "reset_threshold_manager",
    "main",
]
