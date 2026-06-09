from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from heapq import heappop, heappush
from itertools import count

from .deadlock import compute_deadlock_cells, is_deadlocked_positions, is_frozen_deadlock_positions, compute_deadlock_zone
from .grid import (
    Board,
    DIRECTIONS,
    HEADING_DELTAS,
    LEFT_TURN,
    RIGHT_TURN,
    Heading,
    Position,
    SolveResult,
    Step,
    add_pos,
)
from .recognition import plan_approach_recognition


HEADING_ORDER: tuple[Heading, ...] = ("L", "U", "D", "R")
HEADING_INDEX: dict[Heading, int] = {heading: index for index, heading in enumerate(HEADING_ORDER)}
HEADING_DR: tuple[int, ...] = (0, -1, 1, 0)
HEADING_DC: tuple[int, ...] = (-1, 0, 0, 1)
LEFT_INDEX: tuple[int, ...] = (2, 0, 3, 1)
RIGHT_INDEX: tuple[int, ...] = (1, 3, 0, 2)

BoxConfig = tuple[tuple[int, Position], ...]  # (box_id, pos) for *remaining* boxes only; sorted by id. Empty when all delivered (for vanish levels).

State = tuple[Position, Heading, BoxConfig, int]
BombState = tuple[
    Position,
    Heading,
    BoxConfig,
    tuple[Position, ...],
    tuple[Position, ...],
    int,
]

# Precomputed reverse-push distances: (walls_key, goals_key) -> {goal_id: {pos: dist}}
_push_dist_cache: dict[tuple, dict[int, dict[Position, int]]] = {}
_wall_index_cache: dict[tuple[int, int, frozenset[Position]], tuple[int, ...]] = {}
_wall_tuple_cache: dict[tuple[Position, ...], frozenset[Position]] = {}


def _precompute_push_distances(board: Board, walls: frozenset[Position] | None = None) -> dict[int, dict[Position, int]]:
    """Reverse single-box push distances from each numbered goal.

    The table ignores other movable objects and player routing, so every entry
    remains an admissible lower bound for the real directional-car action cost.
    """
    effective_walls = walls if walls is not None else board.walls
    cache_key = (effective_walls, frozenset(board.goals.items()))
    cached = _push_dist_cache.get(cache_key)
    if cached is not None:
        return cached

    result: dict[int, dict[Position, int]] = {}
    for goal_id, goal_pos in board.goals.items():
        dist: dict[Position, int] = {goal_pos: 0}
        queue: deque[Position] = deque([goal_pos])
        while queue:
            cur = queue.popleft()
            cur_d = dist[cur]
            for row_delta, col_delta, _direction in DIRECTIONS:
                previous = (cur[0] - row_delta, cur[1] - col_delta)
                stance = (previous[0] - row_delta, previous[1] - col_delta)
                if (
                    previous in dist
                    or (not board.inside(previous))
                    or (not board.inside(stance))
                    or previous in effective_walls
                    or stance in effective_walls
                ):
                    continue
                dist[previous] = cur_d + 1
                queue.append(previous)
        result[goal_id] = dist
    _push_dist_cache[cache_key] = result
    return result


def _walls_from_tuple(walls_tuple: tuple[Position, ...]) -> frozenset[Position]:
    cached = _wall_tuple_cache.get(walls_tuple)
    if cached is not None:
        return cached
    frozen = frozenset(walls_tuple)
    _wall_tuple_cache[walls_tuple] = frozen
    return frozen


def _heuristic(board: Board, boxes_config: BoxConfig) -> int:
    """Push-aware Manhattan hybrid: use reverse push distance when available.
    Only considers remaining (undelivered) boxes.
    """
    return _heuristic_with_distances(board, boxes_config, _precompute_push_distances(board))


def _heuristic_with_distances(
    board: Board,
    boxes_config: BoxConfig,
    wall_dist: dict[int, dict[Position, int]],
) -> int:
    """Hungarian-style matching heuristic: use max of sum and min-assignment.

    The simple sum is admissible when boxes/goals are far apart; the min
    assignment is tighter when they could share goals.  Taking the max
    preserves admissibility while getting the tighter bound.
    """
    n = len(boxes_config)
    if n == 0:
        return 0

    goal_ids = sorted(board.goals)
    # Simple sum heuristic (individual box->matched goal)
    simple_sum = 0
    cost_matrix: list[list[int]] = [] if n > 1 else []
    for box_id, box_pos in boxes_config:
        goal_pos = board.goals[box_id]
        gd = wall_dist.get(box_id, {})
        c = gd.get(box_pos, abs(box_pos[0] - goal_pos[0]) + abs(box_pos[1] - goal_pos[1]))
        simple_sum += c
        if n > 1:
            row_costs: list[int] = []
            for gid in goal_ids:
                gpos = board.goals[gid]
                gdd = wall_dist.get(gid, {})
                row_costs.append(gdd.get(box_pos, abs(box_pos[0] - gpos[0]) + abs(box_pos[1] - gpos[1])))
            cost_matrix.append(row_costs)

    if n == 1:
        return simple_sum

    assignment = _min_assignment_cost(cost_matrix)
    return max(simple_sum, assignment)


def _min_assignment_cost(cost_matrix: list[list[int]]) -> int:
    """Brute-force minimum assignment for small n (<=4) with early termination."""
    n = len(cost_matrix)
    if n == 0:
        return 0
    m = len(cost_matrix[0])
    best = 10**9
    cols = list(range(m))

    def _permute(path: list[int], remaining: list[int], partial: int) -> None:
        nonlocal best
        if partial >= best:
            return  # prune: already worse than best known
        if len(path) == n:
            if partial < best:
                best = partial
            return
        for j in remaining:
            path.append(j)
            _permute(path, [r for r in remaining if r != j], partial + cost_matrix[len(path) - 1][j])
            path.pop()

    _permute([], cols, 0)
    return best


def _bomb_heuristic(
    board: Board,
    boxes_config: BoxConfig,
    bombs_tuple: tuple[Position, ...],
    walls_tuple: tuple[Position, ...],
) -> int:
    """Improved bomb-mode heuristic.

    While bombs exist, future explosions may remove walls, so pure wall-aware
    BFS distances would be inadmissible.  We combine:
    1. Manhattan distance to goals (admissible lower bound).
    2. A bonus for bombs adjacent to walls that block box paths.
    """
    if not bombs_tuple:
        return _heuristic_with_distances(
            board,
            boxes_config,
            _precompute_push_distances(board, _walls_from_tuple(walls_tuple)),
        )

    wall_set = walls_tuple if isinstance(walls_tuple, frozenset) else frozenset(walls_tuple)
    estimate = 0
    for box_id, box_pos in boxes_config:
        goal_pos = board.goals[box_id]
        estimate += abs(box_pos[0] - goal_pos[0]) + abs(box_pos[1] - goal_pos[1])

    # Bonus: if a bomb is adjacent to a wall on a box-goal corridor
    bomb_bonus = 0
    for bomb_pos in bombs_tuple:
        br, bc = bomb_pos
        for r_delta, c_delta, _direction in DIRECTIONS:
            wall_cell = (br + r_delta, bc + c_delta)
            if wall_cell not in wall_set:
                continue
            for box_id, box_pos in boxes_config:
                goal_pos = board.goals[box_id]
                if _on_manhattan_path(box_pos, goal_pos, wall_cell):
                    bomb_bonus = max(bomb_bonus, 1)
    return max(0, estimate - bomb_bonus)


