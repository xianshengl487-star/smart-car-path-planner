# v01_baseline: Baseline

## Changes
Initial baseline with Hungarian heuristic, frozen deadlock, adaptive expansion, improved bomb heuristic.

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 36 | 125 | 19 | 0.006s |
| 102 | ✅ | 65 | 41 | 138 | 19 | 0.008s |
| 103 | ✅ | 106 | 4,960 | 17,519 | 6,499 | 0.695s |
| 104 | ✅ | 58 | 7,664 | 46,322 | 10,037 | 2.261s |
| 105 | ✅ | 62 | 20,939 | 91,853 | 8,946 | 3.186s |
| 106 | ✅ | 108 | 34,572 | 161,235 | 38,496 | 6.116s |

**Summary:** 6/6 solved | Total Expanded: 68,212 | Total Time: 12.271s
