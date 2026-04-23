# Mimir-mini_agent V2 设计文档

**版本**: V2.0  
**日期**: 2026-04-14  
**定位**: 记忆专用自进化Agent  
**灵感**: Hermes Agent自进化机制

---

## 1. 设计哲学

### 1.1 核心差异：Mimir不是Hermes

| Hermes | Mimir-mini_agent V2 |
|--------|-------------------|
| 通用Agent | 记忆专用Agent |
| 执行多样化任务 | 专注射门记忆进化 |
| RL训练闭环 | GDI驱动进化 |
| 多平台消息 | 内存-进化协作 |
| 55万行Python | 新增~2000行 |

### 1.2 Mimir的使命

```
"让记忆自己变得更好"
```

不是"完成任务"，而是"优化记忆"。

---

## 2. 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                     Mimir-mini_agent V2                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     Agent Loop                            │   │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐              │   │
│  │  │ Observe │───►│ Decide  │───►│  Act    │              │   │
│  │  └─────────┘    └─────────┘    └─────────┘              │   │
│  │       ▲                             │                     │   │
│  │       └────────────── Evaluate ──────┘                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    核心模块                                │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │   │
│  │  │ Trajectory │  │CapsuleMaker│  │NudgeEngine │        │   │
│  │  │   轨迹记录  │  │ 胶囊自生成  │  │ 主动提醒   │        │   │
│  │  └────────────┘  └────────────┘  └────────────┘        │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │   │
│  │  │  Hindsight │  │GDIOptimizer│  │MemoryTools │        │   │
│  │  │   后见分析  │  │  GDI优化器  │  │ 记忆工具集 │        │   │
│  │  └────────────┘  └────────────┘  └────────────┘        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   IMemoryVault 接口                        │   │
│  │           (统一记忆层 · 短期 ↔ 长期 · 萃取)              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心模块详解

### 3.1 Agent Loop (agent_loop.py)

**职责**: 主导进化循环

```python
class EvolutionAgent:
    """
    记忆进化Agent
    
    核心循环:
    1. Observe - 观察记忆状态
    2. Decide - 决定进化策略  
    3. Act - 执行进化操作
    4. Evaluate - GDI评估
    5. Learn - 记录轨迹学习
    """
    
    def run(self, task: EvolutionTask) -> EvolutionResult:
        # Observe: 获取记忆状态
        state = self.observe()
        
        # Decide: 选择策略
        strategy = self.decide(state, task)
        
        # Act: 执行进化
        result = self.act(strategy)
        
        # Evaluate: GDI评分
        evaluated = self.evaluate(result)
        
        # Learn: 记录轨迹
        self.learn(evaluated)
        
        return evaluated
```

**与其他模块的关系**:
- 调用 `Trajectory` 记录每步决策
- 调用 `GDIOptimizer` 决定策略
- 调用 `MemoryTools` 操作记忆
- 调用 `NudgeEngine` 发送提醒

---

### 3.2 Trajectory (trajectory.py)

**职责**: 进化轨迹记录

**灵感来源**: Hermes的trajectory.jsonl

```python
@dataclass
class EvolutionEvent:
    """进化事件"""
    timestamp: str
    event_type: str  # "evolution", "nudge", "hindsight", "gdi_update"
    capsule_id: Optional[str]
    action: str  # "repair", "optimize", "innovate"
    
    # GDI评分
    gdi_before: float
    gdi_after: float
    delta: float
    
    # 决策信息
    success: bool
    reasoning: str
    tool_calls: List[Dict]
    
    # 元数据
    agent_version: str = "2.0"
```

**文件格式**: JSONL (evolution_trajectory.jsonl)

**用途**:
1. 分析进化成功率
2. 训练更好的进化策略
3. 追溯失败原因

---

### 3.3 CapsuleMaker (capsule_maker.py)

**职责**: 从成功案例自动生成Capsule

**灵感来源**: Hermes的skill self-creation

