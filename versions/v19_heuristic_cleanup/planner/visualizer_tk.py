from __future__ import annotations

from pathlib import Path
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont

from .grid import Board, Position, SolveResult, Step

CELL_SIZE = 52

COLORS = {
    "empty": "#efefe7",
    "wall": "#2d2d2d",
    "grid": "#9f9f95",
    "player": "#29a9ff",
    "path": "#2775ff",
    "deadlock": "#ffaaa5",
    "endpoint": "#3cb371",
    "bomb": "#ffd700",
    "text": "#202020",
}

BOX_COLORS = {
    1: "#e65a4f",
    2: "#f0a33b",
    3: "#9d5bd2",
    4: "#7b58c9",
}

GOAL_COLORS = {
    1: "#64bf58",
    2: "#4fb8bc",
    3: "#5389d6",
    4: "#85bd45",
}


def animate_solution(
    board: Board,
    result: SolveResult,
    *,
    delay_ms: int = 120,
    auto_close: bool = True,
) -> None:
    if not result.steps:
        return

    root = tk.Tk()
    root.title(result.level_name)
    width = board.cols * CELL_SIZE
    height = board.rows * CELL_SIZE + 48
    canvas = tk.Canvas(root, width=width, height=height, bg="white", highlightthickness=0)
    canvas.pack()

    def draw(index: int) -> None:
        canvas.delete("all")
        step = result.steps[index]
        _draw_tk_frame(canvas, board, result, step, index)
        if index + 1 < len(result.steps):
            root.after(delay_ms, lambda: draw(index + 1))
        elif auto_close:
            root.after(1800, root.destroy)

    draw(0)
    root.mainloop()


def save_final_frame(board: Board, result: SolveResult, output_path: str | Path) -> str:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    step = result.steps[-1] if result.steps else Step(
        player=board.player,
        boxes=dict(board.boxes),
        action="START",
        pushed_box_id=None,
        hp=board.level.hp_start,
        cost=0,
        walls=board.walls,
        bombs=board.bombs,
    )
    image = Image.new(
        "RGB",
        (board.cols * CELL_SIZE, board.rows * CELL_SIZE + 48),
        "white",
    )
    draw = ImageDraw.Draw(image)
    _draw_pil_frame(draw, board, result, step)
    image.save(output)
    return str(output)


def _draw_tk_frame(
    canvas: tk.Canvas,
    board: Board,
    result: SolveResult,
    step: Step,
    index: int,
) -> None:
    path_points = [frame.player for frame in result.steps[: index + 1]]
    _draw_cells_tk(canvas, board, result, step, path_points)
    compare = ""
    if result.expanded_without_deadlock is not None:
        compare = f" | no-prune expanded {result.expanded_without_deadlock}"
    status = (
        f"{result.level_name} | step {index}/{len(result.steps) - 1} | "
        f"cost {step.cost} | HP {step.hp} | pushes {result.pushes} | "
        f"expanded {result.expanded}{compare} | action {step.action}"
    )
    canvas.create_text(
        8,
        board.rows * CELL_SIZE + 24,
        text=status,
        anchor="w",
        fill=COLORS["text"],
        font=("Consolas", 10),
    )


