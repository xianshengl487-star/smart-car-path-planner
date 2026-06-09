# v18_explosion_inline: Inline Explosion Cells

## Changes
- Inlined boundary check in _explosion_cells with direct coordinate comparison
- Removed redundant _is_boundary_wall function
- Cleaner code with same performance

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 41,315 | 41,315 | +0.0% |
| Total Time | 6.489s | 6.629s | +2.1% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 33 (+0.0%) | 221 | 19 | 0.006s |
| 102 | ✅ | 65 | 38 (+0.0%) | 245 | 20 | 0.007s |
| 103 | ✅ | 106 | 2,916 (+0.0%) | 10,044 | 4,110 | 0.392s |
| 104 | ✅ | 58 | 5,244 (+0.0%) | 65,551 | 6,939 | 1.302s |
| 105 | ✅ | 62 | 13,384 (+0.0%) | 60,849 | 7,322 | 1.805s |
| 106 | ✅ | 108 | 19,700 (+0.0%) | 92,517 | 23,479 | 3.117s |

**Summary:** 6/6 solved | Total Expanded: 41,315 | Total Time: 6.629s
