# Hermes on OpenClaw：真实复刻方案（1:1架构对齐）

**来源**: 负责人提供  
**日期**: 2026-04-14

---

## 模块1：Agent Core Loop（复刻Hermes主循环）

- 实现：`skills/hermes-loop/SKILL.md`
- 接口：`plan() → execute() → reflect() → evolve()`
- 参考：claude-into-openclaw/agent-loop.js

## 模块2：四层记忆系统（完全对齐）

- 目录：`memory/hermes/`
  - short_term（1h）
  - episodic（7d）
  - long_term（永久）
  - skill（永久+索引）
- 实现：OpenClaw memory-core + 分层配置

## 模块3：自进化技能（Hermes核心）

- 路径：`skills/hermes-skill-auto/SKILL.md`
- 逻辑：任务→提炼→生成Skill→自动安装→优化
- 参考：hermes-agent/skills/auto-generate

## 模块4：Spawn子代理（任务分解）

- 实现：`sessions_spawn()` + 复杂度判断
- 规则：复杂度>3 → spawn子代理
- 参考：nemoclaw/agents/hermes/spawn.js

## 模块5：工具编排（28+工具、6种后端）

- 白名单：`tools/hermes-tools.json`
- 沙箱：Docker/SSH/本地隔离
- 参考：Hermes官方tool registry

## 模块6：多平台网关（15+通道）

- 配置：`config/gateway-hermes.json`
- 通道：微信、钉钉、Telegram、Discord
- 参考：OpenClaw官方网关插件

## 模块7：自训练流水线（RL/轨迹）

- 实现：`skills/hermes-rl/SKILL.md`
- 逻辑：每15任务→反思→训练→优化
- 参考：Hermes RL训练文档

---

## 参考链接

- claude-into-openclaw: https://github.com/gungwang/claude-into-openclaw
- nemoclaw: https://github.com/NVIDIA/NeMoClaw
- hermes-agent: hermes-agent/skills/auto-generate
