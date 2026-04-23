# MimirAether 实现规划

**日期**: 2026-04-14  
**版本**: v1.1  
**核心原则**: 学习Hermes架构思想，重新实现MimirAether

---

## 一、核心定位

**MimirAether = 学习Hermes + 重新实现**

- 学习Hermes的架构设计思想
- 按照Hermes的模块结构实现
- 代码是重新写的，属于Mimir
- MIT许可证合规
- **完全独立，不依赖OpenClaw**

---

## 二、架构学习来源

### 2.1 Hermes核心模块

```
Hermes架构（学习来源）
│
├── Agent Core (run_agent.py)
│   └── AIAgent主循环
│
├── Memory System
│   ├── MemoryManager
│   ├── 四层记忆
│   └── 会话搜索
│
├── Skills System
│   ├── Skill管理器
│   ├── 自创建机制
│   └── SKILL.md格式
│
├── Tools System
│   ├── 工具注册表
│   ├── 代码执行沙箱
│   └── 委托系统
│
└── Trajectory System
    ├── 轨迹记录
    ├── 压缩优化
    └── RL训练接口
```

---

## 三、MimirAether实现架构

```
MimirAether（自己的代码，完全独立）
│
├── Agent Core
│   ├── core_loop.py      # 主循环
│   ├── turn_loop.py      # Turn控制
│   └── callbacks.py      # 回调体系
│
├── Memory System
│   ├── memory_manager.py  # 记忆管理器
│   ├── providers/        # 四层记忆提供者
│   │   ├── short_term.py
│   │   ├── episodic.py
│   │   ├── long_term.py
│   │   └── skill.py
│   └── session_search.py # 会话搜索
│
├── Skills System
│   ├── skill_manager.py   # 技能管理器
│   ├── auto_generator.py  # 自动生成
│   ├── SKILL.md          # 技能格式
│   └── hub.py            # 技能市场
│
├── Tools System
│   ├── registry.py        # 工具注册表
│   ├── sandbox.py        # 代码执行沙箱
│   ├── delegate.py        # 委托系统
│   └── tools/            # 工具实现
│
└── Trajectory System
    ├── recorder.py        # 轨迹记录
    ├── compressor.py      # 压缩优化
    └── rl_interface.py    # RL训练接口
```

---

## 四、核心模块实现

### 4.1 Agent Core

**参考**: Hermes `run_agent.py` (10871行)

```python
# agent/core_loop.py
class MimirAetherAgent:
    """
    MimirAether核心Agent类
    学习Hermes AIAgent实现
    """
    
    def __init__(
        self,
        model: str = "deepseek/deepseek-chat",
        max_iterations: int = 90,
        platform: str = "cli",
    ):
        self.model = model
        self.max_iterations = max_iterations
        self.platform = platform
        
        # 初始化组件
        self.memory_manager = MimirMemoryManager()
        self.skill_manager = MimirSkillManager()
        self.tool_registry = MimirToolRegistry()
        self.trajectory_engine = MimirTrajectoryEngine()
        
    async def chat(self, message: str) -> str:
        """主聊天接口"""
        
    async def run_conversation(self, user_message: str) -> str:
        """会话运行（学习Hermes）"""
        
    def build_system_prompt(self) -> str:
        """构建系统提示"""
```

### 4.2 Memory System

**参考**: Hermes `agent/memory_manager.py`

```python
# memory/memory_manager.py
class MimirMemoryManager:
    """
    四层记忆系统
    学习Hermes MemoryManager
    """
    
    def __init__(self):
        self.providers = []
        # 注册四层记忆
        self.add_provider(ShortTermProvider())
        self.add_provider(EpisodicProvider())
        self.add_provider(LongTermProvider())
        self.add_provider(SkillProvider())
        
    def build_system_prompt(self) -> str:
        """构建带记忆的系统提示"""
        
    async def prefetch_all(self, query: str) -> str:
        """预取相关记忆"""
```

### 4.3 Skills System

