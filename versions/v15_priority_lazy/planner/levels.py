from __future__ import annotations

from .grid import Level

ROWS = 12
COLS = 16
# User-facing coordinate: first column, fifth row from left-to-right/top-to-bottom.
# The surrounding wall occupies row/col 0, so this is the first interior column.
START = (5, 1)


def _make_rows(
    *,
    walls: set[tuple[int, int]] | None = None,
    tokens: dict[tuple[int, int], str] | None = None,
) -> tuple[tuple[str, ...], ...]:
    walls = walls or set()
    tokens = dict(tokens or {})
    grid = [["." for _ in range(COLS)] for _ in range(ROWS)]

    for row in range(ROWS):
        grid[row][0] = "#"
        grid[row][COLS - 1] = "#"
    for col in range(COLS):
        grid[0][col] = "#"
        grid[ROWS - 1][col] = "#"

    for row, col in walls:
        _assert_inside(row, col)
        grid[row][col] = "#"

    if START not in tokens:
        tokens[START] = "P"

    for (row, col), token in tokens.items():
        _assert_inside(row, col)
        if grid[row][col] == "#":
            raise ValueError(f"Token {token} cannot be placed on wall {(row, col)}")
        grid[row][col] = token

    return tuple(tuple(row) for row in grid)


def _assert_inside(row: int, col: int) -> None:
    if not (0 <= row < ROWS and 0 <= col < COLS):
        raise ValueError(f"Cell {(row, col)} is outside {ROWS}x{COLS}")


LEVEL_2_WALLS = {
    *((2, col) for col in range(2, 6)),
    *((2, col) for col in range(10, 14)),
    *((4, col) for col in range(2, 4)),
    *((4, col) for col in range(12, 14)),
    *((6, col) for col in range(4, 7)),
    *((6, col) for col in range(9, 12)),
    *((8, col) for col in range(2, 4)),
    *((8, col) for col in range(12, 14)),
    *((10, col) for col in range(2, 6)),
    *((10, col) for col in range(10, 14)),
}

LEVEL_1_WALLS = set(LEVEL_2_WALLS)

# Category 3: an ordinary wall line blocks the box route. The car pushes X
# into that wall; the impact removes non-boundary wall cells in the 3x3 blast.
LEVEL_3_WALLS = {
    *LEVEL_2_WALLS,
    (2, 8),
    (3, 9),
    (4, 8),
}


LEVELS: dict[int, Level] = {
    1: Level(
        level_id=1,
        name="Level 1 - direct numbered multi-box",
        description="Directly read a numbered 16x12 map, then solve three matched boxes without vision. Boxes vanish on target (no longer block).",
        category=2,
        use_vision=False,
        use_deadlock=True,
        boxes_vanish_on_goal=True,
        rows=_make_rows(
            walls=LEVEL_1_WALLS,
            tokens={
                START: "P",
                (3, 4): "B1",
                (3, 10): "T1",
                (7, 11): "B2",
                (7, 5): "T2",
                (9, 6): "B3",
                (9, 12): "T3",
            },
        ),
    ),
    2: Level(
        level_id=2,
        name="Category 2 - vision numbered boxes",
        description="Recognize the grid, then push each numbered box Bi onto matching Ti. Boxes vanish on target (no longer block).",
        category=2,
        use_vision=True,
        use_deadlock=True,
        boxes_vanish_on_goal=True,
        rows=_make_rows(
            walls=LEVEL_2_WALLS,
            tokens={
                START: "P",
                (3, 4): "B1",
                (3, 10): "T1",
                (7, 11): "B2",
                (7, 5): "T2",
                (9, 6): "B3",
                (9, 12): "T3",
            },
        ),
    ),
    3: Level(
        level_id=3,
        name="Category 3 - vision bombs break walls",
        description="Recognize X bombs, push one into a wall, clear a 3x3 opening, then solve B1->T1. Boxes vanish on target (no longer block).",
        category=3,
        use_vision=True,
        use_deadlock=True,
        boxes_vanish_on_goal=True,
        hp_start=20,
        rows=_make_rows(
            walls=LEVEL_3_WALLS,
            tokens={
                START: "P",
                (3, 4): "B1",
                (3, 8): "X",
                (3, 12): "T1",
                (7, 11): "B2",
                (7, 5): "T2",
                (9, 6): "B3",
                (9, 12): "T3",
            },
        ),
    ),
}


def get_level(level_id: int) -> Level:
    try:
        return LEVELS[level_id]
    except KeyError as exc:
        raise ValueError(f"Unknown level id {level_id}") from exc


def all_levels() -> list[Level]:
    return [LEVELS[index] for index in sorted(LEVELS)]
