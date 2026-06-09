"""Package a version and generate its README."""
import subprocess, sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
            'solved': r.solved, 'cost': r.total_cost,
            'expanded': r.expanded, 'generated': r.generated,
            'pruned': r.pruned_deadlocks, 'time': round(elapsed, 4),
        }
    return results

def package(version, title, changes, baseline_results=None):
    root = os.path.dirname(os.path.abspath(__file__))
    dest = os.path.join(root, "versions", version)
    if os.path.exists(dest):
        import shutil
        shutil.rmtree(dest)

    # Run benchmark
    results = benchmark()

    # Package
    subprocess.run([
        "powershell", "-ExecutionPolicy", "Bypass",
        "-File", os.path.join(root, "package_version.ps1"),
        "-Version", version,
    ], check=True, capture_output=True)

    # Generate README
    total_exp = sum(d['expanded'] for d in results.values())
    total_gen = sum(d['generated'] for d in results.values())
    total_time = sum(d['time'] for d in results.values())
    solved = sum(1 for d in results.values() if d['solved'])

    # Build comparison
    comparison = ""
    if baseline_results:
        old_exp = sum(d['expanded'] for d in baseline_results.values())
        old_time = sum(d['time'] for d in baseline_results.values())
        exp_pct = (total_exp - old_exp) / old_exp * 100 if old_exp else 0
        time_pct = (total_time - old_time) / old_time * 100 if old_time else 0
        comparison = f"""
## Performance vs Previous

| Metric | Previous | Current | Change |
|--------|----------|---------|--------|
| Total Expanded | {old_exp:,} | {total_exp:,} | {exp_pct:+.1f}% |
| Total Time | {old_time:.3f}s | {total_time:.3f}s | {time_pct:+.1f}% |
"""

    lines = []
    for lid, d in sorted(results.items()):
        s = "✅" if d['solved'] else "❌"
        old_note = ""
        if baseline_results and lid in baseline_results:
            ob = baseline_results[lid]
            if ob['expanded'] > 0:
                pct = (d['expanded'] - ob['expanded']) / ob['expanded'] * 100
                old_note = f" ({pct:+.1f}%)"
        lines.append(f"| {lid} | {s} | {d['cost']} | {d['expanded']:,}{old_note} | {d['generated']:,} | {d['pruned']:,} | {d['time']:.3f}s |")

    readme = f"""# {version}: {title}

## Changes
{changes}
{comparison}
## Benchmark Results

| Level | Solved | Cost | Expanded | Generated | Pruned | Time |
|-------|--------|------|----------|-----------|--------|------|
{chr(10).join(lines)}

**Summary:** {solved}/6 solved | Total Expanded: {total_exp:,} | Total Time: {total_time:.3f}s
"""
    readme_path = os.path.join(dest, "README.md")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme)

    print(f"  [{version}] {solved}/6 solved | exp={total_exp:,} t={total_time:.3f}s -> {dest}")
    return results

if __name__ == "__main__":
    import importlib
    version = sys.argv[1] if len(sys.argv) > 1 else "test"
    title = sys.argv[2] if len(sys.argv) > 2 else "Test"
    changes = sys.argv[3] if len(sys.argv) > 3 else "Test changes"
    package(version, title, changes)
