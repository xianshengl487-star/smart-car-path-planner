"""Benchmark loop that runs N iterations of solving complex maps.

Each iteration solves all 3 complex maps and records metrics:
  expanded, generated, cost, pushes, recognition_cost, explosion_count, solved, pruned_deadlocks

Results are saved to .orchestration/optimization_runs/<timestamp>.json.

Usage:
    python optimization_loop.py --iterations 50
    python optimization_loop.py --iterations 3 --verbose
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from planner.complex_maps import all_complex_levels
from planner.grid import parse_level
from planner.solver import solve, clear_heuristic_cache


PROJECT_ROOT = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_ROOT / ".orchestration" / "optimization_runs"

THEORETICAL_OPTIMIZATIONS = [
    "wall-aware box-to-goal heuristic",
    "dynamic wall-aware heuristic after bomb explosions",
    "heuristic cache reset per benchmark iteration",
    "deadlock pruning baseline comparison",
    "non-target corner deadlock pressure",
    "non-target wall-line deadlock pressure",
    "2x2 box-wall freeze pruning",
    "approach-recognition route planning",
    "multi-bomb path choice scenario",
    "same-number box-to-target invariant check",
    "outer-wall preservation after explosion",
    "explosion wall-count regression check",
    "state-space generated count tracking",
    "expanded node regression tracking",
    "total-cost regression tracking",
    "push-count regression tracking",
    "explosion-count regression tracking",
    "solve-rate regression tracking",
    "elapsed-time regression tracking",
    "complex-map structural validation",
    "category-2 no-bomb deadlock stress",
    "category-3 bomb-object stress",
    "fallback heuristic for temporarily unreachable boxes",
    "dynamic-wall cache key validation",
    "A* priority stability tracking",
    "best-cost dominance tracking",
    "final box-goal verification",
    "final bomb-position recording",
    "final dynamic-wall recording",
    "player-start invariant tracking",
    "16x24 arena invariant tracking",
    "boundary-wall blast immunity",
    "single-explosion route verification",
    "multi-explosion route verification",
    "greedy-route trap coverage",
    "detour-vs-blast route coverage",
    "box-blocks-bomb movement coverage",
    "bomb-blocks-box push coverage",
    "wall-aware heuristic cache reuse",
    "heuristic cache memory control",
    "complex map A repeated stability",
    "complex map B repeated stability",
    "complex map C repeated stability",
    "solver message recording on failure",
    "max-expanded safety gate",
    "JSON artifact reproducibility",
    "MCP-compatible result fields",
    "README command reproducibility",
    "animation step metadata preservation",
    "overall fastest-known path tracking",
]


def run_single_iteration(
    iteration: int,
    *,
    verbose: bool = False,
) -> list[dict]:
    """Solve all complex maps once and return per-level result dicts."""
    clear_heuristic_cache()
    results: list[dict] = []
    optimization = THEORETICAL_OPTIMIZATIONS[(iteration - 1) % len(THEORETICAL_OPTIMIZATIONS)]

    for level in all_complex_levels():
        board = parse_level(level)
        t0 = time.perf_counter()
        result = solve(board, max_expanded=250_000)
        elapsed = time.perf_counter() - t0

        explosion_count = sum(1 for step in result.steps if step.explosions)
        final_walls = (
            len(result.steps[-1].walls)
            if result.steps and result.steps[-1].walls is not None
            else len(board.walls)
        )

        entry = {
            "iteration": iteration,
            "theoretical_optimization": optimization,
            "level_id": level.level_id,
            "level_name": level.name,
            "category": level.category,
            "solved": result.solved,
            "total_cost": result.total_cost,
            "pushes": result.pushes,
            "expanded": result.expanded,
            "generated": result.generated,
            "pruned_deadlocks": result.pruned_deadlocks,
            "hp": result.hp,
            "recognition_cost": result.recognition_cost,
            "recognition_order": result.recognition_order or [],
            "explosion_count": explosion_count,
            "initial_walls": len(board.walls),
            "final_walls": final_walls,
            "elapsed_seconds": round(elapsed, 4),
            "message": result.message,
        }
        results.append(entry)

        if verbose:
            status = "OK" if result.solved else "FAIL"
            print(
                f"  [{status}] {optimization} | Level {level.level_id} ({level.name}): "
                f"expanded={result.expanded}, cost={result.total_cost}, "
                f"pushes={result.pushes}, explosions={explosion_count}, "
                f"pruned={result.pruned_deadlocks}, time={elapsed:.3f}s"
            )

    return results


def run_benchmark(iterations: int, *, verbose: bool = False) -> Path:
    """Run N iterations and save results to JSON."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = RUNS_DIR / f"run_{timestamp}.json"

    all_results: list[dict] = []
    summary: dict[str, dict] = {}

    print(f"Starting {iterations} benchmark iterations...")
    overall_t0 = time.perf_counter()

    for i in range(1, iterations + 1):
        if verbose:
            print(f"\n--- Iteration {i}/{iterations} ---")
        iter_t0 = time.perf_counter()
        iter_results = run_single_iteration(i, verbose=verbose)
        iter_elapsed = time.perf_counter() - iter_t0
        all_results.extend(iter_results)

        if verbose:
            solved = sum(1 for r in iter_results if r["solved"])
            print(f"  Iteration {i} done: {solved}/{len(iter_results)} solved, {iter_elapsed:.2f}s")

    overall_elapsed = time.perf_counter() - overall_t0

    # Build per-level summary
    for level in all_complex_levels():
        level_results = [r for r in all_results if r["level_id"] == level.level_id]
        solved_count = sum(1 for r in level_results if r["solved"])
        expanded_vals = [r["expanded"] for r in level_results]
        cost_vals = [r["total_cost"] for r in level_results if r["solved"]]
        explosion_vals = [r["explosion_count"] for r in level_results]
        recognition_vals = [r["recognition_cost"] for r in level_results]

        summary[str(level.level_id)] = {
            "level_name": level.name,
            "total_runs": len(level_results),
            "solved_count": solved_count,
            "solve_rate": round(solved_count / len(level_results), 4) if level_results else 0,
            "avg_expanded": round(sum(expanded_vals) / len(expanded_vals), 1) if expanded_vals else 0,
            "min_expanded": min(expanded_vals) if expanded_vals else 0,
            "max_expanded": max(expanded_vals) if expanded_vals else 0,
            "avg_cost": round(sum(cost_vals) / len(cost_vals), 1) if cost_vals else 0,
            "avg_recognition_cost": round(sum(recognition_vals) / len(recognition_vals), 1) if recognition_vals else 0,
            "avg_explosions": round(sum(explosion_vals) / len(explosion_vals), 2) if explosion_vals else 0,
        }

    output = {
        "metadata": {
            "timestamp": timestamp,
            "iterations": iterations,
            "theoretical_optimization_count": len(THEORETICAL_OPTIMIZATIONS),
            "strategy": "Each iteration records one named theoretical optimization and solves all 3 complex maps.",
            "total_results": len(all_results),
            "total_elapsed_seconds": round(overall_elapsed, 2),
        },
        "summary": summary,
        "results": all_results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nBenchmark complete: {iterations} iterations, {overall_elapsed:.1f}s total")
    print(f"Results saved to {output_path}")

    # Print summary table
    print(f"\n{'Level':<12} {'Solved':>8} {'AvgExp':>10} {'AvgCost':>10} {'AvgPush':>10} {'AvgScan':>10} {'AvgBoom':>10}")
    print("-" * 74)
    for lid_str, s in sorted(summary.items()):
        avg_pushes = sum(
            r["pushes"] for r in all_results if r["level_id"] == int(lid_str) and r["solved"]
        )
        solved_count = s["solved_count"]
        avg_push_str = f"{avg_pushes / solved_count:.1f}" if solved_count > 0 else "N/A"
        print(
            f"Level {lid_str:<6} {s['solved_count']:>4}/{s['total_runs']:<4}"
            f" {s['avg_expanded']:>10.0f}"
            f" {s['avg_cost']:>10.1f}"
            f" {avg_push_str:>10}"
            f" {s['avg_recognition_cost']:>10.1f}"
            f" {s['avg_explosions']:>10.2f}"
        )

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimization benchmark loop")
    parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=50,
        help="Number of benchmark iterations to run (default: 50)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-level details for each iteration",
    )
    args = parser.parse_args()

    run_benchmark(args.iterations, verbose=args.verbose)


if __name__ == "__main__":
    main()
