# v10_stance_tightened: Tighter Stance Lower Bound

## Changes
- Improved stance lower bound with min of all 4 stance positions
- Accounts for car heading direction cost more accurately

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 45,605 | 45,605 | +0.0% |
| Total Time | 7.465s | 8.116s | +8.7% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 33 (+0.0%) | 111 | 19 | 0.008s |
| 102 | ✅ | 65 | 38 (+0.0%) | 123 | 20 | 0.011s |
| 103 | ✅ | 106 | 3,497 (+0.0%) | 11,760 | 5,163 | 0.509s |
| 104 | ✅ | 58 | 5,244 (+0.0%) | 32,776 | 6,939 | 1.290s |
| 105 | ✅ | 62 | 14,541 (+0.0%) | 65,578 | 8,349 | 2.211s |
| 106 | ✅ | 108 | 22,252 (+0.0%) | 101,547 | 26,978 | 4.088s |

**Summary:** 6/6 solved | Total Expanded: 45,605 | Total Time: 8.116s
