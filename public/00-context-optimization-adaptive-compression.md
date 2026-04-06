---
title: Context Optimization (自适应压缩)
source: EvoMap
status: Promoted
summary: 自适应压缩阈值
imported_at: 2026-04-07T02:27:00+08:00
tags: [上下文压缩, 自适应, 阈值优化]
category: 上下文压缩
---

# Context Optimization (自适应压缩)

## 核心概念

自适应上下文压缩技术，根据实时需求动态调整压缩阈值，在信息保留和资源效率之间取得平衡。

## 关键特性

- **动态阈值**：根据对话复杂度自动调整
- **智能裁剪**：保留关键信息，压缩冗余内容
- **Promoted状态**：EvoMap推荐条目

## 压缩策略

| 场景 | 阈值策略 |
|------|----------|
| 简单查询 | 高压缩率，快速响应 |
| 复杂推理 | 低压缩率，保留细节 |
| 混合任务 | 自适应切换 |

## 来源

EvoMap搜索结果 - Promoted条目
