# Evomap 架构设计

## 一、节点类型

| 节点 | 说明 | 衰减周期 |
|------|------|---------|
| thought | 想法/灵感 | 30天 |
| task | 任务项 | 90天 |
| decision | 决策点 | 180天 |
| milestone | 里程碑 | 365天 |

## 二、反馈来源

| 来源 | 权重 | 说明 |
|------|------|------|
| 用户确认 | 40% | 用户明确确认的价值 |
| 使用频率 | 35% | 被引用/使用的次数 |
| 时效性衰减 | 25% | 时间流逝带来的价值下降 |

## 三、晋升条件

一个节点晋升为更高价值需要满足：

1. 完成度 = 100%
2. 用户确认次数 ≥ 3
3. 综合评分 ≥ 0.7
4. 创建时间 ≥ 7天

## 四、数据模型

```python
@dataclass
class EvoNode:
    id: str
    type: str  # thought/task/decision/milestone
    content: str
    created_at: datetime
    updated_at: datetime
    completion: float  # 0.0 - 1.0
    user_confirmations: int
    usage_count: int
    score: float  # 综合评分
```

## 五、调度器

- **事件驱动**: 节点更新时触发重新计算
- **定时任务**: 每天凌晨4点执行衰减计算
- **手动触发**: 用户可强制刷新节点评分
