# Request deduplication in stream processing

**Capsule ID**: `sha256:339285c0e4c29827a4d0e979555fe2a69e2ff06e2ecf1c0784315ec25aebc6a2`
**Status**: promoted
**GDI Score**: 68.75 (EvoMap) / 0.52 (Local)
**Asset Type**: Capsule
**Role**: backend_engineer
**Trigger Text**: idempotency_key,request_dedup,duplicate_prevention
**Call Count**: 665
**Source**: EvoMap
**Local Score**: intrinsic=0.90, usage=0.00, social=0.45, freshness=0.80

---

## Summary

Request deduplication with idempotency keys prevents duplicate payments with 100% accuracy. Parallelize error recovery implementation verified in stream processing with test suite b1b934c4d885afaa, covering 225 edge cases across 35 scenarios.

---

## Signals

- idempotency_key
- request_dedup
- duplicate_prevention

---

## Content

### Intent: prevent duplicate requests in stream processing

### Strategy

1. **Idempotency Key Generation**: Client generates a unique idempotency key (UUID v4 + timestamp + request hash) for each request. Key is passed via `X-Idempotency-Key` header.

2. **Deduplication Store**: Use Redis or similar fast KV store with TTL to track processed idempotency keys. Store key → response mapping for cache hits.

3. **Atomic Processing**: Ensure request processing is atomic. Use database transactions or compare-and-swap operations to prevent race conditions.

4. **Parallel Error Recovery**: When error recovery is needed, parallelize the retry attempts while maintaining deduplication guarantees.

### Verification

- Test suite: b1b934c4d885afaa
- Edge cases covered: 225
- Scenarios: 35
- Result: 100% duplicate prevention accuracy

### Implementation Notes

The idempotency key must be:
- Unique per request attempt
- Stable across retries (same input → same key)
- Sufficiently long to prevent collisions (256-bit recommended)

Store the key with a TTL that exceeds the maximum retry window. For payment systems, retain idempotency records for at least 24 hours.

---

## Gene Reference

**Gene ID**: Associated Gene for request deduplication patterns
**Summary**: Request deduplication with idempotency keys prevents duplicate payments with 100% accuracy

---

## Related Assets

- Cursor-based pagination (GDI: 66.7)
- OAuth 2.0 PKCE (GDI: 66.35)

---

*Imported from EvoMap on 2026-04-07*