def _on_manhattan_path(a: Position, b: Position, p: Position) -> bool:
    """Check if point p lies on the Manhattan rectangle between a and b."""
    r1, c1 = a
    r2, c2 = b
    rp, cp = p
    min_r, max_r = min(r1, r2), max(r1, r2)
    min_c, max_c = min(c1, c2), max(c1, c2)
    return min_r <= rp <= max_r and min_c <= cp <= max_c


def _corridor_push_length(
    board: Board,
    box_pos: Position,
    dr: int,
    dc: int,
    box_positions: frozenset[Position],
    walls: frozenset[Position],
    goal_pos: Position | None = None,
) -> int:
    """How far a box can slide in direction (dr,dc) along a corridor.

    A corridor exists when the two cells perpendicular to the push direction
    are both walls/boundary (box is in a 1-wide tunnel).
    Returns 0 if not in a corridor or immediately blocked.
    Stops before the goal if the goal is in the corridor (to allow delivery).
    """
    r, c = box_pos
    rows, cols = board.rows, board.cols

    if dc != 0:  # horizontal push
        up_blocked = (r - 1 < 0) or ((r - 1, c) in walls)
        down_blocked = (r + 1 >= rows) or ((r + 1, c) in walls)
        if not (up_blocked and down_blocked):
            return 0
    else:  # vertical push
        left_blocked = (c - 1 < 0) or ((r, c - 1) in walls)
        right_blocked = (c + 1 >= cols) or ((r, c + 1) in walls)
        if not (left_blocked and right_blocked):
            return 0

    length = 0
    nr, nc = r + dr, c + dc
    while 0 <= nr < rows and 0 <= nc < cols:
        pos = (nr, nc)
        if pos in walls or pos in box_positions:
            break
        length += 1
        # Stop at goal for delivery
        if goal_pos is not None and pos == goal_pos:
            break
        nr += dr
        nc += dc
    return length


def _stance_lower_bound(
    board: Board,
    player: Position,
    box_positions: list[Position] | tuple[Position, ...],
    bomb_positions: list[Position] | tuple[Position, ...],
) -> int:
    """Admissible lower bound for reaching the next push stance.

    This ignores obstacles between the car and stance, so it can never exceed
    the real car movement cost before the next push. Goal states must return 0
    because no further push is required.
    """
    player_row, player_col = player
    best = 10**9
    for row, col in box_positions:
        vertical = min(abs(player_row - (row - 1)), abs(player_row - (row + 1))) + abs(player_col - col)
        horizontal = abs(player_row - row) + min(abs(player_col - (col - 1)), abs(player_col - (col + 1)))
        distance = vertical if vertical < horizontal else horizontal
        if distance < best:
            best = distance
    for row, col in bomb_positions:
        vertical = min(abs(player_row - (row - 1)), abs(player_row - (row + 1))) + abs(player_col - col)
        horizontal = abs(player_row - row) + min(abs(player_col - (col - 1)), abs(player_col - (col + 1)))
        distance = vertical if vertical < horizontal else horizontal
        if distance < best:
            best = distance
    return 0 if best == 10**9 else best


@dataclass(frozen=True)
class Parent:
    previous: State | None
    action: str
    pushed_box_id: int | None
    stance: Position | None = None
    segment_actions: tuple[str, ...] = ()
    segment_path: tuple[Position, ...] = ()
    segment_headings: tuple[Heading, ...] = ()


@dataclass(frozen=True)
class BombParent:
    previous: BombState | None
    action: str
    pushed_box_id: int | None
    explosions: frozenset[Position] = frozenset()
    stance: Position | None = None
    segment_actions: tuple[str, ...] = ()
    segment_path: tuple[Position, ...] = ()
    segment_headings: tuple[Heading, ...] = ()


DEFAULT_MAX_EXPANDED = 750_000


