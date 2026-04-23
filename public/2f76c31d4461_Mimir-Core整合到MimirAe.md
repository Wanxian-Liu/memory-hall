---
title: Mimir-Core整合到MimirAether架构_
source: MimirAether
gdi: 0.54
imported_at: 2026-04-16T20:55:43+08:00
capsule_id: 2f76c31d4461
capsule_type: optimize
---

## 当前状态

待描述

## 优化目标

Mimir-Core整合到MimirAether架构：

整合时间：2026-04-16
整合原因：简化架构，删除hermes后不影响功能

整合前架构：
- MimirAether (主项目)
- Mimir-Core (独立项目，路径: ~/.openclaw/projects/Mimir-Core/)

整合后架构：
- MimirAether/
  ├── mimicore/  (原Mimir-Core)
  └── tools/mimircore_tool.py (调用接口)

关键文件更新：
- tools/mimircore_tool.py: MIMIR_CORE_PATH改为新路径
- MEMORY.md: 更新项目架构文档

整合后Mimicore通过MimirCoreTool提供4个工具：
1. produce_capsule - 生成胶囊
2. get_capsule_by_id - 获取胶囊详情
3. list_capsules - 列出胶囊
4. improve_capsule - 改进胶囊

Ralph进化闭环保持不变：
MimirAether → produce_capsule → GDI评分 → 记忆殿堂


## 优化点

待分析

## 优化方案

待设计

## 预期效果

待评估

## 实施风险

无明显风险
