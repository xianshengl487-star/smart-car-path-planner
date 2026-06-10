"""50-round optimization loop focused on bomb maps.
Solves complex maps (101-106) + contest PNGs + sokoban raw maps.
Tracks bomb-specific metrics and saves results."""
from __future__ import annotations
import json, time
from datetime import datetime, timezone
from pathlib import Path
from planner.complex_maps import all_complex_levels
from planner.grid import parse_level
from planner.solver import solve, clear_heuristic_cache
from planner.vision import batch_solve_contest_levels

PROJECT_ROOT = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_ROOT / ".orchestration" / "optimization_runs"

def run_bomb_optimization(iterations: int = 50):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RUNS_DIR / f"bomb_run_{ts}.json"
    contest_dir = PROJECT_ROOT / "比赛关卡"
    contest_pngs = sorted(contest_dir.glob("*.png")) if contest_dir.exists() else []
    all_results = []
    contest_always_solved = set()
    contest_never_solved = set()

    print(f"=== 50-Round Bomb Optimization ===")
    print(f"Complex maps: 101-106 | Contest PNGs: {len(contest_pngs)}")
    t0 = time.perf_counter()

    for i in range(1, iterations + 1):
        clear_heuristic_cache()
        it0 = time.perf_counter()
        iter_results = []
        for level in all_complex_levels():
            board = parse_level(level)
            st = time.perf_counter()
            r = solve(board, max_expanded=250_000)
            el = time.perf_counter() - st
            exp_count = sum(1 for s in r.steps if s.explosions)
            entry = {
                "iter": i, "id": level.level_id, "name": level.name,
                "cat": level.category, "solved": r.solved,
                "cost": r.total_cost, "pushes": r.pushes,
                "expanded": r.expanded, "pruned": r.pruned_deadlocks,
                "explosions": exp_count, "time": round(el, 4),
                "msg": r.message,
            }
            iter_results.append(entry)
        all_results.extend(iter_results)

        co = batch_solve_contest_levels("比赛关卡", max_expanded=250_000, save_outputs=(i == 1))
        for cr in co:
            cr["iter"] = i
            stem = Path(cr["image"]).stem
            if cr["solved"]:
                contest_always_solved.add(stem)
                contest_never_solved.discard(stem)
            elif stem not in contest_always_solved:
                contest_never_solved.add(stem)

        el = time.perf_counter() - it0
        cs = sum(1 for r in iter_results if r["solved"])
        cos = sum(1 for r in co if r["solved"])
        if i % 5 == 0 or i == 1:
            print(f"  [{i:3d}/{iterations}] complex={cs}/6 contest={cos}/{len(contest_pngs)} time={el:.2f}s")

    total = time.perf_counter() - t0
    summary = {}
    for level in all_complex_levels():
        lr = [r for r in all_results if r["id"] == level.level_id]
        solved = [r for r in lr if r["solved"]]
        summary[f"complex_{level.level_id}"] = {
            "runs": len(lr), "solved": len(solved),
            "rate": round(len(solved) / len(lr), 4) if lr else 0,
            "avg_exp": round(sum(r["expanded"] for r in lr) / len(lr), 1) if lr else 0,
            "avg_cost": round(sum(r["cost"] for r in solved) / len(solved), 1) if solved else 0,
            "avg_explosions": round(sum(r["explosions"] for r in lr) / len(lr), 2) if lr else 0,
        }
    summary["contest"] = {
        "pngs": len(contest_pngs),
        "always_solved": sorted(contest_always_solved),
        "never_solved": sorted(contest_never_solved),
    }
    output = {"meta": {"ts": ts, "iters": iterations, "elapsed": round(total, 2)},
              "summary": summary, "results": all_results}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Done: {iterations} rounds, {total:.1f}s")
    print(f"Results: {out_path}")
    print(f"\n{'Level':<20} {'Solved':>8} {'AvgExp':>10} {'AvgCost':>10} {'AvgBoom':>10}")
    print("-" * 60)
    for k, s in sorted(summary.items()):
        if k == "contest": continue
        print(f"{k:<20} {s['solved']:>4}/{s['runs']:<4} {s['avg_exp']:>10.0f} {s['avg_cost']:>10.1f} {s['avg_explosions']:>10.2f}")
    cs = summary.get("contest", {})
    ns = cs.get("always_solved", [])
    print(f"\nContest: {len(ns)}/{cs.get('pngs',0)} always solved")
    if cs.get("never_solved"): print(f"  Never solved: {cs['never_solved']}")

if __name__ == "__main__":
    run_bomb_optimization(50)
