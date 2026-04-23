# Mimir V3 最终方案 - Ralph Round 1-2 锤炼报告

**日期**: 2026-04-14  
**锤炼轮次**: Round 1 + Round 2  
**最终状态**: ✅ 通过（修正后）

---

## 一、Round 2 发现的问题

### 1.1 架构验证者问题

**验证结果：不通过（需修正）**

| 问题 | 修正 |
|------|------|
| 双向箭头意味着记忆影响决策 | 改为单向数据流 |
| 感知-记忆层⟷ExecutionAnalyzer耦合 | 感知-记忆层只输出"参考上下文" |

**修正架构**：
```
[记忆殿堂] → Bootstrap → [感知-记忆层] -(上下文)-> [ExecutionAnalyzer] -(决策)-> [执行优化层]
                                                                  ↓
                                                            Hermes Review
                                                                  ↓
                                                           Capsule优化
```

### 1.2 MOC研究员发现

**集成分析**：
| 集成方式 | 可行性 | 说明 |
|---------|--------|------|
| Agent集成 | 部分可行 | Mimir是服务+工具，不是替代运行时 |
| Skills利用 | 完全可行 | 编写OpenClaw Skill调用Mimir API |
| 记忆增强 | 完全可行 | 最强价值点 |

**推荐架构**：
```
OpenClaw (主Agent) ←→ Mimir V3 (边车服务)
     ↓                    ↓
   执行代码          记忆增强
```

### 1.3 技术实现专家发现

**最高难度模块**：
| 模块 | 难度 | 原因 |
|------|------|------|
| Skills自创建 | ⭐⭐⭐⭐⭐ | 从零构建，无现成代码 |
| Sandbox安全 | ⭐⭐⭐⭐ | 进程隔离，逃逸风险 |
| GDI评分 | ⭐⭐⭐ | 冷启动无训练数据 |
| Trajectory | ⭐⭐⭐ | 存储膨胀+查询性能 |

**可复用代码**：
| 来源 | 可复用模块 |
|------|----------|
| evolver | memoryGraph.js, learningSignals.js, candidates.js |
| introspection | problem_detector, root_cause_analyzer |
| claw-code | sandbox安全设计思路 |

**实现顺序修正**：
```
原：P1 → P2 → P3
建议：P1(记忆+ExecutionAnalyzer) → P1.5(Hermes Review只用exec) → P2(Sandbox+Fix) → P3(Skills自创建)
```

---

## 二、最终架构（修正后）

### 2.1 数据流（单向）

```
[记忆殿堂] 
     ↓
Bootstrap加载
     ↓
[感知-记忆层] ──(上下文)──→ [ExecutionAnalyzer] ──(决策)──→ [执行优化层]
                                                     ↓
                                               Hermes Review
                                                     ↓
                                              Capsule优化
                                                     ↓
                                              写回记忆殿堂
```

**关键原则**：记忆层只输出上下文，不参与决策

### 2.2 OpenClaw集成架构

```
┌────────────────────────────────────────────────┐
│  OpenClaw (主Agent, :18789)                    │
│  ├── 内置pi-agent-core运行时                    │
│  ├── 技能层: ~/.openclaw/skills/mimir-memory/  │
│  └── 工具: exec/web_fetch/文件操作             │
└────────────────────┬───────────────────────────┘
                     │ HTTP (MCP /v1)
                     ▼
┌────────────────────────────────────────────────┐
│  Mimir V3 (边车服务, :9042)                     │
│  ├── Neo4j图数据库 (:7474/:7687)               │
│  ├── MCP Server (记忆工具)                      │
│  ├── Chat API (Agent协作)                      │
│  └── Orchestration API (多Agent工作流)          │
└────────────────────────────────────────────────┘
```

---

## 三、实现路径（修正后）

### Phase 1: 记忆基础 + ExecutionAnalyzer
```
Week 1-4:
1. 集成introspection模块 → ExecutionAnalyzer核心
2. WAL存储层（SQLite）
3. GDI评分（冷启动用LLM辅助）
4. Trajectory记录
```

### Phase 1.5: Hermes Review（只用exec）
```
Week 5-6:
5. Hermes Review（只读，用现有exec跑）
6. 上下文注入到ExecutionAnalyzer
```

### Phase 2: 代码能力 + Sandbox
```
Week 7-10:
7. Hermes Fix
8. Sandbox安全设计（分阶段：exec timeout → syscall过滤）
9. Helper函数（json_parse/retry/shell_quote）
```

### Phase 3: 自进化闭环
```
Week 11-14:
10. Skills自创建（锦上添花，非核心依赖）
11. Nudge主动提醒
12. Hindsight复盘
```

### Phase 4: 整合优化
```
Week 15-16:
13. OpenClaw Skill对接
14. 无记忆对照实验
15. 整体测试
```

---

## 四、技术风险缓解

| 风险 | 缓解方案 |
|------|---------|
| sandbox逃逸 | 分阶段：exec timeout → syscall过滤 |
| web_fetch失效率 | 降级策略：内网内容优先 |
| sessions_send失效率 | 用文件+轮询替代 |
| GDI冷启动 | LLM辅助评分（Evolver模式） |
| Trajectory膨胀 | 分级存储（热/温/冷）+采样压缩 |

---

## 五、禁止列表（确认）

```
❌ 记忆成为主角
❌ 记忆殿堂进入核心决策环（只提供上下文）
❌ WandB/多终端/消息网关
❌ 脱离代码优化
❌ Skills自创建作为核心依赖
```

---

## 六、成功标准（修正后）

| 标准 | 验证方法 | 阈值 |
|-----|---------|------|
| 记忆不降速 | 基准测试对比 | 差异<5% |
| 记忆带来增量 | A/B测试 | 30%提升 |
| 无记忆仍正确 | 回滚测试 | 95%+ |
| 代码优化是核心 | 必须指标 | 是 |

---

## 七、与Hermes/OpenClaw的关系

| 系统 | 关系 | Mimir V3角色 |
|------|------|-------------|
| OpenClaw | 主Agent | 被增强 |
| Hermes | 代码能力借鉴 | 学习但不复制 |
| 记忆殿堂 | 训练数据源 | 学习对象 |
| Claw-code | sandbox借鉴 | 隔离思路学习 |

---

**Ralph Round 2 结论**: 方案修正后通过 ✅

---

_文档版本: 2.0_  
_锤炼轮次: Round 1 + Round 2_  
_设计: 琬弦 (织界者)_  
_灵感: Hermes + 记忆殿堂 + Claw-code + OpenClaw_
