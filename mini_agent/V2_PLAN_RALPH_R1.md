# Mimir V2 方案锤炼 - Ralph Round 1 综合报告

**日期**: 2026-04-14  
**角色**: 架构架构师 + 方向辩证者 + Hermes研究员  
**目标**: 锤炼出正确的Mimir V2方向

---

## 一、三方评估汇总

### 1.1 方向辩证者问题

| 问题 | 严重程度 | 具体表现 |
|------|---------|---------|
| 复制风险 | **中** | 不是复制Hermes，是用AI编程框架改造记忆系统 |
| 边界清晰度 | **模糊** | "记忆领域"定义太宽泛 |
| 初心保持 | **部分脱离** | 从"知识管理层"变成"数字生命体" |
| 学习素材 | **勉强充足** | 缺乏"记忆如何驱动智能涌现"的深度研究 |

### 1.2 架构架构师问题

| 问题 | 优先级 | 具体表现 |
|------|--------|---------|
| Trajectory模块缺失 | **P0** | 没有专门的轨迹记录组件 |
| Nudge模块缺失 | **P0** | 没有基于GDI的自动干预机制 |
| Hindsight模块缺失 | **P0** | 没有独立的复盘组件 |
| sessions_spawn不稳定 | **P1** | 20% fitness失败率 |
| pipeline模块缺失 | **P1** | DERIVED引擎需要数据驱动 |

### 1.3 Hermes研究员发现

**Hermes核心能力TOP3：**
1. Agent Loop（自主执行）
2. Skills自创建（从经验学习）
3. Trajectory记录（轨迹保存）

**不适合Mimir的设计：**
- 多平台Gateway（不是记忆系统的事）
- RL训练（改用GDI驱动）
- 通用任务执行（应该专注记忆领域）

---

## 二、关键问题识别

### 问题1：Phase 2必须砍掉

**原因**：外部Agent管理不是记忆系统的事，是另一个产品

```
❌ 删除：
- WorkerManager（外部Agent管理）
- TaskScheduler（任务调度）
- Bootstrap Loader（引导加载）

✅ 保留：
- Agent Loop（记忆领域任务执行）
- Skills System（记忆领域技能）
- GDI Optimizer（进化决策）
```

### 问题2：领域边界必须清晰

**记忆领域 = 记忆的存储 + 检索 + 进化 + 优化**

```
可以做：
✅ 记忆存储（写-读-删）
✅ 记忆检索（搜索-推荐）
✅ 记忆进化（GDI驱动）
✅ 记忆优化（Capsule生成）

不能做：
❌ 通用任务执行
❌ 多平台消息
❌ 外部Agent管理
❌ 成为另一个运行时
```

### 问题3：三个P0模块必须补充

| 模块 | Hermes对应 | Mimir实现 |
|------|-----------|----------|
| Trajectory | trajectory.jsonl | 进化轨迹记录 |
| Nudge | memory nudge | GDI下降时主动提醒 |
| Hindsight | hindsight plugin | 失败后复盘分析 |

---

## 三、修正后的Mimir V2框架

### 3.1 顶层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Mimir V2 记忆领域自进化Agent                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Agent Loop (核心)                       │  │
│  │                                                          │  │
│  │   ┌─────────┐    ┌─────────┐    ┌─────────┐            │  │
│  │   │ Observe │───►│ Decide  │───►│  Act    │            │  │
│  │   └─────────┘    └─────────┘    └─────────┘            │  │
│  │        ▲                             │                     │  │
│  │        └────────── Evaluate ─────────┘                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    核心模块                               │  │
│  │                                                          │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │  │
│  │  │  Skills    │  │ Trajectory │  │    GDI     │        │  │
│  │  │  System    │  │  Recorder  │  │  Optimizer │        │  │
│  │  └────────────┘  └────────────┘  └────────────┘        │  │
│  │                                                          │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │  │
│  │  │   Nudge    │  │  Hindsight │  │  Capsule   │        │  │
│  │  │   Engine   │  │  Analyzer  │  │   Maker    │        │  │
│  │  └────────────┘  └────────────┘  └────────────┘        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    学习素材                               │  │
│  │                                                          │  │
│  │  ┌──────────────────┐  ┌──────────────────┐            │  │
│  │  │  OpenClaw Skills │  │  记忆殿堂Capsule │            │  │
│  │  │  (~20个技能)      │  │  (高质量GDI>0.8)│            │  │
│  │  └──────────────────┘  └──────────────────┘            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    产出                                  │  │
│  │                                                          │  │
│  │  ┌──────────────────┐  ┌──────────────────┐            │  │
│  │  │ 高质量Capsule    │  │ 记忆领域Skills   │            │  │
│  │  │ (repair/optimize│  │ (记忆检索/进化/  │            │  │
│  │  │ /innovate)       │  │  优化)           │            │  │
│  │  └──────────────────┘  └──────────────────┘            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Agent Loop 详解

```python
class MimirAgentV2:
    """
    Mimir V2 记忆领域自进化Agent
    
    核心职责：
    - 记忆领域任务执行
    - 记忆优化进化
    - 产出Capsule和Skills
    
    与Hermes的区别：
    - Hermes：通用Agent
    - Mimir：记忆领域专家
    """
    
    def __init__(self):
        # 核心模块
        self.skills = SkillsSystem()      # 技能系统
        self.trajectory = Trajectory()    # 轨迹记录 [P0必须]
        self.gdi = GDIOptimizer()         # GDI优化器
        self.nudge = NudgeEngine()        # 主动提醒 [P0必须]
        self.hindsight = Hindsight()      # 后见分析 [P0必须]
        self.capsule_maker = CapsuleMaker() # 胶囊生成
        
        # 学习素材
        self.openclaw_skills = load_openclaw_skills()
        self.memory_palace = load_memory_palace()
```

