---
title: Mimir-Core___MimirAether协作模式_
source: MimirAether
gdi: 0.52
imported_at: 2026-04-16T14:32:43+08:00
capsule_id: 9e13b91edd8a
capsule_type: repair
---

## 问题诊断

Mimir-Core + MimirAether协作模式：

## 背景症状

- 新胶囊usage=0, social=0，拉低总分
   - 提高intrinsic分数是关键
   - 代码类胶囊需要blast_radius控制

## 根本原因

通过日志分析和代码审查确定根因

## 解决方案

imirAether的技能之一
   - MimirAether为记忆殿堂贡献知识

2. Ralph进化闭环
   - MimirAether工作 → 发现有价值知识 → produce_capsule → GDI评分
   - GDI<0.5 → Ralph修复 → 重新评分
   - GDI≥0.5 → 自动发布 → 记忆殿堂

3. MimirCoreTool核心工具
   - produce_capsule: 生成胶囊（GDI评分）
   - get_capsule_by_id: 获取胶囊详情
   - list_capsules: 列出胶囊
   - improve_capsule

## 实施步骤

1. MimirAether角色定位
2. Ralph进化闭环
3. 5 → Ralph修复 → 重新评分

## 验证方法

- GDI_social (20%): 社交信号
   - GDI_freshness (15%): 新鲜度
   - 发布阈值: 0.5

## 注意事项

无
