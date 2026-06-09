from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from planner.editor_model import (
    CATEGORY_NAMES,
    GRID_PRESETS,
    TOKEN_CHOICES,
    TOKEN_HELP,
    blank_rows,
    level_from_rows,
    set_cell,
    set_grid_size,
)
from planner.grid import parse_level
from planner.solver import solve
from planner.vision import generate_level_image, recognize_level_image
from planner.visualizer_tk import CELL_SIZE, COLORS, save_final_frame

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DRAW_SIZE = 32

TOKEN_COLORS = {
    ".": "#efefe7",
    "#": "#2d2d2d",
    "P": "#29a9ff",
    "E": "#3cb371",
    "X": "#ffd700",
    "B1": "#e65a4f",
    "B2": "#f0a33b",
    "B3": "#9d5bd2",
    "B4": "#7b58c9",
    "T1": "#64bf58",
    "T2": "#4fb8bc",
    "T3": "#5389d6",
    "T4": "#85bd45",
}


class MapEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Map Generator & Smart-Car Path Planner")
        self.rows = blank_rows()
        self.selected_token = tk.StringVar(value="#")
        self.grid_preset = tk.StringVar(value="16x24")
        self.status = tk.StringVar(value="Ready")
        self._undo_stack: list[tuple[tuple[str, ...], ...]] = []
        self._redo_stack: list[tuple[tuple[str, ...], ...]] = []
        self._build_ui()
        self._redraw()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=8)
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        toolbar = ttk.Frame(root)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        ttk.Label(toolbar, text="Brush:").pack(side="left")
        ttk.Combobox(
            toolbar,
            textvariable=self.selected_token,
            values=list(TOKEN_CHOICES),
            width=6,
            state="readonly",
        ).pack(side="left", padx=(2, 10))

        ttk.Label(toolbar, text="Category:").pack(side="left")
        self._cat_combo = ttk.Combobox(
            toolbar,
            values=[f"{key}: {value}" for key, value in CATEGORY_NAMES.items()],
            width=42,
            state="readonly",
        )
        self._cat_combo.set(f"1: {CATEGORY_NAMES[1]}")
        self._cat_combo.pack(side="left", padx=(2, 10))

        ttk.Label(toolbar, text="Grid:").pack(side="left")
        ttk.Combobox(
            toolbar,
            textvariable=self.grid_preset,
            values=list(GRID_PRESETS.keys()),
            width=8,
            state="readonly",
        ).pack(side="left", padx=(2, 10))

        buttons = ttk.Frame(root)
        buttons.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(buttons, text="Solve", command=self.solve).pack(side="left", padx=3)
        ttk.Button(buttons, text="Clear", command=self.clear).pack(side="left", padx=3)
        ttk.Button(buttons, text="Undo", command=self.undo).pack(side="left", padx=3)
        ttk.Button(buttons, text="Redo", command=self.redo).pack(side="left", padx=3)
        ttk.Button(buttons, text="Export PNG", command=self.export_map).pack(side="left", padx=3)
        ttk.Button(buttons, text="Save JSON", command=self.save_map).pack(side="left", padx=3)
        ttk.Button(buttons, text="Load JSON", command=self.load_map).pack(side="left", padx=3)
        ttk.Button(buttons, text="Apply Grid", command=self.apply_grid_size).pack(side="left", padx=3)

        legend = ttk.LabelFrame(root, text="Legend")
        legend.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        for index, token in enumerate(TOKEN_CHOICES):
            row, col = divmod(index, 10)
            label = tk.Label(
                legend,
                text=f" {token} {TOKEN_HELP.get(token, '')} ",
                bg=TOKEN_COLORS.get(token, "#efefe7"),
                fg="#fff" if token == "#" else "#111",
                font=("Consolas", 8),
                relief="ridge",
                padx=3,
                pady=1,
            )
            label.grid(row=row, column=col, padx=1, pady=1, sticky="w")

        self.canvas = tk.Canvas(
            root,
            width=len(self.rows[0]) * DRAW_SIZE,
            height=len(self.rows) * DRAW_SIZE,
            bg="white",
            highlightthickness=1,
            highlightbackground="#999",
        )
        self.canvas.grid(row=3, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_paint)
        self.canvas.bind("<B1-Motion>", self._on_paint)
        self.canvas.bind("<Button-3>", self._on_erase)

        self.bind("<Control-z>", lambda _event: self.undo())
        self.bind("<Control-y>", lambda _event: self.redo())
        self.bind("<Control-s>", lambda _event: self.save_map())
        self.bind("<Control-o>", lambda _event: self.load_map())

        ttk.Label(root, textvariable=self.status).grid(row=4, column=0, sticky="ew", pady=(4, 0))

    def apply_grid_size(self) -> None:
        key = self.grid_preset.get()
        if key not in GRID_PRESETS:
            return
        rows, cols = GRID_PRESETS[key]
        set_grid_size(rows, cols)
        self.rows = blank_rows()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._resize_canvas()
        self._redraw()
        self.status.set(f"Grid size set to {rows}x{cols}")

    def clear(self) -> None:
        self._push_undo()
        self.rows = blank_rows()
        self._resize_canvas()
        self._redraw()
        self.status.set("Cleared")

    def undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self.rows)
        self.rows = self._undo_stack.pop()
        self._redraw()
        self.status.set("Undo")

    def redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self.rows)
        self.rows = self._redo_stack.pop()
        self._redraw()
        self.status.set("Redo")

    def export_map(self) -> None:
        try:
            category = self._get_category()
            level = level_from_rows(self.rows, category=category)
            path = OUTPUT_DIR / "custom_editor_map.png"
            generate_level_image(level, path)
            self.status.set(f"Exported {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def save_map(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Map", "*.json"), ("All files", "*.*")],
            initialdir=str(PROJECT_ROOT / "maps"),
        )
        if not path:
            return
        data = {
            "category": self._get_category(),
            "grid_size": [len(self.rows), len(self.rows[0]) if self.rows else 24],
            "rows": [list(row) for row in self.rows],
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        self.status.set(f"Saved {path}")

    def load_map(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("JSON Map", "*.json"), ("All files", "*.*")],
            initialdir=str(PROJECT_ROOT / "maps"),
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            rows_count, cols_count = data.get("grid_size", [16, 24])
            set_grid_size(rows_count, cols_count)
            preset = f"{rows_count}x{cols_count}"
            if preset in GRID_PRESETS:
                self.grid_preset.set(preset)
            self._push_undo()
            self.rows = tuple(tuple(row) for row in data["rows"])
            self._set_category(int(data.get("category", 1)))
            self._resize_canvas()
            self._redraw()
            self.status.set(f"Loaded {path}")
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))

    def solve(self) -> None:
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            category = self._get_category()
            level = level_from_rows(self.rows, category=category)
            generated_path = None
            recognized_path = None

            if level.use_vision:
                generated_path = OUTPUT_DIR / "custom_generated.png"
                recognized_path = OUTPUT_DIR / "custom_recognized.png"
                generate_level_image(level, generated_path)
                level = recognize_level_image(
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

            board = parse_level(level)
            result = solve(board)
            final_path = OUTPUT_DIR / "custom_final.png"
            result.final_image = save_final_frame(board, result, final_path)
            result.generated_image = str(generated_path) if generated_path else None
            result.recognized_image = str(recognized_path) if recognized_path else None

            if result.solved:
                self.status.set(
                    f"Solved: cost={result.total_cost}, pushes={result.pushes}, "
                    f"expanded={result.expanded}, final={final_path}"
                )
                self._show_solution(board, result)
            else:
                messagebox.showwarning("No solution", result.message)
                self.status.set(result.message)
        except Exception as exc:
            messagebox.showerror("Solve failed", str(exc))
            self.status.set(str(exc))

    def _show_solution(self, board, result) -> None:
        if not result.steps:
            return
        win = tk.Toplevel(self)
        win.title("Solution Path")
        canvas = tk.Canvas(
            win,
            width=board.cols * CELL_SIZE,
            height=board.rows * CELL_SIZE + 48,
            bg="white",
            highlightthickness=0,
        )
        canvas.pack()
        from planner.visualizer_tk import _draw_tk_frame

        index = {"value": 0}

        def draw() -> None:
            canvas.delete("all")
            _draw_tk_frame(canvas, board, result, result.steps[index["value"]], index["value"])

        def next_step() -> None:
            index["value"] = min(index["value"] + 1, len(result.steps) - 1)
            draw()

        def prev_step() -> None:
            index["value"] = max(index["value"] - 1, 0)
            draw()

        buttons = ttk.Frame(win)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Previous", command=prev_step).pack(side="left", padx=4, pady=4)
        ttk.Button(buttons, text="Next", command=next_step).pack(side="left", padx=4, pady=4)
        draw()

    def _on_paint(self, event: tk.Event) -> None:
        self._paint(event, self.selected_token.get())

    def _on_erase(self, event: tk.Event) -> None:
        self._paint(event, ".")

    def _paint(self, event: tk.Event, token: str) -> None:
        row, col = event.y // DRAW_SIZE, event.x // DRAW_SIZE
        if row < 0 or col < 0 or row >= len(self.rows) or col >= len(self.rows[0]):
            return
        if self.rows[row][col] == token:
            return
        self._push_undo()
        try:
            self.rows = set_cell(self.rows, row, col, token)
            self._redraw()
        except ValueError as exc:
            self.status.set(str(exc))

    def _push_undo(self) -> None:
        self._undo_stack.append(self.rows)
        self._redo_stack.clear()
        if len(self._undo_stack) > 200:
            self._undo_stack.pop(0)

    def _resize_canvas(self) -> None:
        self.canvas.config(width=len(self.rows[0]) * DRAW_SIZE, height=len(self.rows) * DRAW_SIZE)

    def _get_category(self) -> int:
        return int(self._cat_combo.get().split(":", 1)[0])

    def _set_category(self, category: int) -> None:
        self._cat_combo.set(f"{category}: {CATEGORY_NAMES[category]}")

    def _redraw(self) -> None:
        self.canvas.delete("all")
        for row_index, row in enumerate(self.rows):
            for col_index, token in enumerate(row):
                x0 = col_index * DRAW_SIZE
                y0 = row_index * DRAW_SIZE
                x1 = x0 + DRAW_SIZE
                y1 = y0 + DRAW_SIZE
                fill = TOKEN_COLORS.get(token, COLORS["empty"])
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="#999", width=1)
                if token != ".":
                    self.canvas.create_text(
                        (x0 + x1) // 2,
                        (y0 + y1) // 2,
                        text=token,
                        fill="#fff" if token == "#" else "#111",
                        font=("Consolas", 8, "bold"),
                    )


def main() -> None:
    app = MapEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