def _draw_cells_tk(
    canvas: tk.Canvas,
    board: Board,
    result: SolveResult,
    step: Step,
    path_points: list[Position],
) -> None:
    walls = step.walls if step.walls is not None else board.walls
    bombs = step.bombs if step.bombs is not None else board.bombs
    for row in range(board.rows):
        for col in range(board.cols):
            pos = (row, col)
            x0, y0, x1, y1 = _bounds(row, col)
            fill = COLORS["wall"] if pos in walls else COLORS["empty"]
            canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=COLORS["grid"])
            if pos in step.explosions:
                canvas.create_rectangle(x0 + 3, y0 + 3, x1 - 3, y1 - 3, fill="#ffcf70", outline="#de6b00", width=2)
            if pos in result.deadlock_cells and pos not in board.goals.values():
                canvas.create_rectangle(x0 + 6, y0 + 6, x1 - 6, y1 - 6, fill=COLORS["deadlock"], outline="")
            # Endpoint
            if pos == board.endpoint:
                canvas.create_rectangle(x0 + 5, y0 + 5, x1 - 5, y1 - 5, fill=COLORS["endpoint"], outline="#2a7a4a", width=2)
                canvas.create_text((x0 + x1) // 2, (y0 + y1) // 2, text="E", font=("Consolas", 14, "bold"))
            if pos in bombs:
                canvas.create_oval(x0 + 9, y0 + 9, x1 - 9, y1 - 9, fill=COLORS["bomb"], outline="#b8860b", width=2)
                canvas.create_text((x0 + x1) // 2, (y0 + y1) // 2, text="X", font=("Consolas", 16, "bold"))

    if len(path_points) > 1:
        coords = []
        for row, col in path_points:
            coords.extend([col * CELL_SIZE + CELL_SIZE // 2, row * CELL_SIZE + CELL_SIZE // 2])
        canvas.create_line(*coords, fill=COLORS["path"], width=3)

    for goal_id, pos in board.goals.items():
        row, col = pos
        x0, y0, x1, y1 = _bounds(row, col)
        canvas.create_oval(x0 + 8, y0 + 8, x1 - 8, y1 - 8, outline=GOAL_COLORS[goal_id], width=4)
        canvas.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=f"T{goal_id}", font=("Consolas", 12, "bold"))

    for box_id, pos in step.boxes.items():
        row, col = pos
        x0, y0, x1, y1 = _bounds(row, col)
        canvas.create_rectangle(x0 + 8, y0 + 8, x1 - 8, y1 - 8, fill=BOX_COLORS[box_id], outline="#3b2f2f", width=2)
        canvas.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=f"B{box_id}", font=("Consolas", 13, "bold"))

    row, col = step.player
    x0, y0, x1, y1 = _bounds(row, col)
    canvas.create_oval(x0 + 11, y0 + 11, x1 - 11, y1 - 11, fill=COLORS["player"], outline="#0b4e75", width=2)
    canvas.create_text((x0 + x1) // 2, (y0 + y1) // 2, text="P", font=("Consolas", 13, "bold"))


def _draw_pil_frame(draw: ImageDraw.ImageDraw, board: Board, result: SolveResult, step: Step) -> None:
    try:
        font = ImageFont.truetype("arial.ttf", 15)
        small_font = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    walls = step.walls if step.walls is not None else board.walls
    bombs = step.bombs if step.bombs is not None else board.bombs

    for row in range(board.rows):
        for col in range(board.cols):
            pos = (row, col)
            x0, y0, x1, y1 = _bounds(row, col)
            fill = COLORS["wall"] if pos in walls else COLORS["empty"]
            draw.rectangle([x0, y0, x1, y1], fill=fill, outline=COLORS["grid"])
            if pos in step.explosions:
                draw.rectangle([x0 + 3, y0 + 3, x1 - 3, y1 - 3], fill="#ffcf70", outline="#de6b00", width=2)
            if pos in result.deadlock_cells and pos not in board.goals.values():
                draw.rectangle([x0 + 6, y0 + 6, x1 - 6, y1 - 6], fill=COLORS["deadlock"])
            if pos == board.endpoint:
                draw.rectangle([x0 + 5, y0 + 5, x1 - 5, y1 - 5], fill=COLORS["endpoint"], outline="#2a7a4a", width=2)
                draw.text((x0 + 18, y0 + 16), "E", fill="black", font=font)
            if pos in bombs:
                draw.ellipse([x0 + 10, y0 + 10, x1 - 10, y1 - 10], fill=COLORS["bomb"], outline="#b8860b", width=2)
                draw.text((x0 + 18, y0 + 14), "X", fill="black", font=font)

    for goal_id, pos in board.goals.items():
        row, col = pos
        x0, y0, x1, y1 = _bounds(row, col)
        draw.ellipse([x0 + 8, y0 + 8, x1 - 8, y1 - 8], outline=GOAL_COLORS[goal_id], width=4)
        draw.text((x0 + 15, y0 + 18), f"T{goal_id}", fill="black", font=small_font)

    for box_id, pos in step.boxes.items():
        row, col = pos
        x0, y0, x1, y1 = _bounds(row, col)
        draw.rectangle([x0 + 8, y0 + 8, x1 - 8, y1 - 8], fill=BOX_COLORS[box_id], outline="#3b2f2f", width=2)
        draw.text((x0 + 15, y0 + 18), f"B{box_id}", fill="black", font=small_font)

    row, col = step.player
    x0, y0, x1, y1 = _bounds(row, col)
    draw.ellipse([x0 + 11, y0 + 11, x1 - 11, y1 - 11], fill=COLORS["player"], outline="#0b4e75", width=2)
    draw.text((x0 + 21, y0 + 18), "P", fill="black", font=font)

    status = (
        f"{result.level_name} | cost {result.total_cost} | HP {result.hp} | "
        f"pushes {result.pushes} | expanded {result.expanded}"
    )
    draw.text((8, board.rows * CELL_SIZE + 18), status, fill=COLORS["text"], font=small_font)


def _bounds(row: int, col: int) -> tuple[int, int, int, int]:
    x0 = col * CELL_SIZE
    y0 = row * CELL_SIZE
    return x0, y0, x0 + CELL_SIZE, y0 + CELL_SIZE
