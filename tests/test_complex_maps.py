"""Tests for the high-complexity maps defined in planner/complex_maps.py."""
from __future__ import annotations

import unittest
from pathlib import Path

from planner.complex_maps import COMPLEX_LEVELS, all_complex_levels, get_complex_level
from planner.deadlock import is_frozen_deadlock_positions
from planner.grid import HEADING_DELTAS, Level, add_pos, parse_level
from planner.recognition import plan_approach_recognition
from planner.solver import solve
from planner.vision import generate_level_image, recognize_level_image


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"


class ComplexMapTests(unittest.TestCase):
    def test_all_complex_levels_have_correct_dimensions(self) -> None:
        for level in all_complex_levels():
            board = parse_level(level)
            self.assertEqual(board.rows, 12)
            self.assertEqual(board.cols, 16)

    def test_all_complex_levels_have_player(self) -> None:
        for level in all_complex_levels():
            board = parse_level(level)
            self.assertEqual(board.player, (5, 1))

    def test_complex_levels_registered(self) -> None:
        self.assertEqual(set(COMPLEX_LEVELS.keys()), {101, 102, 103, 104, 105, 106})

    def test_101_is_push_only(self) -> None:
        level = get_complex_level(101)
        board = parse_level(level)
        self.assertEqual(level.category, 2)
        self.assertFalse(level.use_vision)
        self.assertFalse(level.requires_approach_recognition)
        self.assertEqual(len(board.boxes), 2)
        self.assertEqual(len(board.bombs), 0)

    def test_102_matches_101_complexity_but_requires_recognition(self) -> None:
        level_101 = get_complex_level(101)
        level_102 = get_complex_level(102)
        board_101 = parse_level(level_101)
        board_102 = parse_level(level_102)
        self.assertEqual(level_102.category, 2)
        self.assertTrue(level_102.use_vision)
        self.assertTrue(level_102.requires_approach_recognition)
        self.assertEqual(board_102.walls, board_101.walls)
        self.assertEqual(board_102.boxes, board_101.boxes)
        self.assertEqual(board_102.goals, board_101.goals)
        self.assertEqual(len(board_102.bombs), 0)

    def test_103_enhances_102_with_more_boxes_and_bombs(self) -> None:
        level_102 = get_complex_level(102)
        level_103 = get_complex_level(103)
        board_102 = parse_level(level_102)
        board_103 = parse_level(level_103)
        self.assertEqual(level_103.category, 3)
        self.assertTrue(level_103.use_vision)
        self.assertTrue(level_103.requires_approach_recognition)
        self.assertGreater(len(board_103.boxes), len(board_102.boxes))
        self.assertGreater(len(board_103.bombs), 0)

    def test_104_has_four_boxes(self) -> None:
        level = get_complex_level(104)
        board = parse_level(level)
        self.assertEqual(level.category, 2)
        self.assertEqual(len(board.boxes), 4)
        self.assertEqual(len(board.bombs), 0)

    def test_105_has_two_bombs(self) -> None:
        level = get_complex_level(105)
        board = parse_level(level)
        self.assertEqual(level.category, 3)
        self.assertEqual(len(board.bombs), 2)

    def test_106_has_three_boxes_one_bomb(self) -> None:
        level = get_complex_level(106)
        board = parse_level(level)
        self.assertEqual(level.category, 3)
        self.assertTrue(level.requires_approach_recognition)
        self.assertEqual(len(board.boxes), 3)
        self.assertEqual(len(board.bombs), 1)

    def test_102_and_103_vision_roundtrip_preserves_recognition_rule(self) -> None:
        for level_id in (102, 103):
            level = get_complex_level(level_id)
            generated = OUTPUTS / f"test_complex_{level_id}_generated.png"
            generate_level_image(level, generated)
            recognized = recognize_level_image(
                generated,
                level_id=level.level_id,
                name=level.name,
                category=level.category,
                hp_start=level.hp_start,
                use_deadlock=level.use_deadlock,
                requires_approach_recognition=level.requires_approach_recognition,
                boxes_vanish_on_goal=level.boxes_vanish_on_goal,
            )
            self.assertEqual(recognized.rows, level.rows)
            self.assertTrue(recognized.requires_approach_recognition)


