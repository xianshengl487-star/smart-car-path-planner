"""50-iteration loop: solve curated Sokoban levels, upgrade algorithm on failure.

Strategy:
1. Load all levels from imported Sokoban collections
2. Filter to tractable levels (<=5 boxes, grid <=15x15)
3. Try to solve each with permutation matching
4. Track failures, diagnose, upgrade solver
5. Repeat 50 times
"""
from __future__ import annotations
import os, sys, time, json, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sokoban_import import load_sokoban_dir, try_solve_with_matching
from planner.grid import parse_level, Level
from planner.solver import solve, clear_heuristic_cache
from planner.complex_maps import get_complex_level

LEVEL_DIRS = ['sokoban_raw', 'sokoban_raw2']
BUILTIN_IDS = [101, 102, 103, 104, 105, 106]
MAX_BOXES = 4
MAX_GRID_SIZE = 15
MAX_EXPANDED = 200_000
TIME_LIMIT_PER_LEVEL = 30  # seconds


def collect_levels():
    """Collect all tractable levels."""
    all_levels = []
    for d in LEVEL_DIRS:
        if os.path.isdir(d):
            for fname, level in load_sokoban_dir(d):
                board = parse_level(level)
                # Filter: tractable size
                if len(board.boxes) <= MAX_BOXES and board.rows <= MAX_GRID_SIZE and board.cols <= MAX_GRID_SIZE:
                    all_levels.append((f"{d}/{fname}", level))
                else:
                    pass  # skip too-large levels
    for lid in BUILTIN_IDS:
        try:
            level = get_complex_level(lid)
            all_levels.append((f"builtin_{lid}", level))
        except:
            pass
    return all_levels


def batch_solve(levels, max_expanded=MAX_EXPANDED):
    """Solve all levels."""
    results = {}
    for name, level in levels:
        t0 = time.perf_counter()
        try:
            solved, result, matching = try_solve_with_matching(level, max_expanded)
        except Exception as e:
            solved, result, matching = False, str(e), "error"
        elapsed = time.perf_counter() - t0
        if elapsed > TIME_LIMIT_PER_LEVEL * 2:
            # Skip if too slow
            results[name] = {
                'solved': False, 'cost': 0, 'expanded': 0, 'time': round(elapsed, 4),
                'matching': 'timeout', 'category': level.category, 'message': 'timeout',
            }
            continue
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
    failures = {k: v for k, v in results.items() if not v['solved']}
    successes = {k: v for k, v in results.items() if v['solved']}
    if failures:
        print(f"  FAILURES ({len(failures)}):")
        for name, r in sorted(failures.items()):
            print(f"    {name:45s} exp={r['expanded']:>8,} t={r['time']:.3f}s {r.get('message','')}")
    print(f"  SUCCESSES ({len(successes)}):")
    for name, r in sorted(successes.items()):
        print(f"    {name:45s} exp={r['expanded']:>8,} t={r['time']:.3f}s match={r.get('matching','')}")


if __name__ == "__main__":
    levels = collect_levels()
    print(f"Collected {len(levels)} tractable levels (<= {MAX_BOXES} boxes, <= {MAX_GRID_SIZE}x{MAX_GRID_SIZE})")

    results = batch_solve(levels)
    print_results(results, "Iteration 0")
    solved, total, _, _ = summary(results)
    print(f"\nSolve rate: {solved}/{total} = {solved/total*100:.1f}%")
