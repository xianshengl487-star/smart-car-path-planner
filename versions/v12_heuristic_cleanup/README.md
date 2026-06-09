# v12_heuristic_cleanup: Heuristic Cleanup & Tie-Breaking

## Changes
- Cleaned up heuristic to max(sum, assignment) with local variables
- Goal proximity tie-breaking at 0.01 weight for better ordering

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 45,605 | 45,605 | +0.0% |
| Total Time | 8.378s | 7.821s | -6.6% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 33 (+0.0%) | 221 | 19 | 0.005s |
| 102 | ✅ | 65 | 38 (+0.0%) | 245 | 20 | 0.008s |
| 103 | ✅ | 106 | 3,497 (+0.0%) | 11,760 | 5,163 | 0.517s |
| 104 | ✅ | 58 | 5,244 (+0.0%) | 65,551 | 6,939 | 1.324s |
| 105 | ✅ | 62 | 14,541 (+0.0%) | 65,578 | 8,349 | 2.215s |
| 106 | ✅ | 108 | 22,252 (+0.0%) | 101,547 | 26,978 | 3.752s |

**Summary:** 6/6 solved | Total Expanded: 45,605 | Total Time: 7.821s
