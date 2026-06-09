from __future__ import annotations

import unittest
from pathlib import Path

from planner.editor_model import blank_rows, level_from_rows, set_cell, set_grid_size
from planner.grid import Level, parse_level
from planner.levels import COLS, LEVELS, ROWS, START
from planner.solver import solve, solve_board


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"


class LevelTests(unittest.TestCase):
    def test_category2_and_3_boxes_match_goals(self) -> None:
        for level in LEVELS.values():
            if level.category == 1:
                continue
            board = parse_level(level)
            self.assertEqual(set(board.boxes), set(board.goals))
            self.assertGreaterEqual(len(board.boxes), 1)

    def test_all_levels_have_correct_dimensions(self) -> None:
        set_grid_size(ROWS, COLS)
        for level in LEVELS.values():
            board = parse_level(level)
            self.assertEqual(board.rows, ROWS)
            self.assertEqual(board.cols, COLS)
            self.assertEqual(board.player, START)

    def test_level_1_direct_numbered_multi_box(self) -> None:
        level = LEVELS[1]
        board = parse_level(level)
        self.assertFalse(level.use_vision)
        self.assertEqual(len(board.boxes), 3)
        self.assertEqual(set(board.boxes), set(board.goals))
        result = solve(board)
        self.assertTrue(result.solved, result.message)
        # boxes_vanish_on_goal removes delivered boxes; final snapshot is empty
        self.assertEqual(len(result.steps[-1].boxes), 0)

    def test_level_2_vision_roundtrip_and_deadlock_pruning(self) -> None:
        from planner.vision import generate_level_image, recognize_level_image

        level = LEVELS[2]
        generated = OUTPUTS / "test_level_2_generated.png"
        recognized = OUTPUTS / "test_level_2_recognized.png"
        generate_level_image(level, generated)
        recognized_level = recognize_level_image(
            generated,
            level_id=level.level_id,
            name=level.name,
            category=level.category,
            hp_start=level.hp_start,
            use_deadlock=level.use_deadlock,
            requires_approach_recognition=getattr(level, 'requires_approach_recognition', False),
            boxes_vanish_on_goal=getattr(level, 'boxes_vanish_on_goal', False),
            recognized_output_path=recognized,
        )
        self.assertEqual(recognized_level.rows, level.rows)

        board = parse_level(recognized_level)
        pruned = solve_board(board, use_deadlock=True)
        baseline = solve_board(board, use_deadlock=False)
        self.assertTrue(pruned.solved, pruned.message)
        self.assertGreater(pruned.pruned_deadlocks, 0)
        self.assertLessEqual(pruned.expanded, baseline.expanded)

    def test_level_3_vision_bomb_explosion_and_number_mapping(self) -> None:
        from planner.vision import generate_level_image, recognize_level_image

        level = LEVELS[3]
        generated = OUTPUTS / "test_level_3_generated.png"
        recognized = OUTPUTS / "test_level_3_recognized.png"
        generate_level_image(level, generated)
        recognized_level = recognize_level_image(
            generated,
            level_id=level.level_id,
            name=level.name,
            category=level.category,
            hp_start=level.hp_start,
            use_deadlock=level.use_deadlock,
            requires_approach_recognition=getattr(level, 'requires_approach_recognition', False),
            boxes_vanish_on_goal=getattr(level, 'boxes_vanish_on_goal', False),
            recognized_output_path=recognized,
        )
        self.assertEqual(recognized_level.rows, level.rows)

        board = parse_level(recognized_level)
        result = solve(board)
        self.assertTrue(result.solved, result.message)
        self.assertEqual(result.hp, level.hp_start)
        self.assertTrue(any(step.explosions for step in result.steps))
        self.assertLess(len(result.steps[-1].walls or board.walls), len(board.walls))
        self.assertEqual(len(result.steps[-1].boxes), 0)

    def test_deprecated_legacy_tokens_are_rejected(self) -> None:
        legacy_d_rows = (
            ("#", "#", "#", "#"),
            ("#", "P", "D", "#"),
            ("#", ".", "E", "#"),
            ("#", "#", "#", "#"),
        )
        legacy_star_rows = (
            ("#", "#", "#", "#"),
            ("#", "P", "*", "#"),
            ("#", ".", "E", "#"),
            ("#", "#", "#", "#"),
        )
        with self.assertRaises(ValueError):
            parse_level(Level(99, "legacy D", legacy_d_rows))
        with self.assertRaises(ValueError):
            parse_level(Level(100, "legacy star", legacy_star_rows))

    def test_x_bomb_destroys_normal_non_boundary_walls(self) -> None:
        level = LEVELS[3]
        board = parse_level(level)
        result = solve(board)
        self.assertTrue(result.solved, result.message)
        exploded_cells = set().union(*(step.explosions for step in result.steps))
        self.assertTrue(exploded_cells)
        self.assertTrue(any(cell in board.walls for cell in exploded_cells))
        final_walls = result.steps[-1].walls or board.walls
        self.assertLess(len(final_walls), len(board.walls))
        for row, col in board.walls - final_walls:
            self.assertNotIn(row, (0, board.rows - 1))
            self.assertNotIn(col, (0, board.cols - 1))

    def test_editor_model_category_2_has_boxes(self) -> None:
        set_grid_size(ROWS, COLS)
        rows = blank_rows()
        rows = set_cell(rows, 3, 7, "B1")
        rows = set_cell(rows, 3, 10, "T1")
        level = level_from_rows(rows, category=2)
        board = parse_level(level)
        self.assertEqual(board.rows, ROWS)
        self.assertEqual(board.cols, COLS)
        self.assertTrue(level.use_vision)

    def test_editor_model_keeps_single_player(self) -> None:
        set_grid_size(ROWS, COLS)
        rows = blank_rows()
        rows = set_cell(rows, 2, 2, "P")
        positions = [
            (row_index, col_index)
            for row_index, row in enumerate(rows)
            for col_index, token in enumerate(row)
            if token == "P"
        ]
        self.assertEqual(positions, [(2, 2)])


if __name__ == "__main__":
    unittest.main()
