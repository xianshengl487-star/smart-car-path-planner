# v19_heuristic_cleanup: Heuristic Function Cleanup

## Changes
- Removed dead _bomb_heuristic function
- Cleaned up _heuristic_with_distances inline
- Removed duplicate code in solver

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 41,315 | 41,315 | +0.0% |
| Total Time | 6.503s | 6.744s | +3.7% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 33 (+0.0%) | 221 | 19 | 0.006s |
| 102 | ✅ | 65 | 38 (+0.0%) | 245 | 20 | 0.008s |
| 103 | ✅ | 106 | 2,916 (+0.0%) | 10,044 | 4,110 | 0.410s |
| 104 | ✅ | 58 | 5,244 (+0.0%) | 65,551 | 6,939 | 1.285s |
| 105 | ✅ | 62 | 13,384 (+0.0%) | 60,849 | 7,322 | 1.847s |
| 106 | ✅ | 108 | 19,700 (+0.0%) | 92,517 | 23,479 | 3.187s |

**Summary:** 6/6 solved | Total Expanded: 41,315 | Total Time: 6.744s
