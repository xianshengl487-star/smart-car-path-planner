from __future__ import annotations

from dataclasses import replace

from .grid import Level
from .levels import COLS, ROWS, START

TOKEN_CHOICES = (
    ".",
    "#",
    "P",
    "E",
    "X",
    "B1",
    "T1",
    "B2",
    "T2",
    "B3",
    "T3",
    "B4",
    "T4",
)

TOKEN_HELP = {
    ".": "empty",
    "#": "wall",
    "P": "car start",
    "E": "category-1 endpoint",
    "X": "pushable bomb",
    "B1": "box 1",
    "B2": "box 2",
    "B3": "box 3",
    "B4": "box 4",
    "T1": "target 1",
    "T2": "target 2",
    "T3": "target 3",
    "T4": "target 4",
}

CATEGORY_NAMES = {
    1: "Category 1 - simple navigation",
    2: "Category 2 - vision numbered boxes",
    3: "Category 3 - vision bombs break walls",
}

MODE_NAMES = CATEGORY_NAMES

GRID_PRESETS = {
    "16x12": (12, 16),
}

_current_rows = ROWS
_current_cols = COLS


def get_grid_size() -> tuple[int, int]:
    return _current_rows, _current_cols


def set_grid_size(rows: int, cols: int) -> None:
    global _current_rows, _current_cols
    _current_rows = rows
    _current_cols = cols


def blank_rows() -> tuple[tuple[str, ...], ...]:
    rows_count, cols_count = _current_rows, _current_cols
    grid = [["." for _ in range(cols_count)] for _ in range(rows_count)]
    for row in range(rows_count):
        grid[row][0] = "#"
        grid[row][cols_count - 1] = "#"
    for col in range(cols_count):
        grid[0][col] = "#"
        grid[rows_count - 1][col] = "#"
    start_row, start_col = START if _inside(START, rows_count, cols_count) else (1, 1)
    grid[start_row][start_col] = "P"
    return tuple(tuple(row) for row in grid)


def level_from_rows(
    rows: tuple[tuple[str, ...], ...],
    *,
    category: int,
    name: str | None = None,
    level_id: int = 0,
) -> Level:
    validate_rows(rows, category=category)
    if category not in CATEGORY_NAMES:
        raise ValueError(f"Unknown planning category {category}")

    return Level(
        level_id=level_id,
        name=name or CATEGORY_NAMES[category],
        rows=rows,
        category=category,
        use_vision=category in (2, 3),
        use_deadlock=category in (2, 3),
        hp_start=20,
        description=CATEGORY_NAMES[category],
    )


def validate_rows(rows: tuple[tuple[str, ...], ...], *, category: int = 1) -> None:
    if len(rows) < 4:
        raise ValueError("Map must have at least 4 rows")
    if any(len(row) < 4 for row in rows):
        raise ValueError("Map must have at least 4 columns")
    if any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("All rows must have the same length")

    player_count = 0
    endpoint_count = 0
    boxes: set[int] = set()
    targets: set[int] = set()
    for row in rows:
        for token in row:
            if token in {"D", "*"}:
                raise ValueError("D and * are deprecated. Use # walls and X pushable bombs.")
            if token not in TOKEN_CHOICES:
                raise ValueError(f"Unsupported token {token!r}")
            if token == "P":
                player_count += 1
            elif token == "E":
                endpoint_count += 1
            elif token.startswith("B"):
                boxes.add(int(token[1:]))
            elif token.startswith("T"):
                targets.add(int(token[1:]))

    if player_count != 1:
        raise ValueError("Map must contain exactly one player P")

    if category == 1:
        if endpoint_count != 1:
            raise ValueError("Category 1 map must contain exactly one endpoint E")
        if boxes or targets:
            raise ValueError("Category 1 map should not contain boxes or targets")
    else:
        if not boxes:
            raise ValueError("Map must contain at least one numbered box")
        if boxes != targets:
            raise ValueError(f"Box ids {sorted(boxes)} must match target ids {sorted(targets)}")
        if endpoint_count > 0:
            raise ValueError("Category 2/3 map should not contain endpoint E")


def set_cell(
    rows: tuple[tuple[str, ...], ...],
    row: int,
    col: int,
    token: str,
) -> tuple[tuple[str, ...], ...]:
    if token in {"D", "*"}:
        raise ValueError("D and * are deprecated. Use # walls and X pushable bombs.")
    if token not in TOKEN_CHOICES:
        raise ValueError(f"Unsupported token {token!r}")
    max_row = len(rows)
    max_col = len(rows[0]) if rows else 0
    if not (0 <= row < max_row and 0 <= col < max_col):
        raise ValueError(f"Cell {(row, col)} is outside the map")

    grid = [list(line) for line in rows]
    if token == "P":
        for r in range(len(grid)):
            for c in range(len(grid[r])):
                if grid[r][c] == "P":
                    grid[r][c] = "."
    if token == "E":
        for r in range(len(grid)):
            for c in range(len(grid[r])):
                if grid[r][c] == "E":
                    grid[r][c] = "."
    grid[row][col] = token
    return tuple(tuple(line) for line in grid)


def with_category(level: Level, category: int) -> Level:
    if category not in CATEGORY_NAMES:
        raise ValueError(f"Unknown planning category {category}")
    return replace(
        level,
        category=category,
        name=CATEGORY_NAMES[category],
        use_vision=category in (2, 3),
        use_deadlock=category in (2, 3),
        hp_start=20,
        description=CATEGORY_NAMES[category],
        boxes_vanish_on_goal=category in (2, 3),
    )


def _inside(pos: tuple[int, int], rows: int, cols: int) -> bool:
    return 0 <= pos[0] < rows and 0 <= pos[1] < cols


with_mode = with_category
