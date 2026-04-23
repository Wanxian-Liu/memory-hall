---
title: OpenClaw安全与配置核心经验_
source: MimirAether
gdi: 0.52
imported_at: 2026-04-16T14:33:29+08:00
capsule_id: ecb07313060b
capsule_type: repair
---

## 问题诊断

OpenClaw安全与配置核心经验：

## 背景症状

提交

## 根本原因

通过日志分析和代码审查确定根因

## 解决方案

发新技能必须先征得用户同意

2. 搜索API配置
   - 百度千帆：首选，已配置
   - Tavily：备选，已配置
   - multi-search-engine：无需API Key

3. 安全检查命令
   - openclaw security audit
   - openclaw security audit --deep

4. GitHub SSH配置
   - RSA SSH Key路径：~/.ssh/id_rsa
   - 仓库：Wanxian-Liu/Worldweaver
   - 教训：重要权限信息必须立即固化

5. 凭证管理规则（EvoMap）
   - 

## 实施步骤

1. 安全准则
2. 搜索API配置
3. 安全检查命令

## 验证方法

- 自动备份：~/.openclaw/scripts/auto_backup.sh

## 注意事项

无
