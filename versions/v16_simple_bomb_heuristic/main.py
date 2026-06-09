from __future__ import annotations

import argparse
from pathlib import Path

from planner.grid import Level, parse_level
from planner.levels import all_levels, get_level
from planner.solver import solve
from planner.vision import (
    generate_level_image,
    recognize_level_image,
    recognize_contest_image,
    batch_solve_contest_levels,
)
from planner.visualizer_tk import animate_solution, save_final_frame

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"


def prepare_level(level: Level) -> tuple[Level, str | None, str | None]:
    if not level.use_vision:
        return level, None, None

    generated_path = OUTPUT_DIR / f"level_{level.level_id}_generated.png"
    recognized_path = OUTPUT_DIR / f"level_{level.level_id}_recognized.png"
    generate_level_image(level, generated_path)
    recognized = recognize_level_image(
        generated_path,
        level_id=level.level_id,
        name=level.name,
        category=level.category,
        hp_start=level.hp_start,
        use_deadlock=level.use_deadlock,
        requires_approach_recognition=level.requires_approach_recognition,
        boxes_vanish_on_goal=level.boxes_vanish_on_goal,
        recognized_output_path=recognized_path,
    )
    return recognized, str(generated_path), str(recognized_path)


def run_level(level: Level, *, no_gui: bool, delay_ms: int, max_expanded: int) -> None:
    prepared_level, generated_path, recognized_path = prepare_level(level)
    board = parse_level(prepared_level)

    result = solve(board, max_expanded=max_expanded)
    result.generated_image = generated_path
    result.recognized_image = recognized_path

    final_path = OUTPUT_DIR / f"level_{level.level_id}_final.png"
    result.final_image = save_final_frame(board, result, final_path)

    _print_summary(result)
    if not no_gui:
        animate_solution(board, result, delay_ms=delay_ms)


def _print_summary(result) -> None:
    status = "OK" if result.solved else "FAILED"
    print(f"[{status}] {result.level_name}")
    print(f"  cost={result.total_cost}, pushes={result.pushes}, hp={result.hp}")
    print(f"  expanded={result.expanded}, generated={result.generated}, deadlock_pruned={result.pruned_deadlocks}")
    if result.recognition_cost:
        print(f"  recognition_cost={result.recognition_cost}, recognition_order={result.recognition_order}")
    if result.generated_image:
        print(f"  generated_image={result.generated_image}")
    if result.recognized_image:
        print(f"  recognized_image={result.recognized_image}")
    if result.final_image:
        print(f"  final_image={result.final_image}")
    if not result.solved:
        print(f"  message={result.message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="地图生成器与路径规划 - Map Generator & Path Planner")
    parser.add_argument("--level", default="all", help="1, 2, 3, or all")
    parser.add_argument("--all", action="store_true", help="Run all levels.")
    parser.add_argument("--category", type=int, choices=[1, 2, 3],
                        help="Override category for a single level (1=simple nav, 2=vision+target, 3=vision+target+bombs)")
    parser.add_argument("--no-gui", action="store_true", help="Solve and export PNG without Tkinter animation.")
    parser.add_argument("--delay", type=int, default=120, help="Animation delay in milliseconds.")
    parser.add_argument("--max-expanded", type=int, default=250_000, help="A* expansion limit.")
    parser.add_argument("--editor", action="store_true", help="Launch the map editor GUI.")
    # New: support real image maps (especially 比赛关卡/ folder)
    parser.add_argument("--image", type=str, default=None,
                        help="Path to a single grid screenshot/PNG (auto-recognize + solve).")
    parser.add_argument("--contest", action="store_true",
                        help="Batch process all PNGs under 比赛关卡/ (auto cell size, auto category, vanish rule).")
    return parser.parse_args()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    args = parse_args()

    if args.editor:
        from map_editor import main as editor_main
        editor_main()
        return

    # --- New image / contest paths (priority over built-in levels) ---
    if args.contest:
        print("=== Batch solving contest levels under 比赛关卡/ ===")
        summaries = batch_solve_contest_levels(
            "比赛关卡",
            max_expanded=args.max_expanded,
            save_outputs=True,
        )
        for s in summaries:
            status = "OK" if s.get("solved") else "FAIL"
            print(f"[{status}] {s['image']}  grid={s.get('grid')} cat={s.get('category')} "
                  f"cost={s.get('cost')} pushes={s.get('pushes')} expanded={s.get('expanded')} "
                  f"msg={s.get('message','')}")
        solved = sum(1 for s in summaries if s.get("solved"))
        print(f"\nContest batch: {solved}/{len(summaries)} solved.")
        return

    if args.image:
        print(f"=== Solving image map: {args.image} ===")
        try:
            level = recognize_contest_image(
                args.image,
                # let it auto-infer category / vanish / approach from content
            )
            board = parse_level(level)
            result = solve(board, max_expanded=args.max_expanded)

            # minimal summary
            print(f"  grid=({board.rows}x{board.cols}) category={level.category} vanish={level.boxes_vanish_on_goal}")
            status = "OK" if result.solved else "FAIL"
            print(f"[{status}] cost={result.total_cost} pushes={result.pushes} expanded={result.expanded}")
            if result.recognition_cost:
                print(f"  recognition_cost={result.recognition_cost} order={result.recognition_order}")
            if not result.solved:
                print(f"  message={result.message}")

            # export final frame if possible
            try:
                final_path = OUTPUT_DIR / f"image_final_{Path(args.image).stem}.png"
                result.final_image = save_final_frame(board, result, final_path)
                print(f"  final_image={final_path}")
            except Exception:
                pass

            if not args.no_gui:
                try:
                    animate_solution(board, result, delay_ms=args.delay)
                except Exception as e:
                    print(f"  (GUI animation skipped: {e})")
        except Exception as e:
            print(f"Failed to process image: {e}")
        return

    # --- Original built-in level flow ---
    if args.all or args.level == "all":
        levels = all_levels()
    else:
        levels = [get_level(int(args.level))]

    if args.category:
        from planner.editor_model import with_category
        levels = [with_category(lv, args.category) for lv in levels]

    for level in levels:
        run_level(level, no_gui=args.no_gui, delay_ms=args.delay, max_expanded=args.max_expanded)


if __name__ == "__main__":
    main()
