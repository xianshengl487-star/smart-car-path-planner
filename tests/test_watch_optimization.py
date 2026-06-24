import unittest
from unittest.mock import patch

from scripts.watch_optimization import format_manifest_summary, main, summarize_results, update_manifest


class WatchOptimizationSummaryTests(unittest.TestCase):
    def test_summary_tracks_failures_and_hardest_maps(self) -> None:
        results = [
            {
                "file": "easy.txt",
                "solved": True,
                "expanded": 10,
                "elapsed_seconds": 0.2,
                "cost": 8,
                "pushes": 2,
            },
            {
                "file": "hard.txt",
                "solved": True,
                "expanded": 900,
                "elapsed_seconds": 1.5,
                "cost": 88,
                "pushes": 12,
            },
            {
                "file": "broken.txt",
                "solved": False,
                "expanded": 250,
                "elapsed_seconds": 0.4,
                "message": "No solution",
            },
        ]

        summary = summarize_results(results)

        self.assertEqual(summary["solved"], 2)
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["failed"], ["broken.txt"])
        self.assertEqual(summary["hardest_by_expanded"][0]["label"], "hard.txt")
        self.assertEqual(summary["hardest_by_expanded"][0]["expanded"], 900)
        self.assertEqual(summary["slowest_by_elapsed"][0]["label"], "hard.txt")
        self.assertEqual(summary["total_expanded"], 1160)
        self.assertEqual(summary["max_expanded"], 900)

    def test_manifest_tracks_consecutive_solves_and_regressions(self) -> None:
        manifest = update_manifest(
            {"schema": 1, "runs": 0, "maps": {}},
            [
                {
                    "file": "map_a.txt",
                    "level_id": 5001,
                    "solved": True,
                    "expanded": 50,
                    "cost": 12,
                    "pushes": 3,
                }
            ],
            "2026-06-24T00:00:00+00:00",
        )
        manifest = update_manifest(
            manifest,
            [
                {
                    "file": "map_a.txt",
                    "level_id": 5001,
                    "solved": True,
                    "expanded": 40,
                    "cost": 12,
                    "pushes": 3,
                }
            ],
            "2026-06-24T00:30:00+00:00",
        )

        entry = manifest["maps"]["map_a.txt"]
        self.assertEqual(entry["consecutive_solves"], 2)
        self.assertEqual(entry["best_expanded"], 40)
        self.assertEqual(entry["worst_expanded"], 50)
        self.assertEqual(manifest["coverage"]["min_consecutive_solves"], 2)
        self.assertTrue(manifest["coverage"]["all_tracked_solved_last_run"])

        manifest = update_manifest(
            manifest,
            [
                {
                    "file": "map_a.txt",
                    "level_id": 5001,
                    "solved": False,
                    "expanded": 250000,
                    "message": "No solution within budget",
                }
            ],
            "2026-06-24T01:00:00+00:00",
        )

        entry = manifest["maps"]["map_a.txt"]
        self.assertEqual(entry["consecutive_solves"], 0)
        self.assertEqual(entry["regression_count"], 1)
        self.assertEqual(manifest["coverage"]["total_regressions"], 1)
        self.assertFalse(manifest["coverage"]["all_tracked_solved_last_run"])

    def test_format_manifest_summary_outputs_coverage(self) -> None:
        manifest = {
            "runs": 3,
            "coverage": {
                "tracked_maps": 2,
                "last_run_solved": 2,
                "last_run_total": 2,
                "all_tracked_solved_last_run": True,
                "min_consecutive_solves": 2,
                "total_regressions": 0,
            },
            "maps": {
                "map_a.txt": {
                    "worst_expanded": 900,
                    "consecutive_solves": 3,
                    "regression_count": 0,
                },
                "map_b.txt": {
                    "worst_expanded": 1200,
                    "consecutive_solves": 2,
                    "regression_count": 0,
                },
            },
        }

        text = format_manifest_summary(manifest)

        self.assertIn("Manifest runs: 3", text)
        self.assertIn("Tracked maps: 2", text)
        self.assertIn("Last run solved: 2/2", text)
        self.assertIn("All tracked solved last run: True", text)
        self.assertLess(text.index("map_b.txt"), text.index("map_a.txt"))

    def test_show_manifest_flag_exits_without_solving(self) -> None:
        manifest = {"runs": 0, "coverage": {}, "maps": {}}

        with patch("scripts.watch_optimization.load_manifest", return_value=manifest), \
             patch("scripts.watch_optimization.run_once") as run_once, \
             patch("sys.argv", ["watch_optimization.py", "--show-manifest"]):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        run_once.assert_not_called()


if __name__ == "__main__":
    unittest.main()
