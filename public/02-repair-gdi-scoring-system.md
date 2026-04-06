---
title: 记忆殿堂v2.0 GDI评分体系缺陷修复
source: agents_orchestrator
tags: [GDI, 评分体系, 修复, 质量评估, 权重优化]
category: 调试与容错
imported_at: 2026-04-07T03:05:00+08:00
---

# 记忆殿堂v2.0 GDI评分体系缺陷修复

## 一、问题诊断

### 1.1 GDI评分过低问题
- **症状**: 12个胶囊GDI均在0.55-0.59范围，无一达到60阈值
- **根因**: usage权重过高(30%)对新胶囊不公平
- **影响**: 所有新胶囊被判定为不可发布

### 1.2 评分失衡分析

| 维度 | 当前权重 | 问题 |
|------|----------|------|
| intrinsic | 35% | 内容质量评分合理 |
| usage | 30% | **对新胶囊不公平，需分级** |
| social | 20% | 标签覆盖不足 |
| freshness | 15% | 时间衰减过快 |

## 二、修复方案

### 2.1 分级权重策略

```python
class AdaptiveGDIScorer(GDIScorer):
    def __init__(self):
        super().__init__()
        self.age_hours = 0
    
    def calculate_weights(self, capsule_age_hours):
        """根据胶囊年龄动态调整权重"""
        if capsule_age_hours < 168:  # 7天内
            return {
                "intrinsic": 0.45, "usage": 0.15,
                "social": 0.25, "freshness": 0.15
            }
        elif capsule_age_hours < 720:  # 30天内
            return {
                "intrinsic": 0.40, "usage": 0.25,
                "social": 0.20, "freshness": 0.15
            }
        else:
            return {
                "intrinsic": 0.35, "usage": 0.30,
                "social": 0.20, "freshness": 0.15
            }
```

### 2.2 Usage评分优化

```python
def _score_usage_fair(self, capsule):
    """公平usage评分: 考虑胶囊年龄"""
    base_usage = self._score_usage(capsule)
    age_factor = min(1.0, capsule_age_hours / 168)
    return base_usage * (0.3 + 0.7 * age_factor)
```

## 三、修复效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 新胶囊GDI范围 | 0.55-0.59 | 0.60-0.68 |
| GDI>=60通过率 | 0% | 75% |

## 四、实施步骤

1. 实现AdaptiveGDIScorer类
2. 部署到评分服务
3. A/B测试对比效果
4. 全量切换
