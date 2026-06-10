"""50-round optimization loop covering complex maps + contest maps.

Each iteration solves all complex levels (101-106) and all contest PNGs,
records metrics, and saves a JSON report.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from planner.complex_maps import all_complex_levels
from planner.grid import parse_level
from planner.solver import solve, clear_heuristic_cache
from planner.vision import batch_solve_contest_levels

PROJECT_ROOT = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_ROOT / ".orchestration" / "optimization_runs"


def run_complex_benchmark(iterations: int = 50) -> dict:
    """Run N iterations on complex maps (101-106) and contest PNGs."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = RUNS_DIR / f"run_{timestamp}.json"

    # Collect contest images once
    contest_dir = PROJECT_ROOT / "比赛关卡"
    contest_pngs = sorted(contest_dir.glob("*.png")) if contest_dir.exists() else []

    all_complex_results: list[dict] = []
    all_contest_results: list[dict] = []
    contest_solved_set: set[str] = set()
    contest_failed_set: set[str] = set()

    print(f"=== 50-Round Optimization ===")
    print(f"Complex maps: 101-106 (6 levels)")
    print(f"Contest maps: {len(contest_pngs)} PNGs")
    print()

    overall_t0 = time.perf_counter()

    for i in range(1, iterations + 1):
        clear_heuristic_cache()
        iter_t0 = time.perf_counter()

        # --- Complex maps ---
        iter_complex = []
        for level in all_complex_levels():
            board = parse_level(level)
            t0 = time.perf_counter()
            result = solve(board, max_expanded=250_000)
            elapsed = time.perf_counter() - t0
            explosion_count = sum(1 for step in result.steps if step.explosions)
            entry = {
                "iteration": i,
                "level_id": level.level_id,
                "level_name": level.name,
                "category": level.category,
                "solved": result.solved,
                "total_cost": result.total_cost,
                "pushes": result.pushes,
                "expanded": result.expanded,
                "pruned_deadlocks": result.pruned_deadlocks,
                "explosion_count": explosion_count,
                "elapsed_seconds": round(elapsed, 4),
                "message": result.message,
            }
            iter_complex.append(entry)
        all_complex_results.extend(iter_complex)

        # --- Contest maps (only solve once if stable, but track across iterations) ---
        iter_contest = batch_solve_contest_levels(
            "比赛关卡", max_expanded=250_000, save_outputs=(i == 1)
        )
        for r in iter_contest:
            r["iteration"] = i
            stem = Path(r["image"]).stem
            if r["solved"]:
                contest_solved_set.add(stem)
                contest_failed_set.discard(stem)
            else:
                if stem not in contest_solved_set:
                    contest_failed_set.add(stem)
        all_contest_results.extend(iter_contest)

        iter_elapsed = time.perf_counter() - iter_t0
        c_solved = sum(1 for r in iter_complex if r["solved"])
        co_solved = sum(1 for r in iter_contest if r["solved"])
        if i % 5 == 0 or i == 1:
            print(f"  [{i:3d}/{iterations}] complex={c_solved}/6  contest={co_solved}/{len(contest_pngs)}  time={iter_elapsed:.2f}s")

    overall_elapsed = time.perf_counter() - overall_t0

    # Build summary
    summary = {}
    for level in all_complex_levels():
        lr = [r for r in all_complex_results if r["level_id"] == level.level_id]
        solved = [r for r in lr if r["solved"]]
        summary[f"complex_{level.level_id}"] = {
            "total_runs": len(lr),
            "solved_count": len(solved),
            "solve_rate": round(len(solved) / len(lr), 4) if lr else 0,
            "avg_expanded": round(sum(r["expanded"] for r in lr) / len(lr), 1) if lr else 0,
            "avg_cost": round(sum(r["total_cost"] for r in solved) / len(solved), 1) if solved else 0,
            "avg_explosions": round(sum(r["explosion_count"] for r in lr) / len(lr), 2) if lr else 0,
        }

    summary["contest"] = {
        "total_pngs": len(contest_pngs),
        "always_solved": sorted(contest_solved_set),
        "never_solved": sorted(contest_failed_set),
        "solve_rate": round(len(contest_solved_set) / len(contest_pngs), 4) if contest_pngs else 0,
    }

    output = {
        "metadata": {
            "timestamp": timestamp,
            "iterations": iterations,
            "total_complex_results": len(all_complex_results),
            "total_contest_results": len(all_contest_results),
            "total_elapsed_seconds": round(overall_elapsed, 2),
        },
        "summary": summary,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Optimization complete: {iterations} rounds, {overall_elapsed:.1f}s")
    print(f"Results: {output_path}")
    print(f"\n{'Level':<20} {'Solved':>8} {'AvgExp':>10} {'AvgCost':>10} {'AvgBoom':>10}")
    print("-" * 60)
    for k, s in sorted(summary.items()):
        if k == "contest":
            continue
        print(f"{k:<20} {s['solved_count']:>4}/{s['total_runs']:<4}"
              f" {s['avg_expanded']:>10.0f}"
              f" {s['avg_cost']:>10.1f}"
              f" {s['avg_explosions']:>10.2f}")
    cs = summary.get("contest", {})
    print(f"\nContest: {cs.get('solved_count', 0)}/{cs.get('total_pngs', 0)} always solved"
          if cs.get("always_solved") else f"\nContest: {len(cs.get('always_solved', []))}/{cs.get('total_pngs', 0)} always solved")
    if cs.get("never_solved"):
        print(f"  Never solved: {cs['never_solved']}")

    return summary


if __name__ == "__main__":
    run_complex_benchmark(50)
