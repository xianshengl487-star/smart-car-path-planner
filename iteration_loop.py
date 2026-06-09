"""50-iteration loop: solve imported Sokoban levels, upgrade algorithm on failure.

Each iteration:
1. Collect all levels from sokoban_raw/ and sokoban_raw2/
2. Try to solve each with permutation matching
3. Track solve rate
4. If solve rate drops or new levels fail, diagnose and upgrade algorithm
"""
from __future__ import annotations
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sokoban_import import load_sokoban_dir, try_solve_with_matching
from planner.grid import parse_level, Level
from planner.solver import solve, clear_heuristic_cache
from planner.complex_maps import get_complex_level

LEVEL_DIRS = ['sokoban_raw', 'sokoban_raw2']
BUILTIN_IDS = [101, 102, 103, 104, 105, 106]


def collect_levels():
    """Collect all available levels."""
    all_levels = []
    for d in LEVEL_DIRS:
        if os.path.isdir(d):
            for fname, level in load_sokoban_dir(d):
                all_levels.append((f"{d}/{fname}", level))
    for lid in BUILTIN_IDS:
        try:
            level = get_complex_level(lid)
            all_levels.append((f"builtin_{lid}", level))
        except:
            pass
    return all_levels


def batch_solve(levels, max_expanded=500_000, time_limit=600):
    """Solve all levels with time limit."""
    results = {}
    total_time = 0
    for name, level in levels:
        if total_time > time_limit:
            results[name] = {'solved': False, 'cost': 0, 'expanded': 0, 'time': 0,
                           'message': 'TIME_LIMIT', 'category': level.category}
            continue
        t0 = time.perf_counter()
        solved, result, matching = try_solve_with_matching(level, max_expanded)
        elapsed = time.perf_counter() - t0
        total_time += elapsed
        if solved:
            results[name] = {
                'solved': True, 'cost': result.total_cost,
                'expanded': result.expanded, 'generated': result.generated,
                'pruned': result.pruned_deadlocks, 'time': round(elapsed, 4),
                'matching': matching, 'category': level.category,
            }
        else:
            expanded = getattr(result, 'expanded', 0) if not isinstance(result, str) else 0
            results[name] = {
                'solved': False, 'cost': 0, 'expanded': expanded,
                'generated': 0, 'pruned': 0, 'time': round(elapsed, 4),
                'matching': matching, 'category': level.category,
                'message': str(getattr(result, 'message', result))[:80],
            }
    return results


def summary(results):
    solved = sum(1 for r in results.values() if r['solved'])
    total = len(results)
    total_exp = sum(r['expanded'] for r in results.values())
    total_time = sum(r['time'] for r in results.values())
    return solved, total, total_exp, total_time


def print_results(results, label=""):
    solved, total, total_exp, total_time = summary(results)
    print(f"\n{'='*70}")
    print(f"  {label} | {solved}/{total} solved | exp={total_exp:,} | time={total_time:.2f}s")
    print(f"{'='*70}")
    # Show failures first, then successes
    failures = {k: v for k, v in results.items() if not v['solved']}
    successes = {k: v for k, v in results.items() if v['solved']}
    for name, r in sorted(failures.items()):
        print(f"  [FAIL] {name:50s} exp={r['expanded']:>8,} t={r['time']:.3f}s {r.get('message','')}")
    for name, r in sorted(successes.items()):
        print(f"  [OK]   {name:50s} exp={r['expanded']:>8,} t={r['time']:.3f}s")


if __name__ == "__main__":
    levels = collect_levels()
    print(f"Collected {len(levels)} levels total")

    results = batch_solve(levels)
    print_results(results, "Baseline")
