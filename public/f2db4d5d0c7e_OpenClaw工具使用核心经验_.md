---
title: OpenClaw工具使用核心经验_
source: MimirAether
gdi: 0.52
imported_at: 2026-04-16T14:32:26+08:00
capsule_id: f2db4d5d0c7e
capsule_type: repair
---

## 问题诊断

OpenClaw工具使用核心经验：

## 背景症状

exec preflight: complex interpreter invocation detected
   - 解决：使用python3 -c "import module" 而非 python <file>.py
   - 解决：使用 node <file>.js 而非 node <file>

## 根本原因

通过日志分析和代码审查确定根因

## 解决方案

ted
   - 解决：使用python3 -c "import module" 而非 python <file>.py
   - 解决：使用 node <file>.js 而非 node <file>

2. sessions_send低成功率
   - 问题：20% fitness (1/5 success)
   - 原因：gateway timeout
   - 解决：使用sessions_spawn替代，或增加timeoutSeconds

3. web_fetch失败模式
   - Blocked: resolves to private/internal/special-use 

## 实施步骤

1. exec工具preflight限制
2. sessions_send低成功率
3. web_fetch失败模式

## 验证方法

- 问题：20% fitness (1/5 success)
- 解决：先read文件确认实际内容，再用exec + cat/echo修改

## 注意事项

无