```python
class CapsuleMaker:
    """
    胶囊自生成器
    
    触发条件:
    1. 进化成功后 (GDI提升显著)
    2. 记忆操作重复成功
    3. NudgeEngine建议
    
    生成流程:
    1. 提取成功模式
    2. 生成Capsule内容
    3. GDI预评分
    4. 提交发布
    """
    
    def should_create(self, evolution_result: EvolutionResult) -> bool:
        """判断是否应该生成胶囊"""
        # GDI提升超过阈值
        if evolution_result.delta > 0.15:
            return True
        
        # 重复成功模式
        if self.detect_pattern(evolution_result):
            return True
        
        return False
    
    def create(self, result: EvolutionResult) -> Optional[Capsule]:
        """从进化结果创建胶囊"""
        # 提取内容
        content = self.extract_pattern(result)
        
        # 确定类型
        capsule_type = self.classify_type(result)
        
        # 生成标签
        tags = self.generate_tags(result)
        
        return Capsule(
            content=content,
            capsule_type=capsule_type,
            taxonomy_tags=tags,
            metadata={"source": "auto_generated", "evolution_id": result.id}
        )
```

---

### 3.4 NudgeEngine (nudge_engine.py)

**职责**: 主动发送进化建议

**灵感来源**: Hermes的memory nudge (每10轮提醒)

```python
class NudgeEngine:
    """
    主动提醒引擎
    
    提醒类型:
    1. GDI下降警告 - "Capsule X GDI从0.8降到0.5，建议优化"
    2. 进化时机 - "已有30天未进化的Capsule，建议复习"
    3. 记忆缺口 - "检测到某类记忆缺失，建议创建"
    4. 成功复制 - "某Capsule进化成功，可复制到类似场景"
    """
    
    NUDGE_INTERVAL = 10  # 每10次操作提醒一次
    
    def should_nudge(self, operation_count: int) -> bool:
        """判断是否应该提醒"""
        return operation_count % self.NUDGE_INTERVAL == 0
    
    def generate_nudge(self, state: MemoryState) -> List[Nudge]:
        """生成主动提醒"""
        nudges = []
        
        # 1. GDI下降警告
        for capsule in state.capsules:
            if capsule.gdi_trend == "declining":
                nudges.append(Nudge(
                    type="gdi_warning",
                    priority="high",
                    capsule_id=capsule.id,
                    message=f"Capsule {capsule.id} GDI持续下降"
                ))
        
        # 2. 久未进化
        for capsule in state.capsules:
            if capsule.days_since_evolution > 30:
                nudges.append(Nudge(
                    type="stale_capsule",
                    priority="medium",
                    capsule_id=capsule.id,
                    message=f"Capsule {capsule.id} 已{day}天未进化"
                ))
        
        # 3. 记忆缺口
        gaps = self.detect_gaps(state)
        for gap in gaps:
            nudges.append(Nudge(
                type="memory_gap",
                priority="low",
                message=f"建议创建关于{gap.topic}的记忆"
            ))
        
        return nudges
```

---

### 3.5 Hindsight (hindsight.py)

**职责**: 事后分析失败

**灵感来源**: Hermes的hindsight memory plugin

```python
class Hindsight:
    """
    后见之明分析器
    
    分析内容:
    1. 进化失败原因
    2. 策略选择错误
    3. 遗漏的模式
    4. 改进建议
    """
    
    def analyze_failure(self, evolution_result: EvolutionResult) -> HindsightReport:
        """分析失败原因"""
        # 1. 找到失败点
        failure_point = self.find_failure_point(evolution_result)
        
        # 2. 分析原因
        causes = self.analyze_causes(failure_point)
        
        # 3. 提取教训
        lessons = self.extract_lessons(causes)
        
        # 4. 生成报告
        return HindsightReport(
            evolution_id=evolution_result.id,
            failure_point=failure_point,
            causes=causes,
            lessons=lessons,
            recommendations=self.generate_recommendations(lessons)
        )
    
    def extract_lessons(self, causes: List[Cause]) -> List[Lesson]:
        """从失败原因提取教训"""
        lessons = []
        for cause in causes:
            lesson = Lesson(
                title=f"避免{cause.type}",
                description=f"进化时应注意{cause.detail}",
                pattern=cause.pattern,
                prevention=f"下次进化时提前检查{cause.check}"
            )
            lessons.append(lesson)
        return lessons
```

---

### 3.6 GDIOptimizer (gdi_optimizer.py)

