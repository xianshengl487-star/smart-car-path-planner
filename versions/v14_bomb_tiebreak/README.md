# v14_bomb_tiebreak: Bomb Solver Tie-Breaking

## Changes
- Goal proximity tie-breaking in solve_bombs
- Stance lower bound cleanup for bomb section
- 103: -11.2%, 105: -6.7%, 106: -10.7%

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 45,605 | 41,855 | -8.2% |
| Total Time | 7.908s | 7.305s | -7.6% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 33 (+0.0%) | 221 | 19 | 0.005s |
| 102 | ✅ | 65 | 38 (+0.0%) | 245 | 20 | 0.007s |
| 103 | ✅ | 106 | 3,106 (-11.2%) | 10,599 | 4,467 | 0.449s |
| 104 | ✅ | 58 | 5,244 (+0.0%) | 65,551 | 6,939 | 1.240s |
| 105 | ✅ | 62 | 13,574 (-6.7%) | 61,521 | 7,515 | 2.108s |
| 106 | ✅ | 108 | 19,860 (-10.7%) | 93,025 | 23,738 | 3.494s |

**Summary:** 6/6 solved | Total Expanded: 41,855 | Total Time: 7.305s
