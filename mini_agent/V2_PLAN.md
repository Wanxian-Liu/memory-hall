# Mimir V2 方案锤炼 - Ralph Round 1

**阶段**: 深度研究 → 框架设计  
**目标**: Mimir V2 = 记忆领域完整自进化Agent

---

## 一、核心定位研究

### 1.1 Hermes的核心能力是什么？

```
Hermes = Agent Loop + Skills系统 + Trajectory记录 + RL训练
         ↓
核心：能自主执行任务并从经验中学习
```

### 1.2 Mimir V2要借鉴什么？

| Hermes能力 | Mimir V2如何借鉴 |
|------------|-----------------|
| Agent Loop | ✅ 必须有 - 但专注记忆领域 |
| Skills系统 | ✅ 必须有 - 产出记忆技能 |
| Trajectory | ✅ 必须有 - 进化轨迹记录 |
| RL训练 | ❌ 不抄 - 改用GDI驱动进化 |
| 多平台Gateway | ❌ 不需要 - Mimir专注内部 |
| Nudge机制 | ✅ 必须有 - 主动进化提醒 |

### 1.3 Mimir V2的独特价值

```
Hermes学不会的事：        Mimir V2能做的事：
• 如何优化记忆            ✅ 记忆优化
• 如何产出Capsule         ✅ Capsule生成
• 如何让知识自我进化      ✅ GDI进化
• 记忆领域的专业判断       ✅ 领域专家
```

---

## 二、框架设计

### 2.1 顶层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Mimir V2 完整Agent                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  Agent Loop (主循环)                    │  │
│  │                                                        │  │
│  │   ┌─────────┐    ┌─────────┐    ┌─────────┐         │  │
│  │   │ Observe │───►│ Decide  │───►│  Act    │         │  │
│  │   └─────────┘    └─────────┘    └─────────┘         │  │
│  │        ▲                             │                  │  │
│  │        └────────── Evaluate ─────────┘                  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    核心模块                              │  │
│  │                                                        │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐    │  │
│  │  │   Skills   │  │ Trajectory │  │    GDI     │    │  │
│  │  │   System   │  │  Recorder  │  │  Optimizer │    │  │
│  │  └────────────┘  └────────────┘  └────────────┘    │  │
│  │                                                        │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐    │  │
│  │  │   Nudge    │  │  Hindsight │  │  Capsule   │    │  │
│  │  │   Engine   │  │  Analyzer  │  │  Maker    │    │  │
│  │  └────────────┘  └────────────┘  └────────────┘    │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    学习素材                            │  │
│  │                                                        │  │
│  │  ┌──────────────────┐  ┌──────────────────┐        │  │
│  │  │  OpenClaw Skills │  │  记忆殿堂知识    │        │  │
│  │  │  (~20个技能)      │  │  (Capsule库)     │        │  │
│  │  └──────────────────┘  └──────────────────┘        │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    产出                                │  │
│  │                                                        │  │
│  │  ┌──────────────────┐  ┌──────────────────┐          │  │
│  │  │  高质量Capsule   │  │  记忆领域Skills │          │  │
│  │  └──────────────────┘  └──────────────────┘          │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Agent Loop 详解

```python
class MimirAgentV2:
    """
    Mimir V2 记忆领域自进化Agent
    
    与Hermes的关键区别：
    - Hermes：通用任务执行
    - Mimir：记忆领域任务执行 + 记忆优化
    """
    
    def __init__(self):
        self.skills = SkillsSystem()      # 技能系统
        self.trajectory = Trajectory()    # 轨迹记录
        self.gdi = GDIOptimizer()         # GDI优化器
        self.nudge = NudgeEngine()        # 主动提醒
        self.hindsight = Hindsight()      # 后见分析
        self.capsule_maker = CapsuleMaker() # 胶囊生成
        
        # 学习素材
        self.openclaw_skills = load_openclaw_skills()
        self.memory_vault = load_memory_vault()
    
    async def run(self, task: str) -> EvolutionResult:
        """主循环"""
        # 1. Observe - 观察记忆状态
        state = await self._observe()
        
        # 2. Decide - 决定行动
        decision = await self._decide(task, state)
        
        # 3. Act - 执行
        result = await self._act(decision)
        
        # 4. Evaluate - GDI评估
        evaluated = await self._evaluate(result)
        
        # 5. Learn - 记录并产出
        await self._learn(evaluated)
        
        return evaluated
```

### 2.3 Skills System 详解

```python
class SkillsSystem:
    """
    Mimir的技能系统
    
    与Hermes的区别：
    - Hermes：从经验中创建通用技能
    - Mimir：从OpenClaw skills + 记忆殿堂中学习记忆领域技能
    """
    
    def learn_from_hermes(self):
        """学习OpenClaw skills中的记忆相关技能"""
        # 1. 扫描OpenClaw skills
        for skill in self.openclaw_skills:
            if skill.is_memory_related():
                # 2. 提取记忆模式
                patterns = self.extract_patterns(skill)
                # 3. 生成Mimir技能
                self.create_memory_skill(patterns)
    
    def learn_from_memory_vault(self):
        """从记忆殿堂学习"""
        # 1. 获取Capsule库
        capsules = self.memory_vault.get_all_capsules()
        # 2. 分析成功案例
        for capsule in capsules:
            if capsule.gdi_score > 0.8:
                # 3. 提取成功模式
                self.integrate_successful_pattern(capsule)
```

### 2.4 GDI Optimizer 详解

