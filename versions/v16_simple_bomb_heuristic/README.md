# v16_simple_bomb_heuristic: Simplified Bomb Heuristic

## Changes
- Simplified _heuristic_dynamic to direct Manhattan (bombs exist) or wall-aware BFS (bombs gone)
- Removed _bomb_heuristic indirection
- 103: -6.1%, 105: -1.4%, 106: -0.8%

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 41,855 | 41,315 | -1.3% |
| Total Time | 7.078s | 6.658s | -5.9% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 33 (+0.0%) | 221 | 19 | 0.006s |
| 102 | ✅ | 65 | 38 (+0.0%) | 245 | 20 | 0.008s |
| 103 | ✅ | 106 | 2,916 (-6.1%) | 10,044 | 4,110 | 0.399s |
| 104 | ✅ | 58 | 5,244 (+0.0%) | 65,551 | 6,939 | 1.255s |
| 105 | ✅ | 62 | 13,384 (-1.4%) | 60,849 | 7,322 | 1.853s |
| 106 | ✅ | 108 | 19,700 (-0.8%) | 92,517 | 23,479 | 3.137s |

**Summary:** 6/6 solved | Total Expanded: 41,315 | Total Time: 6.658s
