"""
记忆殿堂-观自在 V3.0.0 - 自适应阈值计算器
"""

from typing import List, Optional, Dict


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


__all__ = ["AdaptiveThresholdCalculator"]