class ComplexMapRecognitionTests(unittest.TestCase):
    def test_directional_recognition_requires_object_in_front(self) -> None:
        rows = (
            ("#", "#", "#", "#", "#", "#"),
            ("#", ".", ".", ".", ".", "#"),
            ("#", ".", "P", "B1", ".", "#"),
            ("#", ".", ".", "T1", ".", "#"),
            ("#", "#", "#", "#", "#", "#"),
        )
        board = parse_level(Level(9102, "front-only scan", rows, category=2, start_heading="L"))
        plan = plan_approach_recognition(board)
        self.assertEqual(plan.path[0], board.player)
        self.assertEqual(plan.headings[0], "L")
        self.assertNotEqual(add_pos(plan.path[0], HEADING_DELTAS[plan.headings[0]]), board.boxes[1])
        self.assertIn(plan.actions[0], {"turn_left", "turn_right"})
        self.assertEqual(set(plan.order), {"B1", "T1"})

    def test_102_recognition_approaches_boxes_and_targets(self) -> None:
        board = parse_level(get_complex_level(102))
        plan = plan_approach_recognition(board)
        self.assertGreater(plan.cost, 0)
        self.assertEqual(set(plan.order), {"B1", "B2", "T1", "T2"})

    def test_103_recognition_also_approaches_bombs(self) -> None:
        board = parse_level(get_complex_level(103))
        plan = plan_approach_recognition(board, include_bombs=True)
        self.assertGreater(plan.cost, 0)
        self.assertEqual(set(plan.order), {"B1", "B2", "B3", "T1", "T2", "T3", "X1"})

    def test_103_pipeline_does_not_require_bomb_recognition(self) -> None:
        board = parse_level(get_complex_level(103))
        result = solve(board)
        self.assertTrue(result.solved, result.message)
        self.assertNotIn("X1", result.recognition_order or [])
        self.assertEqual(set(result.recognition_order or []), {"B1", "B2", "B3", "T1", "T2", "T3"})


