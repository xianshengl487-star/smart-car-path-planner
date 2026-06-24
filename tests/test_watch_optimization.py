import unittest

from scripts.watch_optimization import summarize_results, update_manifest


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


if __name__ == "__main__":
    unittest.main()
