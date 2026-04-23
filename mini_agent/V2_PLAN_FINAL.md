# Mimir V2 最终方案 - Ralph Round 1-2 锤炼报告

**日期**: 2026-04-14  
**锤炼轮次**: Round 1 + Round 2  
**最终状态**: ✅ 通过

---

## 一、锤炼过程回顾

### Round 1 发现的问题

| 来源 | 问题 | 严重程度 |
|------|------|---------|
| 方向辩证者 | Phase 2（WorkerManager等）必须删除 | P0 |
| 方向辩证者 | 领域边界模糊 | P1 |
| 方向辩证者 | 学习素材缺口 | P1 |
| 架构架构师 | Trajectory模块缺失 | P0 |
| 架构架构师 | Nudge模块缺失 | P0 |
| 架构架构师 | Hindsight模块缺失 | P0 |
| Hermes研究员 | 通用设计不适合Mimir | P1 |

### Round 2 发现的问题

| 来源 | 问题 | 严重程度 |
|------|------|---------|
| 框架验证者 | Trajectory Recorder应提升为独立模块 | P1 |
| 框架验证者 | 用sensory扩展Nudge Engine | P1 |
| 框架验证者 | 用audit扩展Hindsight Analyzer | P1 |
| GDI研究员 | GDI命名不一致（文档vs代码） | P0 |
| GDI研究员 | 阈值碎片化 | P1 |
| GDI研究员 | Skills与Capsule耦合不足 | P1 |

---

## 二、最终修正后的架构

### 2.1 顶层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Mimir V2 记忆领域自进化Agent                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Agent Loop                              │  │
│  │   Observe → Decide → Act → Evaluate → Learn               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    核心模块                               │  │
│  │                                                          │  │
│  │  ┌─────────────────┐  ┌─────────────────┐              │  │
│  │  │ Trajectory      │  │ GDI Optimizer   │              │  │
│  │  │ Recorder        │  │                 │              │  │
│  │  │ (独立基础设施)   │  │ repair<0.5     │              │  │
│  │  │                 │  │ optimize<0.7   │              │  │
│  │  │ ⭐ 提升为独立    │  │ innovate≥0.7  │              │  │
│  │  └─────────────────┘  └─────────────────┘              │  │
│  │                                                          │  │
│  │  ┌─────────────────┐  ┌─────────────────┐              │  │
│  │  │ Skills System   │  │ Capsule Maker   │              │  │
│  │  │                 │◄─┼►│                 │              │  │
│  │  │ 学习OpenClaw    │  │ 产出高质量      │              │  │
│  │  │ 学习记忆殿堂    │  │ Capsule         │              │  │
│  │  └─────────────────┘  └─────────────────┘              │  │
│  │           │                                               │  │
│  │           ▼                                               │  │
│  │  ┌─────────────────┐  ┌─────────────────┐              │  │
│  │  │ Nudge Engine   │  │ Hindsight      │              │  │
│  │  │ (扩展sensory)  │  │ (扩展audit)   │              │  │
│  │  └─────────────────┘  └─────────────────┘              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    学习素材                               │  │
│  │  OpenClaw Skills (~20个) + 记忆殿堂Capsule (GDI>0.8)   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    产出                                  │  │
│  │  高质量Capsule + 记忆领域Skills                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 GDI体系（修正后）

**⚠️ 重要修正：统一命名和阈值**

| 设计文档 | 实际代码 | 说明 |
|---------|---------|------|
| gdi_intrinsic | **confidence** | 功能完整性（目标≥0.92） |
| gdi_usage | **success_streak** | 使用频率 |
| gdi_social | **reputation** | 社会认可（来自hub） |
| gdi_freshness | **env_fingerprint** | 新鲜度 |

**阈值体系（修正后）：**

| 类别 | 阈值 | 说明 |
|------|------|------|
| repair | confidence < 0.50 | 需要修复 |
| optimize | 0.50 ≤ confidence < 0.70 | 可以优化 |
| innovate | confidence ≥ 0.70 | 可尝试创新 |