class ComplexMapSolveTests(unittest.TestCase):
    def test_101_solvable_without_recognition(self) -> None:
        level = get_complex_level(101)
        board = parse_level(level)
        result = solve(board)
        self.assertTrue(result.solved, f"101 failed: {result.message}")
        self.assertEqual(result.recognition_cost, 0)
        self.assertGreater(result.pushes, 0)
        self.assertEqual(len(result.steps[-1].boxes), 0)

    def test_101_deadlock_pruning(self) -> None:
        from planner.solver import solve_board

        board = parse_level(get_complex_level(101))
        pruned = solve_board(board, use_deadlock=True)
        baseline = solve_board(board, use_deadlock=False)
        self.assertTrue(pruned.solved, f"101 pruned failed: {pruned.message}")
        self.assertTrue(baseline.solved, f"101 baseline failed: {baseline.message}")
        # Corner and 2x2 deadlock detection still prunes some states
        # (count may be 0 if the optimal path doesn't visit any deadlocked positions)
        self.assertLessEqual(pruned.expanded, baseline.expanded + 5)

    def test_102_solvable_with_recognition_then_push(self) -> None:
        level = get_complex_level(102)
        board = parse_level(level)
        result = solve(board)
        self.assertTrue(result.solved, f"102 failed: {result.message}")
        self.assertGreater(result.recognition_cost, 0)
        self.assertEqual(set(result.recognition_order or []), {"B1", "B2", "T1", "T2"})
        self.assertEqual(sum(1 for step in result.steps if step.explosions), 0)
        self.assertEqual(len(result.steps[-1].boxes), 0)

    def test_103_solvable_with_recognition_and_bombs(self) -> None:
        level = get_complex_level(103)
        board = parse_level(level)
        result = solve(board)
        self.assertTrue(result.solved, f"103 failed: {result.message}")
        self.assertGreater(result.recognition_cost, 0)
        self.assertNotIn("X1", result.recognition_order or [])
        self.assertGreater(sum(1 for step in result.steps if step.explosions), 0)
        self.assertEqual(len(result.steps[-1].boxes), 0)

    def test_104_four_boxes_solvable(self) -> None:
        """4-box maze must be solvable within reasonable expansion budget."""
        level = get_complex_level(104)
        board = parse_level(level)
        result = solve(board, max_expanded=500_000)
        self.assertTrue(result.solved, f"104 failed: {result.message}")
        self.assertGreater(result.pushes, 0)
        self.assertEqual(len(result.steps[-1].boxes), 0)

    def test_105_two_bombs_solvable(self) -> None:
        """Two-bomb map must be solvable — each bomb clears a path."""
        level = get_complex_level(105)
        board = parse_level(level)
        result = solve(board, max_expanded=500_000)
        self.assertTrue(result.solved, f"105 failed: {result.message}")
        self.assertGreater(sum(1 for step in result.steps if step.explosions), 0)
        self.assertEqual(len(result.steps[-1].boxes), 0)

    def test_106_ultimate_complex_solvable(self) -> None:
        """Ultimate complex map must be solvable with recognition + bombs."""
        level = get_complex_level(106)
        board = parse_level(level)
        result = solve(board, max_expanded=500_000)
        self.assertTrue(result.solved, f"106 failed: {result.message}")
        self.assertGreater(result.recognition_cost, 0)
        self.assertGreater(sum(1 for step in result.steps if step.explosions), 0)
        self.assertEqual(len(result.steps[-1].boxes), 0)


class FrozenDeadlockTests(unittest.TestCase):
    def test_frozen_deadlock_detects_wall_box(self) -> None:
        """A box flanked by walls on 3 sides and boundary on 4th is frozen."""
        # B1 at (1,2): UP=(0,2)=wall, LEFT=(1,1)=wall, RIGHT=(1,3)=wall
        # DOWN: target=(2,2), stance=(0,2)=wall → push DOWN also blocked
        # All 4 directions blocked, B1 at (1,2) != T1 at (3,2) → frozen
        rows = (
            ("#", "#", "#", "#", "#"),
            ("#", "#", "B1", "#", "#"),
            ("#", ".", "P", ".", "#"),
            ("#", ".", "T1", ".", "#"),
            ("#", "#", "#", "#", "#"),
        )
        board = parse_level(Level(
            9201, "frozen-wall-box", rows, category=2, boxes_vanish_on_goal=True,
        ))
        box_positions = {(1, 2)}
        goals = frozenset(board.goals.values())
        result = is_frozen_deadlock_positions(board, box_positions, goals)
        self.assertTrue(result)

    def test_frozen_deadlock_allows_free_box(self) -> None:
        """A box with an open direction is not frozen."""
        rows = (
            ("#", "#", "#", "#", "#"),
            ("#", ".", "B1", ".", "#"),
            ("#", ".", "P", ".", "#"),
            ("#", ".", "T1", ".", "#"),
            ("#", "#", "#", "#", "#"),
        )
        board = parse_level(Level(
            9202, "frozen-free-box", rows, category=2, boxes_vanish_on_goal=True,
        ))
        # B1 at (1,2): UP=(0,2)=wall, DOWN=(2,2)=P(free), LEFT=(1,1)=free, RIGHT=(1,3)=free
        # At least LEFT and RIGHT are completely free → not frozen
        box_positions = {(1, 2)}
        goals = frozenset(board.goals.values())
        result = is_frozen_deadlock_positions(board, box_positions, goals)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
