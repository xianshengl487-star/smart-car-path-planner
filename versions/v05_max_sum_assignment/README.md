# v05_max_sum_assignment: Max(Sum, Assignment) Heuristic

## Changes
- Tighter heuristic: max of simple sum and min-assignment cost
- Reduces expansion for multi-box levels (103: -4.1%, 106: -5.8%)

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 68,212 | 65,172 | -4.5% |
| Total Time | 10.732s | 10.631s | -0.9% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 36 (+0.0%) | 125 | 19 | 0.006s |
| 102 | ✅ | 65 | 41 (+0.0%) | 138 | 19 | 0.008s |
| 103 | ✅ | 106 | 4,754 (-4.2%) | 16,875 | 6,136 | 0.651s |
| 104 | ✅ | 58 | 7,256 (-5.3%) | 44,150 | 9,348 | 1.653s |
| 105 | ✅ | 62 | 20,519 (-2.0%) | 90,950 | 8,632 | 3.007s |
| 106 | ✅ | 108 | 32,566 (-5.8%) | 154,474 | 35,485 | 5.307s |

**Summary:** 6/6 solved | Total Expanded: 65,172 | Total Time: 10.631s