```python
class GDIOptimizer:
    """
    GDI驱动的进化决策
    
    这是Mimir的核心差异化模块
    Hermes用RL，Mimir用GDI
    """
    
    # 进化阈值
    REPAIR_THRESHOLD = 0.5   # GDI < 0.5 需要修复
    OPTIMIZE_THRESHOLD = 0.7  # GDI 0.5-0.7 可以优化
    INNOVATE_THRESHOLD = 0.85 # GDI > 0.85 可以创新
    
    def should_evolve(self, capsule: Capsule) -> EvolutionDecision:
        """判断是否应该进化"""
        gdi = capsule.gdi_score.total
        
        if gdi < self.REPAIR_THRESHOLD:
            return EvolutionDecision(
                action_type="repair",
                priority="high"
            )
        elif gdi < self.OPTIMIZE_THRESHOLD:
            return EvolutionDecision(
                action_type="optimize",
                priority="medium"
            )
        elif gdi > self.INNOVATE_THRESHOLD:
            return EvolutionDecision(
                action_type="innovate",
                priority="low"
            )
```

---

## 三、进化闭环

### 3.1 完整闭环

```
┌─────────────────────────────────────────────────────────────────┐
│                      Mimir V2 进化闭环                            │
│                                                                  │
│    ┌─────────┐                                                  │
│    │ OpenClaw│ ←── 学习素材                                    │
│    │ Skills  │                                                 │
│    └────┬────┘                                                  │
│         │                                                        │
│    ┌────▼────┐    ┌─────────┐    ┌─────────┐                  │
│    │         │───►│  Agent  │───►│ Skills  │                  │
│    │  记忆   │    │  Loop   │    │ System  │                  │
│    │ 殿堂   │───►│         │───►│         │                  │
│    │         │    └────┬────┘    └────┬────┘                  │
│    └────┬────┘         │              │                        │
│         │         ┌────▼────┐    ┌────▼────┐                  │
│         │         │   GDI   │───►│ Capsule │                  │
│         │         │Optimizer│    │  Maker │                  │
│         │         └─────────┘    └─────────┘                  │
│         │                                                        │
│    ┌────▼────┐                                                  │
│    │ Capsule │ ←── 产出                                       │
│    │ Library │                                                  │
│    └─────────┘                                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 学习流程

```
1. 学习OpenClaw Skills
   │
   ├── 扫描所有Skills (~20个)
   ├── 识别记忆相关技能
   │    ├── memory相关
   │    ├── context相关
   │    └── learning相关
   ├── 提取模式
   └── 生成Mimir记忆技能

2. 学习记忆殿堂
   │
   ├── 扫描Capsule库
   ├── 识别高质量Capsule (GDI > 0.8)
   ├── 提取成功模式
   └── 集成到Skills系统

3. 产出
   │
   ├── 高质量Capsule
   │    ├── repair型
   │    ├── optimize型
   │    └── innovate型
   │
   └── 记忆领域Skills
        └── 专门用于记忆优化的技能
```

---

## 四、防止偏离的设计原则

### 4.1 Mimir不是Hermes

| 方面 | Hermes | Mimir V2 |
|------|--------|----------|
| **定位** | 通用Agent | 记忆领域Agent |
| **任务** | 多样化任务 | 记忆优化任务 |
| **产出** | 通用Skills | 记忆Skills + Capsule |
| **进化** | RL训练 | GDI驱动 |
| **规模** | 55万行 | 轻量(~2000行新模块) |

### 4.2 Mimir的核心边界

```
可以做：
✅ 记忆领域的任务执行
✅ 从OpenClaw skills学习
✅ 从记忆殿堂学习
✅ 产出Capsule和Skills
✅ GDI驱动的进化

不能做：
❌ 通用任务执行（非记忆领域）
❌ 多平台消息处理
❌ 变成另一个Hermes
❌ 脱离记忆优化目标
```

### 4.3 领域专注检查

每个新功能必须通过以下检查：
1. **是记忆相关的吗？** - 如果不是，不做
2. **能产出Capsule吗？** - 如果不能，不做
3. **GDI能评估吗？** - 如果不能，不做

---

## 五、实现路径

### Phase 1: 核心循环 (MVP)
```
1. agent_loop.py - Agent主循环
2. trajectory.py - 轨迹记录
3. gdi_optimizer.py - GDI决策
4. memory_tools.py - 记忆工具
```

### Phase 2: 学习系统
```
5. skills_system.py - 技能系统
6. openclaw_learner.py - 学习OpenClaw
7. memory_vault_learner.py - 学习记忆殿堂
```

### Phase 3: 产出系统
```
8. capsule_maker.py - 胶囊生成
9. nudge_engine.py - 主动提醒
10. hindsight.py - 后见分析
```

---

## 六、验证清单

### 6.1 功能验证
- [ ] Agent Loop能正常执行
- [ ] Skills能从OpenClaw学习
- [ ] Capsule能正常生成
- [ ] GDI评分正常工作

### 6.2 方向验证
- [ ] 所有功能都围绕记忆优化
- [ ] 产出是Capsule和Skills
- [ ] 没有变成通用Agent

### 6.3 质量验证
- [ ] Trajectory完整记录
- [ ] Hindsight能分析失败
- [ ] Nudge能主动提醒

---

## 七、风险识别

| 风险 | 应对 |
|------|------|
| 变成Hermes复制品 | 严格领域边界检查 |
| 学习素材不足 | 初期专注OpenClaw skills |
| GDI评分不准 | 从简单场景开始迭代 |
| 产出质量低 | 设置GDI > 0.8才发布 |

---

**结论**: Mimir V2是记忆领域的完整自进化Agent，不是Hermes复制品。核心差异在于领域专注（记忆）和进化机制（GDI vs RL）。
