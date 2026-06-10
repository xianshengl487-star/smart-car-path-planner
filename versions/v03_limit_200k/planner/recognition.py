from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .grid import Board, HEADING_DELTAS, LEFT_TURN, RIGHT_TURN, Heading, Position, add_pos


HEADING_ORDER: tuple[Heading, ...] = ("L", "U", "D", "R")
HEADING_INDEX: dict[Heading, int] = {heading: index for index, heading in enumerate(HEADING_ORDER)}
ACTION_NAMES: tuple[str, ...] = ("", "turn_left", "turn_right", "forward")


@dataclass(frozen=True)
class RecognitionPlan:
    path: list[Position]
    headings: list[Heading]
    actions: list[str]
    order: list[str]

    @property
    def cost(self) -> int:
        return len(self.actions)


def plan_approach_recognition(board: Board, *, include_bombs: bool = False) -> RecognitionPlan:
    """Plan a pre-solve route that approaches all objects to be recognized.

    Boxes and bombs are treated as occupied obstacles. Targets are floor marks,
    so the car can drive over them. Recognition is directional: an object is
    recognized only when it is exactly one cell in front of the car.
    """
    objects = _recognition_objects(board, include_bombs=include_bombs)
    if not objects:
        return RecognitionPlan(path=[board.player], headings=[board.start_heading], actions=[], order=[])

    occupied = set(board.boxes.values()) | set(board.bombs)
    pose_count = board.rows * board.cols * 4
    front_masks, left_pose, right_pose, forward_pose = _recognition_pose_tables(board, occupied, objects)
    full_mask = (1 << len(objects)) - 1
    start_pose = _pose_index(board, board.player, board.start_heading)
    start_mask = front_masks[start_pose]
    start_state = start_mask * pose_count + start_pose
    state_count = pose_count * (full_mask + 1)
    parents = [-2] * state_count
    actions = [0] * state_count
    parents[start_state] = -1
    queue: deque[int] = deque([start_state])

    goal_state = -1
    while queue:
        state = queue.popleft()
        mask, pose = divmod(state, pose_count)
        if mask == full_mask:
            goal_state = state
            break

        for action_id, next_pose in ((1, left_pose[pose]), (2, right_pose[pose]), (3, forward_pose[pose])):
            if next_pose < 0:
                continue
            next_mask = mask | front_masks[next_pose]
            next_state = next_mask * pose_count + next_pose
            if parents[next_state] != -2:
                continue
            parents[next_state] = state
            actions[next_state] = action_id
            queue.append(next_state)

    if goal_state < 0:
        raise ValueError("Cannot find a directional route that recognizes every object")

    path, headings, action_names = _reconstruct_int_pose_path(board, goal_state, pose_count, parents, actions)
    order = _recognition_order(path, headings, objects)
    return RecognitionPlan(path=path, headings=headings, actions=action_names, order=order)


def _recognition_objects(board: Board, *, include_bombs: bool) -> list[tuple[str, Position]]:
    objects: list[tuple[str, Position]] = []
    for box_id in board.box_ids:
        objects.append((f"B{box_id}", board.boxes[box_id]))
    for goal_id in sorted(board.goals):
        objects.append((f"T{goal_id}", board.goals[goal_id]))
    if include_bombs:
        for index, pos in enumerate(sorted(board.bombs), start=1):
            objects.append((f"X{index}", pos))
    return objects


def _recognition_pose_tables(
    board: Board,
    occupied: set[Position],
    objects: list[tuple[str, Position]],
) -> tuple[list[int], list[int], list[int], list[int]]:
    pose_count = board.rows * board.cols * 4
    front_masks = [0] * pose_count
    left_pose = [0] * pose_count
    right_pose = [0] * pose_count
    forward_pose = [-1] * pose_count
    object_masks = {pos: 1 << index for index, (_label, pos) in enumerate(objects)}

    for row in range(board.rows):
        for col in range(board.cols):
            cell = row * board.cols + col
            for heading in HEADING_ORDER:
                pose = cell * 4 + HEADING_INDEX[heading]
                left_pose[pose] = cell * 4 + HEADING_INDEX[LEFT_TURN[heading]]
                right_pose[pose] = cell * 4 + HEADING_INDEX[RIGHT_TURN[heading]]

                dr, dc = HEADING_DELTAS[heading]
                front = (row + dr, col + dc)
                front_masks[pose] = object_masks.get(front, 0)
                if not board.is_wall(front) and front not in occupied:
                    forward_pose[pose] = ((row + dr) * board.cols + (col + dc)) * 4 + HEADING_INDEX[heading]
    return front_masks, left_pose, right_pose, forward_pose


def _pose_index(board: Board, pos: Position, heading: Heading) -> int:
    return (pos[0] * board.cols + pos[1]) * 4 + HEADING_INDEX[heading]


def _pose_position(board: Board, pose: int) -> Position:
    cell = pose >> 2
    return cell // board.cols, cell % board.cols


def _reconstruct_int_pose_path(
    board: Board,
    goal_state: int,
    pose_count: int,
    parents: list[int],
    actions: list[int],
) -> tuple[list[Position], list[Heading], list[str]]:
    poses_reversed: list[int] = []
    actions_reversed: list[str] = []
    current = goal_state
    while current >= 0:
        _mask, pose = divmod(current, pose_count)
        poses_reversed.append(pose)
        action_id = actions[current]
        if action_id:
            actions_reversed.append(ACTION_NAMES[action_id])
        current = parents[current]

    poses_reversed.reverse()
    actions_reversed.reverse()
    return (
        [_pose_position(board, pose) for pose in poses_reversed],
        [HEADING_ORDER[pose & 3] for pose in poses_reversed],
        actions_reversed,
    )


def _recognition_order(
    path: list[Position],
    headings: list[Heading],
    objects: list[tuple[str, Position]],
) -> list[str]:
    seen: set[str] = set()
    order: list[str] = []
    for pos, heading in zip(path, headings):
        front = add_pos(pos, HEADING_DELTAS[heading])
        for label, object_pos in objects:
            if label not in seen and front == object_pos:
                seen.add(label)
                order.append(label)
    return order
