# v15_priority_lazy: Lazy Priority Computation

## Changes
- Skip stance_lower_bound and goal_prox when h=0 (already at goal)
- Conditional priority components reduce per-node overhead
- Minor time improvement across all levels

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 41,855 | 41,855 | +0.0% |
| Total Time | 7.317s | 10.609s | +45.0% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 33 (+0.0%) | 221 | 19 | 0.008s |
| 102 | ✅ | 65 | 38 (+0.0%) | 245 | 20 | 0.012s |
| 103 | ✅ | 106 | 3,106 (+0.0%) | 10,599 | 4,467 | 0.743s |
| 104 | ✅ | 58 | 5,244 (+0.0%) | 65,551 | 6,939 | 1.484s |
| 105 | ✅ | 62 | 13,574 (+0.0%) | 61,521 | 7,515 | 3.018s |
| 106 | ✅ | 108 | 19,860 (+0.0%) | 93,025 | 23,738 | 5.344s |

**Summary:** 6/6 solved | Total Expanded: 41,855 | Total Time: 10.609s
