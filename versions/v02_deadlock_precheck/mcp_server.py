from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from planner.grid import Board, Level, parse_level
from planner.levels import all_levels, get_level
from planner.solver import solve
from planner.vision import batch_solve_contest_levels, generate_level_image, recognize_level_image
from planner.visualizer_tk import save_final_frame

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"

mcp = FastMCP(
    "numbered-path-planner",
    instructions=(
        "Tools for the numbered smart-car path planning demo. "
        "Maps are 16x12 grids with walls, empty cells, numbered boxes, "
        "matching numbered targets, and pushable bombs X. "
        "The car starts at row=5, col=1 and only boxes/targets require recognition. "
        "Category 3: pushing X into a wall destroys non-boundary walls in a 3x3 area."
    ),
)


@mcp.tool()
def list_levels() -> list[dict[str, Any]]:
    """List available levels and their core map metadata."""
    result = []
    for level in all_levels():
        board = parse_level(level)
        result.append(
            {
                "level_id": level.level_id,
                "name": level.name,
                "category": level.category,
                "rows": board.rows,
                "cols": board.cols,
                "player": board.player,
                "boxes": board.boxes,
                "goals": board.goals,
                "bombs": sorted(board.bombs),
                "hp_start": level.hp_start,
                "use_vision": level.use_vision,
            }
        )
    return result


@mcp.tool()
def solve_level(level_id: int, max_expanded: int = 250_000) -> dict[str, Any]:
    """Solve a level and return a compact result summary."""
    level = _prepare_level(get_level(level_id))
    board = parse_level(level)
    result = solve(board, max_expanded=max_expanded)
    return _result_summary(board, result)


@mcp.tool()
def render_level(level_id: int, max_expanded: int = 250_000) -> dict[str, Any]:
    """Solve a level and export its final PNG frame under outputs/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_level = get_level(level_id)
    level, generated_image, recognized_image = _prepare_level_with_images(source_level)
    board = parse_level(level)
    result = solve(board, max_expanded=max_expanded)
    final_image = save_final_frame(board, result, OUTPUT_DIR / f"mcp_level_{level_id}_final.png")
    summary = _result_summary(board, result)
    summary.update(
        {
            "generated_image": generated_image,
            "recognized_image": recognized_image,
            "final_image": final_image,
        }
    )
    return summary


@mcp.tool()
def solve_contest_folder(max_expanded: int = 250_000) -> dict[str, Any]:
    """Recognize and solve every PNG under the local contest folder."""
    results = batch_solve_contest_levels(max_expanded=max_expanded, save_outputs=True)
    solved = sum(1 for item in results if item.get("solved"))
    return {
        "solved": solved,
        "total": len(results),
        "results": results,
    }


def _prepare_level(level: Level) -> Level:
    if not level.use_vision:
        return level
    prepared, _, _ = _prepare_level_with_images(level)
    return prepared


def _prepare_level_with_images(level: Level) -> tuple[Level, str | None, str | None]:
    if not level.use_vision:
        return level, None, None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_path = OUTPUT_DIR / f"mcp_level_{level.level_id}_generated.png"
    recognized_path = OUTPUT_DIR / f"mcp_level_{level.level_id}_recognized.png"
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


def _result_summary(board: Board, result) -> dict[str, Any]:
    final_step = result.steps[-1] if result.steps else None
    return {
        "level_id": result.level_id,
        "level_name": result.level_name,
        "solved": result.solved,
        "message": result.message,
        "total_cost": result.total_cost,
        "pushes": result.pushes,
        "expanded": result.expanded,
        "generated": result.generated,
        "pruned_deadlocks": result.pruned_deadlocks,
        "hp": result.hp,
        "recognition_cost": result.recognition_cost,
        "recognition_order": result.recognition_order or [],
        "actions": result.actions,
        "final_player": final_step.player if final_step else None,
        "final_boxes": final_step.boxes if final_step else {},
        "final_bombs": sorted(final_step.bombs or board.bombs) if final_step else sorted(board.bombs),
        "remaining_walls": len(final_step.walls or board.walls) if final_step else len(board.walls),
        "initial_walls": len(board.walls),
        "explosion_count": sum(1 for step in result.steps if step.explosions),
    }


if __name__ == "__main__":
    mcp.run("stdio")
