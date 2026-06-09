from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from export_stm32 import export_stm32_plans


ROOT = Path(__file__).resolve().parents[1]


class STM32ExportTests(unittest.TestCase):
    def test_exported_plans_fit_stm32f304_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            header, report = export_stm32_plans(
                header_path=Path(tmp) / "stm32_plans.h",
                report_path=Path(tmp) / "stm32_memory_report.json",
            )
            self.assertTrue(header.exists())
            self.assertTrue(report.exists())
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["plan_count"], 6)
            self.assertLessEqual(data["max_actions_per_plan"], 128)
            self.assertLessEqual(data["estimated_total_runtime_ram_bytes"], 4096)
            levels = {item["level_id"]: item for item in data["levels"]}
            self.assertEqual(levels[101]["recognition_cost"], 0)
            self.assertGreater(levels[102]["recognition_cost"], 0)
            self.assertGreater(levels[103]["recognition_cost"], levels[102]["recognition_cost"])
            self.assertGreater(levels[103]["explosion_count"], 0)
            self.assertEqual(levels[104]["recognition_cost"], 0)
            self.assertGreater(levels[105]["explosion_count"], 0)
            self.assertGreater(levels[106]["recognition_cost"], 0)

    def test_embedded_core_avoids_dynamic_allocation(self) -> None:
        core_c = (ROOT / "embedded" / "stm32f304" / "planner_core.c").read_text(encoding="utf-8")
        core_h = (ROOT / "embedded" / "stm32f304" / "planner_core.h").read_text(encoding="utf-8")
        combined = core_c + core_h
        for forbidden in ("malloc", "calloc", "realloc", "free("):
            self.assertNotIn(forbidden, combined)
        self.assertIn("PP_CELL_COUNT", core_h)
        self.assertIn("pp_bfs_workspace_t", core_h)


if __name__ == "__main__":
    unittest.main()
