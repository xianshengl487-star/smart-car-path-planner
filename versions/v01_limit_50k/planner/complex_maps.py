"""Extra 16x12 maps used by the optimization loop.

101: push numbered boxes only.
102: same push complexity as 101, but the car must first approach boxes and
targets for recognition before pushing them one-to-one.
103: recognition like 102, with more boxes and an X bomb that must break a wall.
104: four-box maze requiring careful push ordering and corridor traversal.
105: two bombs must be pushed into separate walls to open two independent paths.
106: three boxes + two bombs + narrow corridors — ultimate complexity.
"""
from __future__ import annotations

from .grid import Level
from .levels import START, _make_rows


_MAP_A_WALLS = {
    *((2, c) for c in range(2, 6)),
    *((2, c) for c in range(10, 14)),
    *((4, c) for c in range(2, 4)),
    *((4, c) for c in range(12, 14)),
    *((6, c) for c in range(4, 7)),
    *((6, c) for c in range(9, 12)),
    *((8, c) for c in range(2, 4)),
    *((8, c) for c in range(12, 14)),
    *((10, c) for c in range(2, 6)),
    *((10, c) for c in range(10, 14)),
}

LEVEL_A = Level(
    level_id=101,
    name="101 - push boxes only",
    description="Two numbered boxes in maze-like corridors; no vision scan and no bombs. Boxes vanish on target (no longer block).",
    category=2,
    use_vision=False,
    use_deadlock=True,
    boxes_vanish_on_goal=True,
    rows=_make_rows(
        walls=_MAP_A_WALLS,
        tokens={
            START: "P",
            (3, 4): "B1",
            (3, 10): "T1",
            (7, 11): "B2",
            (7, 5): "T2",
        },
    ),
)

LEVEL_B = Level(
    level_id=102,
    name="102 - approach recognition then push",
    description="Same map complexity as 101, but boxes and targets must be approached for recognition before pushing. Boxes vanish on target (no longer block).",
    category=2,
    use_vision=True,
    use_deadlock=True,
    requires_approach_recognition=True,
    boxes_vanish_on_goal=True,
    hp_start=20,
    rows=_make_rows(
        walls=_MAP_A_WALLS,
        tokens={
            START: "P",
            (3, 4): "B1",
            (3, 10): "T1",
            (7, 11): "B2",
            (7, 5): "T2",
        },
    ),
)

LEVEL_C = Level(
    level_id=103,
    name="103 - recognition with bombs",
    description="Recognition-first route with three numbered boxes; X must be pushed into a wall to open the B1 route. Boxes vanish on target (no longer block).",
    category=3,
    use_vision=True,
    use_deadlock=True,
    requires_approach_recognition=True,
    boxes_vanish_on_goal=True,
    hp_start=20,
    rows=_make_rows(
        walls=_MAP_A_WALLS | {(2, 8), (3, 9), (4, 8)},
        tokens={
            START: "P",
            (3, 4): "B1",
            (3, 12): "T1",
            (7, 11): "B2",
            (7, 5): "T2",
            (9, 6): "B3",
            (9, 12): "T3",
            (3, 8): "X",
        },
    ),
)


# ---- Level 104: four-box maze ----
# Same base wall layout as the other levels but with 4 boxes.
# The four boxes require careful push ordering due to cross-path dependencies.
LEVEL_D = Level(
    level_id=104,
    name="104 - four-box maze",
    description="Four numbered boxes in the standard maze. Requires careful push ordering. Boxes vanish on target.",
    category=2,
    use_vision=False,
    use_deadlock=True,
    boxes_vanish_on_goal=True,
    rows=_make_rows(
        walls=_MAP_A_WALLS,
        tokens={
            START: "P",
            (3, 4): "B1",
            (3, 12): "T1",
            (7, 11): "B2",
            (7, 3): "T2",
            (5, 5): "B3",
            (5, 11): "T3",
            (9, 6): "B4",
            (9, 12): "T4",
        },
    ),
)


# ---- Level 105: two bombs, two blocked paths ----
# Two independent wall obstacles each block a box's route.
# Each bomb must be pushed into its respective wall to open the path.
_MAP_E_WALLS = _MAP_A_WALLS | {
    # Wall blocking B1's path to T1 (vertical wall at col 8, row 2-4)
    (2, 8), (3, 8), (4, 8),
    # Wall blocking B2's path to T2 (vertical wall at col 8, row 6-8)
    (6, 8), (7, 8), (8, 8),
}

LEVEL_E = Level(
    level_id=105,
    name="105 - two bombs two paths",
    description="Two bombs must each be pushed into a wall to open separate paths for two boxes. Tests multi-bomb planning. Boxes vanish on target.",
    category=3,
    use_vision=False,
    use_deadlock=True,
    boxes_vanish_on_goal=True,
    hp_start=20,
    rows=_make_rows(
        walls=_MAP_E_WALLS,
        tokens={
            START: "P",
            (3, 4): "B1",
            (3, 12): "T1",
            (7, 11): "B2",
            (7, 3): "T2",
            (3, 6): "X",
            (7, 6): "X",
        },
    ),
)


# ---- Level 106: ultimate complexity ----
# 3 boxes + 1 bomb + narrow corridors + recognition requirement.
# The car must recognize objects, push bomb to clear wall, then deliver boxes.
_MAP_F_WALLS = _MAP_A_WALLS | {
    # Wall blocking B1 route (must bomb to clear)
    (2, 8), (3, 8), (4, 8),
}

LEVEL_F = Level(
    level_id=106,
    name="106 - ultimate complexity",
    description="3 boxes + 1 bomb + recognition. Requires recognition, bomb-clearing, and precise push ordering. Boxes vanish on target.",
    category=3,
    use_vision=True,
    use_deadlock=True,
    requires_approach_recognition=True,
    boxes_vanish_on_goal=True,
    hp_start=20,
    rows=_make_rows(
        walls=_MAP_F_WALLS,
        tokens={
            START: "P",
            (3, 4): "B1",
            (3, 12): "T1",
            (7, 11): "B2",
            (7, 5): "T2",
            (9, 6): "B3",
            (9, 12): "T3",
            (3, 6): "X",
        },
    ),
)


COMPLEX_LEVELS: dict[int, Level] = {
    101: LEVEL_A,
    102: LEVEL_B,
    103: LEVEL_C,
    104: LEVEL_D,
    105: LEVEL_E,
    106: LEVEL_F,
}


def all_complex_levels() -> list[Level]:
    return [COMPLEX_LEVELS[k] for k in sorted(COMPLEX_LEVELS)]


def get_complex_level(level_id: int) -> Level:
    try:
        return COMPLEX_LEVELS[level_id]
    except KeyError as exc:
        raise ValueError(f"Unknown complex level id {level_id}") from exc
