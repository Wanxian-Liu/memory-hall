# Mimir V3 深度实现方案

**日期**: 2026-04-14  
**目标**: 1:1对齐Hermes架构  
**执念**: 记忆殿堂是灵魂之家，Mimir通过Hermes锻炼技能

---

## 一、核心架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        Mimir Agent                                │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Agent Core Loop                        │   │
│  │              plan() → execute() → reflect() → evolve()   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Memory   │  │ Skills   │  │ Tools    │  │ Trajectory  │   │
│  │ Manager  │  │ Router   │  │ Registry │  │ Engine      │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               OpenClaw Integration Layer                 │   │
│  │         sessions_spawn() | skills | tools               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、七大模块深度实现

### 模块1：Agent Core Loop

**文件**: `mimir/agent/core_loop.py`  
**Hermes参考**: `run_agent.py` (~10,700行)

**核心接口**:
```python
class MimirAgent:
    def plan(self, task: str) -> Plan:
        """分解任务为子任务"""
        
    def execute(self, plan: Plan) -> ExecutionResult:
        """执行计划"""
        
    def reflect(self, result: ExecutionResult) -> Reflection:
        """反思执行结果"""
        
    def evolve(self, reflection: Reflection) -> Evolution:
        """基于反思进化"""
```

**OpenClaw对齐**:
- 使用`sessions_spawn()`实现子代理分解
- 复杂度>3 → spawn子代理
- 迭代预算：默认90次，子agent独立预算50次

**实现步骤**:
```
Phase 1.1: 基础循环骨架
- plan() → 子任务分解
- execute() → 顺序/并行执行
- reflect() → 执行结果评估

Phase 1.2: 循环增强
- 迭代预算控制
- 可中断API调用
- 多API模式支持

Phase 1.3: 高级特性
- Callback体系（thinking/progress/step）
- 自动压缩（>85%上下文）
- 回退模型机制
```

---

### 模块2：四层记忆系统

**文件**: `mimir/memory/`  
**Hermes参考**: `agent/memory_manager.py`

**目录结构**:
```
memory/mimir/
├── short_term/      # 1小时，Working Memory
│   └── session_{timestamp}.json
├── episodic/         # 7天，事件记忆
│   └── {date}_{hash}.json
├── long_term/        # 永久，语义记忆
│   └── {topic}/
│       └── {id}.json
└── skill/            # 永久+索引，技能记忆
    └── {skill_name}/
        └── {version}.md
```

**MemoryManager实现**:
```python
class MimirMemoryManager:
    def __init__(self):
        self._providers = []
        self.add_provider(ShortTermProvider())
        self.add_provider(EpisodicProvider())
        self.add_provider(LongTermProvider())
        self.add_provider(SkillProvider())
    
    def build_system_prompt(self) -> str:
        """构建带记忆上下文的系统提示"""
        
    def prefetch_all(self, user_message: str) -> str:
        """预取相关记忆"""
        
    def sync_all(self, user_msg: str, assistant_resp: str):
        """同步记忆（后处理）"""
```

**OpenClaw对齐**:
- 使用OpenClaw的memory系统作为底层存储
- 分层配置与Hermes完全一致
- FTS5全文搜索支持

**实现步骤**:
```
Phase 2.1: 基础记忆层
- ShortTermProvider (1小时)
- EpisodicProvider (7天)
- LongTermProvider (永久)
- SkillProvider (技能记忆)

Phase 2.2: 记忆增强
- 自动去重
- 安全扫描（注入检测）
- 容量管理（字符限制）

Phase 2.3: 高级特性
- 冷冻快照模式
- 跨会话检索
- 向量嵌入搜索
```

---

### 模块3：自进化技能系统

**文件**: `mimir/skills/`  
**Hermes参考**: `agent/skill_manager_tool.py`, `tools/skills_tool.py`

**SKILL.md格式** (agentskills.io兼容):
```yaml
---
name: example-skill
description: 技能描述
version: 1.0.0
platforms: [darwin, linux]
metadata:
  author: Mimir
  tags: [productivity]
---

## When to Use
何时使用此技能

## Procedure
1. 步骤一
2. 步骤二

## Pitfalls
- 注意事项

## Verification
如何验证
```

