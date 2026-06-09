# v08_wall_line_deadlock: Wall-Line Deadlock with Box Obstacles

## Changes
- Enhanced _is_deadlocked_dynamic to detect wall-line deadlock when boxes block the path toward goal
- Subtle pruning in 103/106

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 47,047 | 46,939 | -0.2% |
| Total Time | 7.714s | 7.861s | +1.9% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 35 (+0.0%) | 120 | 20 | 0.005s |
| 102 | ✅ | 65 | 39 (+0.0%) | 129 | 20 | 0.007s |
| 103 | ✅ | 106 | 3,497 (-0.9%) | 11,760 | 5,163 | 0.505s |
| 104 | ✅ | 58 | 6,575 (+0.0%) | 39,758 | 8,585 | 1.506s |
| 105 | ✅ | 62 | 14,541 (+0.0%) | 65,578 | 8,349 | 2.136s |
| 106 | ✅ | 108 | 22,252 (-0.3%) | 101,547 | 26,978 | 3.700s |

**Summary:** 6/6 solved | Total Expanded: 46,939 | Total Time: 7.861s