### 3.3 六个核心模块

#### 3.3.1 Trajectory（轨迹记录）[P0]

```python
class Trajectory:
    """
    进化轨迹记录
    
    Hermes对应：trajectory.jsonl
    Mimir实现：evolution_trajectory.jsonl
    
    记录内容：
    - 进化决策
    - GDI评分变化
    - 成功/失败
    - 决策原因
    """
    
    def record(self, event: EvolutionEvent):
        """记录进化事件"""
        # 写入JSONL
        # 用于分析成功模式
        # 用于训练更好的决策
```

#### 3.3.2 Nudge Engine（主动提醒）[P0]

```python
class NudgeEngine:
    """
    GDI驱动的主动提醒
    
    提醒类型：
    1. GDI下降警告 - "Capsule X GDI下降，建议修复"
    2. 进化时机 - "已有30天未进化的Capsule"
    3. 成功复制 - "某Capsule进化成功，可复制"
    """
    
    def should_nudge(self, operation_count: int) -> bool:
        """每N次操作提醒一次"""
        return operation_count % 10 == 0
```

#### 3.3.3 Hindsight（后见分析）[P0]

```python
class Hindsight:
    """
    事后复盘分析
    
    分析内容：
    1. 进化失败原因
    2. 策略选择错误
    3. 遗漏的模式
    4. 改进建议
    """
    
    def analyze_failure(self, result: EvolutionResult) -> HindsightReport:
        """分析失败，提取教训"""
```

#### 3.3.4 GDI Optimizer（GDI优化器）

```python
class GDIOptimizer:
    """
    GDI驱动的进化决策
    
    核心差异化：
    - 不是用RL训练
    - 而是用GDI分数驱动进化决策
    """
    
    REPAIR_THRESHOLD = 0.5   # GDI < 0.5 需要修复
    OPTIMIZE_THRESHOLD = 0.7 # GDI 0.5-0.7 可以优化
    INNOVATE_THRESHOLD = 0.85 # GDI > 0.85 可以创新
```

#### 3.3.5 Skills System（技能系统）

```python
class SkillsSystem:
    """
    记忆领域技能系统
    
    与Hermes的区别：
    - 学习来源：OpenClaw skills + 记忆殿堂Capsule
    - 产出：记忆领域Skills
    """
    
    def learn_from_openclaw(self):
        """从OpenClaw skills学习"""
        for skill in self.openclaw_skills:
            if skill.is_memory_related():
                self.create_memory_skill(skill)
    
    def learn_from_memory_palace(self):
        """从记忆殿堂学习"""
        for capsule in self.memory_palace.get_high_gdi():
            self.integrate_successful_pattern(capsule)
```

#### 3.3.6 Capsule Maker（胶囊生成）

```python
class CapsuleMaker:
    """
    Capsule自动生成
    
    从成功案例生成新Capsule
    """
    
    def should_create(self, result: EvolutionResult) -> bool:
        """判断是否应该生成"""
        return result.gdi_delta > 0.15
```

---

## 四、修正后的实现路径

### Phase 1: 核心循环
```
Week 1-4:
1. agent_loop.py - Agent主循环
2. trajectory.py - 轨迹记录 [P0补充]
3. gdi_optimizer.py - GDI决策
4. memory_tools.py - 记忆工具
```

### Phase 2: 主动机制
```
Week 5-8:
5. nudge_engine.py - 主动提醒 [P0补充]
6. hindsight.py - 后见分析 [P0补充]
7. capsule_maker.py - 胶囊生成
```

### Phase 3: 学习系统
```
Week 9-12:
8. skills_system.py - 技能系统
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

## 五、防止偏离的设计原则

### 5.1 领域边界检查

每个新功能必须通过：
```
1. 是记忆相关的吗？     → 如果不是，不做
2. 能产出Capsule吗？   → 如果不能，不做
3. GDI能评估吗？       → 如果不能，不做
4. 需要外部Agent吗？   → 如果需要，不做
```

### 5.2 禁止列表

```
❌ WorkerManager（外部Agent管理）
❌ TaskScheduler（任务调度）
❌ Bootstrap Loader（引导加载）
❌ 多平台Gateway
❌ 通用任务执行
```

### 5.3 核心价值锚定

```
Mimir V2 = 记忆领域的完整自进化Agent
         ≠ Hermes复制品
         ≠ Agent运行时平台
         ≠ 通用任务执行器
```

---

## 六、Round 1 修复清单

| 优先级 | 修复项 | 状态 |
|--------|--------|------|
| P0 | 补充Trajectory模块 | ✅ 已加入 |
| P0 | 补充Nudge模块 | ✅ 已加入 |
| P0 | 补充Hindsight模块 | ✅ 已加入 |
| P0 | 砍掉Phase 2（Worker/调度） | ✅ 已删除 |
| P1 | 明确"记忆领域"边界 | ✅ 已定义 |
| P1 | 聚焦"知识涌现"而非"代码修复" | ✅ 已修正 |

---

## 七、下一步

**Round 2**: 启动Ralph锤炼，验证修正后的框架是否正确

需要验证：
1. 框架设计是否还有偏离风险
2. 模块间依赖是否正确
3. 实现路径是否可行