**SkillManager实现**:
```python
class MimirSkillManager:
    def create(self, name: str, content: str, category: str):
        """创建新技能"""
        
    def patch(self, name: str, old: str, new: str):
        """补丁更新（优先）"""
        
    def edit(self, name: str, content: str):
        """全量编辑"""
        
    def delete(self, name: str):
        """删除技能"""
        
    def list(self) -> List[SkillMetadata]:
        """列出所有技能"""
        
    def view(self, name: str, path: str = None) -> str:
        """查看技能详情"""
```

**自动生成逻辑**:
```python
class SkillAutoGenerator:
    def should_generate(self, task: Task) -> bool:
        """判断是否需要生成技能"""
        return (
            task.complexity > 5 or
            task.error_count > 0 or
            task.user_corrected
        )
    
    def generate(self, task: Task) -> Skill:
        """从任务中提炼技能"""
        
    def install(self, skill: Skill):
        """自动安装技能"""
        
    def optimize(self, skill: Skill) -> Skill:
        """优化技能"""
```

**实现步骤**:
```
Phase 3.1: 技能基础
- SKILL.md格式解析
- create/patch/edit/delete操作
- 渐进式三级加载（L0/L1/L2）

Phase 3.2: 自动生成
- 触发条件判断
- 技能提炼算法
- 自动安装流程

Phase 3.3: 技能生态
- Skills Hub对接
- clawhub/lobehub兼容
- 条件激活机制
```

---

### 模块4：Spawn子代理系统

**文件**: `mimir/agent/spawn.py`  
**Hermes参考**: `run_agent.py`中的subagent逻辑

**复杂度判断**:
```python
def assess_complexity(task: str) -> int:
    """评估任务复杂度（0-10）"""
    factors = [
        task.requires_breaking_down,  # +2
        task.has_multiple_domains,    # +2
        task.needs_specialist_knowledge,  # +3
        task.involves_uncertainty,    # +2
        task.has_side_effects,        # +1
    ]
    return min(sum(factors), 10)
```

**Spawn策略**:
```python
class MimirSpawner:
    def spawn(self, task: Task, complexity: int) -> SubAgent:
        if complexity > 3:
            return self._spawn_child(task)
        else:
            return self._execute_direct(task)
    
    def _spawn_child(self, task: Task) -> SubAgent:
        """启动子代理"""
        return sessions_spawn(
            task=task.prompt,
            mode="session",
            timeout=task.estimated_time * 60
        )
```

**OpenClaw对齐**:
- 使用`sessions_spawn()`原生接口
- 任务分解与子代理调度
- 独立预算机制

**实现步骤**:
```
Phase 4.1: 复杂度评估
- 任务复杂度判断
- 领域识别
- 时间估算

Phase 4.2: 子代理调度
- sessions_spawn封装
- 结果聚合
- 错误处理

Phase 4.3: 高级特性
- 动态预算调整
- 并发/顺序策略
- 交互强制顺序
```

---

### 模块5：工具编排系统

**文件**: `mimir/tools/`  
**Hermes参考**: `tools/`目录 (28+工具)

**工具白名单** (`tools/hermes-tools.json`):
```json
{
  "tools": [
    "web_search",
    "web_extract",
    "read_file",
    "write_file",
    "patch",
    "search_files",
    "terminal",
    "browser",
    "edit",
    "exec"
  ]
}
```

**代码执行沙箱** (execute_code):
```python
class CodeExecutionSandbox:
    def execute(self, code: str, tools: List[str]) -> ExecutionResult:
        """
        Hermes风格：中间结果不进context
        只有最终print()输出返回
        """
        # 生成hermes_tools.py RPC存根
        # Unix domain socket通信
        # 子进程执行，timeout保护
```

**安全模型**:
```python
class ToolSecurity:
    API_KEY_PATTERNS = [
        "sk-", "api_key", "token", "password"
    ]
    
    def sanitize(self, output: str) -> str:
        """剥离敏感信息"""
        
    def validate(self, tool: str) -> bool:
        """验证工具权限"""
```

**OpenClaw对齐**:
- 复用OpenClaw现有工具（exec, web_fetch, file operations）
- 沙箱隔离（Docker/SSH/本地）
- 白名单机制

**实现步骤**:
```
Phase 5.1: 工具基础
- 工具注册表
- 白名单机制
- 基础安全扫描

Phase 5.2: 代码执行
- Unix socket RPC
- hermes_tools存根生成
- Timeout/Kill保护

Phase 5.3: 高级特性
- 工具统计（normalized）
- 批量操作优化
- 自定义工具注册
```

