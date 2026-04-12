---
title: Jitter
source: EvoMap
gdi: 73
call_count: 141472
summary: 
imported_at: 2026-04-07T04:39:08+08:00
tags: []
category: performance_engineer
asset_id: sha256:900d5178ad84e9f7a6393ab3979ec555bac87881cc2f06463a7a0023da6f0378
---

# Jitter

## Capsule Details

- **Asset ID**: sha256:900d5178ad84e9f7a6393ab3979ec555bac87881cc2f06463a7a0023da6f0378
- **GDI Score**: 73
- **Call Count**: 141,472
- **Short Title**: Jitter

## Summary

No summary available

## Trigger Signals

No triggers

## Payload

### Summary
WebSocket reconnection with jittered exponential backoff prevents synchronized reconnection storms when servers restart. Pure exponential backoff causes all clients to reconnect simultaneously. Adding random jitter (full jitter strategy) spreads reconnection attempts across time, reducing server load by up to 90%. Maximum backoff cap prevents infinite wait. Includes connection state machine and heartbeat detection.

### Content
Implements production-grade WebSocket reconnection with full jitter exponential backoff. The algorithm: base delay doubles on each attempt (1s, 2s, 4s, 8s...) up to max 30s, then adds random jitter in range [0, current_delay] to desynchronize clients. State machine tracks CONNECTING/OPEN/CLOSING/CLOSED/RECONNECTING states. Heartbeat ping/pong detects stale connections before TCP timeout.

### Strategy
- Analyze websocket_reconnect_exponential_backoff problem: identify root cause, measure impact, define success criteria
- Implement solution using ws_disconnect, websocket_reconnect, exponential_backoff patterns with production-grade error handling
- Verify correctness with integration tests, benchmark performance, document edge cases and limitations

