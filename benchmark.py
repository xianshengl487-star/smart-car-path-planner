"""Benchmark helper for optimization rounds."""
import time
import sys
from planner.complex_maps import get_complex_level
from planner.grid import parse_level
from planner.solver import solve, clear_heuristic_cache


def benchmark():
    results = {}
    for lid in [101, 102, 103, 104, 105, 106]:
        level = get_complex_level(lid)
        board = parse_level(level)
        clear_heuristic_cache()
        t0 = time.perf_counter()
        r = solve(board, max_expanded=500_000)
        elapsed = time.perf_counter() - t0
        results[lid] = {
            'solved': r.solved,
            'cost': r.total_cost,
            'expanded': r.expanded,
            'generated': r.generated,
            'pruned': r.pruned_deadlocks,
            'time': round(elapsed, 3),
        }
    return results


if __name__ == "__main__":
    results = benchmark()
    for lid, d in sorted(results.items()):
        s = "OK" if d['solved'] else "FAIL"
        print(f"  {lid}: [{s}] cost={d['cost']} exp={d['expanded']} gen={d['generated']} pruned={d['pruned']} time={d['time']}s")
    total_exp = sum(d['expanded'] for d in results.values())
    total_time = sum(d['time'] for d in results.values())
    solved = sum(1 for d in results.values() if d['solved'])
    print(f"  TOTAL: {solved}/6 solved, {total_exp} expanded, {total_time:.3f}s")
