from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .grid import Board, Position


@dataclass(frozen=True)
class Region:
    region_id: int
    cells: frozenset[Position]
    kind: str
    ports: tuple[Position, ...]


@dataclass(frozen=True)
class TargetMotion:
    box_id: int
    box: Position
    goal: Position
    box_region: int
    goal_region: int
    region_path: tuple[int, ...]
    estimated_cell_distance: int


@dataclass(frozen=True)
class RegionPlan:
    regions: tuple[Region, ...]
    cell_to_region: dict[Position, int]
    adjacency: dict[int, tuple[int, ...]]
    target_motions: tuple[TargetMotion, ...]
    notes: tuple[str, ...]


def build_region_plan(board: Board) -> RegionPlan:
    """Build a coarse target-motion plan over small map regions.

    This is intentionally a planning *version*, not a replacement for the exact
    Sokoban A* solver. It decomposes the map into local regions and produces a
    coarse B_i -> T_i motion order/path that can later guide bounded searches.
    """
    free = _free_cells(board)
    anchors = set(board.boxes.values()) | set(board.goals.values()) | {board.player}
    splitters = _splitter_cells(board, free, anchors)
    cell_to_region: dict[Position, int] = {}
    regions: list[Region] = []

    # Split non-critical open/corridor cells first.
    visited: set[Position] = set()
    for cell in sorted(free - splitters):
        if cell in visited:
            continue
        component = _component(board, cell, free - splitters, visited)
        if not component:
            continue
        region_id = len(regions)
        ports = tuple(sorted(_neighbor_splitters(board, component, splitters)))
        kind = _classify_region(board, component)
        region = Region(region_id, frozenset(component), kind, ports)
        regions.append(region)
        for pos in component:
            cell_to_region[pos] = region_id

    # Critical cells become tiny local regions so boxes/goals/doors stay visible.
    for cell in sorted(splitters):
        region_id = len(regions)
        kind = "target" if cell in board.goals.values() else "box" if cell in board.boxes.values() else "gate"
        region = Region(region_id, frozenset({cell}), kind, tuple(sorted(_free_neighbors(board, cell, free))))
        regions.append(region)
        cell_to_region[cell] = region_id

    adjacency_sets: dict[int, set[int]] = {region.region_id: set() for region in regions}
    for cell, region_id in cell_to_region.items():
        for nxt in _free_neighbors(board, cell, free):
            other = cell_to_region.get(nxt)
            if other is not None and other != region_id:
                adjacency_sets[region_id].add(other)
    adjacency = {rid: tuple(sorted(neighbors)) for rid, neighbors in adjacency_sets.items()}

    target_motions = tuple(_target_motions(board, cell_to_region, adjacency))
    notes = (
        "Coarse target-motion plan only; exact push legality is still verified by solver.solve().",
        "Boxes, goals, player, and gate cells are preserved as tiny regions.",
        "If bombs destroy walls, rebuild this region plan after the explosion.",
    )
    return RegionPlan(tuple(regions), cell_to_region, adjacency, target_motions, notes)


def format_region_plan(plan: RegionPlan) -> str:
    lines: list[str] = []
    lines.append(f"regions={len(plan.regions)} target_motions={len(plan.target_motions)}")
    lines.append("region summary:")
    for region in plan.regions:
        lines.append(
            f"  R{region.region_id:02d} kind={region.kind:<8} cells={len(region.cells):>3} "
            f"neighbors={list(plan.adjacency.get(region.region_id, ()))}"
        )
    lines.append("target motions:")
    for motion in plan.target_motions:
        lines.append(
            f"  B{motion.box_id}: {motion.box} R{motion.box_region} -> "
            f"T{motion.box_id} {motion.goal} R{motion.goal_region} "
            f"regions={list(motion.region_path)} estimate={motion.estimated_cell_distance}"
        )
    lines.append("notes:")
    for note in plan.notes:
        lines.append(f"  - {note}")
    return "\n".join(lines)


def format_target_motion_plan(plan: RegionPlan) -> str:
    lines = [
        f"regions={len(plan.regions)} target_motions={len(plan.target_motions)}",
        "target motion order:",
    ]
    for index, motion in enumerate(plan.target_motions, start=1):
        lines.append(
            f"  {index}. B{motion.box_id} R{motion.box_region} -> "
            f"T{motion.box_id} R{motion.goal_region}; "
            f"region_path={list(motion.region_path)}; estimate={motion.estimated_cell_distance}"
        )
    return "\n".join(lines)


def _free_cells(board: Board) -> set[Position]:
    return {
        (row, col)
        for row in range(board.rows)
        for col in range(board.cols)
        if (row, col) not in board.walls
    }


def _splitter_cells(board: Board, free: set[Position], anchors: set[Position]) -> set[Position]:
    splitters = set(anchors)
    for cell in free:
        degree = len(_free_neighbors(board, cell, free))
        if degree != 2:
            splitters.add(cell)
    return splitters


def _component(
    board: Board,
    start: Position,
    allowed: set[Position],
    visited: set[Position],
) -> set[Position]:
    queue: deque[Position] = deque([start])
    visited.add(start)
    component: set[Position] = set()
    while queue:
        cur = queue.popleft()
        component.add(cur)
        for nxt in _free_neighbors(board, cur, allowed):
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return component


def _free_neighbors(board: Board, cell: Position, free: set[Position]) -> tuple[Position, ...]:
    row, col = cell
    candidates = ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1))
    return tuple(pos for pos in candidates if pos in free)


def _neighbor_splitters(board: Board, cells: set[Position], splitters: set[Position]) -> set[Position]:
    result: set[Position] = set()
    for cell in cells:
        result.update(_free_neighbors(board, cell, splitters))
    return result


def _classify_region(board: Board, cells: set[Position]) -> str:
    degrees = [len(_free_neighbors(board, cell, _free_cells(board))) for cell in cells]
    if cells & set(board.goals.values()):
        return "target"
    if cells & set(board.boxes.values()):
        return "box"
    if len(cells) <= 2 or all(degree <= 2 for degree in degrees):
        return "corridor"
    return "room"


def _target_motions(
    board: Board,
    cell_to_region: dict[Position, int],
    adjacency: dict[int, tuple[int, ...]],
) -> list[TargetMotion]:
    motions: list[TargetMotion] = []
    for box_id in sorted(board.boxes):
        box = board.boxes[box_id]
        goal = board.goals[box_id]
        box_region = cell_to_region[box]
        goal_region = cell_to_region[goal]
        path = _region_path(box_region, goal_region, adjacency)
        motions.append(
            TargetMotion(
                box_id=box_id,
                box=box,
                goal=goal,
                box_region=box_region,
                goal_region=goal_region,
                region_path=tuple(path),
                estimated_cell_distance=abs(box[0] - goal[0]) + abs(box[1] - goal[1]),
            )
        )
    motions.sort(key=lambda item: (len(item.region_path), item.estimated_cell_distance, item.box_id))
    return motions


def _region_path(start: int, goal: int, adjacency: dict[int, tuple[int, ...]]) -> list[int]:
    queue: deque[int] = deque([start])
    parent: dict[int, int | None] = {start: None}
    while queue:
        cur = queue.popleft()
        if cur == goal:
            break
        for nxt in adjacency.get(cur, ()):
            if nxt not in parent:
                parent[nxt] = cur
                queue.append(nxt)
    if goal not in parent:
        return [start]
    path: list[int] = []
    cur: int | None = goal
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path
