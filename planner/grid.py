from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

Position = tuple[int, int]
Heading = str

DIRECTIONS: tuple[tuple[int, int, str], ...] = (
    (0, -1, "L"),
    (-1, 0, "U"),
    (1, 0, "D"),
    (0, 1, "R"),
)

HEADING_DELTAS: dict[Heading, Position] = {
    "L": (0, -1),
    "U": (-1, 0),
    "D": (1, 0),
    "R": (0, 1),
}

LEFT_TURN: dict[Heading, Heading] = {
    "U": "L",
    "L": "D",
    "D": "R",
    "R": "U",
}

RIGHT_TURN: dict[Heading, Heading] = {
    "U": "R",
    "R": "D",
    "D": "L",
    "L": "U",
}


@dataclass(frozen=True)
class Level:
    level_id: int
    name: str
    rows: tuple[tuple[str, ...], ...]
    category: int = 1  # 1=simple nav, 2=vision+target, 3=vision+target+bombs
    use_vision: bool = False
    use_deadlock: bool = True
    requires_approach_recognition: bool = False
    hp_start: int = 20
    description: str = ""
    start_heading: Heading = "R"
    boxes_vanish_on_goal: bool = False  # if True, a box pushed onto its matching target is removed and no longer blocks


@dataclass(frozen=True)
class Board:
    level: Level
    rows: int
    cols: int
    walls: frozenset[Position]
    bombs: frozenset[Position]
    goals: dict[int, Position]
    boxes: dict[int, Position]
    player: Position
    start_heading: Heading = "R"
    endpoint: Position | None = None

    @property
    def box_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self.boxes))

    def inside(self, pos: Position) -> bool:
        row, col = pos
        return 0 <= row < self.rows and 0 <= col < self.cols

    def is_wall(self, pos: Position) -> bool:
        return (not self.inside(pos)) or pos in self.walls

    def is_goal_state(self, boxes_tuple: tuple[Position, ...]) -> bool:
        if not self.goals:
            return False
        return all(
            boxes_tuple[index] == self.goals[box_id]
            for index, box_id in enumerate(self.box_ids)
        )

    def boxes_tuple(self) -> tuple[Position, ...]:
        return tuple(self.boxes[box_id] for box_id in self.box_ids)

    def boxes_dict(self, boxes_tuple: tuple[Position, ...]) -> dict[int, Position]:
        return {
            box_id: boxes_tuple[index]
            for index, box_id in enumerate(self.box_ids)
        }


@dataclass(frozen=True)
class Step:
    player: Position
    boxes: dict[int, Position]
    action: str
    pushed_box_id: int | None
    hp: int
    cost: int
    walls: frozenset[Position] | None = None
    bombs: frozenset[Position] | None = None
    explosions: frozenset[Position] = frozenset()
    heading: Heading | None = None


@dataclass
class SolveResult:
    level_id: int
    level_name: str
    solved: bool
    steps: list[Step]
    actions: list[str]
    total_cost: int
    pushes: int
    expanded: int
    generated: int
    pruned_deadlocks: int
    hp: int
    deadlock_cells: set[Position]
    message: str = ""
    expanded_without_deadlock: int | None = None
    recognition_cost: int = 0
    recognition_order: list[str] | None = None
    recognition_path: list[Position] | None = None
    recognition_headings: list[Heading] | None = None
    generated_image: str | None = None
    recognized_image: str | None = None
    final_image: str | None = None


def parse_level(level: Level) -> Board:
    if not level.rows:
        raise ValueError("Level has no rows")

    cols = len(level.rows[0])
    walls: set[Position] = set()
    bombs: set[Position] = set()
    goals: dict[int, Position] = {}
    boxes: dict[int, Position] = {}
    player: Position | None = None
    endpoint: Position | None = None

    for row_index, row in enumerate(level.rows):
        if len(row) != cols:
            raise ValueError(f"Row {row_index} has inconsistent width")
        for col_index, token in enumerate(row):
            pos = (row_index, col_index)
            if token == "#":
                walls.add(pos)
            elif token == "P":
                if player is not None:
                    raise ValueError("Level has more than one player")
                player = pos
            elif token == "X":
                bombs.add(pos)
            elif token == "E":
                if endpoint is not None:
                    raise ValueError("Level has more than one endpoint")
                endpoint = pos
            elif token in {"D", "*"}:
                raise ValueError(
                    f"Token {token!r} is deprecated. Use '#' for walls and 'X' for pushable bombs."
                )
            elif token.startswith("B"):
                boxes[_parse_id(token, "B")] = pos
            elif token.startswith("T"):
                goals[_parse_id(token, "T")] = pos
            elif token != ".":
                raise ValueError(f"Unknown token {token!r} at {pos}")

    if player is None:
        raise ValueError("Level has no player")

    if level.category == 1:
        if endpoint is None:
            raise ValueError("Category 1 level must have an endpoint E")
    else:
        if not boxes:
            raise ValueError("Level has no boxes")
        if set(boxes) != set(goals):
            raise ValueError(
                f"Box ids {sorted(boxes)} do not match goal ids {sorted(goals)}"
            )

    return Board(
        level=level,
        rows=len(level.rows),
        cols=cols,
        walls=frozenset(walls),
        bombs=frozenset(bombs),
        goals=goals,
        boxes=boxes,
        player=player,
        start_heading=level.start_heading,
        endpoint=endpoint,
    )


