"""50-iteration loop: solve Sokoban levels, upgrade algorithm on failure."""
from __future__ import annotations
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sokoban_import import load_sokoban_dir, try_solve
from planner.grid import parse_level
from planner.solver import solve, clear_heuristic_cache

def batch_solve(directory: str, max_expanded: int = 500_000):
    """Solve all levels in directory. Returns dict of results."""
    levels = load_sokoban_dir(directory)
    results = {}
    for fname, level in levels:
        try:
            board = parse_level(level)
            clear_heuristic_cache()
            t0 = time.perf_counter()
            r = solve(board, max_expanded=max_expanded)
            elapsed = time.perf_counter() - t0
            results[fname] = {
                'solved': r.solved,
                'cost': r.total_cost,
                'expanded': r.expanded,
                'generated': r.generated,
                'pruned': r.pruned_deadlocks,
                'time': round(elapsed, 4),
                'rows': board.rows,
                'cols': board.cols,
                'boxes': len(board.boxes),
                'bombs': len(board.bombs),
                'category': level.category,
                'message': r.message if not r.solved else '',
            }
        except Exception as e:
            results[fname] = {
                'solved': False,
                'cost': 0,
                'expanded': 0,
                'generated': 0,
                'pruned': 0,
                'time': 0,
                'rows': 0,
                'cols': 0,
                'boxes': 0,
                'bombs': 0,
                'category': 0,
                'message': str(e)[:100],
            }
    return results


def print_summary(results, label=""):
    solved = sum(1 for r in results.values() if r['solved'])
    total = len(results)
    total_exp = sum(r['expanded'] for r in results.values())
    total_time = sum(r['time'] for r in results.values())
    print(f"\n=== {label} | {solved}/{total} solved | exp={total_exp:,} | time={total_time:.2f}s ===")
    for fname, r in sorted(results.items()):
        s = "OK" if r['solved'] else "FAIL"
        print(f"  {fname:20s} [{s}] {r['rows']}x{r['cols']} B={r['boxes']} X={r['bombs']} exp={r['expanded']:>8,} t={r['time']:.3f}s {r.get('message','')}")


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "sokoban_raw"
    results = batch_solve(directory)
    print_summary(results, "Current")
