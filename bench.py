"""Automated 20-round optimization benchmark."""
import time
import sys
import os

# Ensure we can import planner
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from planner.complex_maps import get_complex_level
from planner.grid import parse_level
from planner.solver import solve, clear_heuristic_cache


def run_benchmark():
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
            'time': round(elapsed, 4),
        }
    return results


def print_results(results, label=""):
    print(f"\n=== {label} ===")
    for lid, d in sorted(results.items()):
        s = "OK" if d['solved'] else "FAIL"
        print(f"  {lid}: [{s}] cost={d['cost']} exp={d['expanded']} gen={d['generated']} pruned={d['pruned']} t={d['time']}s")
    total_exp = sum(d['expanded'] for d in results.values())
    total_gen = sum(d['generated'] for d in results.values())
    total_time = sum(d['time'] for d in results.values())
    solved = sum(1 for d in results.values() if d['solved'])
    print(f"  SUM: {solved}/6 solved | exp={total_exp} gen={total_gen} t={total_time:.3f}s")
    return total_exp, total_gen, total_time


if __name__ == "__main__":
    results = run_benchmark()
    print_results(results, "Current")