@dataclass(frozen=True)
class PoseReachability:
    start_pose: int
    rows: int
    cols: int
    parents: list[int]
    actions: list[int]
    costs: list[int]
    visit_stamp: list[int] | None = None
    generation: int = 0

    def can_reach(self, pos: Position, heading: Heading) -> bool:
        row, col = pos
        if row < 0 or col < 0 or row >= self.rows or col >= self.cols:
            return False
        pose = self._pose_index(pos, heading)
        if self.visit_stamp is not None:
            return self.visit_stamp[pose] == self.generation
        return self.costs[pose] >= 0

    def actions_to(self, pos: Position, heading: Heading) -> list[str]:
        _path, _headings, actions = self._reconstruct((pos, heading))
        return actions

    def cost_to(self, pos: Position, heading: Heading) -> int:
        pose = self._pose_index(pos, heading)
        if self.visit_stamp is not None and self.visit_stamp[pose] != self.generation:
            return -1
        return self.costs[pose]

    def path_to(self, pos: Position, heading: Heading) -> list[Position]:
        path, _headings, _actions = self._reconstruct((pos, heading))
        return path[1:]

    def headings_to(self, pos: Position, heading: Heading) -> list[Heading]:
        _path, headings, _actions = self._reconstruct((pos, heading))
        return headings[1:]

    def segment_to(self, pos: Position, heading: Heading) -> tuple[list[str], list[Position], list[Heading]]:
        path, headings, actions = self._reconstruct((pos, heading))
        return actions, path[1:], headings[1:]

    def _reconstruct(self, target: tuple[Position, Heading]) -> tuple[list[Position], list[Heading], list[str]]:
        poses: list[int] = []
        actions_reversed: list[str] = []
        current = self._pose_index(target[0], target[1])
        while current >= 0:
            if self.visit_stamp is not None and self.visit_stamp[current] != self.generation:
                break
            poses.append(current)
            action = self.actions[current]
            if action:
                actions_reversed.append(_pose_action_name(action))
            current = self.parents[current]
        poses.reverse()
        actions_reversed.reverse()
        return [self._pose_position(pose) for pose in poses], [HEADING_ORDER[pose & 3] for pose in poses], actions_reversed

    def _pose_index(self, pos: Position, heading: Heading) -> int:
        return (pos[0] * self.cols + pos[1]) * 4 + HEADING_INDEX[heading]

    def _pose_position(self, pose: int) -> Position:
        cell = pose >> 2
        return (cell // self.cols, cell % self.cols)


def _pose_action_name(action: int) -> str:
    if action == 1:
        return "turn_left"
    if action == 2:
        return "turn_right"
    return "forward"


class _PoseWorkspace:
    """Reusable storage for the tiny car-pose BFS.

    The search calls this thousands of times on level 103. Generation stamps let
    us avoid clearing 1536-pose arrays for every macro push expansion.
    """

    def __init__(self, rows: int, cols: int, static_walls: frozenset[Position] | None = None) -> None:
        self.rows = rows
        self.cols = cols
        self.cell_count = rows * cols
        self.pose_count = self.cell_count * 4
        self.has_static_walls = static_walls is not None
        static_wall_cells = {
            row * cols + col
            for row, col in (static_walls or frozenset())
            if 0 <= row < rows and 0 <= col < cols
        }
        self.blocked_stamp = [0] * self.cell_count
        self.visit_stamp = [0] * self.pose_count
        self.parents = [-1] * self.pose_count
        self.actions = [0] * self.pose_count
        self.costs = [0] * self.pose_count
        self.queue = [0] * self.pose_count
        self.left_pose = [0] * self.pose_count
        self.right_pose = [0] * self.pose_count
        self.forward_pose = [-1] * self.pose_count
        self.forward_cell = [-1] * self.pose_count
        self.target_stamp = [0] * self.pose_count
        self.block_generation = 0
        self.visit_generation = 0
        self.target_generation = 0
        for pose in range(self.pose_count):
            cell = pose >> 2
            heading_index = pose & 3
            row = cell // cols
            col = cell % cols
            self.left_pose[pose] = cell * 4 + LEFT_INDEX[heading_index]
            self.right_pose[pose] = cell * 4 + RIGHT_INDEX[heading_index]
            nr = row + HEADING_DR[heading_index]
            nc = col + HEADING_DC[heading_index]
            if 0 <= nr < rows and 0 <= nc < cols:
                next_cell = nr * cols + nc
                if next_cell not in static_wall_cells:
                    self.forward_cell[pose] = next_cell
                    self.forward_pose[pose] = next_cell * 4 + heading_index

    def begin(
        self,
        walls: frozenset[Position] | set[Position],
        blocked: set[Position],
        target_poses: tuple[int, ...] | None = None,
    ) -> tuple[int, int, int, int]:
        self.block_generation += 1
        block_generation = self.block_generation
        if not self.has_static_walls:
            for cell in _wall_cell_indices(self.rows, self.cols, walls):
                self.blocked_stamp[cell] = block_generation
        for row, col in blocked:
            if 0 <= row < self.rows and 0 <= col < self.cols:
                self.blocked_stamp[row * self.cols + col] = block_generation

        self.visit_generation += 1
        self.target_generation += 1
        target_generation = self.target_generation
        target_count = -1 if target_poses is None else 0
        if target_poses is not None:
            for pose in target_poses:
                if 0 <= pose < self.pose_count and self.target_stamp[pose] != target_generation:
                    self.target_stamp[pose] = target_generation
                    target_count += 1
        return block_generation, self.visit_generation, target_generation, target_count


def _wall_cell_indices(
    rows: int,
    cols: int,
    walls: frozenset[Position] | set[Position],
) -> tuple[int, ...]:
    frozen_walls = walls if isinstance(walls, frozenset) else frozenset(walls)
    key = (rows, cols, frozen_walls)
    cached = _wall_index_cache.get(key)
    if cached is not None:
        return cached

    indices = tuple(
        row * cols + col
        for row, col in frozen_walls
        if 0 <= row < rows and 0 <= col < cols
    )
    _wall_index_cache[key] = indices
    return indices


def _candidate_stance_poses(
    board: Board,
    movables: tuple[Position, ...],
    walls: frozenset[Position] | set[Position],
    blocked: set[Position],
) -> tuple[int, ...]:
    poses: list[int] = []
    rows = board.rows
    cols = board.cols
    wall_set = walls if isinstance(walls, frozenset) else frozenset(walls)
    append = poses.append
    for row, col in movables:
        for row_delta, col_delta, direction in DIRECTIONS:
            sr, sc = row - row_delta, col - col_delta
            if (
                0 <= sr < rows
                and 0 <= sc < cols
                and (sr, sc) not in wall_set
                and (sr, sc) not in blocked
            ):
                append((sr * cols + sc) * 4 + HEADING_INDEX[direction])
    return tuple(poses)


def _remove_from_tuple(items: tuple[Position, ...], removed: Position) -> tuple[Position, ...]:
    return tuple(item for item in items if item != removed)


def _replace_sorted_tuple(
    items: tuple[Position, ...],
    old: Position,
    new: Position,
) -> tuple[Position, ...]:
    return tuple(sorted(new if item == old else item for item in items))


def _pose_reachability(
    board: Board,
    start: Position,
    heading: Heading,
    walls: frozenset[Position] | set[Position],
    blocked: set[Position],
    workspace: _PoseWorkspace | None = None,
    target_poses: tuple[int, ...] | None = None,
    record_paths: bool = True,
) -> PoseReachability:
    cols = board.cols
    cell_count = board.rows * board.cols
    pose_count = cell_count * 4
    start_pose = (start[0] * cols + start[1]) * 4 + HEADING_INDEX[heading]

    if workspace is not None:
        block_generation, visit_generation, target_generation, remaining_targets = workspace.begin(
            walls,
            blocked,
            target_poses,
        )
        parents = workspace.parents
        actions = workspace.actions
        costs = workspace.costs
        visit_stamp = workspace.visit_stamp
        target_stamp = workspace.target_stamp
        blocked_stamp = workspace.blocked_stamp
        left_pose_by_pose = workspace.left_pose
        right_pose_by_pose = workspace.right_pose
        forward_pose_by_pose = workspace.forward_pose
        forward_cell_by_pose = workspace.forward_cell

        if record_paths:
            parents[start_pose] = -1
            actions[start_pose] = 0
        costs[start_pose] = 0
        visit_stamp[start_pose] = visit_generation
        if remaining_targets > 0 and target_stamp[start_pose] == target_generation:
            remaining_targets -= 1

        queue = workspace.queue
        head = 0
        tail = 1
        queue[0] = start_pose

        if not record_paths:
            while head < tail and remaining_targets != 0:
                pose = queue[head]
                head += 1
                next_cost = costs[pose] + 1

                left_pose = left_pose_by_pose[pose]
                if visit_stamp[left_pose] != visit_generation:
                    visit_stamp[left_pose] = visit_generation
                    costs[left_pose] = next_cost
                    queue[tail] = left_pose
                    tail += 1
                    if target_stamp[left_pose] == target_generation:
                        remaining_targets -= 1

                right_pose = right_pose_by_pose[pose]
                if visit_stamp[right_pose] != visit_generation:
                    visit_stamp[right_pose] = visit_generation
                    costs[right_pose] = next_cost
                    queue[tail] = right_pose
                    tail += 1
                    if target_stamp[right_pose] == target_generation:
                        remaining_targets -= 1

                forward_pose = forward_pose_by_pose[pose]
                if forward_pose >= 0:
                    next_cell = forward_cell_by_pose[pose]
                    if blocked_stamp[next_cell] != block_generation and visit_stamp[forward_pose] != visit_generation:
                        visit_stamp[forward_pose] = visit_generation
                        costs[forward_pose] = next_cost
                        queue[tail] = forward_pose
                        tail += 1
                        if target_stamp[forward_pose] == target_generation:
                            remaining_targets -= 1
            return PoseReachability(
                start_pose,
                board.rows,
                board.cols,
                parents,
                actions,
                costs,
                visit_stamp,
                visit_generation,
            )

        while head < tail and remaining_targets != 0:
            pose = queue[head]
            head += 1
            next_cost = costs[pose] + 1

            left_pose = left_pose_by_pose[pose]
            if visit_stamp[left_pose] != visit_generation:
                visit_stamp[left_pose] = visit_generation
                costs[left_pose] = next_cost
                parents[left_pose] = pose
                actions[left_pose] = 1
                queue[tail] = left_pose
                tail += 1
                if remaining_targets > 0 and target_stamp[left_pose] == target_generation:
                    remaining_targets -= 1

            right_pose = right_pose_by_pose[pose]
            if visit_stamp[right_pose] != visit_generation:
                visit_stamp[right_pose] = visit_generation
                costs[right_pose] = next_cost
                parents[right_pose] = pose
                actions[right_pose] = 2
                queue[tail] = right_pose
                tail += 1
                if remaining_targets > 0 and target_stamp[right_pose] == target_generation:
                    remaining_targets -= 1

            forward_pose = forward_pose_by_pose[pose]
            if forward_pose >= 0:
                next_cell = forward_cell_by_pose[pose]
                if blocked_stamp[next_cell] != block_generation and visit_stamp[forward_pose] != visit_generation:
                    visit_stamp[forward_pose] = visit_generation
                    costs[forward_pose] = next_cost
                    parents[forward_pose] = pose
                    actions[forward_pose] = 3
                    queue[tail] = forward_pose
                    tail += 1
                    if remaining_targets > 0 and target_stamp[forward_pose] == target_generation:
                        remaining_targets -= 1
        return PoseReachability(
            start_pose,
            board.rows,
            board.cols,
            parents,
            actions,
            costs,
            visit_stamp,
            visit_generation,
        )

    blocked_cells = bytearray(cell_count)
    for cell in _wall_cell_indices(board.rows, cols, walls):
        blocked_cells[cell] = 1
    for row, col in blocked:
        if 0 <= row < board.rows and 0 <= col < board.cols:
            blocked_cells[row * cols + col] = 1

    parents = [-1] * pose_count
    actions = [0] * pose_count
    costs = [-1] * pose_count
    costs[start_pose] = 0

    queue: deque[int] = deque([start_pose])
    queue_append = queue.append
    queue_popleft = queue.popleft
    while queue:
        pose = queue_popleft()
        cell = pose >> 2
        heading_index = pose & 3
        row = cell // cols
        col = cell % cols
        next_cost = costs[pose] + 1

        left_pose = cell * 4 + LEFT_INDEX[heading_index]
        if costs[left_pose] < 0:
            costs[left_pose] = next_cost
            parents[left_pose] = pose
            actions[left_pose] = 1
            queue_append(left_pose)

        right_pose = cell * 4 + RIGHT_INDEX[heading_index]
        if costs[right_pose] < 0:
            costs[right_pose] = next_cost
            parents[right_pose] = pose
            actions[right_pose] = 2
            queue_append(right_pose)

        nr = row + HEADING_DR[heading_index]
        nc = col + HEADING_DC[heading_index]
        if 0 <= nr < board.rows and 0 <= nc < cols:
            next_cell = nr * cols + nc
            forward_pose = next_cell * 4 + heading_index
            if not blocked_cells[next_cell] and costs[forward_pose] < 0:
                costs[forward_pose] = next_cost
                parents[forward_pose] = pose
                actions[forward_pose] = 3
                queue_append(forward_pose)
    return PoseReachability(start_pose, board.rows, board.cols, parents, actions, costs)


def solve_simple(board: Board, *, max_expanded: int = DEFAULT_MAX_EXPANDED) -> SolveResult:
    """BFS shortest path from player to endpoint for category 1."""
    start = board.player
    goal = board.endpoint
    if goal is None:
        return _failed(board, 0, 0, 0, "No endpoint E defined")

    queue: deque[Position] = deque([start])
    visited: dict[Position, Position | None] = {start: None}
    actions_map: dict[Position, str] = {start: "START"}
    expanded = 0
    generated = 1

    while queue and expanded < max_expanded:
        current = queue.popleft()
        expanded += 1
        if current == goal:
            steps, actions = _reconstruct_simple(visited, actions_map, goal, board)
            return SolveResult(
                level_id=board.level.level_id,
                level_name=board.level.name,
                solved=True,
                steps=steps,
                actions=actions,
                total_cost=len(steps) - 1,
                pushes=0,
                expanded=expanded,
                generated=generated,
                pruned_deadlocks=0,
                hp=board.level.hp_start,
                deadlock_cells=set(),
                message="Solved",
            )

        for row_delta, col_delta, direction in DIRECTIONS:
            nxt = add_pos(current, (row_delta, col_delta))
            if nxt in visited or board.is_wall(nxt):
                continue
            visited[nxt] = current
            actions_map[nxt] = direction.lower()
            queue.append(nxt)
            generated += 1

    return _failed(board, expanded, generated, 0, f"No solution within {max_expanded} expanded states")


def solve_board(
    board: Board,
    *,
    use_deadlock: bool | None = None,
    max_expanded: int = DEFAULT_MAX_EXPANDED,
) -> SolveResult:
    """A* numbered multi-box Sokoban solver for category 2.

    Supports boxes_vanish_on_goal: when a box is pushed exactly onto its target,
    it is removed from the active config (cell becomes free, no longer blocks).
    """
    if use_deadlock is None:
        use_deadlock = board.level.use_deadlock

    vanish = board.level.boxes_vanish_on_goal
    start_config: BoxConfig = tuple(sorted((bid, board.boxes[bid]) for bid in board.box_ids))
    start: State = (board.player, board.start_heading, start_config, board.level.hp_start)
    deadlock_cells = frozenset(compute_deadlock_cells(board))
    push_dist = _precompute_push_distances(board)

    frontier: list[tuple[int, int, int, State]] = []
    serial = count()
    heappush(frontier, (_heuristic_with_distances(board, start_config, push_dist), 0, next(serial), start))

    best_cost: dict[State, int] = {start: 0}
    parents: dict[State, Parent] = {
        start: Parent(previous=None, action="START", pushed_box_id=None)
    }

    expanded = 0
    generated = 1
    pruned_deadlocks = 0
    goal_state: State | None = None
    pose_workspace = _PoseWorkspace(board.rows, board.cols, board.walls)
    goal_positions = frozenset(board.goals.values())
    start_box_count = len(start_config)
    adaptive_limit = max_expanded

    while frontier and expanded < adaptive_limit:
        _, cost_so_far, _, state = heappop(frontier)
        if cost_so_far != best_cost.get(state):
            continue

        player, heading, boxes_config, hp = state
        expanded += 1

        # Adaptive expansion: if we hit the limit but have made progress (boxes delivered), expand the budget
        if expanded >= adaptive_limit and len(boxes_config) < start_box_count:
            adaptive_limit = int(adaptive_limit * 1.5)

        if _is_remaining_goal(board, boxes_config):
            goal_state = state
            break

        box_positions = {pos for _, pos in boxes_config}
        blocked = box_positions | set(board.bombs)
        # movables for stance targets: only remaining boxes (bombs handled in cat3)
        target_poses = _candidate_stance_poses(board, tuple(sorted(box_positions)), board.walls, blocked)
        reach = _pose_reachability(
            board,
            player,
            heading,
            board.walls,
            blocked,
            pose_workspace,
            target_poses,
            record_paths=False,
        )
        reach_stamp = reach.visit_stamp
        reach_generation = reach.generation
        reach_costs = reach.costs

        for box_index, (pushed_box_id, box_pos) in enumerate(boxes_config):
            for row_delta, col_delta, direction in DIRECTIONS:
                push_heading = direction
                stance = (box_pos[0] - row_delta, box_pos[1] - col_delta)
                stance_row, stance_col = stance
                if stance_row < 0 or stance_col < 0 or stance_row >= board.rows or stance_col >= board.cols:
                    continue
                stance_pose = (stance_row * board.cols + stance_col) * 4 + HEADING_INDEX[push_heading]
                if reach_stamp is None:
                    if reach_costs[stance_pose] < 0:
                        continue
                elif reach_stamp[stance_pose] != reach_generation:
                    continue
                next_box = (box_pos[0] + row_delta, box_pos[1] + col_delta)
                if board.is_wall(next_box) or next_box in box_positions or next_box in board.bombs:
                    continue

                is_delivery = next_box == board.goals[pushed_box_id]
                if not (vanish and is_delivery):
                    # Fast path: check precomputed deadlock cell set first
                    if use_deadlock and next_box in deadlock_cells:
                        pruned_deadlocks += 1
                        continue
                    next_box_positions = {p for bid, p in boxes_config if bid != pushed_box_id} | {next_box}
                    if use_deadlock and is_deadlocked_positions(
                        board,
                        pushed_box_id,
                        next_box,
                        next_box_positions,
                        goal_positions,
                    ):
                        pruned_deadlocks += 1
                        continue
                    # Frozen deadlock: if a group of boxes blocks each other
                    if use_deadlock and len(next_box_positions) >= 2 and is_frozen_deadlock_positions(
                        board, next_box_positions, goal_positions
                    ):
                        pruned_deadlocks += 1
                        continue

                # Build next config: remove on delivery (if vanish), else update position in place
                if vanish and is_delivery:
                    next_config: BoxConfig = tuple(item for item in boxes_config if item[0] != pushed_box_id)
                else:
                    temp = list(boxes_config)
                    temp[box_index] = (pushed_box_id, next_box)
                    next_config = tuple(temp)

                next_state: State = (box_pos, push_heading, next_config, hp)
                next_cost = cost_so_far + reach_costs[stance_pose] + 1
                if next_cost >= best_cost.get(next_state, 10**12):
                    continue

                best_cost[next_state] = next_cost
                parents[next_state] = Parent(
                    previous=state,
                    action=push_heading.upper(),
                    pushed_box_id=pushed_box_id,
                    stance=stance,
                )
                box_h = _heuristic_with_distances(board, next_config, push_dist)
                remaining_box_pos_for_lb = [p for _, p in next_config]
                priority = (
                    next_cost
                    + box_h
                    + (0 if box_h == 0 else _stance_lower_bound(
                        board,
                        box_pos,
                        remaining_box_pos_for_lb,
                        (),
                    ))
                )
                heappush(frontier, (priority, next_cost, next(serial), next_state))
                generated += 1

    if goal_state is None:
        return _failed(
            board,
            expanded,
            generated,
            pruned_deadlocks,
            f"No solution within {max_expanded} expanded states",
            deadlock_cells,
        )

    steps, actions = _reconstruct(board, goal_state, parents, best_cost)
    pushes = sum(1 for action in actions if action.isupper())
    return SolveResult(
        level_id=board.level.level_id,
        level_name=board.level.name,
        solved=True,
        steps=steps,
        actions=actions,
        total_cost=best_cost[goal_state],
        pushes=pushes,
        expanded=expanded,
        generated=generated,
        pruned_deadlocks=pruned_deadlocks,
        hp=goal_state[3],
        deadlock_cells=deadlock_cells,
        message="Solved",
    )


def solve_bombs(board: Board, *, max_expanded: int = DEFAULT_MAX_EXPANDED) -> SolveResult:
    """A* solver for smart-car pushable bombs.

    X is a pushable bomb. If the car pushes X into any wall cell, the bomb
    explodes at that impacted wall cell and removes non-boundary walls in the
    3x3 area around the impact. HP is kept only as display metadata.

    Supports boxes_vanish_on_goal (see solve_board).
    """
    vanish = board.level.boxes_vanish_on_goal
    start_config: BoxConfig = tuple(sorted((bid, board.boxes[bid]) for bid in board.box_ids))
    start_state: BombState = (
        board.player,
        board.start_heading,
        start_config,
        tuple(sorted(board.bombs)),
        tuple(sorted(board.walls)),
        board.level.hp_start,
    )
    deadlock_cells = frozenset(compute_deadlock_cells(board))

    frontier: list[tuple[int, int, int, BombState]] = []
    serial = count()
    heappush(frontier, (_heuristic_dynamic(board, start_config, tuple(sorted(board.bombs)), tuple(sorted(board.walls))), 0, next(serial), start_state))

    best_cost: dict[BombState, int] = {start_state: 0}
    parents: dict[BombState, BombParent] = {
        start_state: BombParent(previous=None, action="START", pushed_box_id=None)
    }

    expanded = 0
    generated = 1
    pruned_deadlocks = 0
    goal_state: BombState | None = None
    pose_workspace = _PoseWorkspace(board.rows, board.cols)
    goal_positions = frozenset(board.goals.values())
    start_box_count = len(start_config)
    adaptive_limit = max_expanded
    walls_frozen = frozenset(board.walls)

    while frontier and expanded < adaptive_limit:
        _, cost_so_far, _, state = heappop(frontier)
        if cost_so_far != best_cost.get(state):
            continue

        player, heading, boxes_config, bombs_tuple, walls_tuple, hp = state
        expanded += 1

        # Adaptive expansion
        if expanded >= adaptive_limit and len(boxes_config) < start_box_count:
            adaptive_limit = int(adaptive_limit * 1.5)

        if _is_remaining_goal(board, boxes_config):
            goal_state = state
            break

        walls = set(walls_tuple)
        bombs = set(bombs_tuple)
        box_positions = {pos for _, pos in boxes_config}
        blocked = box_positions | bombs
        movables = tuple(sorted(box_positions)) + bombs_tuple
        target_poses = _candidate_stance_poses(board, movables, walls, blocked)
        reach = _pose_reachability(
            board,
            player,
            heading,
            walls,
            blocked,
            pose_workspace,
            target_poses,
            record_paths=False,
        )
        reach_stamp = reach.visit_stamp
        reach_generation = reach.generation
        reach_costs = reach.costs

        for box_index, (pushed_box_id, box_pos) in enumerate(boxes_config):
            for row_delta, col_delta, direction in DIRECTIONS:
                push_heading = direction
                stance = (box_pos[0] - row_delta, box_pos[1] - col_delta)
                stance_row, stance_col = stance
                if stance_row < 0 or stance_col < 0 or stance_row >= board.rows or stance_col >= board.cols:
                    continue
                stance_pose = (stance_row * board.cols + stance_col) * 4 + HEADING_INDEX[push_heading]
                if reach_stamp is None:
                    if reach_costs[stance_pose] < 0:
                        continue
                elif reach_stamp[stance_pose] != reach_generation:
                    continue
                next_box = (box_pos[0] + row_delta, box_pos[1] + col_delta)
                if (
                    _is_wall_dynamic(board, next_box, walls)
                    or next_box in box_positions
                    or next_box in bombs
                ):
                    continue

                is_delivery = next_box == board.goals[pushed_box_id]
                if not (vanish and is_delivery):
                    next_box_positions = {p for bid, p in boxes_config if bid != pushed_box_id} | {next_box}
                    if _is_deadlocked_dynamic(board, pushed_box_id, next_box, next_box_positions, walls, goal_positions):
                        pruned_deadlocks += 1
                        continue

                if vanish and is_delivery:
                    next_config: BoxConfig = tuple(item for item in boxes_config if item[0] != pushed_box_id)
                else:
                    temp = list(boxes_config)
                    temp[box_index] = (pushed_box_id, next_box)
                    next_config = tuple(temp)

                next_state: BombState = (
                    box_pos,
                    push_heading,
                    next_config,
                    bombs_tuple,
                    walls_tuple,
                    hp,
                )
                next_cost = cost_so_far + reach_costs[stance_pose] + 1
                if next_cost >= best_cost.get(next_state, 10**12):
                    continue

                best_cost[next_state] = next_cost
                parents[next_state] = BombParent(
                    previous=state,
                    action=push_heading.upper(),
                    pushed_box_id=pushed_box_id,
                    stance=stance,
                )
                box_h = _heuristic_dynamic(board, next_config, bombs_tuple, walls_tuple)
                remaining_box_pos_for_lb = [p for _, p in next_config]
                priority = (
                    next_cost
                    + box_h
                    + (0 if box_h == 0 else _stance_lower_bound(
                        board,
                        box_pos,
                        remaining_box_pos_for_lb,
                        bombs_tuple,
                    ))
                )
                heappush(frontier, (priority, next_cost, next(serial), next_state))
                generated += 1

        for bomb_pos in bombs_tuple:
            for row_delta, col_delta, direction in DIRECTIONS:
                push_heading = direction
                stance = (bomb_pos[0] - row_delta, bomb_pos[1] - col_delta)
                stance_row, stance_col = stance
                if stance_row < 0 or stance_col < 0 or stance_row >= board.rows or stance_col >= board.cols:
                    continue
                stance_pose = (stance_row * board.cols + stance_col) * 4 + HEADING_INDEX[push_heading]
                if reach_stamp is None:
                    if reach_costs[stance_pose] < 0:
                        continue
                elif reach_stamp[stance_pose] != reach_generation:
                    continue
                bomb_target = (bomb_pos[0] + row_delta, bomb_pos[1] + col_delta)
                if bomb_target in box_positions or bomb_target in bombs:
                    continue

                explosions: frozenset[Position] = frozenset()
                if _is_wall_dynamic(board, bomb_target, walls):
                    destroyed = _explosion_cells(board, bomb_target, walls)
                    explosions = frozenset(destroyed | {bomb_target})
                    next_bombs_tuple = _remove_from_tuple(bombs_tuple, bomb_pos)
                    next_walls_tuple = tuple(cell for cell in walls_tuple if cell not in destroyed)
                    action = "X" + push_heading
                else:
                    next_bombs_tuple = _replace_sorted_tuple(bombs_tuple, bomb_pos, bomb_target)
                    next_walls_tuple = walls_tuple
                    action = "x" + push_heading

                next_state: BombState = (
                    bomb_pos,
                    push_heading,
                    boxes_config,  # boxes unchanged by bomb move/explosion
                    next_bombs_tuple,
                    next_walls_tuple,
                    hp,
                )
                next_cost = cost_so_far + reach_costs[stance_pose] + 1
                if next_cost >= best_cost.get(next_state, 10**12):
                    continue

                best_cost[next_state] = next_cost
                parents[next_state] = BombParent(
                    previous=state,
                    action=action,
                    pushed_box_id=None,
                    explosions=explosions,
                    stance=stance,
                )
                box_h = _heuristic_dynamic(board, boxes_config, next_bombs_tuple, next_walls_tuple)
                remaining_box_pos_for_lb = [p for _, p in boxes_config]
                priority = (
                    next_cost
                    + box_h
                    + (0 if box_h == 0 else _stance_lower_bound(
                        board,
                        bomb_pos,
                        remaining_box_pos_for_lb,
                        next_bombs_tuple,
                    ))
                )
                heappush(frontier, (priority, next_cost, next(serial), next_state))
                generated += 1

    if goal_state is None:
        return _failed(
            board,
            expanded,
            generated,
            pruned_deadlocks,
            f"No solution within {max_expanded} expanded states",
            deadlock_cells,
        )

    steps, actions = _reconstruct_bomb(board, goal_state, parents, best_cost)
    pushes = sum(1 for action in actions if action.isupper())
    return SolveResult(
        level_id=board.level.level_id,
        level_name=board.level.name,
        solved=True,
        steps=steps,
        actions=actions,
        total_cost=best_cost[goal_state],
        pushes=pushes,
        expanded=expanded,
        generated=generated,
        pruned_deadlocks=pruned_deadlocks,
        hp=goal_state[5],
        deadlock_cells=deadlock_cells,
        message="Solved",
    )


def solve(board: Board, *, max_expanded: int = DEFAULT_MAX_EXPANDED) -> SolveResult:
    """Dispatch to the appropriate solver based on board.level.category."""
    if board.level.requires_approach_recognition:
        return _solve_with_recognition(board, max_expanded=max_expanded)
    return _solve_core(board, max_expanded=max_expanded)


def _solve_core(board: Board, *, max_expanded: int = DEFAULT_MAX_EXPANDED) -> SolveResult:
    if board.level.category == 1:
        return solve_simple(board, max_expanded=max_expanded)
    if board.level.category == 2:
        return solve_board(board, max_expanded=max_expanded)
    if board.level.category == 3:
        return solve_bombs(board, max_expanded=max_expanded)
    raise ValueError(f"Unknown category {board.level.category}")


def _solve_with_recognition(board: Board, *, max_expanded: int = DEFAULT_MAX_EXPANDED) -> SolveResult:
    plan = plan_approach_recognition(
        board,
        include_bombs=False,
    )
    start_for_push = plan.path[-1]
    recognized_board = replace(board, player=start_for_push, start_heading=plan.headings[-1])
    push_result = _solve_core(recognized_board, max_expanded=max_expanded)

    recognition_steps, recognition_actions = _recognition_steps(board, plan.path, plan.headings, plan.actions)
    shifted_push_steps = [
        replace(step, cost=step.cost + plan.cost)
        for step in push_result.steps[1:]
    ]

    push_result.steps = recognition_steps + shifted_push_steps
    push_result.actions = recognition_actions + push_result.actions
    push_result.total_cost += plan.cost
    push_result.recognition_cost = plan.cost
    push_result.recognition_order = plan.order
    push_result.recognition_path = plan.path
    push_result.recognition_headings = plan.headings
    return push_result


def _recognition_steps(
    board: Board,
    path: list[Position],
    headings: list[str],
    actions: list[str],
) -> tuple[list[Step], list[str]]:
    steps: list[Step] = []
    for index, (pos, heading) in enumerate(zip(path, headings)):
        action = "SCAN_START" if index == 0 else actions[index - 1]
        steps.append(
            Step(
                player=pos,
                boxes=dict(board.boxes),
                action=action,
                pushed_box_id=None,
                hp=board.level.hp_start,
                cost=index,
                walls=board.walls,
                bombs=board.bombs,
                heading=heading,
            )
        )
    return steps, actions


def _direction_between(a: Position, b: Position) -> str:
    delta = (b[0] - a[0], b[1] - a[1])
    for row_delta, col_delta, direction in DIRECTIONS:
        if delta == (row_delta, col_delta):
            return direction.lower()
    raise ValueError(f"Positions {a} and {b} are not adjacent")


def _is_wall_dynamic(board: Board, pos: Position, walls: set[Position]) -> bool:
    row, col = pos
    return row < 0 or col < 0 or row >= board.rows or col >= board.cols or pos in walls


def _is_boundary_wall(board: Board, pos: Position) -> bool:
    row, col = pos
    return row in (0, board.rows - 1) or col in (0, board.cols - 1)


def _explosion_cells(board: Board, center: Position, walls: set[Position]) -> set[Position]:
    """Return non-boundary walls destroyed by a 3x3 explosion at center."""
    row, col = center
    destroyed: set[Position] = set()
    for r in range(row - 1, row + 2):
        for c in range(col - 1, col + 2):
            pos = (r, c)
            if pos in walls and not _is_boundary_wall(board, pos):
                destroyed.add(pos)
    return destroyed


def _is_deadlocked_dynamic(
    board: Board,
    box_id: int,
    box_pos: Position,
    box_positions: set[Position],
    walls: set[Position],
    goal_positions: frozenset[Position],
) -> bool:
    if box_pos == board.goals[box_id]:
        return False
    goal = board.goals[box_id]
    row, col = box_pos
    rows = board.rows
    cols = board.cols

    up = row < 1 or (row - 1, col) in walls
    down = row >= rows - 1 or (row + 1, col) in walls
    left = col < 1 or (row, col - 1) in walls
    right = col >= cols - 1 or (row, col + 1) in walls
    if (up or down) and (left or right):
        return True
    if (up or down) and goal[0] != row:
        return True
    if (left or right) and goal[1] != col:
        return True

    for top in (row - 1, row):
        for left_col in (col - 1, col):
            contains_goal = False
            blocked_block = True
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
                        blocked_block = False
                if contains_goal or not blocked_block:
                    break
            if (not contains_goal) and blocked_block:
                return True
    return False


def _is_corner_dynamic(board: Board, pos: Position, walls: set[Position]) -> bool:
    row, col = pos
    up = _is_wall_dynamic(board, (row - 1, col), walls)
    down = _is_wall_dynamic(board, (row + 1, col), walls)
    left = _is_wall_dynamic(board, (row, col - 1), walls)
    right = _is_wall_dynamic(board, (row, col + 1), walls)
    return (up or down) and (left or right)


def _is_remaining_goal(board: Board, boxes_config: BoxConfig) -> bool:
    """Goal test supporting both vanish and legacy (non-vanish) modes."""
    if board.level.boxes_vanish_on_goal:
        return len(boxes_config) == 0
    if len(boxes_config) != len(board.box_ids):
        return False
    goals = board.goals
    for box_id, pos in boxes_config:
        if pos != goals.get(box_id):
            return False
    return True


def _heuristic_dynamic(
    board: Board,
    boxes_config: BoxConfig,
    bombs_tuple: tuple[Position, ...],
    walls_tuple: tuple[Position, ...],
) -> int:
    """Admissible heuristic for dynamic bomb states.

    Uses the improved bomb heuristic that combines Manhattan with
    bomb-adjacency bonuses for walls blocking box paths.
    """
    return _bomb_heuristic(board, boxes_config, bombs_tuple, walls_tuple)


def clear_heuristic_cache() -> None:
    """Clear heuristic caches. Call between unrelated board solves."""
    _push_dist_cache.clear()
    _wall_tuple_cache.clear()


def _reconstruct_simple(
    visited: dict[Position, Position | None],
    actions_map: dict[Position, str],
    goal: Position,
    board: Board,
) -> tuple[list[Step], list[str]]:
    path: list[Position] = []
    current: Position | None = goal
    while current is not None:
        path.append(current)
        current = visited[current]
    path.reverse()

    steps: list[Step] = []
    actions: list[str] = []
    for index, pos in enumerate(path):
        action = actions_map[pos]
        if index > 0:
            actions.append(action)
        steps.append(
            Step(
                player=pos,
                boxes={},
                action=action,
                pushed_box_id=None,
                hp=board.level.hp_start,
                cost=index,
            )
        )
    return steps, actions


def _config_to_dict(config: BoxConfig) -> dict[int, Position]:
    """Convert remaining box config to the id->pos dict used by Step snapshots."""
    return {bid: pos for bid, pos in config}


def _reconstruct(
    board: Board,
    goal_state: State,
    parents: dict[State, Parent],
    best_cost: dict[State, int],
) -> tuple[list[Step], list[str]]:
    states: list[State] = []
    current: State | None = goal_state
    while current is not None:
        states.append(current)
        current = parents[current].previous
    states.reverse()

    steps: list[Step] = []
    actions: list[str] = []
    start_player, start_heading, start_config, start_hp = states[0]
    steps.append(
        Step(
            player=start_player,
            boxes=_config_to_dict(start_config),
            action="START",
            pushed_box_id=None,
            hp=start_hp,
            cost=best_cost[states[0]],
            heading=start_heading,
        )
    )
    for index in range(1, len(states)):
        previous = states[index - 1]
        state = states[index]
        parent = parents[state]
        _prev_player, _prev_heading, previous_config, _prev_hp = previous
        _player, _heading, boxes_config, hp = state
        previous_boxes = _config_to_dict(previous_config)
        current_boxes = _config_to_dict(boxes_config)
        base_cost = best_cost[previous]
        if parent.segment_actions:
            segment_actions = parent.segment_actions
            segment_path = parent.segment_path
            segment_headings = parent.segment_headings
        else:
            blocked = {pos for _, pos in previous_config} | set(board.bombs)
            reach = _pose_reachability(board, _prev_player, _prev_heading, board.walls, blocked)
            assert parent.stance is not None
            walk_actions, walk_path, walk_headings = reach.segment_to(parent.stance, _heading)
            segment_actions = tuple(walk_actions + [parent.action])
            segment_path = tuple(walk_path + [_player])
            segment_headings = tuple(walk_headings + [_heading])
        for segment_index, action in enumerate(segment_actions):
            is_final = segment_index == len(segment_actions) - 1
            actions.append(action)
            steps.append(
                Step(
                    player=segment_path[segment_index],
                    boxes=current_boxes if is_final else previous_boxes,
                    action=action,
                    pushed_box_id=parent.pushed_box_id if is_final else None,
                    hp=hp,
                    cost=base_cost + segment_index + 1,
                    heading=segment_headings[segment_index],
                )
            )
    return steps, actions


def _reconstruct_bomb(
    board: Board,
    goal_state: BombState,
    parents: dict[BombState, BombParent],
    best_cost: dict[BombState, int],
) -> tuple[list[Step], list[str]]:
    states: list[BombState] = []
    current: BombState | None = goal_state
    while current is not None:
        states.append(current)
        current = parents[current].previous
    states.reverse()

    steps: list[Step] = []
    actions: list[str] = []
    start_player, start_heading, start_config, start_bombs, start_walls, start_hp = states[0]
    steps.append(
        Step(
            player=start_player,
            boxes=_config_to_dict(start_config),
            action="START",
            pushed_box_id=None,
            hp=start_hp,
            cost=best_cost[states[0]],
            walls=frozenset(start_walls),
            bombs=frozenset(start_bombs),
            heading=start_heading,
        )
    )
    for index in range(1, len(states)):
        previous = states[index - 1]
        state = states[index]
        parent = parents[state]
        _prev_player, _prev_heading, previous_config, previous_bombs_tuple, previous_walls_tuple, _prev_hp = previous
        _player, _heading, boxes_config, bombs_tuple, walls_tuple, hp = state
        previous_boxes = _config_to_dict(previous_config)
        current_boxes = _config_to_dict(boxes_config)
        base_cost = best_cost[previous]
        if parent.segment_actions:
            segment_actions = parent.segment_actions
            segment_path = parent.segment_path
            segment_headings = parent.segment_headings
        else:
            blocked = {pos for _, pos in previous_config} | set(previous_bombs_tuple)
            reach = _pose_reachability(board, _prev_player, _prev_heading, set(previous_walls_tuple), blocked)
            assert parent.stance is not None
            walk_actions, walk_path, walk_headings = reach.segment_to(parent.stance, _heading)
            segment_actions = tuple(walk_actions + [parent.action])
            segment_path = tuple(walk_path + [_player])
            segment_headings = tuple(walk_headings + [_heading])
        for segment_index, action in enumerate(segment_actions):
            is_final = segment_index == len(segment_actions) - 1
            actions.append(action)
            steps.append(
                Step(
                    player=segment_path[segment_index],
                    boxes=current_boxes if is_final else previous_boxes,
                    action=action,
                    pushed_box_id=parent.pushed_box_id if is_final else None,
                    hp=hp,
                    cost=base_cost + segment_index + 1,
                    walls=frozenset(walls_tuple if is_final else previous_walls_tuple),
                    bombs=frozenset(bombs_tuple if is_final else previous_bombs_tuple),
                    explosions=parent.explosions if is_final else frozenset(),
                    heading=segment_headings[segment_index],
                )
            )
    return steps, actions


def _failed(
    board: Board,
    expanded: int,
    generated: int,
    pruned_deadlocks: int,
    message: str,
    deadlock_cells: set[Position] | None = None,
) -> SolveResult:
    return SolveResult(
        level_id=board.level.level_id,
        level_name=board.level.name,
        solved=False,
        steps=[],
        actions=[],
        total_cost=0,
        pushes=0,
        expanded=expanded,
        generated=generated,
        pruned_deadlocks=pruned_deadlocks,
        hp=0,
        deadlock_cells=deadlock_cells or set(),
        message=message,
    )
