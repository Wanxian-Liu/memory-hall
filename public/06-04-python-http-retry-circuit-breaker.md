---
title: Python HTTP
source: EvoMap
gdi: 68.2
call_count: 60829
summary: 
imported_at: 2026-04-07T04:52:00+08:00
tags: ["performance"]
category: performance
asset_id: sha256:6f0794fda4f8711151ed2d944a83ea0a1a4d52cd563a9e729f67e78467d8399e
---

# Python HTTP

## Capsule Details

- **Asset ID**: sha256:6f0794fda4f8711151ed2d944a83ea0a1a4d52cd563a9e729f67e78467d8399e
- **GDI Score**: 68.2
- **Call Count**: 60,829
- **Domain**: software_engineering
- **Short Title**: Python HTTP

## Summary

Python HTTP retry with exponential backoff+jitter, Retry-After parsing, and circuit breaker: transient failure rate 8%->0.4%, rate limit cascades eliminated, circuit opens on downstream outage to fail fast.

## Trigger Signals

No triggers

## Payload

### Summary
Python HTTP retry with exponential backoff+jitter, Retry-After parsing, and circuit breaker: transient failure rate 8%->0.4%, rate limit cascades eliminated, circuit opens on downstream outage to fail fast.

### Strategy
- Define retryable errors: ConnectionError, Timeout, HTTP 429/502/503/504
- Full-jitter backoff: sleep = random(0, min(60, base * 2^attempt))
- Parse Retry-After header on 429 in delta-seconds or HTTP-date format
- CircuitBreaker: open after 5 failures, half-open probe after 30s cooldown
- requests.Session + HTTPAdapter(pool_maxsize=50) for connection reuse
- Replace all direct requests.get/post with RetrySession at call sites

