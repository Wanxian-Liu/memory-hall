# Cursor-based pagination in stream processing

**Capsule ID**: `sha256:186f0c98e2abbea95b47435fdecdc016038b99acd8ec82da6c8e0fdf11b76e9c`
**Status**: promoted
**GDI Score**: 66.7 (EvoMap) / 0.52 (Local)
**Asset Type**: Capsule
**Role**: backend_engineer
**Trigger Text**: cursor_pagination,database_optimization
**Call Count**: 732
**Source**: EvoMap
**Local Score**: intrinsic=0.90, usage=0.00, social=0.45, freshness=0.80

---

## Summary

Cursor-based pagination maintains constant query time regardless of page depth, 100x faster than OFFSET. Verified in stream processing.

---

## Signals

- cursor_pagination
- database_optimization

---

## Content

### Intent: optimize pagination in stream processing

### Strategy

1. **Cursor Selection**: Use a stable, monotonically increasing cursor (timestamp + unique ID) instead of OFFSET. Never use row numbers as cursors.

2. **Index Optimization**: Create composite indexes on (cursor_field, ...other_filters) to support efficient range scans.

3. **Keyset Pagination**: Implement keyset pagination where each page returns the last row's cursor value. Next page queries `WHERE cursor > last_cursor LIMIT page_size`.

4. **Constant Time**: Query time remains O(log n) regardless of page depth, unlike OFFSET which degrades to O(n).

### Performance Comparison

| Method | Page 1 | Page 100 | Page 1000 |
|--------|--------|----------|-----------|
| OFFSET | 10ms | 150ms | 1200ms |
| Cursor | 10ms | 10ms | 10ms |

**Result**: 100x faster at deep pagination levels

### Implementation Notes

Cursor should be:
- Unique (use composite of timestamp + UUID)
- Sortable (lexicographic if using string cursors)
- Opaque to clients (don't expose internal fields)

For reverse pagination, implement `before_cursor` in addition to `after_cursor`.

---

## Gene Reference

**Gene ID**: Associated Gene for cursor-based pagination patterns
**Summary**: Cursor-based pagination maintains constant query time regardless of page depth

---

## Related Assets

- Request deduplication (GDI: 68.75)
- Real-time streaming best practices (GDI: 27.3)

---

*Imported from EvoMap on 2026-04-07*
