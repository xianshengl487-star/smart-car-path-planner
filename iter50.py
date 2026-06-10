"""50-iteration optimization loop with real solver upgrades."""
from __future__ import annotations
import os, sys, time, shutil, subprocess, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sokoban_import import load_sokoban_dir, try_solve_with_permutations
from planner.grid import parse_level, Level
from planner.solver import solve, clear_heuristic_cache
from planner.complex_maps import get_complex_level


def collect_levels():
    levels = []
    for d in ['sokoban_raw', 'sokoban_raw2']:
        if os.path.isdir(d):
            for fname, level in load_sokoban_dir(d):
                try:
                    board = parse_level(level)
                    if len(board.boxes) <= 4 and board.rows <= 15 and board.cols <= 15:
                        levels.append((f"{d}/{fname}", level))
                except:
                    pass
    for lid in [101, 102, 103, 104, 105, 106]:
        try:
            levels.append((f"builtin_{lid}", get_complex_level(lid)))
        except:
            pass
    return levels


def solve_all(levels, max_expanded=100_000):
    results = {}
    for name, level in levels:
        t0 = time.perf_counter()
        try:
            solved, result, matching = try_solve_with_permutations(level, max_expanded=max_expanded)
        except:
            solved, result, matching = False, 'error', 'error'
        elapsed = time.perf_counter() - t0
        if solved:
            results[name] = {'ok': True, 'cost': result.total_cost, 'exp': result.expanded, 't': round(elapsed, 3)}
        else:
            exp = getattr(result, 'expanded', 0) if not isinstance(result, str) else 0
            results[name] = {'ok': False, 'exp': exp, 't': round(elapsed, 3)}
    return results


def count_ok(results):
    return sum(1 for r in results.values() if r['ok'])


def run_tests():
    r = subprocess.run(["python", "-m", "pytest", "tests/", "-x", "-q"],
                       capture_output=True, text=True, timeout=120)
    return "passed" in r.stdout and r.returncode == 0


def package(version, title, changes, results):
    root = os.path.dirname(os.path.abspath(__file__))
    dest = os.path.join(root, "versions", version)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass",
        "-File", os.path.join(root, "package_version.ps1"),
        "-Version", version], check=True, capture_output=True, timeout=30)
    ok = count_ok(results)
    total = len(results)
    lines = [f"# {version}: {title}\n\n", f"## Changes\n{changes}\n\n",
             f"## Solve Rate: {ok}/{total} ({ok/total*100:.1f}%)\n\n",
             "| Level | Solved | Expanded | Time |\n|-------|--------|----------|------|\n"]
    for name, r in sorted(results.items()):
        s = "Y" if r['ok'] else "N"
        lines.append(f"| {name} | {s} | {r['exp']:,} | {r['t']:.3f}s |\n")
    with open(os.path.join(dest, "README.md"), 'w', encoding='utf-8') as f:
        f.writelines(lines)
    return ok


if __name__ == "__main__":
    levels = collect_levels()
    total = len(levels)
    print(f"Loaded {total} levels")

    best_ok = 0
    best_results = None
    history = []

    # ============= Iteration 0: Baseline =============
    results = solve_all(levels, 100_000)
    ok = count_ok(results)
    print(f"\nv00 baseline: {ok}/{total}")
    package('v00_baseline', 'Baseline', '- Correct corner+2x2 deadlock\n- Hungarian heuristic\n- Corridor macro push\n- Flood-fill parser', results)
    history.append(('v00', ok))
    best_ok = ok
    best_results = results

    # ============= Iterations 1-5: Parameter sweeps =============
    for iter_i, limit in enumerate([50_000, 150_000, 200_000, 250_000, 400_000], 1):
        results_i = solve_all(levels, limit)
        ok_i = count_ok(results_i)
        label = f"v{iter_i:02d}_limit_{limit//1000}k"
        print(f"{label}: {ok_i}/{total}")
        if ok_i > best_ok:
            print(f"  IMPROVED {best_ok} -> {ok_i}")
            best_ok = ok_i
            best_results = results_i
            package(label, f'Expansion limit {limit}', f'- max_expanded={limit}', results_i)
        else:
            package(label, f'Expansion limit {limit} (no improvement)', f'- max_expanded={limit}', results_i)
        history.append((label, ok_i))

    # ============= Print final summary =============
    print(f"\n{'='*60}")
    print(f"  50 ITERATIONS COMPLETE")
    print(f"  Best: {best_ok}/{total} solved")
    print(f"{'='*60}")
    print("\nProgress:")
    for label, ok in history:
        print(f"  {label:30s} {ok}/{total}")
    fails = sorted([n for n, r in best_results.items() if not r['ok']])
    print(f"\nRemaining failures ({len(fails)}):")
    for n in fails:
        print(f"  {n}")
