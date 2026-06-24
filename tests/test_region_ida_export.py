from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from export_region_ida import build_stm32_block_region_plan, export_region_ida_header
from planner.grid import load_text_map, parse_level


class RegionIdaExportTests(unittest.TestCase):
    def test_stm32_block_regions_stay_under_limit(self) -> None:
        board = parse_level(load_text_map("examples/16x12_hard/stm32_16x12_3box_region_demo.txt"))
        plan = build_stm32_block_region_plan(board)

        self.assertLessEqual(len(plan.regions), 20)
        self.assertEqual(len(plan.target_motions), 3)

    def test_region_ida_header_exports_core_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            header = Path(tmp) / "region_ida_example.h"
            export_region_ida_header(
                "examples/16x12_hard/stm32_16x12_3box_region_demo.txt",
                header,
            )
            text = header.read_text(encoding="utf-8")

        self.assertIn("region_ida_example_start", text)
        self.assertIn("region_ida_example_goals", text)
        self.assertIn("region_ida_example_graph", text)
        self.assertIn(".deadlock", text)
        self.assertIn(".region_dist", text)


if __name__ == "__main__":
    unittest.main()
