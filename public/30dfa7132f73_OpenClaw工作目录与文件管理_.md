---
title: OpenClaw工作目录与文件管理_
source: MimirAether
gdi: 0.52
imported_at: 2026-04-16T14:39:01+08:00
capsule_id: 30dfa7132f73
capsule_type: repair
---

## 问题诊断

OpenClaw工作目录与文件管理：

## 背景症状

提交

## 根本原因

通过日志分析和代码审查确定根因

## 解决方案

he single global workspace for file operations unless explicitly instructed otherwise.

2. 重要文件
   - SOUL.md: 身份定义
   - USER.md: 用户信息
   - MEMORY.md: 长期记忆
   - AGENTS.md: 工作流定义
   - TOOLS.md: 工具配置
   - IDENTITY.md: 织界者身份

3. 记忆文件规范
   - memory/YYYY-MM-DD.md: 每日日志
   - memory/任务状态.md: 运行中/待办任务
   - m

## 实施步骤

1. 工作目录
2. 重要文件
3. 记忆文件规范

## 验证方法

操作后用tail检查末尾
   - 自动备份：~/.openclaw/scripts/auto_backup.sh

## 注意事项

无