---

### 模块6：多平台网关

**文件**: `mimir/gateway/`  
**Hermes参考**: `gateway/`目录

**配置** (`config/gateway-mimir.json`):
```json
{
  "channels": [
    "openclaw-weixin",
    "feishu",
    "telegram",
    "discord",
    "slack"
  ],
  "providers": {
    "deepseek": {
      "api_base": "https://api.deepseek.com",
      "model": "deepseek-chat"
    }
  }
}
```

**OpenClaw对齐**:
- 复用OpenClaw Gateway插件系统
- 多通道消息路由
- 跨平台一致性

**实现步骤**:
```
Phase 6.1: 网关基础
- OpenClaw Gateway对接
- 多通道配置
- 消息路由

Phase 6.2: 专属LLM
- DeepSeek provider
- 多模型路由
- API密钥管理

Phase 6.3: 高级特性
- 跨平台记忆同步
- 通道特定优化
- 负载均衡
```

---

### 模块7：自训练流水线

**文件**: `mimir/rl/`  
**Hermes参考**: `rl_cli.py`, `trajectory_compressor.py`

**Trajectory格式** (ShareGPT兼容JSONL):
```json
{
  "id": "trajectory_uuid",
  "conversations": [...],
  "model": "gpt-4o",
  "temperature": 0.7,
  "completed": true,
  "tool_stats": {
    "web_search": 3,
    "read_file": 5
  },
  "system_prompt_identifier": "default"
}
```

**训练流水线**:
```python
class TrainingPipeline:
    def __init__(self):
        self.trajectory_store = TrajectoryStore()
        self.compressor = TrajectoryCompressor()
        self.rl_trainer = RLTrainer()
    
    def process(self, task_count: int):
        """每N个任务触发训练"""
        if task_count % 15 == 0:
            trajectories = self.trajectory_store.get_recent(15)
            compressed = self.compressor.compress(trajectories)
            self.rl_trainer.train(compressed)
```

**规范化转换**:
```python
class TrajectoryNormalizer:
    def normalize(self, trajectory: dict) -> dict:
        """转换格式"""
        # reasoning → <think>
        # tool calls → <tool_call>XML</tool_call>
        # tool responses → <tool_response>
        return normalized
```

**OpenClaw对齐**:
- 复用OpenClaw的session历史
- JSONL格式导出
- HuggingFace datasets兼容

**实现步骤**:
```
Phase 7.1: 轨迹基础
- TrajectoryStore
- JSONL格式
- 轨迹保存开关

Phase 7.2: 压缩优化
- TrajectoryCompressor
- 规范化转换
- 过滤零reasoning样本

Phase 7.3: RL训练
- RLTrainer封装
- 反馈循环
- 模型更新
```

---

## 三、OpenClaw集成架构

### 3.1 双形态设计

```
形态A: OpenClaw调度模式
┌──────────────────────────────┐
│     OpenClaw Gateway         │
│  sessions_spawn → Mimir      │
│  (作为子Agent被调度)          │
│                              │
│  技能: ~/.openclaw/skills/   │
│       mimir-core/            │
└──────────────────────────────┘

形态B: 独立部署模式
┌──────────────────────────────┐
│  Mimir Standalone CLI        │
│  $ mimir run --task "..."    │
│  $ mimir chat                │
│                              │
│  配置: ~/.mimir/config.yaml  │
└──────────────────────────────┘
```

### 3.2 共享核心

```python
# 两形态共享的核心模块
mimir_core/
├── agent/          # Agent Core Loop
├── memory/         # 四层记忆系统
├── skills/         # 技能管理
├── tools/          # 工具编排
├── trajectory/     # 轨迹记录
├── rl/             # 训练流水线
└── gateway/        # 网关接口

# 差异仅在入口
mimir_openclaw/    # OpenClaw集成层
mimir_cli/         # 独立CLI入口
```

---

## 四、实现优先级与时间线

### 优先级矩阵

| 优先级 | 模块 | 工作量 | 风险 | 依赖 |
|--------|------|--------|------|------|
| P0 | Agent Core Loop | 高 | 高 | 无 |
| P0 | 四层记忆系统 | 高 | 中 | 无 |
| P1 | 工具编排 | 中 | 低 | P0 |
| P1 | Spawn子代理 | 中 | 中 | P0 |
| P2 | 技能系统 | 高 | 中 | P0,P1 |
| P2 | 多平台网关 | 中 | 低 | P0 |
| P3 | 自训练流水线 | 高 | 高 | P1,P2 |

