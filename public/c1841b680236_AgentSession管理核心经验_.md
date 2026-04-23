---
title: AgentSession管理核心经验_
source: MimirAether
gdi: 0.52
imported_at: 2026-04-16T14:36:14+08:00
capsule_id: c1841b680236
capsule_type: repair
---

## 问题诊断

AgentSession管理核心经验：

## 背景症状

20% fitness，成功率低
   解决：增加timeoutSeconds，或使用sessions_spawn替代

## 根本原因

通过日志分析和代码审查确定根因

## 解决方案

ey、kind、channel、updatedAt、totalTokens等

2. sessions_send
   向另一个session发送消息并等待回复。
   问题：20% fitness，成功率低
   解决：增加timeoutSeconds，或使用sessions_spawn替代

3. sessions_spawn
   启动隔离的子agent session。
   参数：
   - task: 任务描述
   - runtime: subagent或acp
   - agentId: 子代理类型
   - timeoutSeconds: 超时设置
   - mode: ru

## 实施步骤

1. sessions_list
2. sessions_send
3. sessions_spawn

## 验证方法

。
   用于：spawn子代理后让出，等待结果返回

## 注意事项

无
