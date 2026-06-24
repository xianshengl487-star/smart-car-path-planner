from __future__ import annotations

import unittest
from pathlib import Path

from planner.grid import load_text_map, parse_level
from planner.region_planner import build_region_plan


class RegionPlannerTests(unittest.TestCase):
    def test_region_plan_covers_all_free_cells(self) -> None:
        board = parse_level(load_text_map(Path("examples/16x12_hard/hard_16x12_high_expand_083.txt")))
        plan = build_region_plan(board)
        free_cells = {
            (row, col)
            for row in range(board.rows)
            for col in range(board.cols)
            if (row, col) not in board.walls
        }

        self.assertEqual(set(plan.cell_to_region), free_cells)
        self.assertGreater(len(plan.regions), 1)

    def test_region_plan_has_one_motion_per_numbered_box(self) -> None:
        board = parse_level(load_text_map(Path("examples/16x12_hard/hard_16x12_corridor_113.txt")))
        plan = build_region_plan(board)

        self.assertEqual(
            sorted(motion.box_id for motion in plan.target_motions),
            sorted(board.boxes),
        )
        for motion in plan.target_motions:
            self.assertEqual(motion.box, board.boxes[motion.box_id])
            self.assertEqual(motion.goal, board.goals[motion.box_id])
            self.assertGreaterEqual(len(motion.region_path), 1)


if __name__ == "__main__":
    unittest.main()