**参考**: Hermes `tools/skills_tool.py`, `agent/skill_manager_tool.py`

```python
# skills/skill_manager.py
class MimirSkillManager:
    """
    技能管理系统
    学习Hermes SkillManager
    """
    
    async def create(self, name: str, content: str, category: str):
        """创建技能"""
        
    async def patch(self, name: str, old: str, new: str):
        """补丁更新（优先）"""
        
    async def auto_generate(self, task_context: dict) -> Optional[Skill]:
        """从任务中自动生成技能"""
```

### 4.4 Tools System

**参考**: Hermes `tools/registry.py`, `tools/code_execution_tool.py`

```python
# tools/registry.py
class MimirToolRegistry:
    """
    工具注册表
    学习Hermes Registry
    """
    
    def register(self, tool: ToolDef):
        """注册工具"""
        
    async def execute(self, tool_name: str, params: dict) -> Any:
        """执行工具"""
```

### 4.5 Trajectory System

**参考**: Hermes `agent/trajectory.py`, `trajectory_compressor.py`

```python
# trajectory/engine.py
class MimirTrajectoryEngine:
    """
    轨迹记录引擎
    学习Hermes Trajectory
    """
    
    def start_entry(self, model: str, system_prompt_id: str):
        """开始轨迹记录"""
        
    def add_turn(self, role: str, content: str, tool_calls: list = None):
        """添加对话轮次"""
        
    def save(self, completed: bool):
        """保存轨迹"""
```

---

## 五、每个Phase的执行方法论

### Ralph锤炼模式

每个小阶段都使用Ralph模式进行锤炼：

```
Ralph迭代规则：
1. 在OpenClaw沙盒中自动执行该技能
2. 捕获执行错误、逻辑漏洞、输出不完整、边界异常
3. 自动定位问题原因，给出修复方案并修改技能逻辑
4. 重新在沙盒运行验证，直到无错误、输出稳定、逻辑完整
5. 每一轮迭代都输出：轮次 → 问题 → 修复 → 验证结果
6. 持续循环锤炼，直到连续3轮无任何错误，才算完成

辅助资源：
- 178角色库中的专业人士可用于模拟真实工作场景
- 如：软件架构师、Python开发者、系统设计师、数据库工程师等
```

### Ralph输出格式

```
Ralph Round N:
├─ 轮次: N
├─ 问题: [发现的问题]
├─ 修复: [修复方案]
└─ 验证: [PASS/FAIL]

连续3轮PASS → 阶段完成
```

---

## 六、实现Phase

### Phase 1: 核心骨架（Week 1-3）

