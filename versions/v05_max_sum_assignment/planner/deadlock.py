from __future__ import annotations

from collections import deque

from .grid import Board, Position


def compute_deadlock_cells(board: Board) -> set[Position]:
    cells: set[Position] = set()
    goals = set(board.goals.values())
    for row in range(board.rows):
        for col in range(board.cols):
            pos = (row, col)
            if board.is_wall(pos) or pos in goals:
                continue
            if _is_corner(board, pos):
                cells.add(pos)
    # Merge simple deadlock zone: positions unreachable from any goal via pushes
    zone = compute_simple_deadlock_zone(board)
    cells |= zone
    return cells


def compute_deadlock_zone(board: Board) -> frozenset[Position]:
    """Precompute positions from which no box can ever reach any goal."""
    return frozenset(compute_deadlock_cells(board))


def compute_simple_deadlock_zone(board: Board) -> set[Position]:
    """Positions from which a box can never reach any goal via any push sequence.

    Reverse BFS from all goals: a goal can be reached by a box pushed from an
    adjacent cell if the stance cell (two steps behind) is free.  All cells not
    visited by this reverse search are dead for any box.
    """
    goals = set(board.goals.values())
    walls = board.walls
    rows = board.rows
    cols = board.cols
    reachable: set[Position] = set(goals)
    queue: deque[Position] = deque(goals)
    while queue:
        cur = queue.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            # previous = cell the box was pushed FROM to reach cur
            pr, pc = cur[0] - dr, cur[1] - dc
            prev = (pr, pc)
            if prev in reachable:
                continue
            if pr < 0 or pc < 0 or pr >= rows or pc >= cols:
                continue
            if prev in walls:
                continue
            # stance = cell the car stood on to push the box from prev to cur
            sr, sc = pr - dr, pc - dc
            if sr < 0 or sc < 0 or sr >= rows or sc >= cols:
                continue
            if (sr, sc) in walls:
                continue
            reachable.add(prev)
            queue.append(prev)
    # Every non-wall, non-goal interior cell not in reachable is a deadlock zone
    zone: set[Position] = set()
    for row in range(rows):
        for col in range(cols):
            pos = (row, col)
            if pos not in walls and pos not in goals and pos not in reachable:
                zone.add(pos)
    return zone


def is_deadlocked(
    board: Board,
    box_id: int,
    box_pos: Position,
    boxes: dict[int, Position],
) -> bool:
    return is_deadlocked_positions(board, box_id, box_pos, set(boxes.values()))


def is_deadlocked_positions(
    board: Board,
    box_id: int,
    box_pos: Position,
    box_positions: set[Position],
    goal_positions: frozenset[Position] | None = None,
) -> bool:
    if goal_positions is None:
        goal_positions = frozenset(board.goals.values())
    goal = board.goals[box_id]
    if box_pos == goal:
        return False

    rows = board.rows
    cols = board.cols
    walls = board.walls
    row, col = box_pos

    up = row - 1 < 0 or (row - 1, col) in walls
    down = row + 1 >= rows or (row + 1, col) in walls
    left = col - 1 < 0 or (row, col - 1) in walls
    right = col + 1 >= cols or (row, col + 1) in walls

    if (up or down) and (left or right):
        return True
    if (up or down) and goal[0] != row:
        return True
    if (left or right) and goal[1] != col:
        return True

    # Wall-line deadlock: if box is against a wall, check if goal is on same line
    if up or down:
        # Box against top/bottom wall — can only move left/right
        # If goal is not on same row, this is a deadlock
        # (already caught above, but also check with boxes as obstacles)
        pass  # handled by (up or down) check above

    for top in (row - 1, row):
        for left_col in (col - 1, col):
            contains_goal = False
            blocked = True
            for check_row in (top, top + 1):
                for check_col in (left_col, left_col + 1):
                    cell = (check_row, check_col)
                    if cell in goal_positions:
                        contains_goal = True
                        break
                    is_wall = (
                        check_row < 0
                        or check_col < 0
                        or check_row >= rows
                        or check_col >= cols
                        or cell in walls
                    )
                    if not (is_wall or cell in box_positions):
                        blocked = False
                        break
                if contains_goal or not blocked:
                    break
            if (not contains_goal) and blocked:
                return True
    return False


