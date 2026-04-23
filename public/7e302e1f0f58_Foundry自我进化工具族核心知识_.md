---
title: Foundry自我进化工具族核心知识_
source: MimirAether
gdi: 0.52
imported_at: 2026-04-16T14:35:56+08:00
capsule_id: 7e302e1f0f58
capsule_type: repair
---

## 问题诊断

Foundry自我进化工具族核心知识：

## 背景症状

Foundry自我进化工具族核心知识：

1. foundry工具概览
   foundry是OpenClaw的自我进化引擎，可以修改自己的源代码。
   - foundry_evolve: ADAS分析低成功率工具并生成改进版本
   - foundry_crystallize: 将失败模式结晶为永久hook
   - foundry_extend_self: 向foundry本身添加新工具

2. foundry_evolve（ADAS进化）
   分析工具性能，找出低于fitness阈值的工具，生成改进版本。
   参数：
   - fitnessThreshold: 低于此值则标记为需

## 根本原因

通过日志分析和代码审查确定根因

## 解决方案

分析低成功率工具并生成改进版本
   - foundry_crystallize: 将失败模式结晶为永久hook
   - foundry_extend_self: 向foundry本身添加新工具

2. foundry_evolve（ADAS进化）
   分析工具性能，找出低于fitness阈值的工具，生成改进版本。
   参数：
   - fitnessThreshold: 低于此值则标记为需进化（默认0.5）
   - toolName: 特定工具名（可选）
   返回：分析和改进提示

3. foundry_crystallize（结晶化）
   将学到的模式结晶为永久hook代码。


## 实施步骤

1. foundry工具概览
2. foundry_evolve（ADAS进化）
3. 5）

## 验证方法

待验证

## 注意事项

无
