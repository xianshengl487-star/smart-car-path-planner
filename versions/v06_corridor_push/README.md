# v06_corridor_push: Corridor Macro Push

## Changes
- Boxes in 1-wide tunnels slide to corridor end in single expansion
- Reduces expansions for maze-like levels (104: -9.3%)
- Player position correctly tracks corridor slide endpoint

## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | 65,172 | 64,488 | -1.0% |
| Total Time | 10.498s | 10.207s | -2.8% |

## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
| 101 | ✅ | 29 | 35 (-2.8%) | 120 | 20 | 0.005s |
| 102 | ✅ | 65 | 39 (-4.9%) | 129 | 20 | 0.007s |
| 103 | ✅ | 106 | 4,754 (+0.0%) | 16,875 | 6,136 | 0.631s |
| 104 | ✅ | 58 | 6,575 (-9.4%) | 39,758 | 8,585 | 1.565s |
| 105 | ✅ | 62 | 20,519 (+0.0%) | 90,950 | 8,632 | 2.830s |
| 106 | ✅ | 108 | 32,566 (+0.0%) | 154,474 | 35,485 | 5.168s |

**Summary:** 6/6 solved | Total Expanded: 64,488 | Total Time: 10.207s