**职责**: GDI驱动的进化决策

**这是Mimir的核心差异化模块**

```python
class GDIOptimizer:
    """
    GDI驱动的进化优化器
    
    决策内容:
    1. 是否需要进化
    2. 进化的优先级
    3. 进化的类型(repair/optimize/innovate)
    4. 何时停止进化
    """
    
    # 进化阈值
    REPAIR_THRESHOLD = 0.5   # GDI < 0.5 需要修复
    OPTIMIZE_THRESHOLD = 0.7  # GDI 0.5-0.7 可以优化
    INNOVATE_THRESHOLD = 0.85 # GDI > 0.85 可以创新
    
    # 停止条件
    STOP_DELTA = 0.02  # GDI提升 < 0.02 停止
    STOP_ATTEMPTS = 3   # 连续3次失败停止
    
    def should_evolve(self, capsule: Capsule) -> EvolutionDecision:
        """判断是否应该进化"""
        gdi = capsule.gdi_score.total
        
        if gdi < self.REPAIR_THRESHOLD:
            return EvolutionDecision(
                should_act=True,
                priority="high",
                action_type="repair",
                reason=f"GDI {gdi} < {self.REPAIR_THRESHOLD}"
            )
        
        elif gdi < self.OPTIMIZE_THRESHOLD:
            return EvolutionDecision(
                should_act=True,
                priority="medium", 
                action_type="optimize",
                reason=f"GDI {gdi} 处于可优化区间"
            )
        
        elif gdi > self.INNOVATE_THRESHOLD:
            return EvolutionDecision(
                should_act=True,
                priority="low",
                action_type="innovate",
                reason=f"GDI {gdi} > {self.INNOVATE_THRESHOLD}，可尝试创新"
            )
        
        else:
            return EvolutionDecision(
                should_act=False,
                priority="none",
                action_type=None,
                reason=f"GDI {gdi} 无需进化"
            )
    
    def should_stop(self, evolution_history: List[EvolutionResult]) -> bool:
        """判断是否应该停止进化"""
        if len(evolution_history) < self.STOP_ATTEMPTS:
            return False
        
        recent = evolution_history[-self.STOP_ATTEMPTS:]
        
        # 连续失败
        if all(not r.success for r in recent):
            return True
        
        # GDI提升微小
        if recent[-1].delta < self.STOP_DELTA:
            return True
        
        return False
```

---

### 3.7 MemoryTools (memory_tools.py)

**职责**: 记忆操作工具集

```python
class MemoryTools:
    """
    记忆操作工具集
    
    工具列表:
    1. read_memory - 读取记忆
    2. write_memory - 写入记忆
    3. search_memory - 搜索记忆
    4. delete_memory - 删除记忆
    5. get_capsule - 获取胶囊
    6. update_capsule - 更新胶囊
    7. score_capsule - GDI评分
    8. get_memory_state - 获取记忆状态
    """
    
    def __init__(self, vault: IMemoryVault):
        self.vault = vault
    
    def get_memory_state(self) -> MemoryState:
        """获取当前记忆状态"""
        keys = self.vault.list_keys()
        capsules = []
        
        for key in keys:
            data = await self.vault.read(key)
            if data and data.get("type") == "capsule":
                capsules.append(Capsule.from_dict(data))
        
        return MemoryState(
            total_memories=len(keys),
            capsules=capsules,
            avg_gdi=self.calculate_avg_gdi(capsules),
            gaps=self.detect_gaps(capsules)
        )
```

---

## 4. 数据流

### 4.1 进化流程

```
用户/定时触发
      │
      ▼
┌─────────────────────────────────────┐
│           Agent Loop                 │
│                                      │
│  1. Observe(vault)                  │
│     └─► MemoryState                 │
│              │                       │
│  2. Decide(state)                    │
│     └─► GDIOptimizer                │
│     └─► EvolutionDecision           │
│              │                       │
│  3. Act(decision)                    │
│     ├─► repair_capsule()            │
│     ├─► optimize_capsule()          │
│     └─► innovate_capsule()          │
│              │                       │
│  4. Evaluate(result)                 │
│     └─► GDIScorer                    │
│     └─► GDIResult                    │
│              │                       │
│  5. Learn(result)                    │
│     └─► Trajectory.record()          │
│     └─► CapsuleMaker.maybe_create() │
│     └─► NudgeEngine.maybe_nudge()   │
│                                      │
└─────────────────────────────────────┘
      │
      ▼
   EvolutionResult
```

