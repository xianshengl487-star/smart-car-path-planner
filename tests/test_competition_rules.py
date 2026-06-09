from __future__ import annotations

import unittest

from planner.grid import Level, parse_level
from planner.levels import LEVELS, START
from planner.solver import _explosion_cells, solve


class CompetitionRuleTests(unittest.TestCase):
    def test_builtin_levels_are_16x12_with_boundary_walls_and_fixed_start(self) -> None:
        for level in LEVELS.values():
            board = parse_level(level)
            self.assertEqual((board.rows, board.cols), (12, 16))
            self.assertEqual(board.player, START)
            for row in range(board.rows):
                self.assertIn((row, 0), board.walls)
                self.assertIn((row, board.cols - 1), board.walls)
            for col in range(board.cols):
                self.assertIn((0, col), board.walls)
                self.assertIn((board.rows - 1, col), board.walls)

    def test_level_2_and_3_require_generated_vision_recognition(self) -> None:
        self.assertFalse(LEVELS[1].use_vision)
        self.assertTrue(LEVELS[2].use_vision)
        self.assertTrue(LEVELS[3].use_vision)

    def test_all_puzzle_levels_have_numbered_one_to_one_targets(self) -> None:
        for level_id in (1, 2, 3):
            board = parse_level(LEVELS[level_id])
            self.assertEqual(set(board.boxes), set(board.goals))
            self.assertNotIn("D", {token for row in LEVELS[level_id].rows for token in row})
            self.assertNotIn("*", {token for row in LEVELS[level_id].rows for token in row})

    def test_bomb_explosion_destroys_only_non_boundary_walls_in_3x3(self) -> None:
        rows = (
            ("#", "#", "#", "#", "#"),
            ("#", "P", "#", "#", "#"),
            ("#", "#", "#", "#", "#"),
            ("#", ".", "B1", "T1", "#"),
            ("#", "#", "#", "#", "#"),
        )
        board = parse_level(Level(301, "blast exactness", rows, category=3))
        destroyed = _explosion_cells(board, (1, 1), set(board.walls))
        self.assertEqual(destroyed, {(1, 2), (2, 1), (2, 2)})

    def test_bomb_can_be_pushed_into_empty_cell(self) -> None:
        rows = (
            ("#", "#", "#", "#", "#", "#"),
            ("#", ".", ".", ".", ".", "#"),
            ("#", "P", "X", "B1", "T1", "#"),
            ("#", ".", ".", ".", ".", "#"),
            ("#", "#", "#", "#", "#", "#"),
        )
        board = parse_level(Level(302, "bomb blocks push stance", rows, category=3))
        result = solve(board)
        self.assertTrue(result.solved, result.message)
        self.assertTrue(any(action.startswith("x") for action in result.actions))
        self.assertFalse(any(step.explosions for step in result.steps))

    def test_level_3_solution_explodes_bomb_and_preserves_hp(self) -> None:
        board = parse_level(LEVELS[3])
        result = solve(board)
        self.assertTrue(result.solved, result.message)
        self.assertTrue(any(action.startswith("X") for action in result.actions))
        self.assertTrue(any(step.explosions for step in result.steps))
        self.assertTrue(all(step.hp == LEVELS[3].hp_start for step in result.steps))


if __name__ == "__main__":
    unittest.main()