**熔断机制：**
- repairLoopThreshold = 0.50
- 当repair事件占比≥50%时，强制切换到innovate策略

### 2.3 Skills-Capsule协作流程

```
1. signals检测 → 生成信号列表
       ↓
2. 基因匹配 → scoreGene = exact_match + tag_overlap + semantic
       ↓
3. 候选提取 → extractCapabilityCandidates生成新能力候选
       ↓
4. 演化执行 → 基于选定基因执行
       ↓
5. 胶囊固化 → 计算confidence/success_streak
       ↓
6. 排名检索 → rank = confidence × streak × reputation
```

---

## 三、禁止列表（已验证）

```
❌ WorkerManager（外部Agent管理）
❌ TaskScheduler（任务调度）
❌ Bootstrap Loader（引导加载）
❌ 多平台Gateway
❌ 通用任务执行
❌ 脱离记忆领域的设计
```

---

## 四、实现路径（修正后）

### Phase 1: 核心循环
```
Week 1-4:
1. agent_loop.py - Agent主循环
2. trajectory.py - 轨迹记录（提升为独立基础设施）
3. gdi_optimizer.py - GDI决策（修正阈值）
4. memory_tools.py - 记忆工具
```

### Phase 2: 主动机制（扩展现有模块）
```
Week 5-8:
5. nudge_engine.py - 主动提醒（扩展sensory）
6. hindsight.py - 后见分析（扩展audit）
7. capsule_maker.py - 胶囊生成
```

### Phase 3: 学习系统
```
Week 9-12:
8. skills_system.py - 技能系统（强化Skills-Capsule耦合）
9. openclaw_learner.py - 学习OpenClaw
10. memory_palace_learner.py - 学习记忆殿堂
```

### Phase 4: 优化
```
Week 13-16:
11. 轨迹分析优化
12. 策略学习
13. 整体集成测试
```

---

## 五、关键修正清单

| 修正项 | Round | 修正内容 |
|--------|-------|---------|
| 删除Phase 2 | R1 | 删除WorkerManager/TaskScheduler/Bootstrap |
| 补充P0模块 | R1 | Trajectory + Nudge + Hindsight |
| Trajectory提升 | R2 | 提升为独立基础设施（非Skills内部） |
| sensory扩展Nudge | R2 | 用现有sensory模块扩展 |
| audit扩展Hindsight | R2 | 用现有audit模块扩展 |
| GDI命名统一 | R2 | gdi_intrinsic→confidence等 |
| GDI阈值统一 | R2 | repair<0.5, optimize<0.7, innovate≥0.7 |
| Skills-Capsule耦合 | R2 | 端到端闭环 |

---

## 六、领域边界检查

每个新功能必须通过：
```
1. 是记忆相关的吗？     → 如果不是，不做
2. 能产出Capsule吗？   → 如果不能，不做
3. GDI能评估吗？       → 如果不能，不做
4. 需要外部Agent吗？   → 如果需要，不做
5. 会变成通用Agent吗？ → 如果会，不做
```

---

## 七、成功标准

1. **自运转**: Agent能无人干预地持续优化记忆
2. **GDI提升**: 平均confidence分数持续提升
3. **轨迹完整**: 所有决策可追溯
4. **提醒有效**: Nudge带来有价值的进化机会
5. **Skills-Capsule闭环**: 从能力发现到胶囊固化端到端

---

## 八、最终评估

| 评估项 | 结果 |
|--------|------|
| 方向正确性 | ✅ 通过 |
| 架构合理性 | ✅ 通过 |
| 实现可行性 | ✅ 通过（带条件） |
| GDI体系 | ✅ 修正后通过 |
| 风险控制 | ✅ 通过 |

**Ralph锤炼结论**: 连续2轮无重大错误，方案通过。

---

_文档版本: 1.0_  
_锤炼轮次: Round 1 + Round 2_  
_设计: 琬弦 (织界者)_  
_灵感: Hermes Agent by NousResearch + 辩证验证_
