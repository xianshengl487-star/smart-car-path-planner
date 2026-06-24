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


def _result_label(result: dict) -> str:
    return str(
        result.get("file")
        or result.get("name")
        or result.get("image")
        or result.get("level_id")
        or "unknown"
    )


def summarize_results(results: list[dict]) -> dict:
    solved = [r for r in results if r.get("solved")]
    failed = [r for r in results if not r.get("solved")]
    by_expanded = sorted(
        solved,
        key=lambda r: int(r.get("expanded") or 0),
        reverse=True,
    )
    by_elapsed = sorted(
        solved,
        key=lambda r: float(r.get("elapsed_seconds") or 0.0),
        reverse=True,
    )
    elapsed_total = sum(float(r.get("elapsed_seconds") or 0.0) for r in results)
    expanded_total = sum(int(r.get("expanded") or 0) for r in results)
    return {
        "solved": len(solved),
        "total": len(results),
        "failed": [_result_label(r) for r in failed],
        "hardest_by_expanded": [
            {
                "label": _result_label(r),
                "expanded": int(r.get("expanded") or 0),
                "cost": r.get("cost"),
                "pushes": r.get("pushes"),
            }
            for r in by_expanded[:5]
        ],
        "slowest_by_elapsed": [
            {
                "label": _result_label(r),
                "elapsed_seconds": float(r.get("elapsed_seconds") or 0.0),
                "expanded": int(r.get("expanded") or 0),
            }
            for r in by_elapsed[:5]
        ],
        "total_expanded": expanded_total,
        "total_elapsed_seconds": round(elapsed_total, 4),
        "max_expanded": int(by_expanded[0].get("expanded") or 0) if by_expanded else 0,
        "max_elapsed_seconds": round(float(by_elapsed[0].get("elapsed_seconds") or 0.0), 4) if by_elapsed else 0.0,
    }


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

    complex_summary = summarize_results(complex_results)
    hard_summary = summarize_results(hard_results)
    contest_summary = summarize_results(contest_results)
    summary = {
        "started": started,
        "max_expanded": max_expanded,
        "complex": complex_summary,
        "hard_maps": hard_summary,
        "contest": contest_summary,
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
    hard_top = summary["hard_maps"]["hardest_by_expanded"][:1]
    hard_top_text = ""
    if hard_top:
        hard_top_text = f" hardest={hard_top[0]['label']}({hard_top[0]['expanded']})"
    failures = (
        len(summary["complex"]["failed"])
        + len(summary["hard_maps"]["failed"])
        + len(summary["contest"]["failed"])
    )
    print(
        f"[{stamp}] complex={summary['complex']['solved']}/{summary['complex']['total']} "
        f"hard={summary['hard_maps']['solved']}/{summary['hard_maps']['total']} "
        f"contest={summary['contest']['solved']}/{summary['contest']['total']} "
        f"failures={failures}{hard_top_text} "
        f"elapsed={round(summary['complex']['total_elapsed_seconds'] + summary['hard_maps']['total_elapsed_seconds'] + summary['contest']['total_elapsed_seconds'], 4)}s -> {out}"
    )
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
