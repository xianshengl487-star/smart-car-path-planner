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


def add_pos(pos: Position, delta: tuple[int, int]) -> Position:
    return pos[0] + delta[0], pos[1] + delta[1]


def to_mutable_rows(rows: Iterable[Iterable[str]]) -> list[list[str]]:
    return [list(row) for row in rows]