def _parse_id(token: str, prefix: str) -> int:
    suffix = token[len(prefix):]
    if not suffix.isdigit():
        raise ValueError(f"Token {token!r} must be {prefix}<number>")
    return int(suffix)


# ---------------------------------------------------------------------------
# load_text_map — read a MapTextCodec-style .txt file into a Level
# ---------------------------------------------------------------------------

# MapTextCodec compact tokens → Level grid tokens expected by parse_level
_TEXT_TO_LEVEL_TOKEN: dict[str, str] = {
    ".": ".",
    "#": "#",
    "P": "P",
    "X": "X",
    "B1": "B1", "B2": "B2", "B3": "B3", "B4": "B4",
    "T1": "T1", "T2": "T2", "T3": "T3", "T4": "T4",
    "a": "T1", "b": "T2", "c": "T3", "d": "T4",
    "1": "B1", "2": "B2", "3": "B3", "4": "B4",
    "5": "B5", "6": "B6", "7": "B7", "8": "B8",
}


def _parse_map_row(line: str) -> list[str]:
    """Parse one grid row from either compact or spaced format."""
    stripped = line.strip()
    if " " in stripped:
        return stripped.split()
    # Compact: 16 characters without spaces
    return list(stripped)


def load_text_map(path: "str | Path") -> Level:
    """Read a MapTextCodec-style .txt map file and return a Level object.

    The file may contain comment lines (starting with ``//``), a header line
    with ``key=value`` pairs, and 12 rows of 16 tokens each.

    Accepted header keys: level, heading, recognition, scanBombs, allowBombPush.
    Tokens are translated from MapTextCodec compact form (``1``, ``a``) to the
    Level grid form (``B1``, ``T1``) expected by :func:`parse_level`.
    """
    from pathlib import Path as _Path

    text = _Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()

    # Defaults (match MapTextCodec defaults)
    level_id = 201
    heading = "R"
    recognition = False
    scan_bombs = False
    allow_bomb_push = False
    grid_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        if "=" in stripped and not stripped[0].isdigit() and stripped[0] != "." and stripped[0] != "#":
            # Header line
            for part in stripped.split():
                eq = part.find("=")
                if eq <= 0:
                    continue
                key = part[:eq].lower()
                val = part[eq + 1:]
                if key == "level":
                    level_id = int(val)
                elif key == "heading":
                    heading = val.upper()
                elif key == "recognition":
                    recognition = val.lower() == "true"
                elif key == "scanbombs":
                    scan_bombs = val.lower() == "true"
                elif key == "allowbombpush":
                    allow_bomb_push = val.lower() == "true"
            continue
        grid_lines.append(stripped)

    if len(grid_lines) != 12:
        raise ValueError(f"Expected 12 grid rows, got {len(grid_lines)} in {path}")

    # Parse grid rows and translate tokens
    rows: list[tuple[str, ...]] = []
    for row_str in grid_lines:
        tokens = _parse_map_row(row_str)
        if len(tokens) != 16:
            raise ValueError(f"Expected 16 tokens per row, got {len(tokens)} in {path}")
        translated = []
        for tok in tokens:
            mapped = _TEXT_TO_LEVEL_TOKEN.get(tok)
            if mapped is None:
                raise ValueError(f"Unknown token {tok!r} in {path}")
            translated.append(mapped)
        rows.append(tuple(translated))

    # Infer category from flags
    if scan_bombs:
        category = 3
    elif recognition:
        category = 2
    else:
        category = 2  # push-only still category 2 in complex_maps convention

    return Level(
        level_id=level_id,
        name=_Path(path).stem,
        rows=tuple(rows),
        category=category,
        use_vision=recognition,
        use_deadlock=True,
        requires_approach_recognition=recognition,
        boxes_vanish_on_goal=True,
        start_heading=heading,
        description=f"Loaded from {_Path(path).name}",
    )


def add_pos(pos: Position, delta: tuple[int, int]) -> Position:
    return pos[0] + delta[0], pos[1] + delta[1]


def to_mutable_rows(rows: Iterable[Iterable[str]]) -> list[list[str]]:
    return [list(row) for row in rows]