### 细腻时间线

```
Month 1: 核心骨架
Week 1: Agent Core Loop骨架 + plan/execute/reflect
Week 2: 基础记忆系统（ShortTerm + Episodic）
Week 3: 工具注册表 + 白名单机制
Week 4: OpenClaw技能封装 + 测试

Month 2: 记忆增强
Week 1: LongTerm + Skill记忆层
Week 2: 复杂度评估 + Spawn封装
Week 3: 代码执行沙箱（基础）
Week 4: 集成测试 + 优化

Month 3: 技能进化
Week 1: SKILL.md解析 + 基础操作
Week 2: 自动生成逻辑
Week 3: Skills Hub对接
Week 4: 优化 + 验证

Month 4: 高级特性
Week 1: Trajectory记录
Week 2: 压缩优化
Week 3: RL训练基础
Week 4: 完整测试 + 文档

Month 5-6: 打磨上线
- 完整测试
- 性能优化
- 文档完善
- 社区准备
```

---

## 五、关键技术决策

### 5.1 存储选择

| 层级 | Hermes | Mimir选择 | 原因 |
|------|--------|----------|------|
| ShortTerm | Memory | SQLite | 成熟、事务安全 |
| Episodic | SQLite | SQLite | 与OpenClaw兼容 |
| LongTerm | Neo4j | SQLite + 向量 | 简化部署 |
| Skill | File | File | SKILL.md原生格式 |

### 5.2 沙箱选择

```
Phase 1: exec timeout (已有)
    ↓
Phase 2: Docker隔离
    ↓
Phase 3: syscall过滤（未来）
```

### 5.3 LLM路由

```yaml
providers:
  deepseek:
    api_base: "https://api.deepseek.com"
    model: "deepseek-chat"
    routing:
      default: true
      
  openai:
    model: "gpt-4o"
    routing:
      code: true
```

---

## 六、测试策略

### 6.1 单元测试

```python
# tests/test_memory/
test_short_term.py
test_episodic.py
test_long_term.py
test_skill_provider.py

# tests/test_skills/
test_frontmatter_parse.py
test_create.py
test_patch.py
test_auto_generate.py
```

### 6.2 集成测试

```python
# tests/integration/
test_agent_loop.py
test_spawn_subagent.py
test_tool_execution.py
test_trajectory.py
```

### 6.3 对齐验证

```python
# tests/alignment/
test_hermes_parity.py  # 与Hermes输出对比
test_memory_parity.py   # 记忆系统对比
test_skill_parity.py    # 技能系统对比
```

---

## 七、文档结构

```
mimir-docs/
├── README.md
├── GETTING_STARTED.md
├── ARCHITECTURE.md
├── MODULES/
│   ├── core_loop.md
│   ├── memory.md
│   ├── skills.md
│   ├── tools.md
│   ├── trajectory.md
│   └── rl.md
├── OPENCLAW_INTEGRATION.md
├── HERMES_ALIGNMENT.md
└── CONTRIBUTING.md
```

---

## 八、禁止事项

```
❌ 不复制Hermes源码（学习思想）
❌ 不使用Hermes的私有API
❌ 不破坏OpenClaw现有功能
❌ 不在生产环境直接运行未测试代码
❌ 不跳过测试提交
```

---

## 九、成功标准

| 标准 | 验证方法 | 阈值 |
|-----|---------|------|
| Hermes能力对齐 | Agent Loop测试 | 100%覆盖 |
| 记忆正确性 | 四层记忆测试 | 无数据丢失 |
| 技能生成 | 自动生成测试 | 80%可用 |
| OpenClaw集成 | 调度测试 | 正常响应 |
| 轨迹记录 | JSONL验证 | 格式正确 |

---

## 十、下一步行动

1. **立即**: 创建`mimir-core`项目结构
2. **Week 1**: 实现Agent Core Loop骨架
3. **Week 2**: 实现四层记忆基础
4. **Week 3**: 实现工具编排
5. **Week 4**: OpenClaw技能封装

---

_文档版本: 1.0_  
_灵感: Hermes官方实现_  
_执念: 记忆殿堂是灵魂之家，Mimir通过Hermes锻炼技能_  
_设计: 琬弦 (织界者)_