def _is_corner(board: Board, pos: Position) -> bool:
    row, col = pos
    rows = board.rows
    cols = board.cols
    walls = board.walls
    up = row - 1 < 0 or (row - 1, col) in walls
    down = row + 1 >= rows or (row + 1, col) in walls
    left = col - 1 < 0 or (row, col - 1) in walls
    right = col + 1 >= cols or (row, col + 1) in walls
    return (up or down) and (left or right)


def _is_wall_line_deadlock(board: Board, box_id: int, pos: Position) -> bool:
    row, col = pos
    goal = board.goals[box_id]

    if board.is_wall((row - 1, col)) or board.is_wall((row + 1, col)):
        return goal[0] != row
    if board.is_wall((row, col - 1)) or board.is_wall((row, col + 1)):
        return goal[1] != col
    return False


def _is_2x2_deadlock(
    board: Board,
    pos: Position,
    box_positions: set[Position],
    goal_positions: frozenset[Position],
) -> bool:
    row, col = pos
    for top in (row - 1, row):
        for left in (col - 1, col):
            contains_goal = False
            blocked = True
            for check_row in (top, top + 1):
                for check_col in (left, left + 1):
                    cell = (check_row, check_col)
                    if cell in goal_positions:
                        contains_goal = True
                        break
                    if not (board.is_wall(cell) or cell in box_positions):
                        blocked = False
                if contains_goal or not blocked:
                    break
            if (not contains_goal) and blocked:
                return True
    return False


# --------------- Frozen (multi-box group) deadlock detection ---------------

def is_frozen_deadlock_positions(
    board: Board,
    box_positions: set[Position],
    goal_positions: frozenset[Position],
) -> bool:
    """Fixed-point detection: if any box is frozen (cannot be pushed in any
    direction) and is NOT on its own goal, the position is deadlocked.

    A box is frozen when every push direction is blocked by a wall, boundary,
    or another frozen box.  We iterate until the frozen set stabilises.

    Only called after the single-box deadlock checks pass, so this catches
    mutually-blocking groups that corner/line checks miss.
    """
    if not box_positions:
        return False
    walls = board.walls
    rows = board.rows
    cols = board.cols

    # A box on any goal is never considered frozen (optimisation: avoids
    # false-positive when two boxes share a 2x2 and one is already delivered).
    candidates = box_positions - goal_positions
    if not candidates:
        return False

    # Direction deltas: up, down, left, right
    deltas = ((-1, 0), (1, 0), (0, -1), (0, 1))

    frozen: set[Position] = set()
    changed = True
    # Limit iterations to avoid blowup (16x12 grid → max ~192 cells)
    max_iter = rows * cols
    iteration = 0
    while changed and iteration < max_iter:
        changed = False
        iteration += 1
        for pos in candidates:
            if pos in frozen:
                continue
            all_blocked = True
            for dr, dc in deltas:
                r, c = pos
                # Direction is blocked for a box if pushing in that direction
                # hits wall/boundary on the target side, OR if the stance cell
                # (car position behind the box) is blocked by wall/boundary.
                target = (r + dr, c + dc)
                stance = (r - dr, c - dc)
                target_blocked = (
                    target[0] < 0 or target[1] < 0
                    or target[0] >= rows or target[1] >= cols
                    or target in walls
                )
                stance_blocked = (
                    stance[0] < 0 or stance[1] < 0
                    or stance[0] >= rows or stance[1] >= cols
                    or stance in walls
                )
                # If another box blocks target or stance, treat that direction
                # as blocked only when that other box is already frozen.
                if not target_blocked and target in box_positions and target not in frozen:
                    all_blocked = False
                    break
                if not stance_blocked and stance in box_positions and stance not in frozen:
                    all_blocked = False
                    break
                if target_blocked or stance_blocked:
                    continue
                # Both target and stance are free or contain frozen boxes → direction blocked
                # Actually, if target and stance are both free, the box CAN be pushed.
                if target not in box_positions and stance not in box_positions:
                    all_blocked = False
                    break
            if all_blocked:
                frozen.add(pos)
                changed = True

    # Any frozen box not on its goal → deadlock
    for pos in frozen:
        if pos not in goal_positions:
            return True
    return False
