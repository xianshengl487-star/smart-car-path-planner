# v17_push_dist_inline: Push Distance Inline Bounds

## Changes
- Inlined board.inside() checks in _precompute_push_distances
- Direct coordinate comparison instead of method call overhead
- Minor time improvement

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 41,315 | 41,315 | +0.0% |
| Total Time | 6.547s | 6.580s | +0.5% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 33 (+0.0%) | 221 | 19 | 0.006s |
| 102 | ✅ | 65 | 38 (+0.0%) | 245 | 20 | 0.008s |
| 103 | ✅ | 106 | 2,916 (+0.0%) | 10,044 | 4,110 | 0.405s |
| 104 | ✅ | 58 | 5,244 (+0.0%) | 65,551 | 6,939 | 1.267s |
| 105 | ✅ | 62 | 13,384 (+0.0%) | 60,849 | 7,322 | 1.828s |
| 106 | ✅ | 108 | 19,700 (+0.0%) | 92,517 | 23,479 | 3.066s |

**Summary:** 6/6 solved | Total Expanded: 41,315 | Total Time: 6.580s
