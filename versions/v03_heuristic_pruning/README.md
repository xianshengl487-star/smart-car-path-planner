# v03_heuristic_pruning: Heuristic & Deadlock Pruning

## Changes
- Hungarian assignment with early termination pruning
- Deadlock cells frozenset for O(1) lookup
- Stance pose optimization with local variable caching
- Simplified bomb heuristic (removed redundant loops)

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 68,212 | 68,212 | +0.0% |
| Total Time | 11.769s | 10.424s | -11.4% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 36 (+0.0%) | 125 | 19 | 0.005s |
| 102 | ✅ | 65 | 41 (+0.0%) | 138 | 19 | 0.007s |
| 103 | ✅ | 106 | 4,960 (+0.0%) | 17,519 | 6,499 | 0.617s |
| 104 | ✅ | 58 | 7,664 (+0.0%) | 46,322 | 10,037 | 1.670s |
| 105 | ✅ | 62 | 20,939 (+0.0%) | 91,853 | 8,946 | 2.816s |
| 106 | ✅ | 108 | 34,572 (+0.0%) | 161,235 | 38,496 | 5.307s |

**Summary:** 6/6 solved | Total Expanded: 68,212 | Total Time: 10.424s