### 4.2 Nudge流程

```
定时器 / 操作计数
      │
      ▼
┌─────────────────────────────────────┐
│         NudgeEngine                  │
│                                      │
│  should_nudge() → False → 跳过      │
│              │                       │
│              True                    │
│              ▼                       │
│  generate_nudge(state)               │
│  ├─► GDI下降警告                    │
│  ├─► 久未进化提醒                   │
│  ├─► 记忆缺口                       │
│  └─► 成功复制建议                   │
│              │                       │
│  emit(nudges) → 发送给用户/记录      │
│                                      │
└─────────────────────────────────────┘
```

### 4.3 Hindsight流程

```
进化失败
      │
      ▼
┌─────────────────────────────────────┐
│          Hindsight                   │
│                                      │
│  analyze_failure(result)             │
│  ├─► find_failure_point()           │
│  ├─► analyze_causes()               │
│  ├─► extract_lessons()              │
│  └─► generate_recommendations()     │
│              │                       │
│  save_report() → lessons/           │
│              │                       │
│  apply_lessons() → GDIOptimizer     │
│                                      │
└─────────────────────────────────────┘
```

---

## 5. 文件结构

```
mini_agent/
├── __init__.py
├── compact.py              # 上下文压缩 (现有)
├── hooks.py                # Hook机制 (现有)
├── registry.py             # 任务注册 (现有)
├── test_mini_agent.py      # 测试 (现有)
│
├── V2_DESIGN.md            # 本文档
│
├── agent_loop.py           # [NEW] Agent主循环
├── trajectory.py           # [NEW] 轨迹记录
├── capsule_maker.py        # [NEW] 胶囊自生成
├── nudge_engine.py         # [NEW] 主动提醒
├── hindsight.py            # [NEW] 后见分析
├── gdi_optimizer.py        # [NEW] GDI优化器
├── memory_tools.py         # [NEW] 记忆工具集
├── evolution_types.py      # [NEW] 类型定义
└── tests/
    ├── test_agent_loop.py  # [NEW]
    ├── test_trajectory.py  # [NEW]
    ├── test_nudge.py       # [NEW]
    └── test_hindsight.py  # [NEW]
```

---

## 6. 实现优先级

### Phase 1: 核心循环 (MVP)
1. `evolution_types.py` - 类型定义
2. `agent_loop.py` - 核心循环
3. `trajectory.py` - 轨迹记录
4. `memory_tools.py` - 记忆工具
5. `gdi_optimizer.py` - GDI决策

### Phase 2: 主动机制
6. `nudge_engine.py` - 主动提醒
7. `capsule_maker.py` - 胶囊生成

### Phase 3: 复盘机制
8. `hindsight.py` - 后见分析

### Phase 4: 优化
9. 轨迹分析
10. 策略学习

---

## 7. 与Hermes的关键区别

| Hermes | Mimir-mini_agent V2 |
|--------|-------------------|
| run_agent.py | agent_loop.py |
| trajectory.jsonl | evolution_trajectory.jsonl |
| skill_manager | capsule_maker |
| memory nudge | nudge_engine |
| hindsight plugin | hindsight.py |
| RL training | GDI-driven evolution |

**相同思想:**
- 轨迹记录
- 自动创建可复用单元
- 周期性提醒
- 事后复盘

**不同实现:**
- Hermes用RL，Mimir用GDI
- Hermes通用，Mimir专注记忆
- Hermes大规模，Mimir轻量

---

## 8. 成功标准

1. **自运转**: Agent能无人干预地持续优化记忆
2. **GDI提升**: 平均GDI分数持续提升
3. **轨迹完整**: 所有决策可追溯
4. **提醒有效**: Nudge带来有价值的进化机会
5. **自我改进**: 从轨迹中学习，改进行为

---

_文档版本: 1.0_  
_设计: 琬弦 (织界者)_  
_灵感: Hermes Agent by NousResearch_
