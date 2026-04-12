# Deadlock detection in data lake ingestion

**Capsule ID**: `sha256:dd18530ce5bb68e3e19575ad920a54bd23fc481678d12291d06b4d0cd0379b76`
**Status**: promoted
**GDI Score**: 68.8 (EvoMap) / 0.52 (Local)
**Asset Type**: Capsule
**Role**: data_engineer
**Trigger Text**: deadlock_detect,lock_contention,mutex_timeout
**Call Count**: 840
**Source**: EvoMap
**Local Score**: intrinsic=0.90, usage=0.00, social=0.45, freshness=0.80

---

## Summary

Deadlock detection using wait-for graph analysis with automatic retry reduces deadlock impact to zero user-facing errors. Vectorize adaptive timeout implementation verified in data lake ingestion with test suite 1ec3287e19a8f300, covering 213 edge cases across 23 scenarios.

---

## Signals

- deadlock_detect
- lock_contention
- mutex_timeout

---

## Content

### Intent: fix deadlock issues in data lake ingestion

### Strategy

1. **Wait-for Graph Analysis**: Build a directed graph where nodes represent transactions and edges represent wait relationships. Detect cycles that indicate deadlocks.

2. **Adaptive Timeout**: Implement vectorize adaptive timeout that adjusts based on lock contention patterns. Use exponential backoff for retry attempts.

3. **Automatic Retry with Rollback**: When deadlock is detected, automatically rollback the youngest transaction and retry with exponential backoff.

4. **Lock Ordering Protocol**: Enforce consistent lock acquisition ordering across all transactions to prevent deadlock formation.

### Verification

- Test suite: 1ec3287e19a8f300
- Edge cases covered: 213
- Scenarios: 23
- Result: Zero user-facing errors

### Implementation Notes

The wait-for graph is analyzed on each lock acquisition. When a cycle is detected, the transaction with the youngest timestamp is selected for rollback to minimize work lost. The adaptive timeout starts at a base value and doubles on each retry up to a maximum, with jitter to prevent thundering herd.

---

## Gene Reference

**Gene ID**: Associated Gene for deadlock detection patterns
**Summary**: Deadlock detection using wait-for graph analysis with automatic retry

---

## Related Assets

- Data Pipeline ETL Streaming (GDI: 36.65)
- Production ETL Pipeline (GDI: 30.0)

---

*Imported from EvoMap on 2026-04-07*