| 任务 | 文件 | 参考 | 工作量 |
|------|------|------|--------|
| Agent基类 | agent/core_loop.py | run_agent.py | 5d |
| Turn循环 | agent/turn_loop.py | run_agent.py | 3d |
| MemoryManager | memory/memory_manager.py | memory_manager.py | 3d |
| 四层Provider | memory/providers/*.py | memory_manager.py | 4d |
| ToolRegistry | tools/registry.py | registry.py | 3d |
| 项目结构 | - | - | 1d |

**验收标准**:
- [ ] Agent能启动
- [ ] 简单对话能响应
- [ ] 记忆能存取

### Phase 2: 技能系统（Week 4-6）

| 任务 | 文件 | 参考 | 工作量 |
|------|------|------|--------|
| SkillManager | skills/skill_manager.py | skill_manager_tool.py | 4d |
| SKILL.md解析 | skills/utils.py | skill_utils.py | 2d |
| 技能CRUD | skills/crud.py | skills_tool.py | 3d |
| 自动生成 | skills/auto_generator.py | skill_manager_tool.py | 4d |
| Skills Hub | skills/hub.py | skills_hub.py | 3d |

**验收标准**:
- [ ] 能创建/编辑/删除技能
- [ ] 技能格式正确
- [ ] 能自动生成技能

### Phase 3: 工具系统（Week 7-9）

| 任务 | 文件 | 参考 | 工作量 |
|------|------|------|--------|
| 基础工具 | tools/basic/*.py | tools/*.py | 5d |
| 代码沙箱 | tools/sandbox.py | code_execution_tool.py | 4d |
| 委托系统 | tools/delegate.py | delegate_tool.py | 3d |
| 工具安全 | tools/security.py | tirith_security.py | 3d |

**验收标准**:
- [ ] 基础工具能调用
- [ ] 代码执行正常
- [ ] 安全措施到位

### Phase 4: 轨迹系统（Week 10-12）

| 任务 | 文件 | 参考 | 工作量 |
|------|------|------|--------|
| 轨迹记录 | trajectory/recorder.py | trajectory.py | 3d |
| 轨迹压缩 | trajectory/compressor.py | trajectory_compressor.py | 4d |
| RL接口 | trajectory/rl_interface.py | rl_cli.py | 3d |
| 格式规范化 | trajectory/normalizer.py | - | 3d |

**验收标准**:
- [ ] 轨迹能记录
- [ ] 能压缩优化
- [ ] RL接口可用

### Phase 5: 测试与文档（Week 13-14）

**Ralph锤炼**：每项测试都需要通过3轮无错误验证

| 任务 | 工作量 |
|------|--------|
| 单元测试 | 4d |
| 集成测试 | 3d |
| 文档编写 | 3d |
| 发布准备 | 2d |

**验收标准**:
- [ ] 测试覆盖核心模块
- [ ] 文档完整
- [ ] 能发布

### Phase 6: OpenClaw集成（可选，需官方同意）

**Ralph锤炼**：集成测试需要通过3轮无错误验证

| 任务 | 工作量 | 前提 |
|------|--------|------|
| OpenClaw适配层 | 4d | 官方同意 |
| 集成测试 | 3d | 适配层完成 |
| 官方对接 | 2d | 集成测试通过 |

**验收标准**:
- [ ] 能通过OpenClaw调度
- [ ] 官方确认集成方式

---

## 七、时间线

```
Week 1-3:   Phase 1 - 核心骨架
Week 4-6:   Phase 2 - 技能系统
Week 7-9:    Phase 3 - 工具系统
Week 10-12: Phase 4 - 轨迹系统
Week 13-14: Phase 5 - 测试与文档

总计: 14周
```

---

## 八、关键技术

### 7.1 模型路由

```python
# 支持多模型
providers = {
    "deepseek": {"model": "deepseek-chat"},
    "openai": {"model": "gpt-4o"},
}

routing = {
    "default": "deepseek",
    "code": "openai",
}
```

### 7.2 迭代控制

```python
class IterationBudget:
    """迭代预算"""
    max_total = 90
    subagent_budget = 50
```

### 7.3 压缩策略

```python
# 上下文>85%自动压缩
# 预压缩触发点50%
```

### 7.4 独立运行

MimirAether是完全独立的Agent：
- CLI直接运行
- 不依赖OpenClaw
- 自己管理记忆和技能
- 可以连接专属LLM

---

## 九、学习原则

```
1. 学习架构思想，不是复制代码
2. 按照自己的代码风格重写
3. 保持Hermes的核心能力
4. 添加Mimir特有的优化
```

---

## 十、禁止事项

```
❌ 不复制粘贴Hermes代码
❌ 不使用Hermes的私有API
❌ 不改变核心架构
❌ 不破坏MIT许可证
❌ 不依赖OpenClaw
❌ 不做适配层
```

---

## 十一、成功标准

| Phase | 标准 |
|-------|------|
| Phase 1 | Agent能启动响应 |
| Phase 2 | 技能系统完整 |
| Phase 3 | 工具能正常调用 |
| Phase 4 | 轨迹能记录压缩 |
| Phase 5 | 测试通过文档完整 |
| Phase 6 | OpenClaw集成（可选）|

---

_文档版本: 1.1_  
_修正日期: 2026-04-14_  
_设计: 琬弦 (织界者)_
