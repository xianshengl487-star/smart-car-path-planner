"""Run recurring planner checks and write timestamped reports.

Default cadence is 30 minutes, matching the long-running optimization workflow:
complex maps + external hard maps + optional contest PNGs. Stop with Ctrl+C.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner.complex_maps import all_complex_levels
from planner.grid import load_text_map, parse_level
from planner.solver import clear_heuristic_cache, solve
from planner.vision import batch_solve_contest_levels


RUNS_DIR = ROOT / ".orchestration" / "optimization_runs"
HARD_MAPS_DIR = ROOT / "hard_maps"


def solve_level_file(path: Path, max_expanded: int) -> dict:
    level = load_text_map(path)
    board = parse_level(level)
    clear_heuristic_cache()
    t0 = time.perf_counter()
    result = solve(board, max_expanded=max_expanded)
    elapsed = time.perf_counter() - t0
    return {
        "file": path.name,
        "level_id": level.level_id,
        "solved": result.solved,
        "cost": result.total_cost,
        "expanded": result.expanded,
        "pushes": result.pushes,
        "elapsed_seconds": round(elapsed, 4),
        "message": result.message,
    }


def run_once(max_expanded: int, include_contest: bool) -> dict:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()

    complex_results = []
    for level in all_complex_levels():
        board = parse_level(level)
        clear_heuristic_cache()
        t0 = time.perf_counter()
        result = solve(board, max_expanded=max_expanded)
        elapsed = time.perf_counter() - t0
        complex_results.append({
            "level_id": level.level_id,
            "name": level.name,
            "solved": result.solved,
            "cost": result.total_cost,
            "expanded": result.expanded,
            "elapsed_seconds": round(elapsed, 4),
            "message": result.message,
        })

    hard_results = []
    if HARD_MAPS_DIR.is_dir():
        for path in sorted(HARD_MAPS_DIR.glob("*.txt")):
            hard_results.append(solve_level_file(path, max_expanded=max_expanded))

    contest_results = []
    if include_contest:
        contest_results = batch_solve_contest_levels(
            "比赛关卡", max_expanded=max_expanded, save_outputs=False
        )

    summary = {
        "started": started,
        "max_expanded": max_expanded,
        "complex": {
            "solved": sum(1 for r in complex_results if r["solved"]),
            "total": len(complex_results),
        },
        "hard_maps": {
            "solved": sum(1 for r in hard_results if r["solved"]),
            "total": len(hard_results),
        },
        "contest": {
            "solved": sum(1 for r in contest_results if r.get("solved")),
            "total": len(contest_results),
        },
    }
    report = {
        "summary": summary,
        "complex_results": complex_results,
        "hard_map_results": hard_results,
        "contest_results": contest_results,
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = RUNS_DIR / f"watch_{stamp}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[{stamp}] complex={summary['complex']['solved']}/{summary['complex']['total']} "
          f"hard={summary['hard_maps']['solved']}/{summary['hard_maps']['total']} "
          f"contest={summary['contest']['solved']}/{summary['contest']['total']} -> {out}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-seconds", type=int, default=1800)
    parser.add_argument("--max-expanded", type=int, default=250000)
    parser.add_argument("--include-contest", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    while True:
        run_once(max_expanded=args.max_expanded, include_contest=args.include_contest)
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
