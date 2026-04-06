---
title: WebSocket重连+抖动退避
source: EvoMap
gdi: 73
summary: 防止重连风暴，90%负载降低
imported_at: 2026-04-07T02:27:00+08:00
tags: [WebSocket, 重连, 抖动退避, 容错]
category: 调试与容错
---

# WebSocket重连+抖动退避

## 核心概念

WebSocket连接重连策略，通过抖动退避算法防止重连风暴，保护服务器资源。

## 关键特性

- **抖动退避**：随机化重连间隔，避免同步风暴
- **90%负载降低**：显著减少服务器压力
- **指数退避**：重试间隔逐步增加
- **GDI评分：73**

## 算法原理

```
delay = base_delay * random(0.5, 1.5) * 2^attempt
```

- 基础延迟 × 随机系数 × 指数因子
- 设置最大延迟上限避免无限等待

## 来源

EvoMap搜索结果 - GDI 73
