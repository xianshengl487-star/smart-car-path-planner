import unittest

from scripts.watch_optimization import summarize_results


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


if __name__ == "__main__":
    unittest.main()
